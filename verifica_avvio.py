"""Rapporto di verifica dopo un riavvio, mandato su Telegram.

Un riavvio e' l'unico momento in cui si puo' controllare che le cose messe a
posto con la macchina accesa siano davvero permanenti. Se il rapporto arriva da
solo lo leggi; se bisogna ricordarsi di chiederlo, non lo si chiede mai.

Lo manda il fisso, non il Mac: il token ce l'ha nel `.env` e il destinatario e'
in `TELEGRAM_ALLOWED_IDS`. Il bot sul Mac non c'entra e non va disturbato.

Lo lancia `elechim-verifica-avvio.timer` tre minuti dopo l'avvio, una volta
sola.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import requests

import energia
import gateway

BASE = Path(__file__).resolve().parent


def _cmd(*argomenti: str) -> str:
    try:
        return subprocess.run(
            argomenti, capture_output=True, text=True, timeout=30
        ).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError) as errore:
        return f"(errore: {type(errore).__name__})"


def _param_nvidia(nome: str) -> str:
    try:
        for riga in Path("/proc/driver/nvidia/params").read_text().splitlines():
            if riga.startswith(f"{nome}:"):
                return riga.split(":", 1)[1].strip()
    except OSError:
        pass
    return "?"


def righe() -> list[str]:
    esiti = []

    # 1. Il tempo di avvio. NetworkManager-wait-online andava in timeout a 60s
    #    perche' la connessione col Mac era legata a un nome di interfaccia
    #    sparito; legata al MAC, quel minuto deve essere sparito.
    avvio = _cmd("systemd-analyze")
    esiti.append(f"Avvio: {avvio.splitlines()[0] if avvio else '?'}")
    lento = _cmd("systemd-analyze", "blame").splitlines()
    if lento:
        esiti.append(f"  il piu' lento: {lento[0].strip()}")

    # 2. I servizi. Tutti utente, tutti col linger: devono essere su senza login.
    stati = []
    for servizio in ("elechim-gateway", "ollama", "searxng", "macmini-tunnel"):
        attivo = _cmd("systemctl", "--user", "is-active", f"{servizio}.service")
        stati.append(f"{servizio}={attivo}")
    esiti.append("Servizi: " + ", ".join(stati))

    # 3. Il modello sul Mac, attraverso il tunnel.
    try:
        r = requests.get("http://127.0.0.1:8080/v1/models", timeout=10)
        esiti.append(f"Modello sul Mac: HTTP {r.status_code}")
    except Exception as errore:  # noqa: BLE001
        esiti.append(f"Modello sul Mac: NON raggiungibile ({type(errore).__name__})")

    # 4. La GPU e il link PCIe, che il rimontaggio della 1050 aveva rinumerato.
    esiti.append("GPU: " + _cmd(
        "nvidia-smi",
        "--query-gpu=name,memory.used,pcie.link.gen.current,pcie.link.width.current",
        "--format=csv,noheader",
    ))

    # 5. La preservazione della VRAM al suspend: deve restare in mano al kernel.
    #    Se PreserveVideoMemoryAllocations diventa 1 vuol dire che qualcuno ha
    #    rimesso il conf sbagliato.
    esiti.append(
        f"Suspend GPU: UseKernelSuspendNotifiers={_param_nvidia('UseKernelSuspendNotifiers')} "
        f"PreserveVideoMemory={_param_nvidia('PreserveVideoMemoryAllocations')} (attesi 1 e 2)"
    )

    # 6. Il risveglio da rete: senza questo il fisso si addormenta e non torna.
    wol = Path("/sys/class/net/enp6s0/device/power/wakeup")
    esiti.append(
        f"Wake-on-LAN: {wol.read_text().strip() if wol.exists() else 'interfaccia assente!'}"
        f" - IP {_cmd('sh', '-c', 'ip -4 -br addr show enp6s0')or '?'}"
    )

    # 7. Il controllo di sospensione e il motivo per cui adesso e' sveglio.
    esiti.append("Sospensione: " + (_cmd(
        "systemctl", "--user", "list-timers", "elechim-sospensione.timer",
        "--no-pager", "--no-legend",
    ) or "TIMER NON ATTIVO"))
    motivi = energia.motivi_per_restare_svegli(aggiorna=False)
    esiti.append("  sveglio perche': " + ("; ".join(motivi) or "nessun motivo, dormira'"))

    # 8. Lo sfratto di whisper, che prima non esisteva.
    esiti.append(f"Sfratto whisper: {gateway.SFRATTO_WHISPER}s")

    # 9. Guasti veri nel kernel.
    errori = _cmd(
        "sh", "-c",
        "journalctl -k -b | grep -icE 'EDAC MC[0-9]+:|Hardware Error|\\bXid\\b'",
    )
    esiti.append(f"Errori kernel (EDAC/Xid): {errori}")

    return esiti


def main() -> int:
    corpo = "Riavvio completato.\n\n" + "\n".join(righe())
    print(corpo, flush=True)

    env = gateway.ENV
    destinatari = [
        x.strip() for x in env.get("TELEGRAM_ALLOWED_IDS", "").split(",") if x.strip()
    ]
    if not destinatari:
        print("nessun destinatario in TELEGRAM_ALLOWED_IDS", flush=True)
        return 1

    for chat in destinatari:
        try:
            requests.post(
                f"https://api.telegram.org/bot{env['TELEGRAM_TOKEN']}/sendMessage",
                json={"chat_id": int(chat), "text": corpo},
                timeout=30,
            ).raise_for_status()
        except Exception as errore:  # noqa: BLE001
            print(f"invio a {chat} fallito: {errore}", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
