"""Il magic packet che sveglia il fisso.

Il fisso si sospende da solo dopo tre ore di inattivita'. Quando il Mac ha
bisogno di uno strumento e trova la porta chiusa, invece di limitarsi a dire
"e' spento" manda il pacchetto e lo dice al modello: fra qualche secondo la
macchina c'e'.

**Non e' un tool.** Un tool in piu' costa il prefill dell'intera conversazione
(`entry.tools == request.tools`) per una decisione che il modello non deve
prendere: se uno strumento serve, il fisso serve. Lo fa l'esecutore, che lo sa
per certo perche' ha appena preso un rifiuto sulla porta.

Il collegamento e' un cavo diretto Mac-fisso senza switch (10.0.0.0/24), quindi
il broadcast arriva alla scheda e basta: niente inoltro da configurare su un
router. La scheda resta alimentata durante la sospensione S3, il carrier non
cade e il Mac continua a vedere il link.
"""

from __future__ import annotations

import os
import socket
import time

# La MAC dell'Intel I225-V del fisso. Si passa da una variabile d'ambiente
# perche' la scheda e' l'unica cosa qui dentro che potrebbe cambiare.
MAC_FISSO = os.environ.get("MAC_FISSO", "c8:7f:54:6e:0d:54")
BROADCAST = os.environ.get("BROADCAST_FISSO", "10.0.0.255")
PORTA = 9

# Il fisso ci mette qualche secondo a risvegliarsi da S3 e una ventina a
# ristabilire il tunnel. Ripetere il pacchetto a ogni tentativo di tool non
# accelera niente e riempie il log: uno ogni due minuti basta.
INTERVALLO = 120

_ultimo_invio = 0.0


def _pacchetto(mac: str) -> bytes:
    grezzo = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(grezzo) != 6:
        raise ValueError(f"MAC non valido: {mac}")
    return b"\xff" * 6 + grezzo * 16


def sveglia(forza: bool = False) -> bool:
    """Manda il magic packet. Falso se e' troppo presto o se la rete non c'e'.

    Non aspetta e non verifica: il fisso ci mette piu' di qualunque timeout
    ragionevole, e chi ha chiamato deve poter rispondere subito all'utente.
    """
    global _ultimo_invio

    adesso = time.monotonic()
    if not forza and (adesso - _ultimo_invio) < INTERVALLO:
        return False

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as presa:
            presa.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            presa.sendto(_pacchetto(MAC_FISSO), (BROADCAST, PORTA))
    except OSError:
        # Interfaccia giu' o cavo staccato. Capita se il fisso e' in S5 con ErP
        # attivo, che toglie corrente alla scheda: da li' non lo si sveglia.
        return False

    _ultimo_invio = adesso
    return True
