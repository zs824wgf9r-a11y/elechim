"""Interfaccia da terminale sulla STESSA conversazione del bot Telegram.

Non e' una seconda chat: legge e scrive lo stesso stato, proprio perche' la
cache del prompt sul Mac ha una sola slot. Due conversazioni separate si
ruberebbero la cache a vicenda e ogni cambio costerebbe il prefill pieno.
"""

from __future__ import annotations

import sys

from core import LIMITE_CONTESTO, ContestoPieno, Conversazione, modello_raggiungibile


def main() -> int:
    conv = Conversazione()

    ok, dettaglio = modello_raggiungibile()
    if not ok:
        print(f"modello non raggiungibile: {dettaglio}")
        print("controlla il tunnel: systemctl --user status macmini-tunnel")
        return 1

    print(f"Elechim ({dettaglio}) - turni finora: {conv.numero_turni()}")
    print("comandi: /nuova per azzerare, Ctrl-D per uscire\n")

    while True:
        try:
            testo = input("tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not testo:
            continue
        if testo.lower() == "/nuova":
            conv.azzera()
            print("conversazione azzerata; il prossimo turno sara' lento\n")
            continue

        try:
            esito = conv.rispondi(testo)
        except ContestoPieno:
            print("conversazione troppo lunga per il contesto: usa /nuova\n")
            continue
        except Exception as errore:  # noqa: BLE001
            print(f"errore: {errore}\n")
            continue

        print(f"\nElechim> {esito.testo}\n{esito.riga_diagnostica()}")
        if esito.vicino_al_limite:
            print(f"(a {esito.prompt_token} token su {LIMITE_CONTESTO}: conviene /nuova)")
        print()


if __name__ == "__main__":
    sys.exit(main())
