# RICERCA-stato-arte — cosa possiamo copiare invece di reinventare

Incarico `INCARICO-ricerca.md`, eseguito il 17 agosto 2026. Ricerca sul web
(SearXNG locale `127.0.0.1:8888`, letture con crawl4ai `127.0.0.1:11235` e
`webfetch`). Regola rispettata: ogni affermazione ha un URL aperto; dove non ho
trovato niente scrivo «non trovato»; nessun nome di repository o costante
inventato.

## Sintesi per il proprietario

**Tre cose da copiare subito:**
1. **L'idea di pdffigures2 e dei modelli di layout (DocLayout-YOLO, HERON/EGRET
   di docling)**: le figure vettoriali si individuano o parsiando gli operatori
   grafici del PDF (pdffigures2) o classificando la pagina renderizzata con un
   modello di layout (tutto il resto). Il modello di layout si usa **da solo**
   (`pip install doclayout-yolo`), senza portarsi dietro MinerU. E' la risposta
   ai nostri ~37 riquadri vettoriali.
2. **L'hash del contenuto per le decorazioni**: non è una scoperta nostra. Il
   mantainer di docling lo raccomanda esplicitamente come best practice per le
   immagini ripetute (header/footer), e i modelli di layout hanno classi
   dedicate alle decorazioni (docling: `PAGE_HEADER`/`PAGE_FOOTER`,
   content layer `furniture`/`background`, classificatore `LOGO`/`ICON`).
3. **La conferma sul pedice**: PyMuPDF espone **solo l'apice**
   (`TEXT_FONT_SUPERSCRIPT = 1`) e il mantainer dichiara "non c'è modo di
   rilevare i pedici". La nostra sessione di misure **non era la ruota**.
4. **Il merge dei pezzi corti di docling** (cap. 6): l'unico pezzo di chunking
   che non facciamo — unire i pezzi sottodimensionati successivi che
   condividono lo stesso titolo.
5. **Temperature diverse fra i ruoli** (cap. 5): LMAD misura 0.1 / 0.5 / 0.9
   fra istanze dello stesso modello, e il dibattito funziona anche su
   Qwen3-8B — ma solo **localizzato** al primo disaccordo; forzare prospettive
   opposte esplicite (dMAD) crolla sui modelli piccoli.

**Tre cose su cui il nostro va bene:**
1. **Apici e pedici con soglie geometriche**: nessuna libreria dà il pedice
   pronto; tutti dicono di dedurlo da `size` + baseline (jsvine per pdfplumber
   lo dice testualmente). Il nostro criterio resta il migliore per noi, ed evita
   AGPL.
2. **Le tabelle verbatim**: marker e docling sono gli unici che non fanno
   passare le tabelle da un LLM; il nostro vincolo "mai attraverso un modello"
   è condiviso ma va difeso: MinerU ha pipeline OCR, nougat genera la tabella
   tutta col modello.
3. **La corsia veloce poppler**: nessuna pipeline del 2026 è più veloce della
   nostra per i born-digital, e le pipeline a modello (marker, docling,
   MinerU) sono la seconda corsia, non un sostituto.
4. **La discussione a cinque ruoli** (cap. 5): non esiste un plugin Obsidian
   che faccia questo, e il disegno (input isolati, obiettore che non vede la
   riformulazione, sintesi che può non risolvere) incarna già le mitigazioni
   che la letteratura misura. Da aggiungere solo temperature diverse e il nome
   della metrica anti-eco (self-BLEU).
5. **La cascata di chunking per struttura** (cap. 6): è il chunking
   gerarchico/structure-aware, che uno studio del 2026 misura superiore al
   fixed-size. Il budget da `num_ctx` che decide quando scendere di livello è
   nostro (soglia «non trovata» pubblicata).
---

## 1. Estrarre le figure da un PDF, comprese quelle vettoriali — URGENTE

**Cosa abbiamo noi oggi.** `pdfimages` vede solo le immagini raster (24 figure
vere su 533 pagine); ~37 pagine hanno figure vettoriali che non sono oggetti
immagine. Piano attuale: rendere la **pagina intera** con `pdftocairo`,
dichiarando il limite di non ritagliare il riquadro.

**Cosa esiste.**

- **pdffigures2** (Allen Institute for AI) — https://github.com/allenai/pdffigures2
  (aperto) e paper https://dl.acm.org/doi/10.1145/2910896.2910904
  (PDF del paper scaricato: `PDFFigures 2.0: Mining Figures from Research
  Papers`, Clark & Divvala, JCDL 2016). **Apache-2.0**. Ultimo commit
  **2023-11-27** (dormiente ma stabile: 74 commit, 754 stelle). **Scala/sbt**:
  si compila con `sbt assembly`, serve la JVM; servono dipendenze extra per
  JPEG2000/jbig2 (ragioni di licenza). Cosa fa: individua la **didascalia**, poi
  il **riquadro** della figura come regione adiacente alla didascalia che non
  contiene testo-corpo; associa figura a didascalia; restituisce bbox della
  figura, della didascalia, il testo interno e il numero ("Figure 1"). Le
  regioni grafiche si trovano **parsiando gli operatori del PDF** (PDFBox 2.0),
  quindi **vede anche le figure vettoriali**. Salva come raster (png/jpeg) e,
  *sperimentalmente*, come vettoriale (svg/ps/eps) se c'è `pdftocairo`.
  **Vincolo duro**: estrae solo figure **con didascalia** (uncaptioned = niente),
  ed è calibrato su **paper scientifici CS** (dataset CS-150 e CS-Large: 346
  paper da 200+ venue, nessun libro monocolonna). Precision 0.98/recall 0.96 su
  CS-150, F1 0.925 su CS-Large. Su un libro di statistica la copertura delle
  didascalie e la geometria monocolonna sono territorio non testato.
  Un fork GUI: https://github.com/ebupi/pdffigures2-gui (non letto in dettaglio).
- **DeepFigures** (AllenAI, 2018) — paper arXiv https://arxiv.org/abs/1804.02445
  (aperto). Rete neurale addestrata con **supervisione debole** dai caption di
  arXiv/PubMed, dataset da 5,5 milioni di label. Approccio: detect sulla pagina
  rasterizzata. Vecchio, pensato per paper, non ha didascalia->figura come
  pdffigures2.
- **DocLayout-YOLO** (opendatalab) — https://github.com/opendatalab/DocLayout-YOLO
  (aperto). **AGPL-3.0**. Ultimo commit **2025-04-14** (vivo ma lento).
  Modello di layout detection **usabile da solo**: `pip install doclayout-yolo`,
  oppure da HuggingFace `YOLOv10.from_pretrained("juliozhao/DocLayout-YOLO-DocStructBench")`.
  Rileva classi di layout (testo, titolo, **figura**, tabella, formula, ...) sul
  **bitmap della pagina** — quindi le figure vettoriali ci sono come pixel.
  Allenato su DocSynth300K + DocLayNet + D4LA. **Questa è la risposta a "quel
  modello si può usare da solo?": sì, il pacchetto è standalone.**
- **PDF-Extract-Kit** (opendatalab) — https://github.com/opendatalab/PDF-Extract-Kit
  (aperto). **AGPL-3.0**. Ultimo commit **2025-01-03** (superato da MinerU).
  Modulare: layout detection (DocLayout-YOLO), OCR, formule. Il layout detection
  si può prendere da solo.
- **MinerU** (opendatalab) — https://github.com/opendatalab/MinerU (aperto).
  **Apache-2.0 con clausole extra** (LICENSE.md aperto: uso commerciale libero
  sotto 100M MAU o 20M$/mese di fatturato; obbligo di attribuzione se offri
  servizi online a terzi). **Vivo**: release 3.4 del 2026-06-18, 77,8k stelle.
  Pipeline `pipeline` (CPU/GPU, niente LLM per le tabelle) + `vlm-engine`.
  Layout detection e ritaglio regioni "figura".
- **marker** (datalab) — https://github.com/datalab-to/marker (aperto).
  **Apache-2.0**. **Vivo**: ultimo commit 2026-08-07. Converte PDF->markdown,
  "Extracts and saves images"; layout con i modelli Surya; LLM opzionale per
  la precisione. 76.0% su olmocr-bench (terza parte, 1403 PDF).
  Surya: https://github.com/datalab-to/surya (layout/OCR/reading order).
- **docling** (IBM) — https://github.com/docling-project/docling (aperto),
  architettura layout https://deepwiki.com/docling-project/docling/4.2-layout-and-table-structure-models
  (aperto). **MIT**. **Vivo**: ultimo commit 2026-08-17. Layout detection con
  modelli **HERON** (RT-DETR) e **EGRET**; struttura tabella con TableFormer e
  Granite Vision; gira su CPU/CUDA/MPS/XPU. Label delle figure: `PICTURE`.
  Ha anche un **classificatore di immagini** che distingue `LOGO`, `ICON`,
  `QR_CODE`, `STAMP`, `SIGNATURE`, `BAR_CODE` dalle figure vere
  (https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/types/doc/labels.py,
  aperto).

**Figura vs decorazione ripetuta (logo, filetto, filigrana).**

- **pdffigures2 non usa hash**: è guidato dalle didascalie; header e numeri di
  pagina li elimina con un criterio di coerenza (frase identica in testa a ogni
  pagina), le decorazioni senza didascalia semplicemente non sono candidate.
- **docling** classifica le decorazioni per classe: label `PAGE_HEADER`/
  `PAGE_FOOTER` e content layer `FURNITURE` (header/footer/numeri pagina) e
  `BACKGROUND` (filigrane, immagini di sfondo), esclusi di default dall'export
  markdown — risposta del mantainer dolfim-ibm in
  https://github.com/docling-project/docling/issues/2037 (aperto).
- **Il mantainer di docling raccomanda l'hash del contenuto** per le immagini
  ripetute: "use the `PictureItem._image_to_hexhash` method to identify and
  remove repeated images across pages by their hash value" (stessa issue, risposta
  di dosubot + conferma del membro del team). Il nostro criterio è **già la best
  practice consigliata**, con in più la misura che la dimensione inganna.
- Nessuno strumento ha un criterio "repetition by hash" come feature
  documentata a parte questo; su questo punto la letteratura è muta
  (cercato: «detect repeated logo watermark decoration in PDF figure
  extraction» — solo tool generici di rimozione filigrane).

**Verdetto: PRENDERE L'IDEA.**
Le figure vettoriali si riquadrano in due modi: (a) parsiando gli operatori del
PDF (pdffigures2, ma Scala, dormiente, paper-only) oppure (b) un modello di
layout sulla pagina renderizzata (DocLayout-YOLO, HERON/EGRET di docling) che
si usa da solo e dà bbox+classe. Il nostro piano `pdftocairo` resta giusto per
**rendere**; il modello di layout è il candidato per **ritagliare il riquadro**
sulle ~37 pagine vettoriali. L'hash del contenuto per le decorazioni lo
teniamo: è la raccomandazione ufficiale di docling.

**Costo del cambio (se si copia l'idea del modello di layout).**
- Dipendenza: `doclayout-yolo` o docling → **torch + AGPL-3.0** (DocLayout-YOLO)
  o MIT (docling, ma porta dietro l'intera pipeline). AGPL-3.0 in un repo
  pubblico è un vincolo vero: contaminerebbe la licenza del repo o richiederebbe
  licenza commerciale. Docling (MIT) la evita.
- GPU: YOLOv10 inferisce su CPU ma lento; la corsia veloce (poppler, 35 ms/pagina
  per le formule) non può dipendere da questo. Va messo come **seconda corsia**,
  esattamente come marker, non nella corsia veloce.
- Cosa si butta: niente; il piano `pdftocairo` pagina intera resta il fallback
  e l'hash resta il filtro decorazioni.

---

## 2. Apici e pedici: li dà già qualcuno bell'e fatti?

**Cosa abbiamo noi oggi.** Soglie misurate su corpo e spostamento dalla linea di
base con `pdftotext -bbox` (corpo ≤ 0.80·h_base, |spostamento centro| ≥ 0.16·h_base,
gap e delta yMax calibrati su DSML) per ricostruire `x^2` e `x_i`.

**Cosa esiste.**

- **PyMuPDF** — documentazione dei flag:
  https://pymupdf.readthedocs.io/en/latest/vars.html#font-properties (aperto).
  I flag di span in `get_text("dict")` sono un bitfield e i bit sono:
  **`TEXT_FONT_SUPERSCRIPT = 1`** (apice), `TEXT_FONT_ITALIC = 2`,
  `TEXT_FONT_SERIFED = 4`, `TEXT_FONT_MONOSPACED = 8`, `TEXT_FONT_BOLD = 16`.
  **Non esiste alcun `TEXT_FONT_SUBSCRIPT`**: il pedice non ha un bit.
  La doc avverte: "the following bits are derived from what a font has to say...
  It may not be (and quite often is not) correct" e per l'apice specifica "This
  property is **computed by MuPDF** and not part of any font information" — cioè
  è dedotto, non letto dal PDF.
- **Conferma ufficiale del mantainer**: discussione
  https://github.com/pymupdf/PyMuPDF/discussions/3286 (aperto), JorjMcKie:
  "You can detect **(many, not all)** superscripts by checking the `span["flags"]`
  in `page.get_text("dict", ...)`, same with rawdict. **There is no way to
  detect subscripts.**" — esattamente il nostro sospetto: apice sì, pedice no.
- **PyMuPDF versione**: il link «latest» si riferisce alla release corrente
  (repo https://github.com/pymupdf/PyMuPDF, ultimo push 2026-08-13). La
  costante esiste da quando il flag field è documentato; per la versione esatta
  della introduzione non ho trovato il changelog specifico (non verificato).
- **Licenza PyMuPDF: AGPL-3.0** (verificata via API GitHub
  https://api.github.com/repos/pymupdf/PyMuPDF). Per noi: il repo è **pubblico**
  e tutto locale. AGPL impone che il lavoro combinato sia distribuito in AGPL:
  adottare PyMuPDF nel codice del repo pubblico **costringerebbe a passare il
  repo a AGPL-3.0** oppure a comprare la licenza commerciale di PyMuPDF. E
  non risolve il pedice. Da soli, sono due buoni motivi per non prenderlo.
- **pdfplumber** — discussione https://github.com/jsvine/pdfplumber/discussions/730
  (aperto), mantainer jsvine: "Subscript and superscript do not have their own
  concepts in PDFs; rather, they're just text that use smaller font sizes and
  positioning. I recommend examining the `size` and `bottom`/`top` attributes
  of the objects in `Page.chars`." Cioè: **niente flag**, geometria, come noi.
  Un utente nella stessa discussione riporta risultati incoerenti col metodo
  geometrico (a volte apici e pedici scambiati). **MIT**.
- **pdfminer.six** — issue https://github.com/pdfminer/pdfminer.six/issues/376
  (aperto): nessun supporto nativo; chi lo ha implementato lo ha fatto da sé
  sulla posizione del cursore. Le coordinate ci sono (LTChar), il flag no.
  **MIT**.
- **pypdf** — estrazione testo pura, nessun flag di script (documentazione
  https://pypi.org/project/pypdf/, aperta; repo https://github.com/py-pdf/pypdf).
  **BSD-3-Clause** (file LICENSE aperto, testo "Redistribution and use in
  source and binary forms").
- **`pdftotext -bbox`**: niente flag, solo geometria (è ciò che usiamo).
- **Metodo pubblicato con soglie**: esiste il paper "Identifying Subscripts and
  Superscripts in Mathematical Documents" (Baker, Sexton, Sorge; Mathematics in
  Computer Science, 2008/2009) — pagina Springer
  https://link.springer.com/article/10.1007/s11786-008-0051-9 (aperta).
  **Il testo integrale non sono riuscito ad aprirlo** (Springer lo serve dietro
  captcha, Semantic Scholar API rate-limited): so che esiste e che lavora su
  caratteristiche geometriche, ma **le soglie pubblicate non le ho viste**.
  Niente di più preciso su questo punto.

**Verdetto: TENERE IL NOSTRO.**
PyMuPDF dà l'apice ma **non il pedice** (la metà del problema in un libro di
statistica), il bit è "computed by MuPDF, spesso sbagliato", la libreria è
AGPL in un repo pubblico. pdfplumber/pdfminer confermano che la via è la
geometria, cioè esattamente la sessione di misure che avevamo fatto. La ruota
**non** esisteva già: le nostre soglie restano, e possono solo essere
confrontate col bit apice di PyMuPDF su un PDF sintetico come cross-check
senza adottare la libreria.

**Costo del cambio**: nessuno (non si copia).

---

## 3. Le pipeline PDF -> markdown, per confronto onesto

**Cosa abbiamo noi oggi.** Corsia veloce con poppler (533 pagine in 70s,
deterministico, zero LLM) e piano di aggiungere **marker** e **docling** come
secondo motore.

**Cosa esiste, nel 2026.** Le pipeline vive sono marker, MinerU, docling,
olmOCR; nougat è fermo; pymupdf4llm è veloce ma AGPL; unstructured è un toolkit
RAG, non un estrattore di verità. Per ogni riga: licenza, vitalità, **tabelle**,
**matematica**, GPU.

| Pipeline | Licenza | Vivo | Tabelle | Matematica | GPU |
|---|---|---|---|---|---|
| **marker** (datalab) | Apache-2.0 (codice), Open Rail-M modificata (weights) | sì, 2026-08-07 | dal **text layer del PDF** di default (fallback VLM); `--use_llm` opzionale | inline→LaTeX in balanced | GPU/CPU/MPS; PyTorch; su NVIDIA il surya VLM gira in vllm (docker). VRAM 8GB: non verificato |
| **MinerU** (opendatalab) | Apache-2.0 + clausole | sì, 3.4 del 2026-06-18 | →HTML via riconoscimento struttura (no LLM) | →LaTeX via formula model | **min VRAM 4GB** (pipeline), CPU sì, GPU Volta+ |
| **docling** (IBM) | **MIT** | sì, 2026-08-17 | TableFormer / Granite Vision (struttura, **non generativo**) | →LaTeX (formula recognition) | CPU/CUDA/MPS/XPU; layout 44ms/pagina su L4 GPU, 633ms su x86 CPU (technical report) |
| **nougat** (Meta) | MIT | **no**, ultimo commit 2025-02-21 | **generate dal modello** (end-to-end) | markdown/LaTeX, generata dal modello | serve GPU (verif. parziale: non ho la misura su 8GB) |
| **olmOCR** (AllenAI) | Apache-2.0 | sì, 2026-03-25 | VLM, **genera** il contenuto | VLM, genera | GPU (Qwen2-VL); 8GB non verificato |
| **pymupdf4llm** | **AGPL-3.0** | sì, 2026-08-14 | dalla struttura MuPDF (no modello) | niente LaTeX: la math esce come testo | **no GPU** |
| **unstructured** | Apache-2.0 | sì, 2026-08-16 | hi_res: OCR/detection opzionali | niente LaTeX | opzionale |

Vincoli per noi: le **tabelle non devono passare da un LLM**. In quest'ordine di
sicurezza: marker (text layer di default) ≈ docling (TableFormer, non
generativo) > MinerU (riconoscimento struttura, non LLM) > nougat/olmOCR
(**le generano col modello**: per noi sono fuori scala) > pymupdf4llm
(nessun modello, ma AGPL e niente LaTeX).

**Benchmark indipendenti.**

- **olmocr-bench** (AllenAI) — https://github.com/allenai/olmocr/tree/main/olmocr/bench
  (aperto). Metodologia solida: 1403 PDF a pagina singola, test a "fatti"
  machine-checkable (frase presente/assente, relazioni tra celle di tabella,
  match LaTeX su arXiv math). Categorie: ArXiv math, Old scans math, Tables,
  Old scans, Headers&footers, Multicolumn, Long tiny text. Risultati riprodotti
  **in-house** da AllenAI: **marker 1.10.1 76.1**, MinerU 2.5.4 75.2,
  olmOCR v0.4.0 82.4, DeepSeek-OCR 75.7, PaddleOCR-VL 80.0, Mistral OCR 72.0.
  **Docling non compare nella tabella riprodotta** (marker dichiara di
  batterlo, ma quella voce non l'ho verificata).
- **OmniDocBench** — citato da MinerU (README aperto): pipeline 86.47,
  vlm-engine 95.39 (versione 1.6). Benchmark citato, non letto per intero.

**Verdetto: PRENDERE L'IDEA.**
Il piano del 2026 è ancora quello giusto, e non è stato superato: le pipeline
a modello (marker, docling, MinerU) sono vive e mature; **docling è il
candidato preferito per la seconda corsia** (MIT, tabelle con TableFormer non
generativo, formule→LaTeX, gira su CPU); marker come alternativa Apache-2.0
ma con weights sotto Open Rail-M modificata. olmOCR è la nuova direzione ma
genera il contenuto (viola il vincolo tabelle) e chiede più GPU. Nougat è
morto e comunque vietato dal vincolo tabelle.

**Costo del cambio.** docling: `pip install docling` (porta onnxruntime e i
modelli HERON/EGRET + TableFormer da HF); niente GPU obbligatoria; si butta
niente — la corsia veloce poppler resta davanti (è più veloce e deterministica).
Attenzione AGPL: marker e pymupdf4llm (AGPL) in un repo pubblico contaminano
la licenza come PyMuPDF (vedi capitolo 2); docling MIT e MinerU Apache-2.0+
no.

## 4. Le tabelle: la nostra euristica è ingenua?

**Cosa abbiamo noi oggi.** «Due o più vuoti ampi **e** densità di cifre ≥ 10%»;
la densità è stata aggiunta dopo aver misurato 26 falsi positivi su 42 su un
libro a due colonne, dove il vuoto era lo spazio fra le colonne.

**Cosa esiste.**

- **pdfplumber `find_tables`** — https://github.com/jsvine/pdfplumber (aperto),
  dettagli algoritmo https://deepwiki.com/jsvine/pdfplumber/3.3-table-extraction
  (aperto). **MIT**, vivo (push 2026-08-06). L'algoritmo è ispirato alla tesi di
  **Anssi Nurminen** (Aalto University, 2013) e a Tabula: edge detection
  (linee/rettangoli, o allineamento testo con la strategia `text`), trova le
  intersezioni, costruisce celle, raggruppa. **Nessun criterio di densità di
  cifre** e nessun concetto di "due colonne di testo vicine": in un libro a due
  colonne la strategia a linee non vede nulla, quella ad allineamento confonde
  la colonna con una tabella. Non è un criterio "migliore del nostro", è un
  approccio diverso e più fragile sul nostro caso.
- **camelot** — https://github.com/camelot-dev/camelot (aperto). **MIT**, vivo
  (ultimo commit 2026-08-06). Cinque parser: `lattice` (tabelle con righe),
  `stream` (**spazi bianchi**: spezza in colonne sui gap), `network`/`hybrid`
  (allineamento del testo), e `ml` (**Table Transformer**, opzionale,
  `pip install "camelot-py[ml]"`). Anche qui: il criterio `stream` è il
  "gap di spazio" puro, cioè **esattamente il criterio che ci ha prodotto i 26
  falsi positivi**; l'aggiunta della densità di cifre è la parte che ci
  differenzia e che non ho trovato pubblicata.
- **tabula** (tabula-java / tabula-py) — https://github.com/chezou/tabula-py
  (aperto). Port Java dell'originale, stesso approccio linee/whitespace; serve
  la JVM. Per il nostro caso vale lo stesso discorso di pdfplumber.
- **Table Transformer (TATR)** — https://github.com/microsoft/table-transformer
  (aperto), modelli su https://huggingface.co/microsoft/table-transformer-detection
  (aperto). **MIT**, ultimo commit **2024-06-24** (fermo). Rete DETR che
  rileva (a) le tabelle e (b) la loro struttura sul bitmap della pagina.
  **Serve torch**, è il backend `ml` di camelot. Fuori scala per la corsia
  veloce, come ci aspettavamo.
- **TableFormer** — https://arxiv.org/abs/2203.01017 (aperto). IBM, struttura
  delle tabelle con transformer; dentro docling. MIT (docling). Torch/onnx.
- **Un benchmark pubblicato** che confronti i criteri classici con la densità
  di cifre: **non trovato**.

**Verdetto: TENERE IL NOSTRO.**
I criteri classici (Nurminen/Tabula: linee; camelot `stream`: spazi bianchi)
sono **più ingenui del nostro sul caso due-colonne**: il nostro fallimento
originario (26/42) era il comportamento *documentato* di questi approcci, non
un difetto nostro. La densità di cifre come discriminante non è pubblicata
(cercato, non trovato) — è la nostra misura, e funziona. L'alternativa vera
non è un'euristica migliore ma i modelli (TATR, TableFormer), che però
vogliono torch: da tenere per la seconda corsia, non per la veloce.

**Costo del cambio**: nessuno (non si copia). Se un domani accettiamo torch,
TableFormer (via docling) o TATR (via camelot `ml`) sono i candidati da
provare sul libro a due colonne.


## 5. Il ragionamento «come una discussione tra colleghi»

**Cosa abbiamo noi oggi** (`INCARICO-pensieri.md`): cinque chiamate separate a
ruoli distinti (ascolto/tesi, domande, obiezione, precedente, sintesi), ognuna
con un input esplicito e **nessuna cronologia condivisa**; chi obietta non vede
la riformulazione; la sintesi **può non risolvere**; invariante anti-eco con
soglia misurata su n-grammi. Tutto su `qwen3:8b` in locale.

**La domanda, e la risposta secca.** «Il dibattito fra istanze dello stesso
modello aggiunge qualcosa, o è teatro?» La letteratura è concorde su un punto:
**il dibattito così com'è nato — istanze dello stesso modello che si scambiano
interi ragionamenti e votano — è in gran parte teatro.** Ma il *meccanismo* non
è teatro: i guadagni misurati vengono da quattro scelte di progetto precise, e
il nostro disegno ne incarna già tre. Dettagli sotto.

**Cosa dice l'evidenza, in ordine.**

- **L'origine** — Du et al., *Improving Factuality and Reasoning in Language
  Models through Multiagent Debate* — https://arxiv.org/abs/2305.14325
  (aperto). Più istanze dello stesso modello propongono e dibattono per più
  round; migliora ragionamento matematico/strategico e validità fattuale. E' il
  paper di partenza, non la misura finale.
- **La replica critica** — *Stop Overvaluing Multi-Agent Debate — We Must
  Rethink Evaluation and Embrace Model Heterogeneity* —
  https://arxiv.org/abs/2502.08788 (aperto). Valutazione sistematica di 5
  metodi MAD su 9 benchmark con 4 modelli: **MAD spesso non supera i baseline
  a singolo agente** (CoT e Self-Consistency) pur consumando molto più
  calcolo di inferenza. La **eterogeneità dei modelli** risulta l'"antidoto
  universale" che migliora i risultati in modo consistente.
- **Il limite formale** — *Breaking the Martingale Curse: Multi-Agent Debate
  via Asymmetric Cognitive Potential Energy* —
  https://arxiv.org/abs/2603.06801 (aperto). La MAD standard **non può
  migliorare la correttezza oltre il voto di maggioranza** ("Martingale
  Curse"): gli errori correlati fanno convergere verso un consenso sbagliato.
  La soluzione proposta (AceMAD) è asimmetria fra i ruoli.
- **Sull'auto-correzione senza feedback esterno** — *Large Language Models
  Cannot Self-Correct Reasoning Yet* — https://arxiv.org/abs/2310.01798
  (aperto). L'auto-correzione *intrinseca* (il modello che si corregge coi soli
  suoi pesi, senza feedback esterno) **non migliora il ragionamento**. Il
  miglioramento di Self-Refine e Reflexion viene quasi tutto dal feedback
  *esterno* o dal rigenerare, non dalla critica a sé stessi.
- **Self-Refine** — https://arxiv.org/abs/2303.17651 (aperto). Un solo LLM
  genera, critica e raffina; guadagni su 7 task con GPT-3.5/4. Ma la critica
  interna da sola aggiunge poco (vedi il punto sopra).
- **Reflexion** — https://arxiv.org/abs/2303.11366 (aperto). Apprende dal
  feedback *linguistico* esterno (ambiente, test) e lo tiene in memoria
  episodica. Funziona perché il segnale di errore è esterno all'agente.
- **Chain-of-Verification** — https://arxiv.org/abs/2309.11495 (aperto). Il
  modello pianifica domande di verifica sulla sua bozza, **le risponde
  indipendentemente** (per non essere condizionato dalle altre risposte) e poi
  rivede. Riduce le allucinazioni. Il punto è l'**indipendenza delle risposte**:
  è la stessa ragione per cui nel nostro disegno ogni ruolo riceve solo ciò che
  gli serve e chi obietta non vede la riformulazione.
- **Devil's Advocate** — https://arxiv.org/abs/2405.16334 (aperto). Google,
  riflessione anticipatoria: scomporre il task, prevedere i fallimenti prima
  dell'azione, rivedere dopo. E' "giocare contro" ma su un agente singolo.

**Sulla sycophancy e l'auto-valutazione.**

- **Sycophancy** — *Towards Understanding Sycophancy in Language Models* —
  https://arxiv.org/abs/2310.13548 (aperto). Cinque assistenti di prima linea
  sono sistematicamente sycophantici su quattro task; la causa è il feedback
  umano: quando una risposta dà ragione all'utente è preferita più spesso. E'
  la ragione per cui «chi obietta non vede l'approvazione di un collega» è una
  contromisura giusta: la sycophancy è diretta verso chi approva.
- **Il bias d'identità nel dibattito** — *When Identity Skews Debate:
  Anonymization for Bias-Reduced Multi-Agent Reasoning* —
  https://arxiv.org/abs/2510.07517 (aperto). Gli agenti non sono neutrali:
  sycophancy legata all'identità e **self-bias** (adottano acriticamente la
  posizione di un pari **o** si ostinano sul proprio output precedente).
  Mitigazione misurata: **anonymization** degli scambi.
- **Il survey del 2026** — *Multi-Agent Debate Strategies: Survey, Taxonomy,
  and Challenges* — https://arxiv.org/abs/2607.26212 (aperto), 141 studi.
  Rischi citati: **consensus collapse**, "echo-chamber", **sycophancy
  inter-agente** (con CONSENSAGENT come mitigazione). Un dato utile: il campo
  è converso su un disegno stretto (topologie statiche completamente connesse,
  scambio *verbatim*, memoria a breve termine, risoluzione a voto) adottato per
  convenzione più che per confronto. Le configurazioni **eterogenee** (persone
  distinte) sono il 53,6% degli approcci e sono quelle che evitano la
  convergenza prematura e gli errori condivisi.

**Le mitigazioni pubblicate per la convergenza fra ruoli.** La domanda
dell'incarico era quali fossero misurate e quali folklore:

| mitigazione | fonte | stato |
|---|---|---|
| **modelli diversi per ruoli diversi** | 2502.08788 ("antidoto universale") | misurato |
| **persone/ruoli asimmetrici** (angel/devil, critico) | survey 2607.26212 §4.1 | misurato nel complesso, ma vedi sotto il "divergent MAD" che crolla |
| **temperature diverse fra istanze** | LMAD 2608.01463 (0.1 / 0.5 / 0.9, stesso modello) | misurato |
| **informazione nascosta a un ruolo** / risposte indipendenti | CoVe 2309.11495; nostro ruolo 3 | misurato (CoVe) |
| **anonymization degli scambi** | 2510.07517 | misurato |
| **feedback esterno** (non autovalutazione) | 2310.01798, Reflexion | misurato |
| **dibattito localizzato al primo disaccordo** | LMAD 2608.01463 | misurato, +7,2pp sul miglior baseline convenzionale |

**Sul modello piccolo (la cosa che conta per noi).** Il dubbio era: «se il
dibattito funziona solo sopra una certa scala, è la cosa più importante da
riportare». L'evidenza migliore che ho trovato è **LMAD, *Where Reasoning
Diverges: Localized Multi-Agent Debate for Multi-Hop QA*** —
https://arxiv.org/abs/2608.01463 (aperto, ago 2026). Mette nella tabella dei
risultati i modelli piccoli: **Qwen3-8B** e **Qwen2.5-7B** (oltre a Gemma3-4B/12B,
Qwen2.5-14B, Qwen3-14B...). Su Qwen3-8B il dibattito localizzato supera CoT,
Self-Consistency, Consensus e MAD standard su 3 dei 4 benchmark (2Wiki +3,0pp,
MuSiQue +4,4pp, StrategyQA +1,0pp; HotpotQA pari). Su Qwen2.5-7B i guadagni sono
più larghi (+3,2 / +7,2pp). Quindi **il dibattito funziona anche sotto i 10B**,
con due avvertenze misurate: (a) funziona quando è **localizzato** al primo
disaccordo, non quando si scambiano interi ragionamenti; (b) **forzare
prospettive divergenti esplicite (dMAD) crolla sui modelli piccoli** — su
Qwen3-8B StrategyQA scende a 68,4 contro 91,8 del semplice CoT. La lezione per
il nostro disegno: temperature diverse e input isolati sì, persone opposte
esplicite no. Giudice esterno Qwen2.5-32B; task di QA multi-hop, non prosa
aperta — quindi per la nostra esatta combinazione (8b, cinque ruoli, prosa in
italiano) non c'è ancora un benchmark pubblicato («non trovato»).

**Sull'invariante anti-eco.** Il confronto «se l'obiezione sovrappone troppi
n-grammi con la riformulazione, è un'eco e si rifà» — esiste qualcosa di
pubblicato di identico? **Non trovato come gate di rifacimento.** Ma la *famiglia*
è nota e ha metriche già pronte: il problema è la **diversità testuale** fra
due output, e le metriche economiche sono **self-BLEU** e **distinct-n**
(entrambe calcolabili sugli n-grammi, senza modello), più il concetto di
**divergenza** che il survey 2607.26212 cita come rimedio al consensus collapse
(diversity-pruning). Scegliamo noi la soglia (come già previsto), ma la metrica
ha già un nome: self-BLEU / Jaccard sugli n-grammi. Nessuna metrica migliore e
altrettanto economica trovata.

**Esiste già uno strumento che fa questo per Obsidian?** **Non trovato.** I
roundup dei plugin AI per Obsidian 2026 (Smart Connections, Copilot for
Obsidian, Text Generator; fonti:
https://www.moltyflywheel.com/blog/best-obsidian-ai-plugins-2026 aperto, e
https://systemsculpt.com/blog/best-obsidian-ai-plugins-2026 non aperto) sono
tutti single-agent: ricerca semantica, chat col vault, drafting da prompt.
Nessuno fa una discussione multi-ruolo con obiezioni e domande su una nota. Il
disegno di `INCARICO-pensieri.md` non ha un equivalente pubblico da copiare:
è il nostro, ed è allineato con ciò che la letteratura considera misurato.

**Verdetto punto 5: TENERE IL NOSTRO**, con due aggiunte che la letteratura
sostiene: (1) temperature diverse fra i ruoli (LMAD usa 0.1/0.5/0.9) invece di
una sola; (2) la soglia anti-eco dichiarata come self-BLEU. Da NON fare: persone
opposte esplicite sul modello piccolo (dMAD crolla, misura sopra).

---

## 6. Spezzare un documento lungo per struttura

**Cosa abbiamo noi oggi.** Cascata di confini naturali (titoli → ancore di
pagina → paragrafi → frasi → parole) con un budget derivato da `num_ctx`;
scendiamo di livello solo se il pezzo non entra.

**Ha un nome, e la letteratura lo valida.**

- Il nostro approccio è il **chunking strutturato/gerarchico** (structure-aware,
  hierarchical). Non è un nome nostro: è la categoria "structure-aware /
  hierarchical" dello studio sistematico del 2026 — *A Systematic Investigation
  of Document Chunking Strategies and Embedding Sensitivity* —
  https://arxiv.org/abs/2603.06976 (aperto, mar 2026). Misura 36 metodi
  (fixed-size, semantic, structure-aware, hierarchical, adaptive, LLM-assisted)
  su 6 domini con 5 modelli di embedding: **il chunking content-aware supera
  nettamente lo split a lunghezza fissa** (top: Paragraph Group Chunking,
  nDCG@5 ≈ 0,459; fixed-size a caratteri sotto 0,244, Precision@1 del 2-3%).
  Caveat: il benchmark è per *dense retrieval* (qualità degli embedding), non
  per mandare pezzi a un LLM; ma la gerarchia-che-vince è la stessa.
- **MarkdownHeaderTextSplitter** di LangChain —
  https://reference.langchain.com/python/langchain-text-splitters/markdown/MarkdownHeaderTextSplitter
  (aperto) e https://docs.langchain.com/oss/python/integrations/splitters/markdown_header_metadata_splitter
  (aperto). Spezza un markdown sui livelli di titolo specificati e porta i
  titoli nei metadata. E' esattamente la nostra scelta «titoli prima di tutto»,
  senza budget e senza discesa di livello: è la versione meno raffinata della
  nostra cascata.
- **HybridChunker di docling** — https://docling-project.github.io/docling/concepts/chunking/
  (aperto). E' il parente maturo della nostra cascata: parte dal chunking
  **gerarchico** del documento (titoli/paragrafi) e ci applica un raffinamento
  *token-aware*: (a) un passaggio che **spezza solo quando il pezzo supera i
  token** e (b) un passaggio che **unisce i pezzi sottodimensionati** successivi
  con lo stesso titolo/didascalia (opt-out via `merge_undersized_chunks`). Il
  passaggio (a) è la nostra discesa di livello; il passaggio (b) **non lo
  facciamo** — i nostri pezzi corti restano corti. E' l'unica cosa che la
  letteratura ci suggerisce di copiare: unire i pezzi che non riempiono il
  budget quando condividono lo stesso titolo.

**Semantic chunking e late chunking.** Il **semantic chunking** (spezzare dove
il significato cambia, via embedding) nello studio del 2026 non batte
sistematicamente lo structure-aware, e costa un passaggio di embedding in più:
per la corsia veloce non è un'idea da prendere. Il **late chunking** — *Late
Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models* —
https://arxiv.org/abs/2409.04701 (aperto) — è una tecnica per gli *embedding* di
recupero (si embedda l'intero documento e si spezzano i vettori dopo), non per
l'input a un LLM: citata per nome, ma irrilevante per il nostro uso.

**Cosa ci perdiamo.** Niente di ovvio: la cascata ha un nome pubblicato
(chunking gerarchico/structure-aware), la priorità ai titoli è condivisa da
LangChain, e il budget che decide quando scendere di livello è la nostra misura
in più (non trovato un criterio pubblicato per la soglia "scendi se non entra").
Unica aggiunta suggerita: il **merge** dei pezzi corti dello stesso titolo di
docling.

**Verdetto punto 6: PRENDERE L'IDEA** — solo il merge di docling; il resto è
già il nostro, con un nome in letteratura.

---

## Non trovato

Cercato e non esiste, o non raggiungibile. Ogni riga è un punto dove **dobbiamo
inventare noi**, o dove l'invenzione è necessità e non spreco.

- **Pedici con flag di libreria.** Nessuna libreria espone un flag "pedice":
  PyMuPDF ha solo `TEXT_FONT_SUPERSCRIPT`, e il mantainer dichiara che i pedici
  non si rilevano. (Capitolo 2)
- **Soglie geometriche pubblicate** per apici/pedici. Il paper che le propone
  (Baker/Sexton/Sorge, Springer 10.1007/s11786-008-0051-9) non è leggibile:
  Springer dietro captcha, API di Semantic Scholar in rate-limit (429). Le
  soglie restano le nostre, misurate da noi. (Capitolo 2)
- **Un criterio a densità di cifre per le tabelle.** Le librerie classiche
  (pdfplumber/camelot/tabula) decidono su linee e spazi bianchi, i modelli
  (TATR/TableFormer) vogliono torch. Nessuna soglia pubblicata paragonabile
  alla nostra; è la nostra misura. (Capitolo 4)
- **L'invariante anti-eco come gate di rifacimento.** Nessun lavoro pubblicato
  fa "se l'obiezione somiglia troppo al testo, rifai la chiamata". La famiglia
  esiste (diversità testuale, self-BLEU, distinct-n; divergence per il
  consensus collapse), la metrica la scegliamo noi. (Capitolo 5)
- **Un benchmark per la nostra esatta combinazione** (8B, cinque ruoli in
  italiano, prosa aperta). LMAD arriva vicino (Qwen3-8B, QA multi-hop) ma non
  copre prosa aperta né il flusso a cinque ruoli. (Capitolo 5)
- **Uno strumento per Obsidian che "discute" una nota** producendo obiezioni e
  domande. I plugin del 2026 sono tutti single-agent (ricerca semantica, chat,
  drafting). Il nostro disegno non ha un equivalente pubblico. (Capitolo 5)
- **La soglia "scendi di livello solo se non entra".** Nessun criterio
  pubblicato per decidere *quando* passare da titoli a paragrafi a frasi; il
  budget da `num_ctx` è la nostra scelta. (Capitolo 6)
- **docling nell'olmocr-bench riprodotto.** AllenAI riproduce marker/MinerU/
  olmOCR/DeepSeek-OCR/PaddleOCR-VL/Mistral OCR ma non docling; e OmniDocBench
  (v1.6, citato da MinerU) non è letto per intero. (Capitolo 3)
