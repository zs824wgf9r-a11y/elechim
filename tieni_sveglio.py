#!/usr/bin/env python3
"""Tiene il fisso sveglio finche' c'e' lavoro vivo.

DA LANCIARE SOTTO systemd-inhibit, sempre:

    systemd-inhibit --what=sleep:idle --mode=block --who=Elechim \
        --why="sessione di lavoro" .venv/bin/python tieni_sveglio.py

Il perche' e' costato 11 ore la notte del 20 agosto 2026. energia.blocco()
e' una convenzione interna a Elechim: la legge solo motivi_per_restare_svegli()
in energia.py, cioe' la decisione di sospensione DI ELECHIM. logind e KDE non
la vedono. Con tre blocchi attivi e nessuno alla scrivania, PowerDevil ha
sospeso il fisso alle 01:22:52, 29 minuti dopo il lancio.

energia.blocco lega il blocco al PID di chi lo tiene, quindi serve un processo
che resti in piedi. Questo e' quel processo: veglia finche' una delle sessioni
di lavoro e' viva, piu' una coda di 30 minuti perche' la macchina non crolli
nell'istante esatto in cui l'ultima finisce.

Risolve il caso generale della sezione 8-bis del DA-FARE solo per stanotte:
il lavoro lanciato a mano non prende il blocco da solo.
"""
import pathlib, subprocess, sys, time

BASE = pathlib.Path.home() / "assistente"
sys.path.insert(0, str(BASE))
import energia  # noqa: E402

SESSIONI = ["lancio_studio.py", "lancio_ronda.py"]
CODA = 30 * 60          # quanto restare svegli dopo l'ultima sessione
TETTO = 12 * 3600       # non vegliare oltre, qualunque cosa succeda


def viva() -> list[str]:
    return [s for s in SESSIONI
            if subprocess.run(["pgrep", "-f", s],
                              capture_output=True).returncode == 0]


t0 = time.time()
ultima_attivita = t0
with energia.blocco("lavoro-notturno"):
    while True:
        v = viva()
        ora = time.time()
        if v:
            ultima_attivita = ora
        if ora - t0 > TETTO:
            print(f"tetto delle {TETTO//3600}h raggiunto, mollo il blocco", flush=True)
            break
        if not v and ora - ultima_attivita > CODA:
            print("nessuna sessione viva da 30 minuti, mollo il blocco", flush=True)
            break
        time.sleep(30)
print(f"vegliato per {(time.time()-t0)/60:.0f} minuti")
