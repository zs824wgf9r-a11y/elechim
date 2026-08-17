"""Il guardiano: sorvegliare un agente da riga di comando invece di sperare.

Lancia un motore (agy o opencode serve), ne legge il flusso di eventi,
si accorge del silenzio ed escala: abort -> SIGTERM -> SIGKILL.

Il cuore e' uno solo (`esegui`); i due adattatori sono sottili e
normalizzano il flusso in tre fatti: *e' vivo* (un evento e' arrivato),
*ha finito* (bene o male), *ha fallito*.

Le tre regole non negoziabili (INCARICO-guardiano.md, misurate il 17
agosto 2026 su tre sessioni piantate 5h57m):

1. La salute vuole TRE segnali insieme: stato finale non d'errore,
   output non vuoto, file attesi esistenti. Ognuno da solo mente
   (provato su agy: run vuoto con exit 0 E status SUCCESS).
2. `session.idle` non e' un fine turno affidabile (issue opencode
   #26635, #38661): prima di dichiarare finita una sessione opencode si
   interroga `GET /session/:id/message`.
3. L'escalation e' a gradini e ognuno ha un tempo: silenzio -> abort ->
   SIGTERM -> SIGKILL. SIGTERM da solo non basta (issue #24658).

Ogni evento normalizzato finisce in un diario JSONL,
`stato/guardiano/<nome>.jsonl`: e' quello che resta quando una sessione
muore. L'evento `finito` ci scrive l'output INTEGRALE, perche' le
conclusioni sono l'ultima cosa che una sessione scrive e la prima che
si perde.
"""

from __future__ import annotations

import json
import queue
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Costanti. I tempi dell'escalation e il silenzio_max sono dichiarati e
# misurati in RAPPORTO-guardiano.md; qui stanno i PREDEFINITI.
# ---------------------------------------------------------------------------

SILENZIO_MAX = 900.0        # secondi senza eventi prima di escalare (misura nel rapporto)
ATTESA_ABORT = 10.0         # dopo abort, attesa prima di SIGTERM
ATTESA_TERM = 15.0          # dopo SIGTERM, attesa prima di SIGKILL
ATTESA_KILL = 5.0           # dopo SIGKILL, attesa per raccogliere l'uscita
GRACE_USCITA = 5.0          # attesa di uscita pulita dopo l'evento `result`
TIC = 0.5                   # granularita' del loop di sorveglianza
RICONTROLLO_IDLE = 3.0      # opencode: ri-interroga /message dopo un idle non confermato
DIARIO = Path("stato/guardiano")


# ---------------------------------------------------------------------------
# I tipi che attraversano il cuore
# ---------------------------------------------------------------------------

@dataclass
class Evento:
    """Un fatto normalizzato. `segno_di_vita` distingue gli eventi emessi
    dal motore (riarmano l'orologio del silenzio) da quelli sintetici del
    guardiano (un ricontrollo fallito NON e' un segno di vita)."""

    fatto: str                  # vivo | finito | fallito | chiuso
    tipo: str                   # tipo originale: init, step_update, result, session.idle...
    dettaglio: dict = field(default_factory=dict)
    segno_di_vita: bool = True


@dataclass
class Esito:
    """Quello che il guardiano risponde. `esito` vale:
    finito_bene | fallito | ucciso_per_silenzio | ucciso_per_durata."""

    esito: str
    motivo: str
    output: str = ""
    durata_s: float = 0.0
    n_eventi: int = 0
    escalation: list = field(default_factory=list)
    file_mancanti: list = field(default_factory=list)
    diario: str = ""
    exit_code: int | None = None
    silenzio_max_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.esito == "finito_bene"

    def in_breve(self) -> str:
        righe = [
            f"esito:       {self.esito}",
            f"motivo:      {self.motivo}",
            f"durata:      {self.durata_s:.1f}s, eventi: {self.n_eventi}, exit: {self.exit_code}",
        ]
        if self.escalation:
            righe.append(f"escalation:  {' -> '.join(self.escalation)}")
        if self.file_mancanti:
            righe.append(f"file mancanti: {', '.join(self.file_mancanti)}")
        righe.append(f"diario:      {self.diario}")
        return "\n".join(righe)


class Diario:
    """Un rigo JSON per evento normalizzato, flush a ogni riga: il diario
    deve sopravvivere alla morte del processo sorvegliato."""

    def __init__(self, percorso: Path, t0: float):
        self.percorso = percorso
        self._t0 = t0
        self._fh = open(percorso, "w", encoding="utf-8")
        self._ultimo = t0

    def scrivi(self, fatto: str, tipo: str, dettaglio: dict):
        ora = time.monotonic()
        riga = {
            "t": round(ora - self._t0, 3),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "fatto": fatto,
            "tipo": tipo,
            "silenzio_s": round(ora - self._ultimo, 3),
            "dettaglio": dettaglio,
        }
        if fatto == "vivo":
            self._ultimo = ora
        self._fh.write(json.dumps(riga, ensure_ascii=False) + "\n")
        self._fh.flush()

    def chiudi(self):
        self._fh.close()


# ---------------------------------------------------------------------------
# Gli adattatori: sottili, normalizzano il flusso in tre fatti
# ---------------------------------------------------------------------------

class Adattatore:
    """Interfaccia fra il cuore e un motore. Il cuore conosce solo questi
    metodi; tutto cio' che e' specifico del motore vive qui sotto."""

    nome = "base"

    def __init__(self):
        self._coda: queue.Queue = queue.Queue()

    # -- da implementare -------------------------------------------------
    def avvia(self, incarico: str) -> None: raise NotImplementedError
    def abort(self) -> None: raise NotImplementedError
    def termina(self) -> None: raise NotImplementedError
    def uccidi(self) -> None: raise NotImplementedError
    def attendi_uscita(self, timeout: float) -> bool: raise NotImplementedError
    def exit_code(self) -> int | None: raise NotImplementedError
    def stato_finale(self) -> dict: raise NotImplementedError
    def stato_finale_ok(self) -> bool: raise NotImplementedError
    def output(self) -> str: raise NotImplementedError
    def chiudi(self) -> None: raise NotImplementedError
    def descrizione(self) -> dict: raise NotImplementedError

    # -- lettura: uguale per tutti ---------------------------------------
    def leggi_evento(self, timeout: float) -> Evento | None:
        """None = tic scaduto senza eventi. L'hook `_interno` lascia agli
        adattatori azioni a tempo (opencode: il ricontrollo post-idle)."""
        try:
            pezzo = self._coda.get(timeout=timeout)
        except queue.Empty:
            return self._interno()
        if pezzo is None:
            return self._evento_chiusura()
        if isinstance(pezzo, Evento):
            return pezzo
        return self._normalizza(pezzo)

    def _interno(self) -> Evento | None:
        return None

    def _evento_chiusura(self) -> Evento:
        return Evento("chiuso", "flusso_chiuso",
                      {"exit_code": self.exit_code()})


class AdattatoreAgy(Adattatore):
    """agy --print con `--output-format stream-json`: NDJSON su stdout,
    chiave `event` (NON `type`), eventi init / step_update / result.

    L'abort gentile e' la chiusura dello stdin (da incarico); il processo
    viene poi spento con SIGTERM/SIGKILL. `comando` permette di sostituire
    l'eseguibile: e' la porta del finto motore dei collaudi."""

    nome = "agy"

    def __init__(self, comando=None, *, mode="plan", model=None,
                 print_timeout="10m", cwd=None):
        super().__init__()
        self._comando_dato = comando
        self._mode = mode
        self._model = model
        self._print_timeout = print_timeout
        self._cwd = cwd
        self.proc: subprocess.Popen | None = None
        self._status: str | None = None
        self._output = ""
        self._errore: str | None = None
        self._stderr: deque = deque(maxlen=50)
        self._terminato_dopo_result = False

    def _costruisci_comando(self, incarico: str) -> list:
        cmd = ["agy", "--print", incarico,
               "--output-format", "stream-json",
               "--print-timeout", self._print_timeout,
               "--mode", self._mode]
        if self._model:
            cmd += ["--model", self._model]
        return cmd

    def avvia(self, incarico: str) -> None:
        cmd = self._comando_dato or self._costruisci_comando(incarico)
        self.comando = cmd
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, cwd=self._cwd)
        threading.Thread(target=self._pompa_stdout, daemon=True).start()
        threading.Thread(target=self._pompa_stderr, daemon=True).start()

    def _pompa_stdout(self):
        for riga in self.proc.stdout:
            self._coda.put(riga.rstrip("\n"))
        self._coda.put(None)  # EOF: il processo ha chiuso lo stdout

    def _pompa_stderr(self):
        for riga in self.proc.stderr:
            self._stderr.append(riga.rstrip("\n"))

    # -- normalizzazione --------------------------------------------------
    def _normalizza(self, riga: str) -> Evento:
        if not riga.strip():
            return Evento("vivo", "riga_vuota", {})
        try:
            obj = json.loads(riga)
        except json.JSONDecodeError:
            return Evento("vivo", "riga_non_json", {"riga": riga[:200]})
        ev = obj.get("event")
        if ev == "init":
            init = obj.get("init") or {}
            return Evento("vivo", "init", {
                "n_strumenti": len(init.get("tools") or []),
                "permission_mode": init.get("permission_mode"),
                "cwd": init.get("cwd"),
            })
        if ev == "step_update":
            su = obj.get("step_update") or {}
            det = {
                "step_index": su.get("step_index"),
                "state": su.get("state"),
                "step_type": su.get("step_type"),
            }
            if su.get("tool_name"):
                det["tool"] = su.get("tool_name")
            ti = su.get("tool_info") or {}
            if ti.get("error"):
                det["errore_tool"] = str(ti["error"])[:300]
            if su.get("text_delta"):
                det["text_delta_caratteri"] = len(su["text_delta"])
            return Evento("vivo", "step_update", det)
        if ev == "result":
            r = obj.get("result") or {}
            self._status = r.get("status")
            self._output = r.get("response") or ""
            self._errore = r.get("error")
            det = {"status": self._status,
                   "output": self._output,
                   "durata_motore_s": r.get("duration_seconds")}
            if self._errore:
                det["errore"] = str(self._errore)[:500]
            if self._status == "SUCCESS":
                return Evento("finito", "result", det)
            return Evento("fallito", "result", det)
        return Evento("vivo", f"sconosciuto:{ev}", {"chiavi": sorted(obj)[:10]})

    # -- escalation e salute ----------------------------------------------
    def abort(self):
        try:
            if self.proc and self.proc.stdin:
                self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    def termina(self):
        if self.proc:
            self.proc.terminate()

    def uccidi(self):
        if self.proc:
            self.proc.kill()

    def attendi_uscita(self, timeout: float) -> bool:
        if not self.proc:
            return True
        try:
            self.proc.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False

    def exit_code(self):
        return self.proc.poll() if self.proc else None

    def marca_terminato_dopo_result(self):
        self._terminato_dopo_result = True

    def stato_finale(self):
        return {"status": self._status, "exit_code": self.exit_code(),
                "terminato_dopo_result": self._terminato_dopo_result,
                "errore": self._errore,
                "stderr_coda": list(self._stderr)[-5:]}

    def stato_finale_ok(self) -> bool:
        if self._status != "SUCCESS":
            return False
        # Dopo `result` il processo dovrebbe uscire da solo; se non esce lo
        # spegniamo noi (issue #548) e l'exit code non e' piu' colpa sua.
        return self.exit_code() == 0 or self._terminato_dopo_result

    def output(self) -> str:
        return self._output

    def chiudi(self):
        if self.proc and self.proc.poll() is None:
            self.uccidi()
            self.attendi_uscita(ATTESA_KILL)

    def descrizione(self):
        return {"motore": "agy", "comando": self.comando, "cwd": self._cwd}


class AdattatoreOpencode(Adattatore):
    """opencode serve: SSE da GET /event + REST di controllo.

    Ordine obbligato (da incarico): si apre il flusso PRIMA di mandare il
    prompt, o si perdono i primi eventi. Regola 2: `session.idle` non dichiara
    la fine; la fine si conferma interrogando GET /session/:id/message.
    Le richieste di permesso ricevono risposta secondo una politica
    dichiarata (dict tipo->risposta con chiave "*" di ripiego, oppure
    callable(tipo, proprieta') -> risposta)."""

    nome = "opencode"

    def __init__(self, base_url=None, *, porta=None, avvia_server=True,
                 politica_permessi=None, auth=None, cwd=None):
        super().__init__()
        self._base_url = base_url
        self._porta = porta
        self._avvia_server = avvia_server
        self._auth = auth
        self._cwd = cwd
        self._politica = politica_permessi or {"*": "reject"}
        self._http = requests.Session()
        if auth:
            self._http.auth = auth
        self.proc: subprocess.Popen | None = None
        self._sid: str | None = None
        self._sock_sse = None
        self._stop = False
        self._quiet = threading.Event()     # sessione tornata quieta
        self._finito_confermato = False
        self._errore_sessione: dict | None = None
        self._output = ""
        self._idle_da_ricontrollare: float | None = None

    # -- avvio: server -> sessione -> flusso -> prompt --------------------
    def avvia(self, incarico: str) -> None:
        if self._avvia_server and not self._base_url:
            self._porta = self._porta or _porta_libera()
            self.proc = subprocess.Popen(
                ["opencode", "serve", "--hostname", "127.0.0.1",
                 "--port", str(self._porta)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                cwd=self._cwd)
            self._base_url = f"http://127.0.0.1:{self._porta}"
            self._attendi_salute()
        r = self._http.post(f"{self._base_url}/session", json={}, timeout=10)
        r.raise_for_status()
        self._sid = r.json()["id"]
        self._apri_flusso()
        # Il flusso e' aperto: ora si puo' mandare il prompt senza perdere
        # i primi eventi.
        r = self._http.post(f"{self._base_url}/session/{self._sid}/prompt_async",
                            json={"parts": [{"type": "text", "text": incarico}]},
                            timeout=10)
        r.raise_for_status()

    def _attendi_salute(self, timeout=20.0):
        fine = time.monotonic() + timeout
        while time.monotonic() < fine:
            try:
                if self._http.get(f"{self._base_url}/global/health",
                                  timeout=2).ok:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.25)
        raise RuntimeError("opencode serve non risponde su /global/health")

    def _apri_flusso(self):
        self._stop = False
        self._pronto = threading.Event()
        threading.Thread(target=self._pompa_sse, daemon=True).start()
        if not self._pronto.wait(timeout=10):
            raise RuntimeError("lo stream /event non ha mandato server.connected")

    def _pompa_sse(self):
        # http.client, non requests: tenere un riferimento diretto al socket
        # e' l'unico modo per svegliare la readline bloccata all'uscita —
        # close() da un altro thread si impianta sul lock del buffer mentre
        # il lettore e' in recv (trappola pagata nel collaudo, caso 7).
        import http.client
        from urllib.parse import urlsplit
        try:
            u = urlsplit(self._base_url)
            conn = http.client.HTTPConnection(u.hostname, u.port, timeout=10)
            testate = {"Accept": "text/event-stream"}
            if self._auth:
                import base64
                utente, password = self._auth
                token = base64.b64encode(
                    f"{utente}:{password}".encode()).decode()
                testate["Authorization"] = f"Basic {token}"
            conn.request("GET", "/event", headers=testate)
            self._sock_sse = conn.sock  # prima di getresponse: poi passa alla risposta
            resp = conn.getresponse()
            if resp.status != 200:
                self._coda.put(Evento("chiuso", "sse_rifiutato",
                                      {"status": resp.status}))
                self._coda.put(None)
                return
            # lo stream puo' tacere a lungo: niente timeout di lettura
            self._sock_sse.settimeout(None)
            while not self._stop:
                riga = resp.readline()
                if not riga:
                    break  # EOF: server morto o socket spento da chiudi()
                riga = riga.decode("utf-8", "replace").rstrip("\r\n")
                if not riga.startswith("data:"):
                    continue
                try:
                    obj = json.loads(riga[5:].strip())
                except json.JSONDecodeError:
                    self._coda.put(Evento("vivo", "sse_non_json",
                                          {"riga": riga[:200]}))
                    continue
                ev = self._normalizza_sse(obj)
                if ev is not None:
                    self._coda.put(ev)
        except (OSError, http.client.HTTPException) as e:
            if not self._stop:
                self._coda.put(Evento("chiuso", "sse_interrotto",
                                      {"errore": str(e)[:300]}))
        self._coda.put(None)

    # -- normalizzazione --------------------------------------------------
    def _normalizza_sse(self, obj: dict) -> Evento | None:
        tipo = obj.get("type")
        props = obj.get("properties") or {}
        if props.get("sessionID") and self._sid and \
                props.get("sessionID") != self._sid:
            return None  # il flusso e' di progetto: le altre sessioni non ci dicono niente
        if tipo == "server.connected":
            self._pronto.set()
            return Evento("vivo", tipo, {})
        if tipo == "session.status":
            stato = (props.get("status") or {}).get("type")
            if stato == "retry":
                return Evento("vivo", tipo, {
                    "stato": "retry",
                    "tentativo": (props.get("status") or {}).get("attempt"),
                    "messaggio": str((props.get("status") or {}).get("message"))[:300],
                })
            if stato == "idle":
                return self._idle()
            return Evento("vivo", tipo, {"stato": stato})
        if tipo == "session.idle":
            return self._idle()
        if tipo == "session.error":
            self._errore_sessione = props.get("error") or {}
            self._quiet.set()
            return Evento("fallito", tipo, {"errore": self._errore_sessione})
        if tipo == "message.part.updated":
            parte = props.get("part") or {}
            return Evento("vivo", tipo, {
                "parte": parte.get("type"),
                "tool": parte.get("tool"),
                "stato": (parte.get("state") or {}).get("status")
                         if isinstance(parte.get("state"), dict) else None,
            })
        if tipo == "permission.updated":
            risposta = self._rispondi_permesso(props)
            return Evento("vivo", tipo, {"permesso": props.get("type"),
                                         "titolo": str(props.get("title"))[:120],
                                         "risposta": risposta})
        return Evento("vivo", str(tipo), {})

    def _idle(self) -> Evento:
        """Regola 2: il primo idle puo' precedere gli eventi finali. Si
        dichiara finito solo se /session/:id/message mostra un messaggio
        assistant completato con testo."""
        ok, testo = self._conferma_finito()
        if ok:
            self._finito_confermato = True
            self._output = testo
            self._quiet.set()
            return Evento("finito", "session.idle+conferma",
                          {"via": "GET /session/:id/message", "output": testo})
        self._idle_da_ricontrollare = time.monotonic() + RICONTROLLO_IDLE
        return Evento("vivo", "session.idle", {"confermato": False})

    def _interno(self) -> Evento | None:
        """Ricontrollo a tempo del /message dopo un idle non confermato.
        Il ricontrollo fallito NON e' un segno di vita del motore."""
        if self._idle_da_ricontrollare is None:
            return None
        if time.monotonic() < self._idle_da_ricontrollare:
            return None
        self._idle_da_ricontrollare = None
        ok, testo = self._conferma_finito()
        if ok:
            self._finito_confermato = True
            self._output = testo
            self._quiet.set()
            return Evento("finito", "ricontrollo+conferma",
                          {"via": "GET /session/:id/message", "output": testo})
        self._idle_da_ricontrollare = time.monotonic() + RICONTROLLO_IDLE
        return Evento("vivo", "idle_ricontrollo", {"confermato": False},
                      segno_di_vita=False)

    def _conferma_finito(self) -> tuple[bool, str]:
        """Finito davvero = esiste un messaggio assistant con tempo
        `completed` e almeno una parte di testo non vuota. Forma attesa:
        [{info: {...}, parts: [...]}] (tollerante: anche messaggi nudi)."""
        try:
            r = self._http.get(f"{self._base_url}/session/{self._sid}/message",
                               params={"limit": 50}, timeout=10)
            r.raise_for_status()
            messaggi = r.json()
        except (requests.RequestException, ValueError):
            return False, ""
        for m in reversed(messaggi if isinstance(messaggi, list) else []):
            info = m.get("info", m) if isinstance(m, dict) else {}
            if info.get("role") != "assistant":
                continue
            parti = m.get("parts") if isinstance(m, dict) else None
            parti = parti if parti is not None else info.get("parts") or []
            tempo = info.get("time") or {}
            completato = tempo.get("completed") or info.get("completed")
            testi = [p.get("text", "") for p in parti
                     if isinstance(p, dict) and p.get("type") == "text"]
            if completato and any(t.strip() for t in testi):
                return True, "\n".join(t for t in testi if t.strip())
        return False, ""

    def _rispondi_permesso(self, props: dict) -> str:
        tipo = props.get("type")
        if callable(self._politica):
            risposta = self._politica(tipo, props)
        else:
            risposta = self._politica.get(tipo, self._politica.get("*", "reject"))
        try:
            self._http.post(
                f"{self._base_url}/session/{self._sid}/permissions/{props.get('id')}",
                json={"response": risposta}, timeout=5)
        except requests.RequestException:
            pass
        return risposta

    # -- escalation e salute ----------------------------------------------
    def abort(self):
        try:
            self._http.post(f"{self._base_url}/session/{self._sid}/abort",
                            timeout=5)
        except requests.RequestException:
            pass

    def termina(self):
        # Il bersaglio e' il server, solo se lo abbiamo avviato noi.
        if self.proc:
            self.proc.terminate()

    def uccidi(self):
        if self.proc:
            self.proc.kill()

    def attendi_uscita(self, timeout: float) -> bool:
        if self.proc:
            try:
                self.proc.wait(timeout=timeout)
                return True
            except subprocess.TimeoutExpired:
                return False
        # Server esterno: ci basta che la sessione torni quieta.
        return self._quiet.wait(timeout=timeout)

    def exit_code(self):
        return self.proc.poll() if self.proc else None

    def stato_finale(self):
        return {"finito_confermato": self._finito_confermato,
                "errore_sessione": self._errore_sessione,
                "exit_code": self.exit_code()}

    def stato_finale_ok(self) -> bool:
        return self._finito_confermato and not self._errore_sessione

    def output(self) -> str:
        return self._output

    def chiudi(self):
        self._stop = True
        sock = getattr(self, "_sock_sse", None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)  # sveglia la readline bloccata
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=ATTESA_TERM)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def descrizione(self):
        return {"motore": "opencode", "base_url": self._base_url,
                "sessione": self._sid, "server_avviato": bool(self.proc)}


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Il cuore
# ---------------------------------------------------------------------------

def esegui(incarico, motore, file_attesi=(), silenzio_max=SILENZIO_MAX, *,
           nome=None, durata_max=None, cartella_diario=DIARIO,
           attese_escalation=(ATTESA_ABORT, ATTESA_TERM, ATTESA_KILL),
           **kwargs_motore) -> Esito:
    """Sorveglia un incarico dall'avvio alla fine (o all'escalation).

    `motore`: "agy", "opencode" oppure un'istanza di Adattatore (collaudi).
    `file_attesi`: percorsi che devono esistere alla fine (regola 1).
    `silenzio_max`: secondi senza eventi prima dell'escalation.
    `durata_max`: tetto assoluto opzionale — il caso «retry infinito con
    eventi regolari» (opencode #40330) non lo vede l'orologio del silenzio.
    """
    if isinstance(motore, Adattatore):
        adattatore = motore
    elif motore == "agy":
        adattatore = AdattatoreAgy(**kwargs_motore)
    elif motore == "opencode":
        adattatore = AdattatoreOpencode(**kwargs_motore)
    else:
        raise ValueError(f"motore sconosciuto: {motore!r}")

    nome = nome or f"{adattatore.nome}-{time.strftime('%Y%m%d-%H%M%S')}"
    nome = nome.replace("/", "_")
    cartella = Path(cartella_diario)
    cartella.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    diario = Diario(cartella / f"{nome}.jsonl", t0)
    n_eventi = 0
    ultimo_evento = t0

    def _esito(esito, motivo, escalation=()):
        durata = time.monotonic() - t0
        mancanti = [str(f) for f in file_attesi if not Path(f).exists()]
        es = Esito(esito=esito, motivo=motivo, output=adattatore.output(),
                   durata_s=durata, n_eventi=n_eventi,
                   escalation=list(escalation), file_mancanti=mancanti,
                   diario=str(diario.percorso), exit_code=adattatore.exit_code(),
                   silenzio_max_s=silenzio_max)
        diario.scrivi("esito", esito, {
            "motivo": motivo, "durata_s": round(durata, 3),
            "escalation": list(escalation), "file_mancanti": mancanti,
            "exit_code": es.exit_code})
        return es

    def _escala(perche):
        passi = []
        diario.scrivi("escalation", "abort", {"perche": perche})
        adattatore.abort()
        passi.append("abort")
        if adattatore.attendi_uscita(attese_escalation[0]):
            return passi
        diario.scrivi("escalation", "sigterm", {})
        adattatore.termina()
        passi.append("sigterm")
        if adattatore.attendi_uscita(attese_escalation[1]):
            return passi
        diario.scrivi("escalation", "sigkill", {})
        adattatore.uccidi()
        passi.append("sigkill")
        adattatore.attendi_uscita(attese_escalation[2])
        return passi

    try:
        adattatore.avvia(incarico)
        diario.scrivi("avvio", adattatore.nome, adattatore.descrizione())

        ev_finale: Evento | None = None
        escalation: list = []
        motivo_uccisione = ""

        while True:
            ora = time.monotonic()
            silenzio = ora - ultimo_evento
            trascorso = ora - t0
            if durata_max is not None and trascorso >= durata_max:
                motivo_uccisione = (f"durata massima superata "
                                    f"({trascorso:.0f}s >= {durata_max:.0f}s)")
                escalation = _escala(motivo_uccisione)
                break
            if silenzio >= silenzio_max:
                motivo_uccisione = (f"nessun evento per {silenzio:.0f}s "
                                    f"(silenzio_max {silenzio_max:.0f}s)")
                escalation = _escala(motivo_uccisione)
                break
            budget = silenzio_max - silenzio
            if durata_max is not None:
                budget = min(budget, durata_max - trascorso)
            ev = adattatore.leggi_evento(timeout=min(budget, TIC))
            if ev is None:
                continue
            n_eventi += 1
            if ev.segno_di_vita:
                ultimo_evento = time.monotonic()
            diario.scrivi(ev.fatto, ev.tipo, _dettaglio_per_diario(ev))
            if ev.fatto == "finito":
                ev_finale = ev
                break
            if ev.fatto == "fallito":
                ev_finale = ev
                break
            if ev.fatto == "chiuso":
                # Il flusso si e' chiuso senza un result: qualunque cosa
                # dica l'exit code, non abbiamo uno stato finale fidato.
                adattatore.attendi_uscita(GRACE_USCITA)
                ev_finale = Evento("fallito", "flusso_chiuso",
                                   {"exit_code": adattatore.exit_code()})
                break

        if escalation:
            return _esito(
                "ucciso_per_durata" if "durata" in motivo_uccisione
                else "ucciso_per_silenzio",
                f"{motivo_uccisione}; escalation: {' -> '.join(escalation)}",
                escalation)

        if ev_finale is not None and ev_finale.fatto == "finito":
            # Il processo dovrebbe uscire da solo dopo il result; se resta
            # appeso (agy #548) lo spegniamo noi senza inficiare lo stato.
            if not adattatore.attendi_uscita(GRACE_USCITA):
                diario.scrivi("guardiano", "processo_appeso_dopo_result", {})
                if hasattr(adattatore, "marca_terminato_dopo_result"):
                    adattatore.marca_terminato_dopo_result()
                adattatore.termina()
                if not adattatore.attendi_uscita(ATTESA_TERM):
                    adattatore.uccidi()
                    adattatore.attendi_uscita(ATTESA_KILL)

        # Regola 1: tre segnali insieme.
        problemi = []
        if ev_finale is None or ev_finale.fatto != "finito":
            det = ev_finale.dettaglio if ev_finale else {}
            problemi.append(f"stato finale d'errore: {det or 'nessun evento finale'}")
        else:
            if not adattatore.stato_finale_ok():
                problemi.append(f"stato finale non pulito: {adattatore.stato_finale()}")
            if not adattatore.output().strip():
                problemi.append("output vuoto")
        mancanti = [str(f) for f in file_attesi if not Path(f).exists()]
        if mancanti:
            problemi.append(f"file attesi mancanti: {', '.join(mancanti)}")

        if problemi:
            return _esito("fallito", "; ".join(problemi))
        return _esito("finito_bene",
                      f"stato ok, output {len(adattatore.output())} caratteri, "
                      f"{len(file_attesi)} file attesi presenti")
    finally:
        adattatore.chiudi()
        diario.chiudi()


def _dettaglio_per_diario(ev: Evento) -> dict:
    """Nel diario l'evento `finito` porta l'output INTEGRALE (sono le
    conclusioni, la prima cosa che si perde); per gli altri eventi i campi
    lunghi vengono tosati."""
    det = dict(ev.dettaglio)
    if ev.fatto != "finito":
        for k, v in det.items():
            if isinstance(v, str) and len(v) > 300:
                det[k] = v[:300] + "..."
    return det
