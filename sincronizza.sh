#!/usr/bin/env bash
# Porta sul Mac i sorgenti di Elechim e lo riavvia.
#
# L'originale dei file del Mac sta QUI, in ~/assistente/mac/. Si modifica qui e
# si sincronizza con questo script: due copie modificabili sono il modo piu'
# rapido di ritrovarsi con un bug gia' corretto da una parte e ancora vivo
# dall'altra.
#
# Non tocca stato.db (la conversazione vive sul Mac) ne' il .venv.

set -euo pipefail

MAC=macmini-plain
SORGENTE="$HOME/assistente/mac/"

rsync -az \
    --exclude '__pycache__' \
    --exclude '.venv' \
    --exclude 'stato.db' \
    "$SORGENTE" "$MAC:assistente/"

echo "sorgenti sincronizzati"

# Elechim gira come LaunchDaemon (dominio `system`, il Mac e' headless): un
# `launchctl kickstart` vorrebbe sudo, che qui non abbiamo. Ma il processo gira
# come utente normale e il daemon ha KeepAlive, quindi basta ucciderlo e
# launchd lo ritira su entro ThrottleInterval (10s).
#
# Il pattern e' scritto `[b]ot.py` di proposito: senza le parentesi pkill
# ammazzerebbe anche la shell che ssh apre per eseguirlo, visto che il pattern
# compare nella sua stessa riga di comando.
ssh "$MAC" "pkill -f 'assistente/[b]ot.py'" \
    && echo "bot fermato, launchd lo riavvia entro ~10s" \
    || echo "nessun bot in esecuzione (lo avviera' launchd)"
