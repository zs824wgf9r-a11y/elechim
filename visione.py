"""Immagini: descrizione e trascrizione del testo, sulla 4060 Ti del fisso.

Stesso principio dei vocali (`voce.py`): i pixel non lasciano mai questa
macchina, al Mac arriva solo testo gia' compresso. Un'immagine data in pasto al
Gemma del Mac costerebbe 300-800 token di prefill e romperebbe la forma di
continuazione su cui si regge la cache; qui costa qualche secondo di GPU che
altrimenti sta ferma.

Il modello gira in ollama, che lo scarica dalla VRAM dopo 5 minuti di inerzia:
e' quello che gli permette di convivere con faster-whisper sugli 8GB della
scheda senza che i due si pestino i piedi.
"""

from __future__ import annotations

import base64
import io
import os
import re

import requests
from PIL import Image, ImageOps

OLLAMA = "http://127.0.0.1:11434"
MODELLO = os.environ.get("OLLAMA_VLM", "qwen3-vl:4b")

# Quello che torna di qui finisce nel contesto del Mac, dove ogni token di
# prefill costa ~14ms: 1600 caratteri sono ~400 token, cioe' ~6s. E' lo stesso
# tetto di `leggi` in strumenti.py, per la stessa ragione.
TETTO = 1600

# Temperatura bassa: qui non serve creativita', serve che trascriva quello che
# c'e' scritto davvero. Sulle immagini con testo l'invenzione e' il rischio
# principale, non la noia.
TEMPERATURA = 0.1

# **Il tetto deve coprire anche il ragionamento, non solo la risposta.**
# qwen3-vl ragiona prima di rispondere e il ragionamento consuma `num_predict`
# come tutto il resto. Misurato l'11 agosto: 500-2.200 caratteri di pensiero a
# seconda dell'immagine, e quando la coda lunga sfonda il tetto la risposta esce
# **completamente vuota** (`done_reason: length`, `content: ""`), che e' il modo
# peggiore di fallire. Con 600 e' successo due volte su una ventina di prove;
# 1000 lascia margine al pensiero piu' lungo visto, e non costa niente quando il
# modello e' breve, perche' si ferma da solo.
MAX_TOKEN = 1000

# Lato massimo prima di passare l'immagine al modello. Non e' solo un risparmio:
# misurato il 2026-08-10 su una schermata 3840x2160, a piena risoluzione il
# modello legge "AROSAKA" dove c'e' scritto "ARASAKA", ridotta a 1536 lo legge
# giusto. La risoluzione dinamica di Qwen spezza l'immagine grande in tanti
# riquadri e le lettere finiscono a cavallo dei tagli: **rimpicciolire migliora
# l'accuratezza**, oltre a far scendere il payload da 1 MB a 220 KB.
LATO_MASSIMO = 1536

ISTRUZIONI_APERTE = """Guarda questa immagine e riassumila in italiano.

Se contiene testo leggibile (schermate, documenti, codice, errori, cartelli, scontrini) trascrivilo fedelmente: e' la parte che conta di piu'.
Se invece e' una scena o un oggetto, descrivi cosa si vede e i dettagli che distinguono questa immagine da una qualsiasi.

Vai dritto al contenuto: niente preamboli, niente "l'immagine mostra"."""

# **La didascalia orienta lo sguardo, non sostituisce la descrizione.**
#
# Fino all'11 agosto la didascalia diventava una domanda secca ("rispondi a
# «{domanda}», se non basta dillo in una riga"). Con "ti piacerebbe come foto
# profilo?" il modello ha risposto "l'immagine non contiene testo che risponda
# alla domanda" e al Mac non e' arrivata **nessuna** descrizione: Gemma ha
# ragionato sul nulla ("e' un file binario") e il proprietario ha dovuto incollare a
# mano il prompt con cui l'immagine era stata generata.
#
# Il parere lo da' il Mac, che e' quello che parla con il proprietario e che la
# didascalia ce l'ha gia' nel messaggio. Qui serve solo che la descrizione ci
# sia sempre. Provato anche il contrario — istruzioni piu' articolate, con
# descrizione *e* risposta separate — ed e' andata peggio: piu' l'istruzione e'
# complessa, piu' questo 4B ragiona invece di guardare, fino a consumare tutto
# il tetto di token e restituire il vuoto. Su un modello piccolo l'istruzione
# semplice non e' una rinuncia, e' la scelta accurata.
ISTRUZIONI_MIRATE = (
    ISTRUZIONI_APERTE
    + "\n\nChi te l'ha mandata ha scritto in chat: «{domanda}». Non e' testo "
    "dell'immagine e non devi rispondere: usalo solo per capire su cosa dare "
    "piu' dettaglio."
)


def _riduci(immagine: bytes) -> bytes:
    """Rimpicciolisce e normalizza prima di dare l'immagine al modello."""
    try:
        with Image.open(io.BytesIO(immagine)) as aperta:
            # Le foto da telefono portano l'orientamento nell'EXIF invece che nei
            # pixel: senza questo, una foto verticale arriva coricata e il testo
            # diventa illeggibile.
            raddrizzata = ImageOps.exif_transpose(aperta).convert("RGB")
            raddrizzata.thumbnail((LATO_MASSIMO, LATO_MASSIMO), Image.LANCZOS)
            buffer = io.BytesIO()
            raddrizzata.save(buffer, "JPEG", quality=85)
            return buffer.getvalue()
    except Exception:  # noqa: BLE001
        # Formato che Pillow non digerisce: tentiamo comunque col grezzo, sara'
        # ollama a lamentarsi se non ce la fa.
        return immagine


def _taglia(testo: str) -> str:
    """Tronca al tetto senza spezzare una riga a meta'."""
    testo = testo.strip()
    if len(testo) <= TETTO:
        return testo
    tagliato = testo[:TETTO]
    ultimo_a_capo = tagliato.rfind("\n")
    if ultimo_a_capo > TETTO * 0.6:
        tagliato = tagliato[:ultimo_a_capo]
    return tagliato.rstrip() + "\n[...]"


def _chiedi(immagine_ridotta: bytes, istruzioni: str, timeout: int) -> str:
    """Un giro di modello. Torna il solo `content`, che puo' essere vuoto."""
    corpo = {
        "model": MODELLO,
        "messages": [
            {
                "role": "user",
                "content": istruzioni,
                "images": [base64.b64encode(immagine_ridotta).decode("ascii")],
            }
        ],
        "stream": False,
        # ollama 0.32.7 accetta la flag ma il modello continua a ragionare un
        # po': serve lo stesso, perche' accorcia il pensiero, e non e' un
        # sostituto del margine su MAX_TOKEN.
        "think": False,
        "options": {
            "temperature": TEMPERATURA,
            "num_predict": MAX_TOKEN,
            # Le immagini occupano molti token di contesto: col default di 4096
            # una schermata fitta si mangia il prompt e il modello risponde a
            # meta'.
            "num_ctx": 8192,
        },
    }

    risposta = requests.post(f"{OLLAMA}/api/chat", json=corpo, timeout=timeout)
    risposta.raise_for_status()
    return ((risposta.json().get("message") or {}).get("content") or "").strip()


def descrivi(immagine: bytes, domanda: str = "", timeout: int = 300) -> str:
    """Da immagine a testo. `domanda` e' la didascalia, se c'era.

    La descrizione esce sempre; la didascalia sposta solo il dettaglio dove
    serve. Al Mac arriva testo gia' compresso, mai i pixel.
    """
    domanda = (domanda or "").strip()
    istruzioni = (
        ISTRUZIONI_MIRATE.format(domanda=domanda) if domanda else ISTRUZIONI_APERTE
    )
    ridotta = _riduci(immagine)

    testo = _chiedi(ridotta, istruzioni, timeout)
    if not testo:
        # Il modello ha ragionato fino a esaurire il tetto senza scrivere niente
        # (vedi MAX_TOKEN). Un secondo giro con l'istruzione piu' corta che
        # esista costa 4 secondi di GPU e salva l'unica cosa che conta: che al
        # Mac arrivi una descrizione invece di un buco.
        print("visione: contenuto vuoto, riprovo con l'istruzione minima", flush=True)
        testo = _chiedi(ridotta, "Descrivi questa immagine in italiano.", timeout)

    # Rete di sicurezza per un eventuale cambio di modello: ollama 0.32.7 il
    # ragionamento lo tiene gia' fuori, in un campo `thinking` a parte che qui
    # non leggiamo nemmeno, ma un modello che lo sputasse inline nel contenuto
    # manderebbe al Mac centinaia di token di prefill pagati per niente.
    testo = re.sub(r"<think>.*?</think>", "", testo, flags=re.DOTALL)

    testo = testo.strip()
    if not testo:
        return "Immagine ricevuta ma non sono riuscito a ricavarne niente."
    return _taglia(testo)


def pronto() -> tuple[bool, str]:
    """Il modello di visione e' scaricato e ollama risponde?"""
    try:
        r = requests.get(f"{OLLAMA}/api/tags", timeout=5)
        r.raise_for_status()
        nomi = [m["name"] for m in r.json().get("models", [])]
        if MODELLO in nomi or f"{MODELLO}:latest" in nomi:
            return True, MODELLO
        return False, f"{MODELLO} non scaricato (presenti: {', '.join(nomi) or 'nessuno'})"
    except Exception as errore:  # noqa: BLE001 - diagnostica, va mostrato tutto
        return False, str(errore)
