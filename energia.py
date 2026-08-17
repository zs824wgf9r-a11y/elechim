"""Energia: quando il fisso dorme, e di chi e' la VRAM.

Due problemi che sembrano diversi e sono lo stesso problema — questa macchina
serve a due padroni. Elechim la vuole sempre viva e con i modelli caldi; il
proprietario ci gioca, e un gioco a 4K su una scheda da 8GB non ha un gigabyte da regalare.

Le due politiche si tengono per mano:

- **Sospensione dopo tre ore di inattivita'.** Non e' un timer solo: e' un elenco
  di ragioni per restare svegli, e si dorme quando l'elenco e' vuoto. Il motivo
  per cui NON si e' dormito viene sempre scritto nel log, perche' e' l'unica cosa
  che serve davvero quando alle due di notte la macchina e' ancora accesa.
- **VRAM a comando.** `/gioco` scarica i modelli e alza una bandiera che impedisce
  di ricaricarli; `/amici` la abbassa e li rimette in caldo. Finche' la bandiera
  e' su, gli strumenti che vogliono la GPU rispondono che e' occupata **dicendo
  come liberarla**: la degradazione silenziosa e' l'errore che questo progetto
  ha gia' pagato una volta, con un PDF sparito senza un messaggio.

Nessuna delle due cose e' un tool del modello. Aggiungere un tool invalida la
cache del prompt sul Mac (`entry.tools == request.tools`), e sono decisioni che
il modello non deve prendere: le prende il proprietario dal bot, o le prende
l'esecutore quando trova il fisso spento.
"""

from __future__ import annotations

import contextlib
import ctypes
import fcntl
import os
import subprocess
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
STATO = BASE / "stato"
BLOCCHI = STATO / "blocca"
ATTIVITA = STATO / "ultima-attivita"
GIOCO = STATO / "gioco"
DERIVA = STATO / "deriva-sospensione"
GPU_LOCK = STATO / ".gpu.lock"

OLLAMA = "http://127.0.0.1:11434"

# Timeout per l'attesa della GPU in riserva_gpu. Sei ore coprono anche la
# sbobina completa di un libro grosso (`sbobina dsml --tutte`), che e' il
# lavoro piu' lungo che usa questo lock. Un timeout serve per non lasciare
# un processo appeso per sempre se qualcun altro muore senza rilasciare.
TIMEOUT_GPU = 6 * 3600

# Tre ore. Volutamente generose: una sospensione sbagliata costa al proprietario un
# risveglio e trenta secondi di attesa, mentre restare accesi un'ora in piu'
# costa qualche centesimo. L'errore da evitare non e' simmetrico.
INATTIVITA = 3 * 3600

# Sotto questa soglia consideriamo la scheda scarica. X11 e plasma da soli
# stanno sui 700MB e non se ne vanno: non e' VRAM che possiamo liberare noi.
VRAM_A_RIPOSO = 1200


def _prepara() -> None:
    BLOCCHI.mkdir(parents=True, exist_ok=True)


# --- attivita' -------------------------------------------------------------


def segna_attivita() -> None:
    """Chiamata dal gateway a ogni richiesta: e' il polso di Elechim."""
    _prepara()
    ATTIVITA.touch()


def inattivo_da() -> float:
    """Secondi dall'ultima richiesta. Senza file, si parte dall'avvio."""
    try:
        return max(0.0, time.time() - ATTIVITA.stat().st_mtime)
    except FileNotFoundError:
        return _uptime()


def _uptime() -> float:
    with open("/proc/uptime", encoding="ascii") as f:
        return float(f.read().split()[0])


# --- blocchi ---------------------------------------------------------------


@contextlib.contextmanager
def blocco(nome: str):
    """Impedisce la sospensione mentre un lavoro lungo e' in corso.

    Il file contiene il PID di chi lo tiene, cosi' un processo morto male non
    lascia la macchina sveglia per sempre: chi legge scarta i blocchi orfani.
    Serve alla coda documenti della fase 4, dove un lavoro da venti minuti non
    deve trovarsi la macchina addormentata a meta'.
    """
    _prepara()
    percorso = BLOCCHI / nome.replace("/", "_")
    percorso.write_text(str(os.getpid()), encoding="ascii")
    try:
        yield
    finally:
        percorso.unlink(missing_ok=True)


def blocchi_attivi() -> list[str]:
    _prepara()
    vivi = []
    for percorso in sorted(BLOCCHI.iterdir()):
        try:
            pid = int(percorso.read_text(encoding="ascii").strip())
            os.kill(pid, 0)  # non lo uccide: chiede solo se esiste
        except (ValueError, ProcessLookupError, OSError):
            percorso.unlink(missing_ok=True)  # orfano, si butta
            continue
        vivi.append(percorso.name)
    return vivi


# --- sessione grafica ------------------------------------------------------


class _InfoScreenSaver(ctypes.Structure):
    _fields_ = [
        ("window", ctypes.c_ulong),
        ("state", ctypes.c_int),
        ("kind", ctypes.c_int),
        ("since", ctypes.c_ulong),
        ("idle", ctypes.c_ulong),
        ("event_mask", ctypes.c_ulong),
    ]


def _ambiente_sessione() -> dict[str, str]:
    """Pesca DISPLAY e XAUTHORITY da un processo della sessione grafica.

    Un servizio utente avviato dal linger non ha nessuna delle due variabili, e
    indovinarle (`:0`, `~/.Xauthority`) funziona finche' SDDM non cambia idea.
    Leggerle dall'ambiente di plasmashell e' autoconfigurante e non richiede
    permessi: e' un nostro processo.
    """
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
                if f.read().strip() not in ("plasmashell", "kwin_x11", "Xorg"):
                    continue
            grezzo = Path(f"/proc/{pid}/environ").read_bytes()
        except (OSError, PermissionError):
            continue
        env = {}
        for voce in grezzo.split(b"\0"):
            chiave, _, valore = voce.decode("utf-8", "replace").partition("=")
            if chiave in ("DISPLAY", "XAUTHORITY"):
                env[chiave] = valore
        if "DISPLAY" in env:
            return env
    return {}


def inattivita_sessione() -> float | None:
    """Secondi dall'ultimo input su tastiera o mouse. `None` se non c'e' X.

    Passa dall'estensione XScreenSaver via ctypes invece che da `xprintidle`,
    che su Fedora 44 non e' pacchettizzato. `libXss.so.1` c'e' gia'.

    Serve perche' l'IdleHint di logind su X11 con KDE **non viene mai
    aggiornato** (verificato: resta `no` con `IdleSinceHintMonotonic=0` anche a
    sessione ferma), quindi la strada idiomatica di systemd qui non funziona.

    Questo controllo copre anche il gioco: se stai giocando stai anche dando
    input, quindi non serve andare a caccia di processi di Steam per sapere che
    la macchina non va addormentata.
    """
    env = _ambiente_sessione()
    if not env:
        return None  # nessuno alla scrivania: nessun motivo di restare svegli

    if "XAUTHORITY" in env:
        os.environ["XAUTHORITY"] = env["XAUTHORITY"]

    try:
        x11 = ctypes.CDLL("libX11.so.6")
        xss = ctypes.CDLL("libXss.so.1")
    except OSError:
        return None

    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x11.XDefaultRootWindow.restype = ctypes.c_ulong
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_InfoScreenSaver)
    xss.XScreenSaverQueryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_InfoScreenSaver),
    ]

    schermo = x11.XOpenDisplay(env["DISPLAY"].encode("ascii"))
    if not schermo:
        return None
    try:
        info = xss.XScreenSaverAllocInfo()
        if not xss.XScreenSaverQueryInfo(
            schermo, x11.XDefaultRootWindow(schermo), info
        ):
            return None
        return info.contents.idle / 1000.0
    finally:
        x11.XCloseDisplay(schermo)


def sessioni_remote() -> int:
    """Quante sessioni ssh aperte. Addormentarsi sotto le dita e' scortese."""
    try:
        uscita = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return 0
    return sum(1 for riga in uscita.splitlines() if "pts/" in riga)


# --- risveglio -------------------------------------------------------------


def appena_risvegliato(soglia: float = 60.0, aggiorna: bool = True) -> bool:
    """Vero se la macchina ha appena finito di dormire.

    Senza questo controllo c'e' un giro vizioso preciso: il Mac sveglia il fisso
    col magic packet, il controllo parte dieci minuti dopo, trova `ultima
    attivita'` vecchia di tre ore (perche' e' l'ora in cui ci si e' addormentati)
    e lo rimanda a dormire — magari prima che il proprietario abbia finito di scrivere.

    Si rileva senza root e senza hook di sistema confrontando i due orologi:
    CLOCK_MONOTONIC si ferma durante la sospensione, CLOCK_BOOTTIME no. La loro
    differenza e' il tempo dormito da sempre; se e' cresciuta dall'ultimo giro,
    nel mezzo si e' dormito.

    `aggiorna=False` guarda senza consumare il segnale: serve a `/energia`, che
    altrimenti guardando lo stato lo cancellerebbe per il controllo vero.
    """
    _prepara()
    dormito = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
    try:
        precedente = float(DERIVA.read_text(encoding="ascii"))
    except (FileNotFoundError, ValueError):
        precedente = dormito
    if aggiorna:
        DERIVA.write_text(f"{dormito}", encoding="ascii")
    return (dormito - precedente) > soglia


# --- la decisione ----------------------------------------------------------


def motivi_per_restare_svegli(aggiorna: bool = True) -> list[str]:
    """Elenco vuoto = si puo' dormire. Ogni voce e' gia' leggibile nel log."""
    motivi = []

    if appena_risvegliato(aggiorna=aggiorna):
        motivi.append("appena risvegliato")
        if aggiorna:
            # Il risveglio conta come attivita': qualcuno lo voleva, col magic
            # packet o col pulsante.
            segna_attivita()

    inattivo = inattivo_da()
    if inattivo < INATTIVITA:
        motivi.append(f"Elechim usato {inattivo / 60:.0f} min fa")

    fermo = inattivita_sessione()
    if fermo is not None and fermo < INATTIVITA:
        motivi.append(f"qualcuno alla scrivania ({fermo / 60:.0f} min di inerzia)")

    if blocchi := blocchi_attivi():
        motivi.append(f"lavori in corso: {', '.join(blocchi)}")

    if remote := sessioni_remote():
        motivi.append(f"{remote} sessioni ssh aperte")

    return motivi


def sospendi() -> None:
    # Prima di dormire segniamo l'attivita': al risveglio il contatore riparte
    # da adesso invece che da tre ore fa.
    segna_attivita()
    subprocess.run(["systemctl", "suspend"], check=True, timeout=30)


# --- VRAM ------------------------------------------------------------------


def vram_usata() -> tuple[int, int]:
    """(usati, totali) in MiB. (0, 0) se nvidia-smi non risponde."""
    try:
        uscita = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout.strip().splitlines()[0]
        usati, totali = (int(x.strip()) for x in uscita.split(","))
        return usati, totali
    except Exception:  # noqa: BLE001 - diagnostica, mai fatale
        return 0, 0


def in_gioco() -> bool:
    return GIOCO.exists()


@contextlib.contextmanager
def riserva_gpu(chi: str, timeout: float | None = TIMEOUT_GPU):
    """Mutex fra processi sulla GPU.

    Chi arriva secondo **aspetta** invece di uscire, perche' qui il lavoro
    e' legittimo e lungo. Il lock e' un `flock` su file: se il processo
    muore male (anche `SIGKILL`) il kernel rilascia il lock insieme al
    descrittore. Il timeout evita di restare appesi per sempre.

    Durante l'attesa si stampa chi tiene la GPU, perche' un'attesa
    silenziosa di venti minuti e' indistinguibile da un blocco.
    """
    _prepara()
    STATO.mkdir(parents=True, exist_ok=True)
    f = open(GPU_LOCK, "w")  # noqa: SIM115 - il lock vive con il descrittore aperto
    try:
        scadenza = time.time() + timeout if timeout is not None else None
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if scadenza is not None and time.time() >= scadenza:
                    raise TimeoutError(
                        f"timeout ({timeout}s) in attesa della GPU"
                    ) from None
                try:
                    occupante = GPU_LOCK.read_text(encoding="utf-8").strip()
                except Exception:  # noqa: BLE001
                    occupante = ""
                occupante = occupante or "altro processo"
                print(f"GPU occupata da {occupante}, aspetto...", flush=True)
                time.sleep(0.5)
        f.write(f"{chi} (pid {os.getpid()})\n")
        f.flush()
        yield
    finally:
        f.close()  # chiude il descrittore e rilascia il flock


def _modelli_caricati() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA}/api/ps", timeout=10)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001
        return []


def libera_vram() -> str:
    """`/gioco`: scarica tutto e impedisce che qualcosa si ricarichi da solo.

    Il flag non e' un dettaglio: senza, la prima foto che arriva su Telegram
    ricarica qwen3-vl (3,5GB) nel bel mezzo di una partita a 4K, che e'
    esattamente il modo in cui gli 8GB finiscono.
    """
    _prepara()
    prima, totali = vram_usata()
    GIOCO.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")

    scaricati = []
    for nome in _modelli_caricati():
        try:
            # keep_alive 0 e' il modo di ollama per dire "sfrattalo adesso".
            requests.post(
                f"{OLLAMA}/api/generate",
                json={"model": nome, "keep_alive": 0},
                timeout=60,
            ).raise_for_status()
            scaricati.append(nome)
        except Exception:  # noqa: BLE001
            pass

    import voce

    if voce.scarica():
        scaricati.append("whisper")

    # ollama libera la memoria in modo asincrono: senza una pausa la misura
    # racconta una bugia rassicurante.
    time.sleep(2)
    dopo, _ = vram_usata()

    elenco = ", ".join(scaricati) if scaricati else "niente da scaricare"
    return (
        f"GPU liberata per il gioco ({elenco}).\n"
        f"VRAM: {prima} -> {dopo} MiB su {totali}.\n"
        "Vocali e immagini restano fermi finche' non mandi /amici."
    )


def carica_vram() -> str:
    """`/amici`: rimette in caldo i modelli che servono a Elechim."""
    GIOCO.unlink(missing_ok=True)
    prima, totali = vram_usata()

    import visione
    import voce

    pronti, falliti = [], []

    try:
        # Prompt vuoto: ollama carica il modello e non genera niente.
        requests.post(
            f"{OLLAMA}/api/generate",
            json={"model": visione.MODELLO, "prompt": "", "keep_alive": "5m"},
            timeout=300,
        ).raise_for_status()
        pronti.append(visione.MODELLO)
    except Exception as errore:  # noqa: BLE001
        falliti.append(f"visione ({type(errore).__name__})")

    try:
        voce.carica()
        pronti.append("whisper")
    except Exception as errore:  # noqa: BLE001
        falliti.append(f"whisper ({type(errore).__name__})")

    dopo, _ = vram_usata()
    righe = [f"Amici di Elechim di nuovo in VRAM: {', '.join(pronti) or 'nessuno'}."]
    if falliti:
        righe.append(f"Non caricati: {', '.join(falliti)}.")
    righe.append(f"VRAM: {prima} -> {dopo} MiB su {totali}.")
    return "\n".join(righe)


def riassunto() -> str:
    """Diagnostica per `/energia`, sullo stesso modello di `/stato`."""
    usati, totali = vram_usata()
    fermo = inattivita_sessione()
    righe = [
        f"VRAM: {usati} MiB su {totali}"
        + (" (a riposo)" if usati < VRAM_A_RIPOSO else ""),
        f"Modelli caricati: {', '.join(_modelli_caricati()) or 'nessuno'}",
        f"Ultima richiesta: {inattivo_da() / 60:.0f} min fa",
        "Scrivania: "
        + (f"{fermo / 60:.0f} min di inerzia" if fermo is not None else "nessuna sessione grafica"),
    ]
    if in_gioco():
        righe.append(f"MODALITA' GIOCO attiva da {GIOCO.read_text(encoding='utf-8')} - /amici per uscirne")
    if motivi := motivi_per_restare_svegli(aggiorna=False):
        righe.append(f"Resta sveglio perche': {'; '.join(motivi)}")
    else:
        righe.append("Nessun motivo per restare sveglio: si sospende al prossimo giro")
    return "\n".join(righe)
