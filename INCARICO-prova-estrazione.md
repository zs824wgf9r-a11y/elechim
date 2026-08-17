# Incarico: l'estrazione di Honcho regge l'italiano?

Scritto il 17 agosto 2026. Leggi prima `AGENTS.md`, poi `RICERCA-memoria.md`
(il confronto che porta qui).

## Perche' questa prova viene prima di installare qualsiasi cosa

Il proprietario ha scelto **Honcho** per la fase 3. Ma `RICERCA-memoria.md` dice
che sull'italiano **nessuno dei candidati ha prove, solo promesse**: Honcho
genera i riassunti in inglese di default (issue #748 aperta), Graphiti ha i
prompt «all in English» (issue #1141). Le nostre conversazioni sono in italiano.

Se l'estrazione non regge l'italiano, Postgres, pgvector e tutto il resto sono
lavoro buttato. Quindi si prova **prima**, e si prova **senza installare niente**:
l'estrazione di Honcho e' un LLM guidato da un prompt, e il modello e'
configurabile. Basta prendere il prompt vero e girarlo in locale.

## Il vincolo che viene prima di tutto

**`archivio/` contiene le conversazioni vere del proprietario.**

- **Non leggerle.** Non aprirle, non stamparle, non citarne pezzi — ne' nel
  codice, ne' nei log, ne' nel rapporto. Tu scrivi lo script; i dati li tocca
  solo la macchina quando lo script gira.
- L'output dell'estrazione contiene **fatti sul proprietario**: va scritto in una
  cartella **ignorata da git** (`stato/` o `archivio/` lo sono gia'). Verificalo
  con `git check-ignore` prima di scriverci.
- Nel tuo rapporto vanno **solo numeri**: quante osservazioni, in che lingua,
  quanto tempo. **Zero testo delle conversazioni, zero osservazioni estratte.**
  Chi giudica se le osservazioni sono buone e' il proprietario, leggendole in
  locale — come per la sbobina.

## Il lavoro

Uno script `prova_estrazione.py`.

### 1. Il prompt vero, non uno inventato

Prendilo dal sorgente di Honcho (`plastic-labs/honcho`, il prompt del *deriver*
che ricava osservazioni dai messaggi). **Cita l'URL e la revisione** nel rapporto:
se un giorno cambia, dobbiamo sapere su cosa abbiamo misurato. Se non trovi il
prompt esatto, **fermati e dillo** invece di scriverne uno tuo: misureresti una
cosa diversa da quella che poi installeremo.

C'e' un `GITHUB_TOKEN` in `.env` per non sbattere nel rate limit. **Non stamparlo
mai.**

### 2. Girarlo in locale

- modello: `qwen3:8b` su ollama del fisso — lo stesso che useremmo davvero;
- **prendi il lock GPU**: `energia.riserva_gpu("prova-estrazione")`, che esiste
  da oggi. Senza, sfratti il modello a un'altra sessione;
- **prendi anche `energia.blocco`**, o il fisso si addormenta a meta';
- campione **deterministico**, con un criterio ripetibile che dichiari, cosi' la
  prova si puo' rifare identica.

**Il materiale disponibile, gia' inventariato (conteggi, non contenuti):**

| dove | quanto |
|---|---|
| `archivio/stato-prima-dei-fix-20260811-1205.db` | tabella `messaggi`, **54 righe** |
| `archivio/stato-prima-del-trasloco-20260810-2357.db` | tabella `messaggi`, **30 righe** |
| `archivio/stato-mac-20260811-0021.db` | tabella `messaggi`, **6 righe** |
| `archivio/*.jsonl` | 36 righe in tutto |

Sono **~90 messaggi**: sono SQLite, si aprono in sola lettura
(`sqlite3.connect("file:...?mode=ro", uri=True)`). `stato.db` sul fisso **non
esiste** — il bot gira sul Mac, quindi quelle istantanee sono tutto cio' che c'e'
in locale.

**Novanta messaggi bastano per la domanda binaria** (esce italiano? esce
qualcosa?) e **non bastano** per giudicare la qualita' su larga scala. Dillo nel
rapporto invece di far finta: un campione piccolo dichiarato vale piu' di una
conclusione gonfiata.

### 3. Cosa misurare

Sono le uniche cose che finiscono nel rapporto:

| misura | perche' |
|---|---|
| osservazioni estratte per conversazione (min/mediana/max) | zero osservazioni = non funziona; trecento = rumore |
| **in che lingua sono** — % italiano contro inglese | e' la domanda dell'incarico |
| conversazioni con **zero** osservazioni | il modo di fallimento piu' probabile |
| tempo per conversazione, e token di prompt | quanto costerebbe ingerire un anno di chat |
| quante osservazioni contengono **numeri o date** | se li altera, vale la regola della sbobina |

Per la lingua serve un criterio **meccanico**, non a occhio: una lista di parole
funzione italiane contro inglesi, o una libreria gia' presente. Dichiara il
criterio e la sua soglia.

### 4. Il file da far leggere al proprietario

Un solo file, in una cartella ignorata da git, con le osservazioni estratte
accanto alla conversazione da cui vengono — cosi' si giudica se sono giuste.
Scrivi **il percorso** nel rapporto. Non aprirlo.

## Cosa NON fare

- **Non installare Honcho**, ne' Postgres, ne' pgvector, ne' container.
- Non toccare `energia.py`, `sbobina.py`, `documenti.py`, i loro collaudi,
  `gateway.py`, `mac/`, `AGENTS.md`, `DA-FARE.md`, `unita/`, `lavoro.py`,
  `guardiano.py`, gli altri `INCARICO-*` e `RAPPORTO-*`.
- **`DEFINIZIONI` non si tocca.**
- Niente dipendenze nuove: ollama e la libreria standard bastano.
- **Non lanciare la prova su tutto `archivio/`**: un campione, dichiarato.

## Criterio di uscita

- `prova_estrazione.py` gira e produce le misure;
- `RAPPORTO-prova-estrazione.md` con: l'URL e la revisione del prompt usato, il
  criterio di campionamento, il criterio di rilevamento della lingua, **tutte le
  misure della tabella**, e il percorso del file da leggere.
  **Nessun testo di conversazione, nessuna osservazione riportata.**
- Una riga di verdetto tua: **l'estrazione regge l'italiano, si' o no**, e su
  quale numero lo dici. Se il verdetto e' «non si capisce», va bene, ma spiega
  cosa servirebbe per capirlo.

Scrivi il rapporto **appena hai i numeri**. E crea il file del rapporto, anche
vuoto coi soli titoli, **prima** di cominciare a misurare: oggi sei sessioni su
nove hanno perso le conclusioni scrivendole per ultime.
