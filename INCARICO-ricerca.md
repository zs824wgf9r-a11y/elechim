# Incarico: lo stato dell'arte — cosa possiamo copiare invece di reinventare

Scritto il 17 agosto 2026. Questo incarico **non tocca codice**: produce un solo
file, `RICERCA-stato-arte.md`. Chiesto dal proprietario: *«Non ci sono metodi che
possiamo copiare? Penso che qualcun altro ci sia riuscito a fare una cosa simile.
Se non dobbiamo re-inventare la ruota è meglio.»*

Ha ragione, e la domanda arriva al momento giusto: stiamo per costruire le figure
e il ragionamento sui pensieri. Meglio scoprire adesso che esiste uno strumento
fatto, che dopo.

## Come cercare

Hai un motore di ricerca **in locale** e un fetcher, entrambi gia' in piedi:

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235   (vedi web.py e strumenti.py per l'uso)
```

Usali. `webfetch` va bene per leggere una pagina di cui hai già l'URL.

**La regola piu' importante, e su questa ti giudico**: ogni affermazione deve
avere un **URL che hai davvero aperto**. Se non l'hai aperto, scrivilo. Se non
trovi niente su un punto, **scrivi «non trovato»** — e' un risultato utile e
onesto. Un elenco di repository inventati con capacita' immaginarie e' peggio di
niente, perche' ci fa progettare su una cosa che non esiste. Per ogni strumento
dichiara **la licenza** e se e' vivo (ultimo commit / ultima release).

## Cosa cercare, in ordine di urgenza

Per **ognuno** dei sei punti chiudi con un verdetto secco fra tre:
**COPIARE** (esiste, si usa) · **PRENDERE L'IDEA** (il metodo si', il codice no) ·
**TENERE IL NOSTRO** (e allora scrivi perche').

### 1. Estrarre le figure da un PDF, comprese quelle vettoriali — URGENTE

E' il pezzo che stiamo per costruire, quindi cerca questo per primo e bene.

Noi abbiamo misurato che `pdfimages` vede solo le immagini raster (24 figure vere
su 11 pagine di un libro da 533) mentre **~37 pagine hanno figure vettoriali**, che
per costruzione non sono oggetti immagine. Il nostro piano e' rendere la **pagina
intera** con `pdftocairo`, dichiarando come limite che non ritagliamo il riquadro.

Domande precise:

- Esiste uno strumento che individua il **riquadro** di una figura in una pagina
  PDF, comprese le figure vettoriali, e ci associa la **didascalia**? Cerca in
  particolare **`pdffigures2`** (Allen Institute for AI) e i suoi eredi/derivati,
  e qualunque cosa lo abbia superato. Funziona su libri o solo su paper a due
  colonne? Che licenza, e che cosa serve per farlo girare (Scala/JVM?).
- Come lo fanno **MinerU / PDF-Extract-Kit**, **marker**, **docling**? Fanno
  layout detection con un modello (DocLayout-YOLO e simili) e ritagliano le
  regioni "figure"? Se si', **quel modello si puo' usare da solo** senza portarsi
  dietro tutta la pipeline?
- Come si distingue una figura da una decorazione ripetuta (logo, filetto,
  watermark)? Noi usiamo l'**hash del contenuto**, perche' abbiamo misurato che la
  dimensione inganna: la forma piu' grande del nostro libro (2368x2800, 24
  occorrenze) e' **un hash solo**, cioe' decorazione. Gli strumenti fatti usano
  questo criterio o un altro? C'e' un criterio migliore?

### 2. Apici e pedici: li da' gia' qualcuno bell'e fatti?

Abbiamo speso una sessione a misurare soglie su corpo e spostamento dalla linea di
base (`pdftotext -bbox`) per ricostruire `x^2` e `x_i`. Se una libreria espone
l'informazione direttamente, quella sessione era la ruota.

- **PyMuPDF**: `get_text("dict")` restituisce dei *flag* per ogni span. **C'e' un
  bit per l'apice?** Verificalo nella documentazione vera e riporta il nome
  esatto della costante e la versione. E per il **pedice**? (sospetto che l'apice
  ci sia e il pedice no: se e' cosi', e' un risultato importante, perche' in un
  libro di statistica i pedici sono la meta' del problema.)
- `pdfplumber`, `pdftotext -bbox`, `pdfminer.six`: espongono qualcosa di simile?
- Licenza di PyMuPDF (AGPL?) e se questo la rende inutilizzabile per noi. Noi
  siamo tutto locale e il repo e' pubblico: dillo chiaro.
- Esiste un metodo **documentato** (paper o codice) per dedurre apici/pedici dalle
  coordinate, con soglie pubblicate a cui confrontare le nostre?

### 3. Le pipeline PDF -> markdown, per confronto onesto

Noi abbiamo una corsia veloce con poppler e il piano di aggiungere **marker** e
**docling**. Domanda: quel piano e' ancora giusto nel 2026, o e' stato superato?

Confronta **marker**, **MinerU**, **docling**, **nougat**, **olmOCR**,
**pymupdf4llm**, **unstructured** su tre cose che per noi sono vincoli, non
preferenze:

- le **tabelle** restano verbatim, o passano da un modello? (per noi non devono
  passare da un LLM, mai: e' il punto in cui un 4B cambia un 180 in un 150);
- la **matematica** sopravvive, e in che notazione;
- girano su **una GPU da 8GB** o vogliono di piu'? E quanto costano per pagina?

Cerca anche **benchmark indipendenti** e recenti che li mettano a confronto, non
le tabelle di marketing dei rispettivi README.

### 4. Le tabelle: la nostra euristica e' ingenua?

Noi riconosciamo una tabella con «due o piu' vuoti ampi **e** densita' di cifre
>= 10%» — la densita' l'abbiamo aggiunta dopo aver misurato **26 falsi positivi su
42** su un libro a due colonne, dove il vuoto era lo spazio fra le colonne.

`camelot`, `tabula`, `pdfplumber` (`find_tables`), e i modelli tipo
**TableFormer**/**table-transformer**: come decidono? C'e' un criterio semplice e
pubblicato meglio del nostro? Ci interessa **precisione senza dipendenze nuove**;
un modello che vuole torch e' fuori scala per la corsia veloce, ma dillo comunque.

### 5. Il ragionamento «come una discussione tra colleghi»

E' `INCARICO-pensieri.md`: un pensiero in prosa, cinque chiamate a ruoli distinti
(chi ascolta, chi chiede, chi obietta, chi porta un precedente, la sintesi), e una
sintesi a cui e' **permesso non risolvere**.

Il difetto che ci preoccupa: **un modello solo che recita entrambe le parti e'
d'accordo con se stesso**, e l'obiezione esce come un complimento riformulato.

- Cerca la letteratura vera su questo: **multi-agent debate** (Du et al. e chi lo
  ha criticato), **Self-Refine**, **Reflexion**, **Chain-of-Verification**,
  **Society of Minds**, **devil's advocate prompting**, e la ricerca sulla
  **sycophancy** e sull'**auto-valutazione** dei modelli. Cosa dice l'evidenza:
  il dibattito fra istanze dello stesso modello **aggiunge** qualcosa, o e'
  teatro? Ci sono misure?
- Esistono **mitigazioni pubblicate** per la convergenza fra ruoli — ruoli
  asimmetrici, informazione nascosta a un ruolo, personas, temperature diverse,
  modelli diversi per ruoli diversi? Quali sono **misurate** e quali sono folklore?
- La nostra invariante anti-eco (**se l'obiezione sovrappone troppi n-grammi con
  la riformulazione, e' un'eco e si rifa'**) somiglia a qualcosa di pubblicato?
  Esiste una metrica migliore e altrettanto economica? (self-BLEU? distinct-n?)
- **Attenzione al modello piccolo**: quasi tutta questa letteratura e' su modelli
  grandi. C'e' evidenza su cosa succede con un **8B in locale**? Se il dibattito
  funziona solo sopra una certa scala, e' la cosa piu' importante che puoi
  riportare, perche' cambierebbe il progetto.
- Esiste gia' uno strumento che fa **questo** — prendere una nota e "discuterla"
  producendo obiezioni e domande — per **Obsidian** o dintorni? Se si', com'e'
  strutturato il prompt?

### 6. Spezzare un documento lungo per struttura

Noi usiamo una cascata di confini naturali (titoli -> ancore di pagina ->
paragrafi -> frasi -> parole) con un budget derivato da `num_ctx`, e scendiamo di
livello solo se il pezzo non entra. Cerca: `MarkdownHeaderTextSplitter` di
LangChain, l'`HybridChunker` di docling, il **semantic chunking**, la **late
chunking**. Il nostro approccio ha un nome in letteratura? Ci stiamo perdendo
qualcosa di ovvio?

## Cosa NON fare

- **Non toccare nessun file di codice.** Non `sbobina.py` (c'e' un'altra sessione
  che ci lavora **adesso**), non `documenti.py`, non i collaudi, non i `RAPPORTO-*`,
  non gli altri `INCARICO-*`, non `AGENTS.md`, non `DA-FARE.md`, non git.
  **L'unico file che scrivi e' `RICERCA-stato-arte.md`.**
- **Non installare niente**, nessun `pip install`, nessun clone. Si legge, non si
  prova. Se una cosa va provata, lo scrivi come raccomandazione.
- **Niente contenuto dei documenti del proprietario** nel rapporto: qui non ti
  serve nemmeno, stai leggendo il web.
- **Non inventare URL, nomi di repository, funzioni o costanti.** Se non l'hai
  aperto e letto, dichiaralo come non verificato. Questa e' la regola che decide
  se il tuo lavoro serve o fa danno.

## Come si scrive `RICERCA-stato-arte.md`

Un capitolo per ognuno dei sei punti, e ogni capitolo:

1. **Cosa abbiamo noi oggi** (una riga, dal contesto qui sopra);
2. **Cosa esiste**: strumento o metodo, URL aperto, licenza, se e' vivo, in una
   riga ciascuno;
3. **Il verdetto**: COPIARE / PRENDERE L'IDEA / TENERE IL NOSTRO, con **una frase**
   di motivo;
4. **Il costo del cambio**, se il verdetto e' copiare: dipendenze nuove, GPU, e
   cosa si butta di quello che abbiamo.

In cima, una **sintesi da dieci righe**: le tre cose che conviene copiare subito e
le tre su cui il nostro va bene. Quella sintesi e' l'unica parte che il
proprietario legge di sicuro.

Chiudi con una sezione **«non trovato»**: i punti su cui hai cercato e non c'e'
niente. Vale quanto il resto — ci dice dove **dobbiamo** inventare, e dove
inventare non e' spreco ma necessita'.

Scrivi il file **mentre** lavori, un capitolo alla volta, non alla fine: le
sessioni che si piantano perdono le conclusioni perche' sono l'ultima cosa che
scrivono.
