# Le unit systemd

Le otto unit utente che tengono in piedi Elechim sul fisso. Fino al 17 agosto 2026
vivevano **solo** in `~/.config/systemd/user/`: nessuna storia, nessun backup, e
alcune delle lezioni piu' care del progetto scritte dentro file che il repo non
conteneva. Questa cartella e' la copia canonica.

I percorsi usano `%h` (la home dell'utente, risolta da systemd), non percorsi
assoluti: le unit sono uguali per chiunque le installi.

## Installare

```sh
./installa.sh          # copia, ricarica, abilita
systemctl --user list-units 'elechim*'
```

Lo script **non abilita** `elechim-bot.service` (vedi sotto).

## Cosa fa ciascuna

| unit | mestiere |
|---|---|
| `elechim-gateway.service` | il gateway degli strumenti sul fisso (ricerca, vocali, immagini) |
| `elechim-documenti.path` | sorveglia `documenti/in/*.pdf` |
| `elechim-documenti.service` | macina i PDF in coda e scrive le note |
| `elechim-sospensione.timer` + `.service` | ogni dieci minuti decide se il fisso puo' dormire |
| `elechim-verifica-avvio.timer` + `.service` | rapporto di verifica tre minuti dopo l'avvio |
| `elechim-bot.service` | **disabilitata e superata**: il bot gira sul Mac via launchd. Resta qui come documentazione di com'era prima, e punta a un `bot.py` che sul fisso non esiste. Non abilitarla. |

## Le lezioni che stanno dentro questi file

Sono commentate nelle unit stesse, ed e' il motivo per cui vanno versionate: si
leggono dove sono implementate.

- **`elechim-documenti.service`: `StartLimitIntervalSec=0`.** Un servizio
  `oneshot` innescato da un path unit che sorveglia la cartella che il servizio
  stesso svuota viene riavviato in continuazione finche' c'e' lavoro. Le istanze
  che trovano il lock preso escono con **successo**, ma col default di systemd (5
  avvii in 10 secondi) al sesto arriva `start-limit-hit`, il fallimento **si
  propaga al path unit**, e la coda smette di sorvegliare. Successo il 15 agosto
  2026: dieci avvii riusciti in 33 secondi, coda ferma **1 giorno e 19 ore**, in
  silenzio. Alzare il burst non basta: gli avvii sono illimitati per costruzione.
- **`elechim-documenti.path`: il glob e' `*.pdf`, non la cartella.** Syncthing
  scrive con un nome temporaneo e rinomina solo a trasferimento completo, quindi
  il glob non scatta mai su un file a meta'. Sorvegliare la cartella avrebbe
  fatto macinare documenti troncati senza un errore da nessuna parte.
- **Niente `BindsTo`.** Uno stop ordinato da systemd su un'unita' legata con
  `BindsTo` disattiva `Restart`, e il servizio non torna su.
- **Attenzione a `OnUnitActiveSec`**: non avanza durante la sospensione, quindi
  su una macchina che dorme un timer basato su quello salta i giri senza dirlo.

## La copia che gira non si tocca

Le unit installate in `~/.config/systemd/user/` possono contenere percorsi
assoluti: **e' voluto lasciarle come sono**. La regola, pagata il 15 agosto
depersonalizzando un file eseguibile in place, e' che un file che gira non si
modifica per farlo star bene in un repo pubblico — o il dato si legge da fuori, o
la copia pubblica e' distinta da quella che gira. Qui vale la seconda.
