# Incarico: fase 4, corsia veloce

> **CONSEGNATO il 15 agosto 2026**, primo e secondo giro. La catena gira in
> esercizio: `DSML.pdf` 533 pagine in 70s. **Restano aperti** i falsi positivi
> sulle tabelle (punto 1 del secondo giro), che sono passati a
> `INCARICO-tabelle-e-scansioni.md` insieme alla riproduzione sul sintetico.

Scritto il 15 agosto 2026. Leggi prima `AGENTS.md` e `PIANO-DOCUMENTI.md`.
Questo file restringe il piano a cio' che va costruito **adesso**, e corregge un
punto del piano che si e' rivelato sbagliato alla prova.

## Cosa consegnare

Un modulo `documenti.py` in `~/assistente/` che porta un PDF con livello di
testo dalla cartella d'ingresso fino alle note su Obsidian, con un rapporto di
copertura. Deterministico: **in questa fase nessun LLM tocca il contenuto.**

Deve funzionare da CLI per la prova:

```
.venv/bin/python documenti.py "/percorso/al/file.pdf"
```

## La correzione al piano — verificata, non teorica

`PIANO-DOCUMENTI.md` prescrive `pdftotext -layout`. **Su un documento a due
colonne `-layout` produce prosa illeggibile**, perche' affianca le colonne riga
per riga. Misurato su `Basic_Statistics_2007.pdf`:

```
$ pdftotext -layout -f 1 -l 1 ...
Statistics is a relatively new science with         scribing the information being studied. Ran-
most of the important developments occurring        dom variables can be further described by the

$ pdftotext -f 1 -l 1 ...        # senza -layout: ordine di lettura corretto
most of the important developments occurring
within the last 100 years. Motivation for statistics as a formal scientific discipline came from
```

Ma `-layout` **serve** per le tabelle: e' cio' che tiene allineate le colonne di
numeri, e la regola non negoziabile dice che le tabelle si conservano verbatim.

**Quindi servono tutte e due le modalita', scelte per regione:**

- prosa -> `pdftotext` senza `-layout` (ordine di lettura)
- tabelle -> `pdftotext -layout` sulla stessa pagina, ritagliando la regione

Come riconoscere una pagina o una regione tabellare e' parte del lavoro. Un
euristico ragionevole: nell'output `-layout`, righe con piu' occorrenze di 2+
spazi consecutivi e alta densita' di cifre. Non inventare: **provalo e misura**.
Se il riconoscimento e' incerto, sbaglia per eccesso — una tabella conservata
verbatim dentro il testo non fa danno, una tabella persa si'.

## La catena

1. **Coda.** Cartella sorvegliata `documenti/in/`. Il lavoro deve essere
   **ripartibile**: il fisso si sospende da solo dopo tre ore, e un documento
   interrotto riprende da dove era, non da capo. Marcatore di stato per
   documento (una cartella `stato/documenti/` o una tabella sqlite, decidi tu e
   motiva la scelta nel README). A lavoro finito il PDF si sposta, non si
   cancella.

2. **Estrazione integrale** in `markdown/<slug>.md`, **fuori dal vault**, con
   **ancore di pagina** (es. `<!-- pag 7 -->`) — servono alle note per puntare
   al punto giusto, e all'indice vettoriale della fase 6. Questo file e' la
   verita': se una nota e' imprecisa, l'informazione e' a un link di distanza.

3. **Sezionamento per struttura**, non a lunghezza fissa. I titoli si
   riconoscono dal PDF (dimensione del font via `pdftotext -bbox` o
   `pdffonts`/`pdftohtml -xml`), non a occhio sul testo semplice: un euristico
   su MAIUSCOLE e righe corte fallisce su qualsiasi documento vero. Se non trovi
   struttura affidabile, **dillo nel rapporto** invece di inventare sezioni.

4. **Note su Obsidian.** Una cartella per documento in
   `~/Obsidian/20-Documenti/<slug>/` con la nota indice (frontmatter, tag,
   metadati del documento, link al markdown integrale) e da li' wikilink alle
   note atomiche, **una per sezione**, in `~/Obsidian/30-Note/`. Mai una nota
   unica da 80 pagine. Il vault e' vuoto: sei tu a stabilire la convenzione, e
   va scritta nel README.

5. **Rapporto di copertura**, la parte che rende vera la promessa "senza
   tralasciare nulla": pagine processate su totali, caratteri estratti, sezioni
   trovate e sezioni con nota, tabelle conservate, figure trovate. Restituiscilo
   come **dict** da una funzione, piu' una formattazione leggibile. **Non
   spedirlo su Telegram in questa fase** (vedi Fuori scopo).

## Fuori scopo — non toccare

- **`DEFINIZIONI` in `strumenti.py`, ne' qui ne' in `mac/strumenti.py`.** I tool
  documenti si aggiungeranno tutti insieme piu' avanti, in un momento deciso.
  Se ti sembra che serva un tool per finire il lavoro, **fermati e scrivilo nel
  rapporto finale** invece di aggiungerlo.
- **Marker, `torch`, OCR**: sono la corsia piena, vengono dopo. Non installare
  pacchetti da gigabyte.
- **Le figure**: `pdfimages -list` sul PDF di prova non trova nulla perche' le
  figure sono **vettoriali**, quindi andranno rese con `pdftocairo` a livello di
  pagina, non estratte con `pdfimages`. In questa fase **limitati a contarle e
  segnalarle nel rapporto**. La descrizione con qwen3-vl viene dopo.
- **Non riavviare ne' fermare i servizi attivi** (`elechim-gateway`,
  `macmini-tunnel`, `searxng`, `ollama`): il bot e' in uso vero.
- **Non leggere ne' stampare `.env`.**

## Ambiente

- venv `.venv`, **Python 3.12, creato con uv: non c'e' `pip`.** Si installa con
  `uv pip install --python .venv/bin/python <pacchetto>`. Preferisci la libreria
  standard e poppler (gia' installato, 26.01) a una dipendenza nuova.
- Poppler da riga di comando: `pdftotext`, `pdfinfo`, `pdfimages`, `pdftocairo`,
  `pdffonts`, `pdftohtml`. Sono tutti disponibili.

## Come si prova — leggi bene, questo vincola il metodo

**Tu sei l'architetto e il muratore, non l'operaio che macina i PDF.** A
macinare documenti e' sempre e solo il fisso, in locale. Tu scrivi il codice e
il collaudo; il contenuto dei documenti **non deve entrare nel tuo contesto**
(vedi la regola in `AGENTS.md`).

Quindi la prova si fa cosi', ed e' anche ingegneria migliore:

**1. Costruisci un PDF di prova sintetico**, generato da uno script tuo
(`prova_documenti.py`), con **testo noto scritto da te**: due colonne, un
titolo, due o tre sezioni, una tabella di numeri, dieci pagine circa. Serve
`pdftocairo`/`ps2pdf` o una libreria leggera — decidi tu, ma niente da
gigabyte. Il testo noto e' la verita' di riferimento.

**2. Il collaudo e' fatto di asserzioni esatte**, non di giudizi a occhio:

- la prosa estratta **contiene le frasi note per intero**, nell'ordine giusto:
  e' cosi' che si dimostra che le colonne non sono interlacciate, con un
  confronto invece che con un'impressione;
- la tabella estratta contiene **le cifre note, tutte**, verbatim;
- il rapporto di copertura dice N pagine su N;
- le note in `20-Documenti/` e `30-Note/` esistono e **ogni wikilink risolve** a
  una nota che esiste davvero (verificalo con codice, non a mano);
- rilanciare sullo stesso file **non duplica** le note;
- interrompere a meta' e rilanciare **riprende**, non ricomincia.

Lascia `prova_documenti.py` nel progetto: e' il collaudo che serve anche domani.

**3. Sul PDF vero non guardare il testo.** Puoi far girare la catena su
`Basic_Statistics_2007.pdf` (10 pagine, due colonne, pubblico) per vedere se
regge un documento non costruito da te, ma **stampa e leggi solo le metriche**:
pagine, sezioni, tabelle, caratteri, wikilink risolti. Non stampare il
contenuto, non aprire il markdown integrale, non incollarne pezzi nel rapporto.
Se serve un'occhiata al testo per capire un guasto, **fermati e chiedi al
proprietario**: quella verifica la fa lui, in locale.

Lascia nel vault quello che la prova ha prodotto: e' vuoto, e il proprietario deve poter
vedere il risultato con Obsidian.

## Quando hai finito

- Aggiorna **`README.md`** con una sezione sulla fase 4: come funziona la
  catena, la convenzione delle note, e **cio' che hai imparato con la misura che
  lo dimostra** — in particolare come hai risolto il problema delle colonne e
  come riconosci le tabelle. Scrivi in italiano, con lo stile del resto del
  file: la lezione e il numero che la prova, non l'elenco delle funzioni.
- Nel rapporto finale a me elenca: cosa hai costruito, **cosa hai lasciato
  indietro e perche'**, e le decisioni che vuoi far confermare al proprietario.
- Se qualcosa nel piano si rivela sbagliato come il flag `-layout`, **non
  aggirarlo in silenzio**: correggilo e scrivi perche'.

---

# Secondo giro — 15 agosto 2026, dopo la prima consegna

Il primo giro ha consegnato `documenti.py` e `prova_documenti.py`, ma il
collaudo non passava. **Sei difetti corretti a mano dopo la consegna** (sono in
`README.md`, sezione fase 4): `pdftohtml` che appende `.xml` al nome, i titoli
in grassetto persi perche' `t.text` e' `None` quando c'e' un `<b>` figlio, lo
slug che si mangiava l'estensione, la normalizzazione degli apostrofi nel
collaudo, il generatore che dichiarava 25 cifre e ne disegnava 24, e il
verificatore dei wikilink che cercava i nomi una cartella per volta.

Ora `prova_documenti.py` e' **TUTTO VERDE**: prosa in ordine, cifre verbatim,
ancore, note, 9/9 wikilink, rilancio senza duplicati, ripresa dopo interruzione.

## Ma sul PDF vero non regge, ed e' il lavoro di questo giro

`Basic_Statistics_2007.pdf`, 10 pagine, due colonne, misurato:

```
pagine 10/10 · caratteri 38.204     <- l'estrazione regge
sezioni trovate 0                   <- il rilevatore non aggancia niente
tabelle conservate 42               <- su 10 pagine
wikilink 0/6 risolti
```

**Il PDF sintetico e' stato costruito attorno all'implementazione**: e' il
tranello classico del collaudo scritto insieme al codice. Verde sul sintetico
non significa niente finche' non regge un documento vero.

### 1. Le tabelle sono falsi positivi — misurato

Delle 42 tabelle: **densita' media di cifre 2,9%, di lettere 55,9%, e 26 su 42
sono per piu' del 50% lettere**, cioe' paragrafi di prosa.

La causa e' `_e_tabella`, che dichiara tabella una riga con due o piu' spazi
ampi: **su una pagina a due colonne il vuoto fra le colonne e' esattamente
questo**. Il rilevatore sta trovando l'impaginazione, non le tabelle.

Serve distinguere le due cose. Un'idea da provare e misurare, non da adottare
al buio: le colonne di testo hanno **un solo** vuoto ampio, sempre alla stessa
x su tutta la pagina, mentre una tabella ne ha piu' d'uno e le sue colonne sono
corte e ricche di cifre. La densita' di cifre e' gia' un segnale forte (2,9%
contro il ~40% di una tabella vera). **Rimisura le stesse 42 dopo la
correzione**: il numero da battere e' 26 falsi positivi.

Attenzione a non ribaltare l'errore: la regola dice di sbagliare per eccesso,
ma 26 paragrafi di prosa chiusi in un recinto verbatim non sono prudenza, sono
il testo reso illeggibile.

### 2. Zero sezioni su un documento che ne ha

`struttura: font-size` non trova nulla. Sul PDF vero i titoli probabilmente non
sono abbastanza piu' grandi del corpo perche' la soglia `body * 1.25` scatti.
Misura le dimensioni reali con `pdftohtml -xml` prima di toccare la soglia, e
considera che **il grassetto e' un segnale quanto il corpo**: nel PDF sintetico
i titoli erano in Helvetica-Bold, ed e' proprio il `<b>` che aveva nascosto i
titoli al primo giro.

Se un documento davvero non ha struttura riconoscibile va detto — ma qui va
prima verificato che non ce l'abbia.

### 3. Wikilink 0/6 con zero sezioni

Senza sezioni non ci sono note atomiche, ma la nota indice scrive comunque 6
link. Una nota indice che punta a note inesistenti e' peggio che una nota senza
link: decidi cosa scrivere quando le sezioni sono zero, e falla risultare
coerente nel rapporto.

### 4. Il collaudo va reso onesto

- **Il marcatore di stato falsava le prove**: a `stadio: fatto` la pipeline
  ripesca il rapporto salvato e il collaudo valida il risultato di *prima* della
  correzione. Ci ho perso due giri. `prova_documenti.py` deve **partire da
  stato pulito** (stato, markdown, elaborati, note nel vault).
- Aggiungi un secondo PDF sintetico **piu' cattivo**: titoli poco piu' grandi
  del corpo, una tabella vera accanto a prosa a due colonne sulla stessa pagina,
  una pagina senza struttura. Il primo PDF non ha mai messo in difficolta' il
  codice perche' e' nato con lui.
- Fai girare la catena sul PDF vero **dentro il collaudo**, con asserzioni sulle
  sole metriche: pagine 10/10, tabelle sotto una soglia sensata, wikilink tutti
  risolti. Il contenuto resta fuori dal tuo contesto, come sempre.
