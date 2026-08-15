"""Trascrizione dei messaggi vocali, sulla GPU del fisso.

Il Mac non vede mai l'audio: riceve solo il testo trascritto, che sono poche
decine di token. E' lo stesso principio della compressione dei risultati dei
tool — il lavoro pesante sta qui, il collo di bottiglia del Mac resta scarico.
"""

from __future__ import annotations

import gc
import os
import subprocess
import tempfile
import time
from pathlib import Path

# int8_float16 invece di float16: ~1,6GB di VRAM invece di ~3, con una perdita
# di accuratezza trascurabile sul parlato. Lo spazio serve ai modelli di Honcho,
# che finiranno sulla stessa scheda.
MODELLO = os.environ.get("WHISPER_MODELLO", "large-v3")
QUANTIZZAZIONE = os.environ.get("WHISPER_QUANT", "int8_float16")

_modello = None
_ultimo_uso = 0.0


def _precarica_cuda() -> bool:
    """Carica a mano le librerie CUDA installate via pip.

    CTranslate2 le cerca col linker di sistema, ma i pacchetti `nvidia-*-cu12`
    finiscono dentro il venv, dove il linker non guarda. Precaricarle con
    RTLD_GLOBAL le rende risolvibili senza dover impostare LD_LIBRARY_PATH
    nell'unit systemd.
    """
    import ctypes
    import site

    trovate = False
    for radice in site.getsitepackages():
        base = Path(radice) / "nvidia"
        if not base.is_dir():
            continue
        for libreria in sorted(base.glob("*/lib/lib*.so*")):
            try:
                ctypes.CDLL(str(libreria), mode=ctypes.RTLD_GLOBAL)
                trovate = True
            except OSError:
                pass
    return trovate


def _carica():
    """Caricamento pigro: il modello entra in VRAM al primo vocale, non al boot."""
    global _modello
    if _modello is None:
        _precarica_cuda()
        from faster_whisper import WhisperModel

        try:
            _modello = WhisperModel(MODELLO, device="cuda", compute_type=QUANTIZZAZIONE)
        except Exception:
            # Se le librerie CUDA non collaborano, la CPU e' lenta ma funziona:
            # meglio un vocale trascritto in dieci secondi che un errore.
            _modello = WhisperModel(MODELLO, device="cpu", compute_type="int8")
    return _modello


def carica():
    """Caricamento esplicito, per `/amici` dopo una sessione di gioco."""
    return _carica()


def caricato() -> bool:
    return _modello is not None


def inattivo_da() -> float | None:
    """Secondi dall'ultima trascrizione. `None` se non e' in VRAM.

    Serve allo sfratto: whisper era l'unico modello della macchina che, una
    volta caricato, restava in VRAM per sempre. ollama sfratta i suoi dopo
    cinque minuti, lui no — un'asimmetria, non una scelta, e sono 1835 MiB su
    una scheda da 8188 che serve anche a giocare e che deve far posto al
    modello di ingestion di Honcho.
    """
    if _modello is None:
        return None
    return time.monotonic() - _ultimo_uso


def scarica() -> bool:
    """Molla il modello e restituisce la VRAM. Torna Vero se c'era qualcosa.

    CTranslate2 libera la memoria della scheda quando l'oggetto viene raccolto,
    e senza un `gc.collect()` esplicito puo' restare appeso a un riferimento
    ciclico per un tempo indefinito — cioe' proprio mentre il gioco sta
    chiedendo quei 1,6GB.
    """
    global _modello
    if _modello is None:
        return False
    _modello = None
    gc.collect()
    return True


def _in_wav(percorso_ingresso: str) -> str:
    """Telegram manda OGG/Opus; Whisper vuole PCM 16 kHz mono."""
    uscita = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-i", percorso_ingresso, "-ar", "16000", "-ac", "1", uscita],
        check=True,
    )
    return uscita


def trascrivi(percorso_audio: str, lingua: str | None = "it") -> str:
    global _ultimo_uso

    wav = _in_wav(percorso_audio)
    try:
        segmenti, _ = _carica().transcribe(
            wav,
            language=lingua,
            beam_size=5,
            vad_filter=True,  # taglia i silenzi: meno audio, meno allucinazioni
        )
        return " ".join(s.text.strip() for s in segmenti).strip()
    finally:
        # Dopo e non prima: il cronometro dello sfratto deve partire da quando
        # il lavoro e' finito, o una trascrizione lunga si sfratterebbe da sola.
        _ultimo_uso = time.monotonic()
        Path(wav).unlink(missing_ok=True)
