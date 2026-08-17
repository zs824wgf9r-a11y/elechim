"""Collaudo del guardiano: sette casi, nessuno brucia quota.

I casi 1-6 usano un FINTO motore agy: uno script che emette righe NDJSON da
un copione JSON, pause comprese. Il leggere (adattatore) e il decidere
(cuore) si provano cosi' separati dal modello vero, e i casi patologici
(silenzio, SIGTERM ignorato) si riproducono in pochi secondi.

Il caso 7 usa un finto server opencode in-process (SSE + REST da copione)
per la regola 2: `session.idle` non e' un fine turno affidabile.

I sette casi (da INCARICO-guardiano.md):
1. flusso normale fino a `result` -> finito_bene;
2. status SUCCESS ma output vuoto -> fallito (regola 1);
3. status SUCCESS ma file attesi mancanti -> fallito (regola 1);
4. flusso interrotto a meta' -> ucciso per silenzio, e il diario contiene
   tutti gli eventi arrivati fino a li';
5. processo che ignora SIGTERM -> si arriva a SIGKILL e lo si dice;
6. eventi lenti ma regolari -> NON ucciso (il falso positivo che rende
   inutile un guardiano);
7. `idle` prima degli eventi finali -> non si dichiara finito troppo presto.

Tutto gira in /tmp/opencode/guardiano: diari, copioni e file attesi.
"""

from __future__ import annotations

import json
import shutil
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import guardiano

BASE = Path("/tmp/opencode/guardiano")
if BASE.exists():
    shutil.rmtree(BASE)
BASE.mkdir(parents=True)
DIARI = BASE / "diari"
FINTO_PY = BASE / "motore_finto.py"

# Il finto motore agy: legge un copione JSON, emette le righe NDJSON con le
# pause dichiarate, puo' creare file (come farebbe un tool), puo' restare
# appeso alla fine e puo' ignorare SIGTERM.
FINTO = '''\
import json, signal, sys, time

copione = json.load(open(sys.argv[1]))
if copione.get("ignora_sigterm"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
for passo in copione["passi"]:
    time.sleep(passo.get("pausa", 0))
    if "crea_file" in passo:
        with open(passo["crea_file"], "w") as f:
            f.write("prodotto dal finto motore\\n")
    if "riga" in passo:
        sys.stdout.write(json.dumps(passo["riga"]) + "\\n")
        sys.stdout.flush()
if copione.get("resta_appeso_alla_fine"):
    while True:
        time.sleep(60)
sys.exit(copione.get("esci_con", 0))
'''
FINTO_PY.write_text(FINTO)

# Escalation veloce da collaudo; i default produzione stanno in guardiano.py.
ATTESE = (1.5, 1.5, 1.0)


def step(i, tipo, **kw):
    su = {"conversation_id": "finta", "step_index": i, "state": "DONE",
          "step_type": tipo}
    su.update(kw)
    return {"event": "step_update", "step_update": su}


def init_evento():
    return {"event": "init",
            "init": {"cwd": str(BASE), "tools": ["run_command", "write_file"],
                     "permission_mode": "request-review"}}


def result_evento(status="SUCCESS", response="Ho finito. Ecco le conclusioni."):
    return {"event": "result",
            "result": {"conversation_id": "finta", "status": status,
                       "response": response, "duration_seconds": 0.3,
                       "num_turns": 1}}


def lancia_agy_finto(copione, *, nome, file_attesi=(), silenzio_max=30.0):
    pcop = BASE / f"{nome}.copione.json"
    pcop.write_text(json.dumps(copione))
    adattatore = guardiano.AdattatoreAgy(
        comando=[sys.executable, str(FINTO_PY), str(pcop)])
    esito = guardiano.esegui("incarico finto", adattatore,
                             file_attesi=file_attesi, silenzio_max=silenzio_max,
                             nome=nome, cartella_diario=DIARI,
                             attese_escalation=ATTESE)
    return esito, adattatore


def leggi_diario(nome):
    return [json.loads(riga)
            for riga in (DIARI / f"{nome}.jsonl").read_text().splitlines()]


# ---------------------------------------------------------------------------
# Caso 1: flusso normale fino a result -> finito bene
# ---------------------------------------------------------------------------

def test_flusso_normale():
    atteso = BASE / "prodotto-1.txt"
    copione = {"passi": [
        {"pausa": 0.05, "riga": init_evento()},
        {"pausa": 0.05, "riga": step(0, "user_input")},
        {"pausa": 0.05, "riga": step(1, "agent_response", text_delta="lavoro...")},
        {"pausa": 0.05, "crea_file": str(atteso)},
        {"pausa": 0.05, "riga": step(2, "tool", tool_name="write_file")},
        {"pausa": 0.05, "riga": result_evento()},
    ]}
    esito, adattatore = lancia_agy_finto(copione, nome="caso-1-normale",
                                         file_attesi=[atteso])
    assert esito.ok, esito.in_breve()
    assert esito.esito == "finito_bene"
    assert esito.exit_code == 0, esito.exit_code
    assert not esito.escalation
    assert "conclusioni" in esito.output
    assert esito.n_eventi == 5, esito.n_eventi  # init + 3 step + result
    assert adattatore.proc.poll() is not None, "il processo e' ancora vivo"
    righe = leggi_diario("caso-1-normale")
    assert [r["fatto"] for r in righe] == (
        ["avvio"] + ["vivo"] * 4 + ["finito", "esito"]), \
        [r["fatto"] for r in righe]
    finito = [r for r in righe if r["fatto"] == "finito"][0]
    assert "conclusioni" in finito["dettaglio"]["output"], \
        "il diario non conserva l'output integrale"
    print("OK 1: flusso normale -> finito_bene, diario con output integrale")


# ---------------------------------------------------------------------------
# Caso 2: SUCCESS ma output vuoto -> fallito (regola 1)
# ---------------------------------------------------------------------------

def test_output_vuoto():
    copione = {"passi": [
        {"pausa": 0.05, "riga": init_evento()},
        {"pausa": 0.05, "riga": result_evento(response="")},
    ]}
    esito, _ = lancia_agy_finto(copione, nome="caso-2-vuoto")
    assert esito.esito == "fallito", esito.in_breve()
    assert "output vuoto" in esito.motivo
    print("OK 2: SUCCESS con output vuoto -> fallito (regola 1)")


# ---------------------------------------------------------------------------
# Caso 3: SUCCESS ma file attesi mancanti -> fallito (regola 1)
# ---------------------------------------------------------------------------

def test_file_mancanti():
    atteso = BASE / "prodotto-3-mai-scritto.txt"
    copione = {"passi": [
        {"pausa": 0.05, "riga": init_evento()},
        {"pausa": 0.05, "riga": result_evento()},
    ]}
    esito, _ = lancia_agy_finto(copione, nome="caso-3-file-mancanti",
                                file_attesi=[atteso])
    assert esito.esito == "fallito", esito.in_breve()
    assert str(atteso) in esito.file_mancanti
    assert "file attesi mancanti" in esito.motivo
    print("OK 3: SUCCESS con file mancanti -> fallito (regola 1)")


# ---------------------------------------------------------------------------
# Caso 4: flusso interrotto a meta' -> ucciso per silenzio, diario completo
# ---------------------------------------------------------------------------

def test_interrotto_silenzio():
    copione = {"resta_appeso_alla_fine": True, "passi": [
        {"pausa": 0.05, "riga": init_evento()},
        {"pausa": 0.05, "riga": step(0, "user_input")},
        {"pausa": 0.05, "riga": step(1, "tool", tool_name="run_command")},
        # poi piu' niente: il flusso si interrompe a meta'
    ]}
    esito, adattatore = lancia_agy_finto(copione, nome="caso-4-silenzio",
                                         silenzio_max=2.0)
    assert esito.esito == "ucciso_per_silenzio", esito.in_breve()
    assert esito.escalation == ["abort", "sigterm"], esito.escalation
    assert esito.exit_code == -signal.SIGTERM, esito.exit_code
    assert adattatore.proc.poll() is not None, "il processo e' ancora vivo"
    righe = leggi_diario("caso-4-silenzio")
    # Il diario conserva TUTTI gli eventi arrivati fino all'interruzione,
    # poi i passi dell'escalation e l'esito: quello che oggi manca quando
    # una sessione muore.
    fatti = [r["fatto"] for r in righe]
    assert fatti == ["avvio", "vivo", "vivo", "vivo",
                     "escalation", "escalation", "esito"], fatti
    assert [r["tipo"] for r in righe if r["fatto"] == "escalation"] == (
        ["abort", "sigterm"])
    assert esito.durata_s < 2.0 + 1.5 + 3.0, esito.durata_s
    print("OK 4: flusso interrotto -> ucciso_per_silenzio, "
          f"escalation abort->sigterm in {esito.durata_s:.1f}s, diario completo")


# ---------------------------------------------------------------------------
# Caso 5: il processo ignora SIGTERM -> si arriva a SIGKILL
# ---------------------------------------------------------------------------

def test_ignora_sigterm():
    copione = {"resta_appeso_alla_fine": True, "ignora_sigterm": True,
               "passi": [
                   {"pausa": 0.05, "riga": init_evento()},
                   {"pausa": 0.05, "riga": step(0, "user_input")},
               ]}
    esito, adattatore = lancia_agy_finto(copione, nome="caso-5-sigkill",
                                         silenzio_max=2.0)
    assert esito.esito == "ucciso_per_silenzio", esito.in_breve()
    assert esito.escalation == ["abort", "sigterm", "sigkill"], esito.escalation
    assert esito.exit_code == -signal.SIGKILL, esito.exit_code
    assert adattatore.proc.poll() is not None, "il processo e' ancora vivo"
    assert "sigkill" in esito.motivo
    print(f"OK 5: SIGTERM ignorato -> SIGKILL in {esito.durata_s:.1f}s, dichiarato")


# ---------------------------------------------------------------------------
# Caso 6: eventi lenti ma regolari -> NON ucciso
# ---------------------------------------------------------------------------

def test_lenti_ma_regolari():
    passi = [{"pausa": 0.05, "riga": init_evento()}]
    for i in range(5):
        passi.append({"pausa": 1.0,
                      "riga": step(i, "agent_response", text_delta=f"pezzo {i}")})
    passi.append({"pausa": 0.05, "riga": result_evento()})
    copione = {"passi": passi}
    esito, _ = lancia_agy_finto(copione, nome="caso-6-lenti", silenzio_max=3.0)
    assert esito.ok, esito.in_breve()
    assert not esito.escalation
    print("OK 6: eventi ogni 1.0s con silenzio_max 3.0s -> mai escalato")


# ---------------------------------------------------------------------------
# Caso 7: idle prima degli eventi finali (finto opencode, regola 2)
# ---------------------------------------------------------------------------

SID = "finta-1"
TESTO_FINALE = "Queste sono le conclusioni che non devono perdersi."


class _StatoFintoOpencode:
    """Il messaggio assistant diventa 'completato' solo dopo che il copione
    ha emesso `completo_da` eventi: prima di li', /message mostra un turno
    ancora aperto. E' la corsa delle issue #26635/#38661 riprodotta."""

    def __init__(self, eventi, completo_da):
        self.eventi = eventi
        self.completo_da = completo_da
        self.emessi = 0
        self.lock = threading.Lock()
        self.permessi = []
        self.abort = False
        self.chiudi = False

    def messaggi(self):
        with self.lock:
            emessi = self.emessi
        if emessi >= self.completo_da:
            return [{"info": {"role": "assistant",
                              "time": {"created": 1, "completed": 2}},
                     "parts": [{"type": "text", "text": TESTO_FINALE}]}]
        return [{"info": {"role": "assistant", "time": {"created": 1}},
                 "parts": []}]


def avvia_finto_opencode(eventi, completo_da):
    stato = _StatoFintoOpencode(eventi, completo_da)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            dati = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dati)))
            self.end_headers()
            self.wfile.write(dati)

        def do_GET(self):
            percorso = self.path.split("?", 1)[0]  # via la query string
            if percorso == "/event":
                self._sse()
            elif percorso.startswith("/session/") and \
                    percorso.endswith("/message"):
                self._json(stato.messaggi())
            else:
                self.send_error(404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            corpo = json.loads(self.rfile.read(n) or b"{}") if n else {}
            if self.path == "/session":
                self._json({"id": SID})
            elif self.path.endswith("/prompt_async"):
                self.send_response(204)
                self.end_headers()
            elif "/permissions/" in self.path:
                stato.permessi.append(corpo.get("response"))
                self._json(True)
            elif self.path.endswith("/abort"):
                stato.abort = True
                self._json(True)
            else:
                self.send_error(404)

        def _sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i, (pausa, ev) in enumerate(stato.eventi):
                time.sleep(pausa)
                with stato.lock:
                    stato.emessi = i + 1  # prima si conta, poi si spedisce
                try:
                    self.wfile.write(b"data: " + json.dumps(ev).encode() + b"\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
            while not stato.chiudi:  # flusso aperto ma in silenzio
                time.sleep(0.2)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, stato, f"http://127.0.0.1:{httpd.server_address[1]}"


def test_idle_precoce():
    eventi = [
        (0.05, {"type": "server.connected", "properties": {}}),
        (0.05, {"type": "session.status",
                "properties": {"sessionID": SID, "status": {"type": "busy"}}}),
        (0.10, {"type": "permission.updated",
                "properties": {"sessionID": SID, "id": "perm-1",
                               "type": "webfetch", "title": "fetch example.com"}}),
        # idle PRECOCE: il turno non e' finito, gli eventi finali mancano
        (0.10, {"type": "session.idle", "properties": {"sessionID": SID}}),
        # l'evento finale arriva DOPO l'idle
        (0.30, {"type": "message.part.updated",
                "properties": {"sessionID": SID,
                               "part": {"type": "text", "text": TESTO_FINALE}}}),
        # poi silenzio: la fine vera la dichiara il ricontrollo di /message
    ]
    httpd, stato, url = avvia_finto_opencode(eventi, completo_da=5)
    try:
        adattatore = guardiano.AdattatoreOpencode(
            base_url=url, avvia_server=False,
            politica_permessi={"*": "reject", "webfetch": "once"})
        t0 = time.monotonic()
        esito = guardiano.esegui("incarico finto", adattatore,
                                 silenzio_max=15.0, nome="caso-7-idle-precoce",
                                 cartella_diario=DIARI)
        durata = time.monotonic() - t0
        assert esito.ok, esito.in_breve()
        assert TESTO_FINALE in esito.output
        # la conferma arriva dal ricontrollo a tempo, non dal primo idle:
        assert durata >= guardiano.RICONTROLLO_IDLE, durata
        # la politica dei permessi dichiarata e' stata applicata
        assert stato.permessi == ["once"], stato.permessi
        righe = leggi_diario("caso-7-idle-precoce")
        finite = [r for r in righe if r["fatto"] == "finito"]
        assert len(finite) == 1, finite
        assert finite[0]["tipo"] == "ricontrollo+conferma", finite[0]["tipo"]
        idle = [r for r in righe if r["tipo"] == "session.idle"]
        assert idle and idle[0]["dettaglio"]["confermato"] is False
        # nessun 'finito' prima dell'evento finale
        i_finale = next(i for i, r in enumerate(righe)
                        if r["tipo"] == "message.part.updated")
        assert all(r["fatto"] != "finito" for r in righe[:i_finale])
        print(f"OK 7: idle precoce non dichiara finito; conferma via /message "
              f"a {durata:.1f}s, permesso risposto 'once'")
    finally:
        stato.chiudi = True
        httpd.shutdown()
        httpd.server_close()


def main():
    print("collaudo del guardiano (finto motore, nessuna quota bruciata)...")
    test_flusso_normale()
    test_output_vuoto()
    test_file_mancanti()
    test_interrotto_silenzio()
    test_ignora_sigterm()
    test_lenti_ma_regolari()
    test_idle_precoce()
    print("TUTTO VERDE")


if __name__ == "__main__":
    main()
