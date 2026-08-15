"""Il controllo periodico che decide se il fisso puo' andare a dormire.

Lo lancia `elechim-sospensione.timer` ogni dieci minuti. Non decide niente da
solo: chiede a `energia.motivi_per_restare_svegli()` e obbedisce.

Scrive **sempre** una riga di log, anche quando non fa niente. E' voluto: la
domanda che ci si fa davvero e' "perche' ieri notte non si e' addormentato", e
la risposta deve stare nel journal invece che in una sessione di indagine.

    python sospendi.py            controlla e, se e' il caso, sospende
    python sospendi.py --spiega   dice cosa farebbe, senza farlo
"""

from __future__ import annotations

import sys

import energia


def main() -> int:
    prova = "--spiega" in sys.argv
    motivi = energia.motivi_per_restare_svegli(aggiorna=not prova)

    if motivi:
        print("sveglio: " + "; ".join(motivi), flush=True)
        return 0

    usati, totali = energia.vram_usata()
    print(
        f"nessun motivo per restare sveglio (VRAM {usati}/{totali} MiB): "
        + ("sospenderei" if prova else "sospendo"),
        flush=True,
    )
    if not prova:
        energia.sospendi()
    return 0


if __name__ == "__main__":
    sys.exit(main())
