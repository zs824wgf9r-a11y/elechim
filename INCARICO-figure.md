# Incarico: le figure, il pezzo che di solito si perde

Scritto il 17 agosto 2026, dopo aver misurato le 267 immagini di `DSML.pdf`.
Leggi prima `AGENTS.md`, poi `PIANO-DOCUMENTI.md` (la parte sulle figure), poi
`documenti.py` — in particolare `figure()`, che e' tre righe e va rifatta.

## Lo stato di oggi, in due righe

`90-Allegati/` **e' vuota**. `documenti.py` ha questa funzione:

```python
def figure(pdf: Path) -> int:
    out = _comando(["pdfimages", "-list", str(pdf)])
    righe = [r for r in out.splitlines()[2:] if re.match(r"^\s*\d+", r)]
    return len(righe)
```

Conta e butta. Il rapporto di copertura dichiara `figure trovate: 267` su `dsml`,
e nel vault non c'e' una figura. Delle tre promesse della fase 4 — testo, tabelle,
figure — questa e' l'unica non mantenuta.

## Le misure, prese il 17 agosto su `DSML.pdf`

Sono la parte importante di questo incarico: **tre delle quattro soluzioni ovvie
sono sbagliate, e i numeri dicono perche'.**

### Il 267 e' un numero sbagliato in tre modi

```
267 oggetti da `pdfimages -list`
  di cui tipo:  image 241 · smask 23 · stencil 3
  hash distinti: 174 · hash ricorrenti: 6, che coprono 99 file
  lato minore:  mediana 46px (p10 = 9px)
  pagine con immagini: 63 su 533
```

1. **`smask` e `stencil` non sono figure**: sono canali alfa e maschere *di altre
   immagini*. Contarli gonfia il totale di 26.
2. **Metà sono glifi, non figure.** La mediana del lato minore e' **46px**: in un
   libro di matematica i simboli composti finiscono embeddati come immaginette.
   Su una pagina sola ce ne sono **50 da 29x29px, tutte con hash diverso**.
3. **Le decorazioni ricorrono.** 6 hash coprono 99 file.

### Il filtro giusto e' l'hash, non la dimensione

Qui sta la lezione, e va contro l'intuizione. Cercavo i loghi fra le immagini
**piccole**. Misurando:

| forma | occorrenze | hash distinti | cos'e' |
|---|---|---|---|
| 600x500 | 46 | **2** (23 + 23) | due loghi ripetuti su 23 pagine |
| 2368x2800 | 24 | **1** | **la forma piu' grande del libro e' una decorazione ripetuta 24 volte** |
| 1870x46 | 56 | 33 | righelli, su una pagina sola |
| 29x29 | 50 | 50 | glifi matematici, tutti diversi |

**Il criterio dell'hash e' anche la pratica raccomandata ufficialmente**, quindi non
stiamo inventando: il mantainer di docling consiglia esattamente questo per le
immagini ripetute (`PictureItem._image_to_hexhash`, issue 2037), e i modelli di
layout hanno classi dedicate alle decorazioni (`PAGE_HEADER`/`PAGE_FOOTER`, content
layer `furniture`/`background`). Vedi `RICERCA-stato-arte.md` capitolo 1.

**La riga da ricordare e' la seconda.** Un filtro "tieni le immagini grandi"
promuoverebbe a figura principale la decorazione piu' grossa del volume, 24 volte.
E un filtro "scarta le forme che ricorrono" butterebbe 46 grafici veri se il libro
li avesse esportati tutti alla stessa dimensione — cosa che il caso 600x500
somigliava tantissimo a essere, e non era. **Solo l'hash del contenuto distingue
"la stessa immagine" da "immagini diverse della stessa misura".**

### La cascata misurata

```
partenza (solo tipo image)                    267
1. via gli hash ripetuti (decorazione)        168
2. via il lato minore < 64px (glifi)           25
3. via le proporzioni oltre 8:1 (righelli)     24
```

**24 figure raster vere, su 11 pagine.** A ~8s per descrizione sono **3 minuti**
di GPU. La soglia dei 64px e' misurata, non inventata: la curva del filtro sul
lato minore e' `64px -> 95, 100px -> 93, 150px -> 89, 200px -> 89`, cioe' **si
appiattisce subito**. C'e' un gruppo di decorazioni piccole e un gruppo di figure
vere, e quasi niente in mezzo: la separazione e' reale.

### E qui il difetto vero: le figure del libro sono vettoriali

24 figure su 11 pagine, in un libro di statistica da 533 pagine, **non e'
credibile**. Verificato contando gli elementi di disegno (`pdftocairo -svg`) su un
campione di 43 pagine sparse:

```
elementi vettoriali per pagina: mediana 232 · p75 331 · p90 813 · max 4960
pagine oltre 4x la mediana: 3 su 43 (6%)  ->  stima ~37 pagine su 533
```

**`pdfimages` non le vede per costruzione**: un grafico vettoriale non e' un
oggetto immagine. Quindi oggi vediamo **un quarto** delle pagine con figure (11
raster contro ~37 vettoriali) e ne conserviamo zero. Era il sospetto scritto nel
DA-FARE sul PDF sintetico; ora e' misurato sul libro vero.

Il p90 a 813 contro una mediana di 232 dice anche che la soglia va **raffinata**:
la mediana e' alta perche' anche una pagina di sola prosa contiene tracciati.
Prendi la mia come punto di partenza, misura meglio, e **dichiara la tua**.

## Il lavoro

### 1. `figure()` diventa `figure_raster()` e restituisce oggetti, non un numero

Per ogni figura sopravvissuta alla cascata: pagina, dimensioni, hash, percorso del
file estratto. La cascata va implementata nell'ordine misurato sopra — **prima
l'hash, poi la dimensione, poi le proporzioni** — perche' l'hash e' l'unico
filtro che non sbaglia sui casi grossi.

Il rapporto di copertura cambia numero: `figure trovate` passera' da 267 a ~24 su
`dsml`. **E' voluto e va dichiarato nel rapporto**, altrimenti sembra una
regressione. Aggiungi anche i conteggi degli scartati per motivo (`decorazione`,
`glifo`, `righello`): senza, il giorno che il filtro sbaglia non si capisce dove.

### 2. Le figure vettoriali: si rende la pagina, non si estrae la figura

Non esiste "l'oggetto figura" da tirare fuori. Si rende con `pdftocairo -png -r`
a livello di **pagina** quelle pagine che superano la soglia di elementi
vettoriali. Ritagliare il riquadro della figura sarebbe meglio ma e' un problema
piu' difficile: **non farlo in questo incarico**, rendi la pagina intera e
dichiaralo come limite. Una pagina resa e descritta e' infinitamente meglio di
una figura perfetta che non c'e'.

### 2-bis. La didascalia, che e' il segnale gratuito

Aggiunto il 17 agosto dopo `RICERCA-stato-arte.md`. **`pdffigures2` di Allen AI non
cerca le figure: cerca le didascalie**, e poi prende come figura la regione
adiacente priva di testo-corpo (precision 0,98 / recall 0,96 sul loro dataset). Noi
non possiamo copiare lo strumento — e' Scala/JVM, fermo dal novembre 2023, e
calibrato su paper CS a due colonne, che non e' la geometria di un libro — ma **il
segnale e' testo, quindi lo abbiamo gia' gratis** con poppler.

Cerca le righe che aprono con `Figure N`, `Fig. N`, `Figura N`, `Tabella N`,
`Table N` (le forme vere le misuri tu sul libro, non fidarti di questo elenco).
Servono a tre cose, in ordine di valore:

1. **Dare un nome vero alla figura** nella nota, invece di "figura 3 di pagina 260";
2. **Confermare** che una pagina con molti tracciati vettoriali contiene davvero
   una figura, e non solo tipografia densa. E' il controllo che rende la soglia
   sugli elementi vettoriali molto piu' affidabile: due segnali indipendenti che
   concordano valgono piu' di una soglia sola;
3. **Attaccare la figura alla sezione giusta**, perche' la didascalia sta nel testo
   e il testo lo sezioniamo gia'.

**Non trasformarlo in un requisito.** `pdffigures2` estrae **solo** figure con
didascalia, ed e' il suo limite dichiarato: una figura senza didascalia per lui non
esiste. Da noi la didascalia **arricchisce** ma non decide — una figura senza
didascalia si conserva comunque, con il nome generico. Misura e riporta **quante**
delle figure trovate hanno una didascalia: se sono la grande maggioranza, il
segnale e' solido; se sono una minoranza, dillo, perche' cambia quanto ci si puo'
appoggiare.

### 2-ter. Il ritaglio del riquadro vettoriale: fuori da questo incarico

Per completezza, cosi' non viene riaperto: ritagliare il riquadro invece di rendere
la pagina intera si fa con un **modello di layout** (DocLayout-YOLO, o quello di
docling), che da' bbox e classe. Non si fa qui, per tre motivi misurati nella
ricerca: vuole **torch**, DocLayout-YOLO e' **AGPL-3.0** (e il nostro repo e'
pubblico), e un modello non puo' stare nella corsia veloce che oggi fa 35ms per
pagina. E' materiale per la **seconda corsia**, accanto a marker. Il render a
pagina intera resta il comportamento giusto e il fallback permanente.

### 3. La descrizione con `qwen3-vl:4b`

Gia' installato e in servizio. Prendi il lock GPU con lo stesso meccanismo di
`sbobina.py` (`gpu_della_sbobina`, che sfratta e **rimette a posto**), **una volta
sola** per tutto il giro: prenderlo e rilasciarlo 60 volte fa ricaricare il
modello 60 volte.

**La descrizione e' testo generato da un modello 4B, quindi non e' una fonte.**
Nella nota va marcata come descrizione automatica, e l'immagine — che e' la verita'
— va sempre linkata accanto. Vale la regola di casa: *l'integrale e' la verita', le
note sono l'indice*. Una figura descritta male con l'immagine accanto e' recuperabile;
una descrizione presa per buona senza immagine e' una perdita.

Budget: 24 raster + ~37 pagine ≈ 61 chiamate, ~8 minuti di GPU per `dsml`. Se
misuri molto di piu', fermati e riportalo invece di lanciare un'ora di GPU.

### 4. Dove finiscono

- l'immagine (o la pagina resa) in **`90-Allegati/`**, che oggi e' vuota;
- la nota della sezione che la contiene la linka con la descrizione sotto;
- nomi di file deterministici (documento + pagina + indice), cosi' rimacinare
  **sovrascrive** invece di accumulare copie. `dsml` verra' rimacinato di nuovo.

## Cosa NON fare

- **Non toccare `sbobina.py` ne' `prova_sbobina.py`**: c'e' un'altra sessione che
  ci lavora adesso (`INCARICO-sbobina-formule.md`). E' l'errore del 15 agosto, e
  costa il lavoro di entrambi.
- Non toccare `fusione.py`, `strumenti.py`, `gateway.py`, `energia.py`, `mac/`,
  `README.md`, `README.it.md`, `AGENTS.md`, `DA-FARE.md`, git.
- **`DEFINIZIONI` non si tocca.**
- **Niente OCR, niente torch, niente docling, niente dipendenze nuove**: poppler e
  ollama, che ci sono. Pillow c'e' gia' ed e' usato dal collaudo.
- Non ritagliare i riquadri delle figure vettoriali (vedi punto 2).
- Non rigenerare le note di `dsml` nel vault: lo fa il proprietario. Tu lavori sul
  PDF sintetico e sui **conteggi** del libro vero.

## Come si prova

Il contenuto del libro non entra nel tuo contesto: hash, dimensioni, conteggi e
tempi sono metriche e li puoi guardare; le immagini e la prosa no. **Non aprire le
figure di `dsml`** — nemmeno per controllare se il filtro ha fatto bene. Il
controllo si fa sui numeri e sul sintetico.

Nel PDF sintetico di `prova_documenti.py` disegna tu: **una figura vera**
(abbastanza grande), **un logo ripetuto su tre pagine**, **un glifo da 20px**, **un
righello lungo e sottile**, e su una pagina a parte **un grafico vettoriale**.
Sono verita' di riferimento, quindi le asserzioni sono esatte:

1. la figura vera finisce in `90-Allegati/` **con la sua descrizione**;
2. il logo ripetuto viene scartato come `decorazione` — **una volta**, non tre;
3. glifo e righello vengono scartati, e il rapporto dice con quale motivo;
4. la pagina col grafico vettoriale viene **resa e descritta**, benche'
   `pdfimages` non trovi niente su quella pagina (e' il caso che oggi si perde);
5. rimacinare due volte **non duplica** i file in `90-Allegati/`;
5-bis. la figura con una didascalia nota (`Figura 1: ...` scritta da te) prende
   **quel nome** nella nota; e una figura **senza** didascalia si conserva
   comunque, col nome generico — la didascalia arricchisce, non decide;
6. il collaudo resta verde senza la GPU disponibile: se il modello di visione non
   risponde, la figura si conserva **comunque** e la descrizione resta vuota. Una
   figura senza descrizione e' un ritardo; una figura non salvata e' una perdita.

## Criterio di uscita

- `prova_documenti.py` **TUTTO VERDE**, coi sei casi sopra;
- `RAPPORTO-figure.md` con: la cascata e quanti scartati per motivo su `dsml`, la
  **tua** soglia per le pagine vettoriali e come l'hai misurata, quante pagine
  supera, i tempi reali di `qwen3-vl` per figura, e il numero nuovo di `figure
  trovate` con la spiegazione del perche' scende da 267. **Nessuna immagine e
  nessun testo del libro nel rapporto.**
- `DEFINIZIONI` intatta, e dichiaralo;
- il percorso di **una** figura sintetica con la sua descrizione, pronta da
  guardare: se il descrittore sia all'altezza lo dice il proprietario, non il
  collaudo.

Scrivi il rapporto **appena hai i numeri**, non alla fine.
