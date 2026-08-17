# Rapporto — la sorveglianza durante l'esercizio

Scritto il **17 agosto 2026** eseguendo `INCARICO-salute.md`. Il guasto che
motiva tutto: il 15 agosto alle 17:20 `elechim-documenti.path` e' andato in
`failed` e nessuno se ne e' accorto per **1 giorno e 19 ore** (sezione 1-bis di
`DA-FARE.md`): `verifica_avvio.py` guarda le unit dopo il riavvio, `op_salute`
guarda visione e ricerca su richiesta. Manca il pezzo in mezzo. Questo rapporto
e' scritto **mentre** il lavoro procede, non alla fine: i numeri prima, le
conclusioni quando sono pronte.

## I numeri di partenza (17 agosto 2026, 14:15)

| controllo | valore misurato | esito |
|---|---|---|
| `elechim-documenti.path` | `active` | verde (era il guasto del 15) |
| `elechim-gateway.service` | `active` | verde |
| container `searxng` | service `active`, container Up 45h | verde |
| container `crawl4ai` | service `active`, container Up 45h | verde |
| coda | `documenti/in/` senza PDF al primo livello | verde |
| disco `/home` | **769 GB liberi** su 929 GB (18% usato) | verde |
| core dump `/var/lib/systemd/coredump` | **989 MB** (957 stamattina: cresce) | verde, sotto soglia |

## I controlli scelti, le soglie e il perche'

La misura vive in **una sola funzione**, `misura_salute()` in `gateway.py`:
`op_salute` (su richiesta, via HTTP) e il timer `elechim-salute.timer` (ogni 15
minuti) chiamano la stessa. Un solo meccanismo, due lettori. Chi **decide** se
notificare e' `decide()` in `salute.py`, una funzione pura: separare il
misurare dal decidere e' quello che rende provabili le transizioni senza
tocccare systemd (casi 1-6 di `prova_salute.py` con misurazioni finte).

| controllo | verde quando | soglia | perche' questa soglia |
|---|---|---|---|
| `elechim-documenti.path` | `systemctl --user is-active` = `active` | — | e' il guasto vero appena avvenuto |
| `elechim-gateway.service` | `active` | — | idem; la sorveglianza non dipende dal gateway: legge systemd direttamente, quindi lo vede anche caduto |
| container `searxng`, `crawl4ai` | service `active` (quadlet podman) | — | stesso colpo di `systemctl`, costo nullo |
| coda ferma | nessun `*.pdf` in `documenti/in/` fermo oltre **1 h** col lock libero | 3600 s | vedi sotto, e' il criterio delicato |
| disco | liberi **> 50 GB** su `/home` | 50 GiB | oggi 769 GB (15x la soglia): scatta quando resta margine per settimane, non per ore |
| core dump | `/var/lib/systemd/coredump` sotto **2 GB** | 2 GiB | oggi 989 MB: avvisa al raddoppio, ~2g di crescita al ritmo osservato. Si misura e si avvisa, non si cancella |

Le prime due sono quelle che contano: sono il guasto del 15 agosto. Le altre
costano pochi millisecondi quando il timer e' gia' li' a guardare.

### Il criterio esatto per «coda ferma», e come esclude i falsi allarmi

Un PDF in `in/` **non** e' un guasto. Lo diventa solo con **entrambe** le
condizioni, verificate in quest'ordine:

1. esiste almeno un `*.pdf` al primo livello di `documenti/in/` con eta' oltre
   `SOGLIA_CODA_SEC` (1 ora);
2. **e** il lock `stato/documenti/.coda.lock` e' **libero**: la sorveglianza
   prova `flock(LOCK_EX | LOCK_NB)`; se fallisce, qualcuno sta macinando.

Come esclude i falsi allarmi del lavoro normale:

- **PDF arrivato un secondo fa** (Syncthing rinomina solo a trasferimento
  completo): eta' sotto soglia → verde, qualunque stato del lock.
- **Documento legittimamente lungo in lavorazione** (533 pagine, o una coda di
  piu' file): `documenti.py` tiene il `flock` per **tutta** la macinazione
  (`_coda_esclusiva` in `main`) → condizione 2 non vera → verde. Il lock e'
  la differenza fra «lento» e «fermo»: senza guardarlo, un libro grosso
  genererebbe un falso allarme ogni volta.
- **PDF arrivato mentre macina un altro**: sta in `in/`, il lock e' preso →
  verde.
- Soglia 1 ora contro i 70 s misurati per `DSML.pdf` (533 pagine): margine
  50x. Non e' il tempo di lavorazione che la soglia deve coprire — quello lo
  copre il lock — ma il tempo ragionevole perche' il path unit scatti (secondi)
  piu' un errore di orologio generoso.
- La directory `documenti/in/falliti/` non conta: il glob e' `in/*.pdf`, non
  ricorsivo, come il path unit.

Cosa **non** copre e va dichiarato: la sorveglianza gira ogni 15 minuti, quindi
un guasto che nasce e **guarisce** dentro una finestra di 15 minuti non viene
notificato. E' un limite accettato: abbassare la cadenza alzerebbe il rumore,
che e' il modo piu' rapido per rendere inutile l'allarme.

## Il decidere: transizioni, non ripetizioni

`decide(precedente, misurazioni, adesso)` in `salute.py`, pura, con lo stato
precedente su disco in `stato/salute.json` (scrittura atomica: tmp +
`os.replace`, perche' uno stato corrotto si deve trattare, non subire):

- primo controllo (stato assente, corrotto, o controllo nuovo): **registra e
  tace**, anche se qualcosa e' gia' rosso — la ripetizione giornaliera lo
  annunciara' se dura;
- transizione verde→rosso: una riga «GUASTO ... (dal gg/mm hh:mm)»;
- resta rosso: silenzio, **tranne** una ripetizione ogni 24 h esatte
  (`RIPETIZIONE_SEC = 86400`): un guasto che dura non deve diventare invisibile
  solo perche' e' vecchio;
- transizione rosso→verde: una riga di ripristino con la durata della caduta,
  poi silenzio;
- piu' transizioni nello stesso ciclo → **un solo messaggio** Telegram con una
  riga ciascuna.

Perche' 24 h e non 10 minuti: la ripetizione serve a non dimenticare un guasto
cronico, non a tormentare. Una volta al giorno e' la cadenza di una cosa che
un umano decide di rimandare a domani.

## Come arriva l'avviso

- `elechim-salute.timer`, **`OnCalendar=*:0/15`**: l'orologio da muro avanza
  anche mentre il fisso dorme, `OnUnitActiveSec` no (lezione gia' pagata, in
  README e AGENTS). `Persistent=true`: un controllo perso col fisso spento o
  addormentato viene recuperato al risveglio — e' la copertura del buco che ha
  motivato questo lavoro. Nessun `BindsTo`, nessun `StartLimitIntervalSec`
  copiato per abitudine: qui innesca un timer, non un path unit.
- L'invio riusa **un solo meccanismo**: `notifica_telegram()` estratto in
  `gateway.py` da `verifica_avvio.py`, che adesso lo richiama. Nessun secondo
  sender e' stato scritto.
- La sorveglianza non passa dal gateway HTTP: legge `systemctl` direttamente,
  quindi vede `elechim-gateway.service` caduto anche col gateway giu'.

### Cosa cambia in `op_salute` (e cosa non)

`op_salute` ora include `misura_salute()` nella risposta, sotto la chiave
`controlli`. La chiave `ok` **resta** `visione AND ricerca`: la legge
`gateway_raggiungibile()` in `mac/strumenti.py` per decidere se il Mac puo'
usare gli strumenti, e i core dump sopra soglia non devono togliere la ricerca
al proprietario. `mac/` non si tocca, quindi il formato risposta resta
compatibile al byte: stesse tre chiavi di prima piu' `controlli`.

## Stato dei lavori

- [x] Misure di partenza (tabella sopra)
- [ ] `misura_salute()` + `notifica_telegram()` in `gateway.py`, `op_salute` estesa
- [ ] `salute.py` (decide + stato su disco + main)
- [ ] `prova_salute.py` TUTTO VERDE, casi 1-6
- [ ] timer + service installati e armati
- [ ] prova reale: path unit fermato a mano → una notifica; riattivato → ripristino; coda funzionante
- [ ] `DEFINIZIONI` intatta (verifica in fondo)

## Esiti (aggiornati a lavoro finito)

_(in corso)_

## Dichiarazione su DEFINIZIONI

_(da verificare a fine lavoro: confronto `strumenti.py` contro `mac/strumenti.py`)_
