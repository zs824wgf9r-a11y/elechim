# Incarico: accorgersi che qualcosa e' morto, mentre e' morto

Scritto il 17 agosto 2026, dopo aver scoperto per caso che la coda documenti era
ferma da **1 giorno e 19 ore**. Leggi prima `AGENTS.md`, poi la sezione 1-bis di
`DA-FARE.md` (il guasto che motiva questo incarico), poi `gateway.py` (`op_salute`)
e `verifica_avvio.py`.

## Il difetto, e non e' un bug: e' un buco nella sorveglianza

Il 15 agosto alle 17:20 `elechim-documenti.path` e' andato in `failed` e **ha
smesso di sorvegliare la coda**. Nessuno se ne e' accorto per **1 giorno e 19 ore**.
Non c'e' stato nessun allarme perche' non esiste nessun allarme: un PDF messo in
`documenti/in/` non sarebbe stato macinato, in silenzio.

Cosa esiste oggi:

- **`verifica_avvio.py`**: guarda le unit **dopo il riavvio** e manda un rapporto su
  Telegram. Copre l'avvio, non l'esercizio.
- **`op_salute`** in `gateway.py`: controlla **visione** e **ricerca**, ed e' su
  richiesta. Non guarda la coda, non guarda i container.

Manca il pezzo in mezzo: **qualcosa che guardi durante**, e che parli solo quando
c'e' da parlare.

## Il principio, che viene prima del codice

**Un allarme che suona sempre viene ignorato; un allarme che non suona mai e'
decorativo.** Quindi:

- si notifica **sulla transizione** (una cosa che era sana diventa malata, o
  viceversa), **non** a ogni controllo;
- lo stato precedente si tiene su disco (`stato/salute.json`), perche' la
  transizione ha bisogno di memoria;
- il ripristino si annuncia una volta («la coda e' tornata») e poi si tace;
- se una cosa e' malata da molto, si **ripete** l'avviso con parsimonia (una volta
  al giorno, non ogni dieci minuti). Un guasto che dura non deve diventare
  invisibile solo perche' e' vecchio.

## Cosa controllare

Estendi `op_salute` — non farne un secondo meccanismo — con:

| controllo | verde quando |
|---|---|
| `elechim-documenti.path` | `systemctl --user is-active` dice `active` |
| `elechim-gateway.service` | `active` |
| container `searxng`, `crawl4ai` | in esecuzione |
| coda ferma | nessun `*.pdf` in `documenti/in/` piu' vecchio di ~1 ora |
| disco | spazio libero sopra una soglia che dichiari tu |
| core dump | `/var/lib/systemd/coredump` sotto una soglia (oggi **957 MB**) |

Le prime due sono quelle che contano: sono il guasto vero appena avvenuto. Le
altre sono a costo quasi zero se sei li' a guardare.

**«Coda ferma» e' il controllo piu' importante e il piu' delicato.** Un PDF in
`in/` non e' un guasto: potrebbe essere arrivato un secondo fa. Lo diventa se ci
resta **mentre nessuno lo lavora**. Il criterio va scelto con attenzione: un
documento da 533 pagine e' legittimamente in lavorazione per minuti, e
`stato/documenti/.coda.lock` dice se qualcuno ce l'ha in mano. **Non produrre falsi
allarmi mentre la coda funziona**: e' il modo piu' rapido per rendere inutile
l'allarme.

## Come si notifica

Un timer utente `elechim-salute.timer` che gira **ogni 15 minuti** e chiama la
verifica. Su transizione a malato, messaggio Telegram con la riga essenziale: cosa
e' rotto e da quando. Riusa il meccanismo di invio che `verifica_avvio.py` ha
gia' — **non scriverne un secondo**.

**Il timer va costruito con le due lezioni gia' pagate**, e sono scritte nel README:

- `OnUnitActiveSec` **non avanza durante la sospensione**: un timer basato su
  quello, su una macchina che dorme, salta i controlli senza dirlo. Usa
  `OnCalendar`, e considera `Persistent=true` se un controllo perso al risveglio va
  recuperato.
- **Niente `BindsTo`**: disattiva `Restart` (vedi il README). Non serve qui, ma non
  introdurlo.
- E la lezione del 17 agosto: se un giorno questo servizio venisse innescato da un
  path unit, ci vuole `StartLimitIntervalSec=0`. Qui e' un timer, quindi non
  serve — ma **non copiare** un default che non hai capito.

## Cosa NON fare

- **Non toccare `documenti.py` ne' `prova_documenti.py`**: c'e' un'altra sessione
  che ci lavora **adesso**.
- **Non toccare `sbobina.py` ne' `prova_sbobina.py`**: appena consegnati, e sta per
  partire una macinata da 4 ore su quel file.
- Non toccare `fusione.py`, `strumenti.py`, `energia.py`, `mac/`, `README.md`,
  `README.it.md`, `AGENTS.md`, `DA-FARE.md`, gli altri `INCARICO-*`, git.
- **`DEFINIZIONI` non si tocca.**
- **Non usare la GPU** e non chiamare modelli: questo lavoro non ne ha bisogno, e
  la GPU e' occupata da un'altra sessione.
- **Non cancellare i core dump** e non fare pulizia di disco di tua iniziativa:
  qui si **misura e si avvisa**, non si buttano dati. La cancellazione la decide il
  proprietario.
- Niente dipendenze nuove.

## Come si prova

`prova_salute.py` nuovo, e i casi che contano sono le **transizioni**, non i
controlli:

1. tutto sano -> **nessuna notifica**. E' il caso che si rompe piu' spesso ed e'
   il piu' importante: un allarme che parla quando va tutto bene e' peggio di
   nessun allarme;
2. una unit passa a `failed` -> **una** notifica, con cosa e da quando;
3. resta `failed` al controllo successivo -> **nessuna** seconda notifica (fino
   alla ripetizione giornaliera);
4. torna `active` -> **una** notifica di ripristino, poi silenzio;
5. un PDF appena messo in `in/` con il lock preso -> **nessun** allarme (e' lavoro
   in corso, non un guasto);
6. lo stato su disco corrotto o assente -> si riparte senza esplodere, trattando
   tutto come "primo controllo" e senza sparare notifiche a raffica.

La verifica non deve richiedere di rompere davvero le unit del sistema: rendi
iniettabile la funzione che legge lo stato (una funzione che torna il dizionario dei
controlli), cosi' i casi 1-6 si provano con dati finti e **senza toccare systemd**.
E' anche progetto migliore, perche' separa il misurare dal decidere.

## Criterio di uscita

- `prova_salute.py` **TUTTO VERDE**, coi sei casi sopra;
- una prova reale: fermi il path unit a mano, aspetti un ciclo, arriva **una**
  notifica; lo riattivi, arriva **il ripristino**; e la coda resta funzionante;
- `RAPPORTO-salute.md` con: i controlli scelti, le soglie e il perche', il criterio
  esatto per "coda ferma" e come hai escluso i falsi allarmi durante il lavoro
  normale, e la cadenza di ripetizione scelta;
- `DEFINIZIONI` intatta, e dichiaralo.

Scrivi il rapporto appena hai i numeri, non alla fine.
