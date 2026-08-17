#!/usr/bin/env bash
# Installa le unit utente di Elechim. Vedi README.md per cosa fa ciascuna.
set -euo pipefail

qui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dest="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

# `elechim-bot.service` resta fuori: e' superata dal bot sul Mac e punta a un
# file che sul fisso non esiste. Si copia lo stesso, ma non si abilita.
da_abilitare=(
  elechim-gateway.service
  elechim-documenti.path
  elechim-sospensione.timer
  elechim-verifica-avvio.timer
)

mkdir -p "$dest"
for u in "$qui"/elechim-*; do
  n="$(basename "$u")"
  if [ -f "$dest/$n" ] && ! cmp -s "$u" "$dest/$n"; then
    cp -a "$dest/$n" "$dest/$n.prima-$(date +%Y%m%d%H%M%S)"
    echo "  $n differiva: copia di sicurezza salvata"
  fi
  cp "$u" "$dest/$n"
done
echo "copiate $(ls "$qui"/elechim-* | wc -l) unit in $dest"

systemctl --user daemon-reload

# `reset-failed` prima di abilitare: se una unit e' rimasta in `failed` da un
# guasto precedente, `start` non la fa ripartire e sembra che l'installazione
# non abbia funzionato. Successo il 15 agosto con la coda in `start-limit-hit`.
systemctl --user reset-failed "${da_abilitare[@]}" 2>/dev/null || true

for u in "${da_abilitare[@]}"; do
  systemctl --user enable --now "$u"
  printf "  %-32s %s\n" "$u" "$(systemctl --user is-active "$u")"
done

echo
echo "fatto. Controlla con:  systemctl --user list-units 'elechim*'"
