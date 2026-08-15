"""Gateway degli strumenti: tutto il lavoro sporco, su questa macchina.

Il bot e il modello stanno sul Mac mini. Qui restano le cose che hanno bisogno
della GPU, della rete o di molta RAM: ricerca web, trascrizione dei vocali,
lettura delle immagini. Il Mac chiama questo server e riceve **solo testo**,
gia' tagliato sotto i tetti di `strumenti.py` e `visione.py`.

Ci si arriva dal forward inverso del tunnel ssh (`-R 8090`), che apre il PC
verso il Mac. Il tunnel lo avvia questa macchina, quindi quando questa macchina
e' spenta il tunnel non esiste e il Mac riceve un rifiuto immediato invece di un
timeout: e' esattamente la degradazione che vogliamo, Elechim continua a
rispondere senza strumenti.

Non c'e' autenticazione perche' non c'e' superficie: il socket ascolta solo su
127.0.0.1 e l'unico modo di raggiungerlo da fuori e' la chiave ssh del tunnel.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

import energia
import strumenti
import visione

BASE = Path(__file__).resolve().parent
PORTA = 8090

# Un solo lavoro pesante alla volta sulla scheda. Whisper occupa 1,6GB e il
# modello di visione ~3,5: ci starebbero insieme, ma due caricamenti in
# contemporanea sugli 8GB della 4060 Ti sono il modo piu' facile di prendersi un
# OOM proprio mentre l'utente aspetta. Con un utente solo la coda non si vede.
GPU = threading.Lock()

# Dopo quanto whisper lascia la VRAM. Dieci minuti invece dei cinque di ollama:
# ricaricarlo costa pochi secondi (i pesi restano nella cache del filesystem),
# ma dentro una conversazione a vocali le pause superano facilmente i cinque
# minuti, e sfrattarlo li' vorrebbe dire pagarlo di continuo. Fuori da una
# conversazione dieci minuti bastano a liberare la scheda per il gioco e per
# l'ingestion notturna di Honcho.
SFRATTO_WHISPER = int(os.environ.get("SFRATTO_WHISPER", "600"))



def carica_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for riga in (BASE / ".env").read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, _, valore = riga.partition("=")
        env[chiave.strip()] = valore.strip()
    return env


ENV = carica_env()
TELEGRAM = f"https://api.telegram.org/bot{ENV['TELEGRAM_TOKEN']}"


def scarica_da_telegram(file_id: str, timeout: int = 120) -> bytes:
    """Scarica un allegato dai server di Telegram.

    Lo fa il fisso, non il Mac: il Mac manda solo il `file_id`, cosi' i byte non
    attraversano mai il tunnel e non toccano la macchina che ospita il modello.
    Il token ce l'abbiamo gia' nel .env, quindi non serve duplicare segreti.
    """
    info = requests.post(
        f"{TELEGRAM}/getFile", json={"file_id": file_id}, timeout=30
    )
    info.raise_for_status()
    percorso = info.json()["result"]["file_path"]

    contenuto = requests.get(
        f"https://api.telegram.org/file/bot{ENV['TELEGRAM_TOKEN']}/{percorso}",
        timeout=timeout,
    )
    contenuto.raise_for_status()
    return contenuto.content


# --- gli strumenti veri e propri ------------------------------------------


def op_esegui(dati: dict) -> dict:
    """`cerca` e `leggi`, gli stessi di prima: qui non e' cambiato niente."""
    nome = dati.get("nome", "")
    argomenti = dati.get("argomenti") or {}
    return {"testo": strumenti.esegui(nome, argomenti)}


# Cosa rispondere quando la scheda e' riservata al gioco. Dice **come**
# tornare indietro: un "non disponibile" secco ripeterebbe l'errore del PDF
# sparito in silenzio, dove il problema non era il limite ma non saperlo.
IN_GIOCO = (
    "GPU riservata al gioco: i modelli sono scarichi e non li ricarico "
    "adesso, o la partita ne risente. Manda /amici quando hai finito."
)


def op_trascrivi(dati: dict) -> dict:
    import voce  # import pigro: senza vocali il modello non entra mai in VRAM

    if energia.in_gioco():
        return {"testo": IN_GIOCO}

    audio = scarica_da_telegram(dati["file_id"])
    percorso = tempfile.mktemp(suffix=".ogg")
    Path(percorso).write_bytes(audio)
    try:
        with GPU, energia.blocco("vocale"):
            return {"testo": voce.trascrivi(percorso)}
    finally:
        Path(percorso).unlink(missing_ok=True)


def op_immagine(dati: dict) -> dict:
    if energia.in_gioco():
        return {"testo": IN_GIOCO}

    immagine = scarica_da_telegram(dati["file_id"])
    with GPU, energia.blocco("immagine"):
        return {"testo": visione.descrivi(immagine, dati.get("didascalia", ""))}


def op_gioco(_: dict) -> dict:
    """`/gioco` dal bot: la scheda passa al proprietario."""
    with GPU:
        return {"testo": energia.libera_vram()}


def op_amici(_: dict) -> dict:
    """`/amici` dal bot: i modelli di Elechim tornano in VRAM."""
    with GPU, energia.blocco("ricarico-modelli"):
        return {"testo": energia.carica_vram()}


def op_energia(_: dict) -> dict:
    return {"testo": energia.riassunto()}


def op_ping(_: dict) -> dict:
    """Risposta immediata: niente GPU, niente rete, niente disco.

    Serve al preflight del Mac. Non puo' essere `/salute`, che fa una ricerca
    vera su SearXNG e interroga ollama: sarebbe un secondo di lavoro appeso a
    ogni chiamata di strumento.
    """
    return {"testo": "ok"}


def op_salute(_: dict) -> dict:
    ok_vlm, dettaglio_vlm = visione.pronto()
    try:
        requests.get(
            strumenti.SEARXNG, params={"q": "prova", "format": "json"}, timeout=5
        ).raise_for_status()
        ok_ricerca, dettaglio_ricerca = True, "ok"
    except Exception as errore:  # noqa: BLE001 - diagnostica
        ok_ricerca, dettaglio_ricerca = False, str(errore)[:120]

    return {
        "ok": ok_vlm and ok_ricerca,
        "ricerca": dettaglio_ricerca,
        "visione": dettaglio_vlm,
    }


OPERAZIONI = {
    "/esegui": op_esegui,
    "/trascrivi": op_trascrivi,
    "/immagine": op_immagine,
    "/salute": op_salute,
    "/gioco": op_gioco,
    "/amici": op_amici,
    "/energia": op_energia,
    "/ping": op_ping,
}


class Gestore(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _rispondi(self, codice: int, corpo: dict) -> None:
        grezzo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codice)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(grezzo)))
        self.end_headers()
        self.wfile.write(grezzo)

    def _serve(self) -> None:
        operazione = OPERAZIONI.get(self.path.rstrip("/") or "/salute")
        if operazione is None:
            self._rispondi(404, {"errore": f"operazione sconosciuta: {self.path}"})
            return

        lunghezza = int(self.headers.get("Content-Length") or 0)
        try:
            dati = json.loads(self.rfile.read(lunghezza) or "{}") if lunghezza else {}
        except json.JSONDecodeError as errore:
            self._rispondi(400, {"errore": f"JSON malformato: {errore}"})
            return

        # Il polso di Elechim: finche' arrivano richieste il fisso non dorme.
        # Sta qui e non nei singoli strumenti perche' anche un `/salute` dal Mac
        # e' segno che dall'altra parte qualcuno sta usando l'assistente.
        energia.segna_attivita()

        inizio = time.time()
        try:
            risultato = operazione(dati)
            self._rispondi(200, risultato)
            esito = (
                f"{len(risultato['testo'])} caratteri"
                if "testo" in risultato
                else "ok"
            )
        except Exception as errore:  # noqa: BLE001 - va riportato al bot, non nascosto
            traceback.print_exc()
            self._rispondi(500, {"errore": f"{type(errore).__name__}: {errore}"})
            esito = f"ERRORE {type(errore).__name__}"

        print(
            f"{self.path} in {time.time() - inizio:.1f}s -> {esito}",
            flush=True,
        )

    do_POST = _serve
    do_GET = _serve

    def log_message(self, *_):  # il log lo facciamo noi, con i tempi
        pass


def _sfratta_whisper() -> None:
    """Toglie whisper dalla VRAM quando e' fermo da un po'.

    Gira in un thread suo perche' non c'e' nessun altro momento in cui possa
    succedere: whisper vive dentro questo processo e nessuno lo richiama fra
    un vocale e l'altro. Prende il lock GPU per non strappare il modello a una
    trascrizione in corso.
    """
    import voce

    while True:
        time.sleep(60)
        try:
            fermo = voce.inattivo_da()
            if fermo is None or fermo < SFRATTO_WHISPER:
                continue
            with GPU:
                # Ricontrollo dentro il lock: nel frattempo puo' essere
                # arrivato un vocale e aver rimesso il cronometro a zero.
                fermo = voce.inattivo_da()
                if fermo is not None and fermo >= SFRATTO_WHISPER and voce.scarica():
                    print(
                        f"whisper sfrattato dopo {fermo / 60:.0f} min di inerzia",
                        flush=True,
                    )
        except Exception:  # noqa: BLE001 - un thread di servizio non deve morire
            traceback.print_exc()


def main() -> int:
    ok_vlm, dettaglio = visione.pronto()
    print(f"visione: {'ok' if ok_vlm else 'NON pronta'} ({dettaglio})", flush=True)
    threading.Thread(target=_sfratta_whisper, daemon=True).start()

    print(f"gateway in ascolto su 127.0.0.1:{PORTA}", flush=True)

    server = ThreadingHTTPServer(("127.0.0.1", PORTA), Gestore)
    server.daemon_threads = True
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
