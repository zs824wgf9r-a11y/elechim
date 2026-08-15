# Da fare — stato, bug e prossime mosse

Scritto il **15 agosto 2026, sera**, dopo il blackout e la riparazione della
coda. Questo file e' la lista operativa: cosa e' rotto, cosa e' stato corretto e
come, cosa aspetta una decisione del proprietario. Lo stato architetturale sta in
`AGENTS.md`, il piano dei documenti in `PIANO-DOCUMENTI.md`.

Convenzione: ✅ fatto e verificato · 🔧 in lavorazione · ⬜ da fare ·
👤 serve una decisione o una prova del proprietario.

---

## DOVE ERAVAMO — notte fra il 15 e il 16 agosto 2026, ore 01:20

**La sbobina di `dsml` NON e' ancora stata lanciata, ed e' voluto.** Lanciarla
adesso vorrebbe dire spendere 4 ore di GPU per riscrivere un testo in cui la
matematica e' gia' rovinata dall'estrazione, e rifare tutto dopo.

**La sequenza decisa, in quest'ordine:**

1. 🔧 `documenti.py` impara a ricostruire apici/pedici e a marcare le formule
   (`INCARICO-formule.md`, opencode in corso alle 01:20 — stava misurando le
   soglie di riconoscimento);
2. ⬜ **rimacinare `dsml`**: `documenti.py documenti/elaborati/DSML.pdf`, costa
   **70 secondi**, e rigenera markdown e note con la matematica a posto;
3. ⬜ `sbobina.py` protegge le formule dal modello **come gia' fa con le
   tabelle** — oggi le formule (16% delle righe) passerebbero tutte da un 8B.
   Va scritto un incarico: tocca `sbobina.py`, quindi non poteva partire mentre
   c'era l'altra sessione;
4. ⬜ **poi** partono le 4 ore: `sbobina.py dsml --tutte`.

**Prima di ripartire, una verifica unica** su tutto il codice messo insieme
stanotte da tre sessioni diverse: `prova_documenti.py` e `prova_sbobina.py`
entrambi verdi, e la **copertura su `dsml` vero** (l'invariante e' provata solo
sul sintetico, dove pero' `sezioni divise: 0` — cioe' il caso facile; su `dsml`
si divide davvero, 7 sezioni in 15 pezzi). Attenzione: `_chunk_fonte` **ha
cambiato firma**, ora torna `(chunks, statistiche)`.

**Fatto stanotte, tutto verificato:** chunking adattivo col budget derivato da
`num_ctx` (17.190 caratteri contro la costante 9.000), cascata dei confini
naturali, **0 sezioni saltate** dove prima se ne perdevano 46 pari a **meta' del
libro**, rapporto di copertura con l'invariante `caratteri_coperti ==
caratteri_fonte` come asserzione permanente, e `fusione.py` con RRF (nove casi
verdi) pronto per `ricorda` della fase 3.

---

## 0. Il blackout: nessun danno

Corrente staccata per un temporale, fisso e Mac riavviati. **Tutto e' risalito da
solo**: tunnel, gateway, searxng, crawl4ai, syncthing, il path unit della coda,
il bot sul Mac via launchd. Zero unit di sistema fallite.

Il rapporto automatico dopo il riavvio dice **0 errori kernel (EDAC/Xid)**,
contro i 6 della sessione precedente. Le due unit utente fallite sono gli
autostart di `nvidia-settings` e PowerMizer: rumore del desktop, non c'entrano
con Elechim.

---

## 1. Bug: la coda documenti si fermava ✅ CORRETTO

**Sintomo.** `elechim-documenti.service` usciva 1 e la coda restava ferma.

**Analisi.** Due difetti distinti che si sommavano.

*Il primo e' una corsa.* Il path unit sorveglia `documenti/in/*.pdf` e il
servizio svuota **proprio quella cartella** spostando i file finiti: la
condizione cambia mentre il lavoro e' in corso e systemd fa ripartire il
servizio sopra quello vivo. Il 15 agosto sono partiti due processi nello stesso
secondo; il secondo ha fatto `glob()` su una lista che il primo stava svuotando
e si e' ritrovato il PDF sparito a meta' elaborazione:

```
RuntimeError: comando fallito: pdfinfo .../documenti/in/prova-due-colonne.pdf
I/O Error: Couldn't open file ... No such file or directory
```

*Il secondo e' nel gestore d'errore.* Il blocco `except` che deve garantire «`in/`
si svuota sempre» faceva `shutil.move` di un file che `processa` aveva **gia'**
portato in `elaborati/`. Quel secondo `FileNotFoundError` partiva da dentro il
gestore, non lo prendeva nessuno, e il servizio moriva: **la coda si fermava
esattamente per il guasto che quel gestore esiste per evitare.**

**Correzione.**

- `_coda_esclusiva()` in `documenti.py`: `flock` non bloccante. Chi arriva
  secondo esce con **codice 0** — non e' un guasto, e uscire 1 farebbe segnare
  `failed` alla coda. Non e' stato riusato `energia.blocco`: quello scrive il
  proprio PID sopra quello di chi c'era, perche' il suo mestiere e' tenere
  sveglio il fisso, non escludere.
- `_scarta()`: controlla che il file esista prima di spostarlo, e scrive accanto
  un `<nome>.ragione.txt` col motivo. Senza, fra un mese in `falliti/` c'e' un
  PDF e nessun modo di sapere perche'.
- `_macina()` rilegge la cartella a ogni giro invece di fidarsi di una `glob()`
  sola: i PDF arrivati mentre macinava un documento da 533 pagine entrano in
  **questo** giro.

**Verifica.** Riprodotta la corsa vera — due istanze a mano piu' il path unit
che scatta: **tre processi, tre exit 0**, `Result=success`, `in/` svuotata,
11/11 pagine, 9/9 wikilink. Due casi permanenti aggiunti a `prova_documenti.py`
(`test_coda_esclusiva`, `test_scarto_file_sparito`).

---

## 2. Bug: la ripresa duplicava le pagine ✅ RISOLTO — non era un bug a se'

**Sintomo.** `markdown/prova-due-colonne.md` contiene **18 marcatori di pagina
per 11 pagine**: le pagine 5-11 scritte due volte.

```
occorrenze per pagina: {1:1, 2:1, 3:1, 4:1, 5:2, 6:2, 7:2, 8:2, 9:2, 10:2, 11:2}
```

**Perche' e' grave.** Su un libro vero interrotto da una sospensione — che e' il
caso **normale**, il fisso dorme da solo dopo tre ore — significa integrale
doppio, sezioni doppie e conteggi gonfiati. Gli altri quattro documenti sono
puliti solo perche' non sono mai stati interrotti a meta'.

**Analisi — e qui la diagnosi iniziale era sbagliata.** Sembrava un difetto di
idempotenza in `genera_markdown`, che riprende da `ultima = max(pagine gia'
presenti)`. **Non lo era.** Era la stessa corsa del punto 1, vista dall'altro
capo: il collaudo scriveva i PDF in `documenti/in/` senza prendere il lock, il
path unit faceva partire il servizio in parallelo, e **due processi scrivevano
lo stesso markdown**. Le pagine 5-11 non erano riscritte da una ripresa
difettosa: erano scritte due volte da due processi diversi.

**Correzione.** Nessuna modifica a `genera_markdown`. Il lock del punto 1 toglie
la causa, e il collaudo ora prende `_coda_esclusiva()` **prima** di creare i PDF
e lo tiene finche' macina. Verificato: occorrenze == pagine su tutti i
documenti, e `test_interruzione` arriva in fondo con la sua asserzione.

**La lezione da tenere**, che vale piu' della correzione: due difetti che si
presentano in posti diversi — un servizio che esce 1 e un markdown con le pagine
doppie — possono avere **una causa sola**. Cercare la seconda causa dove non c'e'
costa piu' del bug.

**La trappola nella verifica, che resta valida.** Il difetto era stato
dichiarato risolto contando i marcatori **distinti** e confrontandoli con le
pagine totali: torna sempre `11 = 11` e **per costruzione non puo' vedere
nulla**. L'asserzione giusta conta le **occorrenze**:

```python
assert md.count("<!-- pag ") == pagine_totali
```

Quell'asserzione **esisteva gia'** in `test_interruzione`, e non proteggeva
perche' il collaudo si fermava prima, sul rosso del punto 3: *un test che non
viene raggiunto non protegge niente.* Adesso il collaudo arriva in fondo.

---

## 3. Bug: le tabelle erano falsi positivi ✅ CORRETTO (opencode)

**Sintomo.** `prova_documenti.py` e' **rosso**, e lo era gia' al commit pubblico:

```
percorso font-size (PDF senza indice)...
AssertionError: tabelle_conservate == 2, atteso 1
```

Su `Basic_Statistics_2007.pdf`: **42 tabelle su 10 pagine**, di cui **26 per piu'
del 50% lettere**, cioe' paragrafi di prosa. Densita' media di cifre 2,9% contro
il ~40% di una tabella vera.

**Analisi.** `_e_tabella` dichiara tabella una riga con due o piu' spazi ampi. Su
una pagina a due colonne quel vuoto e' **lo spazio fra le colonne**: il
rilevatore sta trovando l'impaginazione, non le tabelle.

**Correzione.** `_e_tabella` ora richiede anche una **densita' minima di cifre**
(`SOGLIA_DENSITA_TABELLA = 0.10`) quando trova due o piu' vuoti ampi: la prosa a
due colonne ha un solo vuoto ampio e densita' sotto l'1%, una tabella ne ha piu'
d'uno ed e' ricca di cifre.

**Misura**: su `Basic_Statistics_2007.pdf` i falsi positivi passano da **42 a
13**, e il sintetico continua a trovare la sua tabella vera (`1`, non `0`).

Nota: il rosso del collaudo **non era il rilevatore**. Il rilevamento sul
sintetico era gia' corretto; il `2` veniva dalla pagina duplicata del punto 2.
Il difetto sui documenti veri era invece reale, ed e' quello corretto qui.

---

## 4. Bug: le scansioni fallivano in silenzio ✅ CORRETTO (opencode)

**Il piu' pericoloso del sistema, ed e' pericoloso perche' non fa rumore.** Su
una scansione senza livello di testo la pipeline estrae **3 caratteri contro
3.610**, non dice niente e archivia il vuoto. Te ne accorgi mesi dopo, quando
cerchi quel documento e non c'e'.

**Correzione.** `classifica()` guarda il documento prima di lavorarlo:
`caratteri_pagina()` conta i caratteri non-spazio per pagina, piu' livello di
testo e outline. Sotto `SOGLIA_CARATTERI_PAGINA = 100` di **mediana** il
documento non produce note: va in `falliti/` con la ragione scritta. Il rapporto
di copertura dichiara ora la **corsia** usata e la mediana di caratteri/pagina.

**La soglia e' misurata, non inventata:**

| documento | pagine | mediana caratteri/pagina | esito |
|---|---|---|---|
| sintetico `prova-due-colonne` | 11 | 770 | corsia veloce |
| `DSML.pdf` | 533 | 1.606 | corsia veloce |
| scansione sintetica (`pdftoppm` + Pillow) | 11 | **0** | **rifiutata** |

100 sta molto sotto ai documenti veri e molto sopra a una scansione. Il collaudo
ha un caso permanente: la scansione viene rifiutata, finisce in `falliti/` con
la ragione, e **non lascia note nel vault**.

---

## 5. La trappola della depersonalizzazione ✅ CORRETTO

Pubblicare il repo ha sostituito il nome proprio con "il proprietario" e i path
con `NOME_UTENTE` **anche dentro file che girano**. Due danni veri:

- **`mac/core.py`**: il `SYSTEM_PROMPT` versionato diceva "assistente personale
  del proprietario". Sincronizzare avrebbe peggiorato il prompt **e** cambiato il
  prefisso della cache, cioe' prefill pieno (~340s a 8K token) su ogni
  conversazione viva.
- **`opencode.json`**: `/home/NOME_UTENTE/.config/containers/systemd/*` non
  agganciava piu' nessun permesso reale.

**Correzione.** Il nome si legge da `mac/.env` (`PROPRIETARIO`), il path usa
`{env:HOME}`. Verifica che conta: col valore a posto il prompt torna **byte per
byte** quello di prima — 2090 caratteri, `sha256 87ccb758c121ddf9` — quindi la
sincronizzazione **non ha azzerato la cache**. Bot sincronizzato e risalito,
`DEFINIZIONI` identica su tutte e tre le copie (fisso, `mac/`, Mac vivo).

**La regola che ne esce**: un file eseguibile non si depersonalizza in place. O
il dato si legge da `.env`, o la copia pubblica e' distinta da quella che gira.

---

## 6. La memoria condivisa era vecchia ✅ CORRETTO

`AGENTS.md` diceva «fase 4 ❌, il vault e' vuoto» con **233 note gia' dentro**, e
il README diceva «non legge PDF». E' il ponte da cui parte ogni sessione di
opencode: una fotografia vecchia moltiplica gli errori invece di risparmiare
tempo.

Riscritti la sezione "Stato" di `AGENTS.md` e il README (nuova sezione sui
documenti, con le lezioni e le misure). I cinque incarichi consegnati sono
marcati con data ed esito, cosi' non si confondono con quelli aperti.

---

## 7. Il da fare, in ordine di dipendenza

### Consegnato dal lavoro in parallelo del 15 agosto ✅

| filone | modello | esito |
|---|---|---|
| tabelle + scansioni (punti 3 e 4) | `kimi-k2.7-code` | **completo**, rapporto consegnato, collaudo verde |
| sbobina, stadio due della fase 4 | `glm-5.3` | **codice completo e funzionante**, rapporto mancante |

Entrambe le sessioni si sono poi **piantate su una connessione morta** verso
l'API (vedi la sezione 10): il lavoro sul disco e' buono, ma nessuna delle due
ha potuto scrivere le conclusioni. Il primo aveva gia' fatto in tempo.

### Sbobina — cosa manca per chiuderla ⬜

`sbobina.py` (19,5KB) e `prova_sbobina.py` ci sono e il **collaudo e' verde**,
provato di persona sul PDF sintetico:

```
6 sezioni riscritte su 6 · 0 numeri segnalati · 323s
qwen3:8b (500a1f067a9f) · 13,1-13,5 tok/s · 6.751 MiB di VRAM
```

Fa le cose giuste: due chiamate separate (spiegazione e punti, mai una che
chiede due cose), tabelle isolate e ricopiate **verbatim** con un segnaposto al
loro posto nel testo che va al modello, verifica di ogni numero generato contro
la sorgente, `<think>` ripulito, stato **per sezione**, e il lock GPU di
`gateway.py` — sfratta `qwen3-vl` e whisper, e **li rimette a posto alla fine**
(verificato: VRAM rientrata a 5.337 MiB, la visione risponde).

Restano tre cose, tutte corte:

1. **Il confronto fra modelli.** L'incarico ne chiedeva due o tre misurati; c'e'
   solo `qwen3:8b`. Un secondo candidato era scaricato al 43% quando la sessione
   si e' piantata.
2. **Una nota vera** riscritta su una sezione di `dsml`, **da non leggere**: il
   percorso va nel rapporto, la qualita' la giudica il proprietario. 👤
3. **`RAPPORTO-sbobina.md`**, che non e' stato scritto.

**Non lanciare le 214 sezioni** prima che il proprietario abbia visto una nota:
se il professore non e' all'altezza si cambia modello, e sarebbero un'ora di GPU
e 214 note buttate.

### Subito dopo ⬜

1. **Le figure**: `90-Allegati/` e' vuota. Sul PDF di prova `pdfimages -list` non
   trova niente perche' sono **vettoriali** — vanno rese con `pdftocairo` a
   livello di pagina, non estratte con `pdfimages`. Poi qwen3-vl le descrive.
   Serve un filtro su dimensione e proporzioni, o si finisce a descrivere
   quaranta loghi di intestazione.
3. **`documenti/originali/`**: la decisione delle tre cartelle (originale /
   arricchito nel vault / integrale fuori) non e' applicata, oggi c'e'
   `elaborati/`.

### Poi ⬜

4. **Le foto degli appunti a mano.** `qwen3-vl:4b` e' gia' installato e in
   servizio: probabilmente e' la cosa che il proprietario usera' di piu', e non
   serve niente di nuovo. Va solo verificato che una foto passata a `visione.py`
   produca testo utile. 👤 la prova la fa il proprietario, in locale.
5. **Docling** come seconda corsia (CPU, prende anche DOCX/PPTX/HTML), solo dopo
   che i punti 3 e 4 sono chiusi.
6. **Fase 3, Honcho**: Postgres+pgvector, Redis, `bge-m3`, LLM di ingestion su
   ollama. **Mai il modello del Mac**: sfratterebbe la conversazione dall'unica
   slot di cache. E' il prerequisito di `ricorda`/`salva`, dell'elaborazione
   appunti e del dreaming mode.
7. **`INCARICO-elaborazione-appunti.md`**: dipende dai titoli (fatti) e, per i
   collegamenti semantici veri, dalla fase 3.

### Ultimo atto, quando 3 e 4 sono entrambe pronte ⬜

**Applicare `TOOL-DEFINITIVI.md`**: i quattro tool (`cerca`, `leggi`, `ricorda`,
`salva`) si aggiungono **tutti insieme, una volta sola**, perche' toccare
`DEFINIZIONI` invalida la cache di ogni conversazione. La procedura e' scritta
li'. La prima conversazione dopo va fatta con `/nuova`.

---

## 8. Cosa aspetta il proprietario 👤

1. **Guardare una nota sbobinata.** Nel vault ci sono 223 note da `DSML.pdf`, e
   oggi sono segnalibri con un estratto troncato a meta' parola. `sbobina.py`
   adesso sa riscriverle. La domanda vera non e' se la macchina gira — gira, 13
   tok/s, tabelle verbatim, numeri verificati — ma **se il professore e'
   all'altezza**, e quello lo dice solo lui leggendo. Serve prima il punto 2
   della sezione sbobina qui sopra.
2. **Provare una foto di appunti a mano** su `visione.py` (punto 4 sopra).
3. **Decidere se la 1050 va tolta** al prossimo spegnimento: non serve a niente
   e non fa danni, ma il giorno che si toglie **l'interfaccia di rete si
   rinumera di nuovo**. La connessione col Mac e' gia' legata al MAC e non al
   nome, quindi dovrebbe reggere — ma va guardato quel giorno, non dato per
   scontato.

---

## 8-bis. La sospensione deve essere intelligente 👤 DA PROGETTARE

Posto dal proprietario la notte del 16 agosto 2026, da discutere con calma:

> «Il sistema per poter funzionare deve essere intelligente: quando l'ecosistema
> lavora non va in sospensione. Quando il fisso e' in idle puo' andare in
> sospensione dopo tre ore.»

Oggi la sospensione guarda **l'inerzia della scrivania** (XScreenSaver) e
l'ultimo uso di Elechim. Non guarda il lavoro in corso: i lavori lunghi lanciati
a mano (una sessione opencode, uno script) **non prendono `energia.blocco`**, e
il fisso puo' addormentarsi sotto un lavoro vivo. Finora e' andata bene solo
perche' c'era qualcuno alla scrivania.

`documenti.py` e `sbobina.py` il blocco lo prendono. Manca il caso generale:
**qualunque cosa stia lavorando davvero tiene sveglia la macchina**, e l'idle
vero — nessun lavoro, nessuno alla scrivania — porta a dormire dopo tre ore.
Da definire: cosa conta come "l'ecosistema lavora" (GPU occupata? un blocco?
una sessione ssh? un container che macina?) e come accorgersene senza fare del
polling costoso.

---

## 9. Difetti latenti, da tenere d'occhio

- **I lavori lunghi lanciati a mano non prendono `energia.blocco`.** Oggi il
  fisso e' rimasto sveglio solo perche' rilevava qualcuno alla scrivania: un
  lavoro lungo mentre non c'e' nessuno si troverebbe la macchina addormentata
  sotto. Ripartirebbe al risveglio — e' ripartibile — ma resterebbe fermo in
  silenzio.
- **`opencode run` esce 0 anche quando non ha fatto niente**, se l'endpoint del
  modello e' giu' (`deepseek-v4-flash-free`, il default, oggi era down). Il
  codice di uscita non basta: si guarda se i file attesi esistono davvero.
- **`opencode run` non ha timeout sulla risposta del modello.** Vedi sezione 10.
- **Le fixture sintetiche versionate** (`documenti/elaborati/prova-*.pdf`)
  vengono rigenerate dal collaudo e risultano modificate in git. Vanno
  ricontrollate prima di un commit.

---

## 10. Lo stallo di opencode — 15 agosto sera, da sapere prima di rilanciarlo

Le due sessioni lanciate in parallelo si sono **piantate**, e vanno riconosciute
perche' non somigliano a un guasto:

```
STAT  WCHAN     ELAPSED   %CPU
Sl    ep_poll   07:06:13  0.5     <- vivo, ma fermo da 6h43m
ESTAB 0 0  192.168.1.68:33348  172.65.90.20:443  users:(("opencode",pid=...))
```

Il processo e' **vivo**, la connessione TCP verso l'API e' **stabilita**, le code
di invio e ricezione sono a **zero**, e la CPU e' allo 0,5%. Cioe': opencode sta
aspettando su `epoll` una risposta che il server non manda piu', e **non ha un
timeout**. Restava li' indefinitamente.

Non c'entra la sospensione: il fisso non ha mai dormito (nessun `PM: suspend`
nel journal), e comunque le sessioni erano partite alle 17:19.

**Come accorgersene**: non guardare il processo, guarda **l'orologio del log**.
`ls -la` sul file di log contro l'ora attuale dice in un colpo se sta ancora
lavorando. Sei ore di silenzio non sono un lavoro lungo, sono uno stallo.

**Da fare la prossima volta**: dare a `opencode run` un `timeout` esterno
generoso ma finito (es. `timeout 3600`), cosi' un endpoint che smette di
rispondere costa un'ora e non una notte. E ricontrollare comunque i file
prodotti, mai il solo codice di uscita.

**Nota sul lavoro perso**: poco. Le modifiche al codice erano gia' sul disco e
sono buone — il collaudo di entrambi passa. Si e' perso il rapporto di sbobina e
il confronto fra modelli, cioe' le **conclusioni**, che sono l'ultima cosa che
una sessione scrive. Vale la regola gia' in `INCARICO-qualsiasi-documento.md`:
*le sessioni che hanno consegnato sono quelle che hanno scritto per prime.*
