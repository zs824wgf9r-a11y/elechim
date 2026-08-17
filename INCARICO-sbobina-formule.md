# Incarico: proteggere le formule dal modello, come si fa con le tabelle

Scritto il 17 agosto 2026, subito dopo che `documenti.py` ha imparato a marcare
le formule. Leggi prima `AGENTS.md`, poi `RAPPORTO-formule.md` (cosa producono i
marcatori), poi `sbobina.py` — e in particolare `_dividi`, `_chunk_fonte` e
`scrivi_nota`, che sono i tre punti da cambiare.

## Il difetto, e adesso e' misurato sul libro vero

`documenti.py` marca ora le formule esattamente come le tabelle:
`<!-- formula pag N blocco M -->` piu' un recinto ```` ``` ````. Rimacinato
`DSML.pdf` il 17 agosto:

```
formule marcate: 1815 · apici ricostruiti: 1718 · pedici ricostruiti: 1374
tabelle conservate: 1168
```

**`sbobina.py` non sa che esistono.** `RE_BLOCCO` riconosce solo `tabella`:

```python
RE_BLOCCO = re.compile(r"<!-- tabella pag \d+ blocco \d+ -->\s*```.*?```", re.S)
```

Quindi oggi **tutte e 1815 le formule passerebbero da un modello 8B**, che le
riscriverebbe "spiegandole". E' la stessa classe di errore del 180 che diventa
150, applicata a un libro di statistica: un `x^2` che torna `x2`, un pedice che
cambia indice, un segno che si perde. **Ed e' silenzioso** — la nota resta
leggibile e plausibile, e te ne accorgi mesi dopo provando a usare una formula.

La macchina per evitarlo **esiste gia' e funziona**: recinto -> segnaposto nel
testo che va al modello -> ricopiatura verbatim sotto *Materiale originale*.
Questo incarico la estende, non la reinventa.

## Il lavoro, e sta tutto in `sbobina.py`

### 1. Un segnaposto per tipo, e non e' cosmetica

Oggi c'e' un solo `SEGNAPOSTO_TABELLA`:

```python
SEGNAPOSTO_TABELLA = "[qui c'e' una tabella, riportata uguale nella nota sotto Materiale originale]"
```

Serve il gemello per le formule. **Non riusare quello delle tabelle**: il
segnaposto e' testo che il modello legge e su cui costruisce la spiegazione. Dirgli
"qui c'e' una tabella" dove c'e' un'equazione lo fa parlare di una tabella che non
esiste — un difetto che nessun test coglie e che si legge subito nella nota.

`RE_BLOCCO` deve riconoscere **entrambi** i tipi e restare **un solo passaggio**
sul testo: due regex applicate in sequenza si pestano i piedi sull'imbottitura del
punto 2. Cattura il tipo come gruppo e scegli il segnaposto in base a quello.

### 2. La trappola: l'imbottitura si misura sul segnaposto giusto

Questo e' il punto dove il cambio si rompe in silenzio, e il progetto ha **gia'
pagato** questo errore una volta. In `_chunk_fonte`, `salva()` imbottisce il
marcatore interno fino alla lunghezza del segnaposto vero:

```python
marca = f"__TABELLA_{len(tabelle) - 1}__"
return "\n\n" + marca.ljust(len(SEGNAPOSTO_TABELLA), "_") + "\n\n"
```

Il commento accanto spiega perche', ed e' una misura vera: senza l'imbottitura, un
pezzo dato per 17.190 caratteri ne consegnava **22.076**, cioe' ~7.200 token, che
sfondavano `num_ctx` e facevano **tagliare la fonte a ollama in silenzio**.

Se i due segnaposti hanno lunghezze diverse — e le avranno — imbottire tutto a
`len(SEGNAPOSTO_TABELLA)` rimette esattamente quel difetto. **Ogni blocco si
imbottisce fino alla lunghezza del segnaposto che ricevera' lui.**

Consiglio di struttura, ma decidi tu e motiva: **una lista sola** di blocchi con
il loro tipo (`__BLOCCO_{i}__`) invece di due liste parallele. Due liste
significano due contatori da tenere allineati con due regex di ripristino, ed e'
il genere di simmetria che si rompe al primo cambio. Il ripristino
(`__TABELLA_(\d+)__+`) va generalizzato di conseguenza.

I recinti restano **blocchi indivisibili** nella cascata dei confini, come le
tabelle: la regola c'e' gia', deve valere anche per le formule.

### 3. `_dividi` e il *Materiale originale*

`_dividi` raccoglie i recinti in `materiale` e li ricopia sotto *Materiale
originale*. Con `RE_BLOCCO` esteso questo funziona da solo, e **in ordine di
documento** perche' usa `finditer` sulla fonte: formule e tabelle si alternano
come stanno nel libro. Verificalo, non darlo per fatto.

Nella nota, distingui visibilmente una formula da una tabella (una riga di
intestazione per blocco, o due sottosezioni). Chi rilegge deve capire cosa sta
guardando senza interpretare il contenuto.

## Le due misure che voglio, perche' cambiano delle decisioni

### A. Quanta parte della sezione diventa segnaposto

**E' il rischio nuovo di questo cambio, e non esisteva con le sole tabelle.** Le
formule sono 1815 e in un libro di statistica sono dense: una sezione molto
matematica, tolte le formule, puo' ridursi a una sequenza di segnaposti con tre
righe di prosa in mezzo. Il modello ne ricava una spiegazione vuota, e la nota
**sembra perfetta** — perche' i numeri sono verbatim e gli allarmi sono zero.

Misura, sulle **223 sezioni di `dsml`**, la distribuzione della frazione di
caratteri sostituiti da segnaposti. Riporta mediana, 90° percentile e il caso
peggiore, e **quante sezioni** stanno sopra una soglia che dichiari tu. Poi
decidi un comportamento e motivalo: la nota lo **dichiara** («sezione in gran
parte formule: la spiegazione copre solo la prosa») invece di tacere. Il
principio di casa e' quello: dichiarare invece di fingere.

### B. `CAR_PER_TOKEN` va rimisurato, e probabilmente regala budget

`CAR_PER_TOKEN = 3.06` e' il **caso peggiore** misurato il 16 agosto leggendo
`prompt_eval_count`, e il commento dice perche' e' basso: *«la matematica
tokenizza male — formule e simboli costano piu' token della prosa»*. Ma quella
misura e' stata presa su testo **con le formule dentro**. Togliendole, il testo
che parte e' prosa quasi pura, che tokenizza **meglio**.

Rimisura `CAR_PER_TOKEN` su cinque sezioni dense **dopo** la sostituzione dei
segnaposti, sempre leggendo `prompt_eval_count` e sempre prendendo il **caso
peggiore**, non la media. Se risulta piu' alto, il budget di `budget_caratteri`
diventa piu' generoso, i pezzi si riducono e la macinata da 4 ore si accorcia.

**Non cambiare la costante di tua iniziativa**: riporta il numero misurato e la
tua raccomandazione nel rapporto. Il default resta 3,06 finche' non lo decide il
proprietario — un budget troppo generoso fa tagliare la fonte a ollama in
silenzio, ed e' il guasto peggiore che questa pipeline abbia.

## Cosa NON fare

- **Non toccare `documenti.py`**: i marcatori li produce già, e sono verificati.
- **Non estrarre `modello.py`** e non spostare `_chiedi`, `verifica_numeri`,
  `_senza_pensiero`, `gpu_della_sbobina`. E' il lavoro di
  `INCARICO-pensieri.md`, che parte **dopo** questo e toccherebbe le stesse righe.
  Due sessioni sullo stesso file e' l'errore del 15 agosto.
- **Non lanciare `sbobina.py` sul libro vero** e non generare note nel vault. Le
  4 ore le lancia il proprietario, dopo aver letto una nota.
- Non toccare `fusione.py`, `documenti.py`, `strumenti.py`, `gateway.py`,
  `energia.py`, `mac/`, `README.md`, `README.it.md`, `AGENTS.md`, `DA-FARE.md`, git.
- **`DEFINIZIONI` non si tocca**, mai, per nessun motivo.
- Niente dipendenze nuove, niente cambi al prompt della spiegazione o dei punti
  che non servano a questo incarico.

## Come si prova

Vale la regola di sempre: **il contenuto di `dsml` non entra nel tuo contesto**.
Conteggi, percentuali, lunghezze e `prompt_eval_count` sono metriche e le puoi
guardare; la prosa e le formule vere no. Il PDF sintetico di `prova_sbobina.py`
lo scrivi tu, quindi e' verita' di riferimento.

Casi permanenti in `prova_sbobina.py`, che deve restare **TUTTO VERDE**:

1. una formula nota **non compare** nel testo dato al modello — al suo posto c'e'
   il segnaposto delle formule, non quello delle tabelle;
2. la stessa formula compare **verbatim, byte per byte**, sotto *Materiale
   originale*, apici e pedici compresi;
3. una sezione con **una tabella e una formula** insieme: entrambe protette,
   entrambe nel materiale, **in ordine di documento**, ciascuna col suo segnaposto;
4. **la contabilita' del budget**: la lunghezza del pezzo misurata dal chunker
   coincide con la lunghezza del testo che parte davvero, con segnaposti di
   lunghezze diverse mescolati. E' l'asserzione che protegge dalla trappola del
   punto 2, e va scritta come invariante esatta, non come tolleranza a occhio;
5. un recinto di formula piu' lungo del budget resta **indivisibile**;
6. l'invariante di copertura che c'e' gia' (`caratteri_coperti ==
   caratteri_fonte`) resta vera.

## Criterio di uscita

- `prova_sbobina.py` **TUTTO VERDE**, coi sei casi sopra dentro;
- `prova_documenti.py` verde (non lo tocchi, ma verificalo: e' la prova che non hai
  cambiato i marcatori);
- `RAPPORTO-sbobina-formule.md` con: la distribuzione della frazione di segnaposti
  sulle 223 sezioni (mediana, p90, peggiore, quante sopra soglia), la soglia scelta
  e il comportamento deciso, il nuovo `CAR_PER_TOKEN` misurato col caso peggiore e
  la raccomandazione, e la scelta di struttura (lista unica o due liste) motivata.
  **Nessun testo del libro.**
- `DEFINIZIONI` intatta, e dichiaralo.

Scrivi il rapporto **appena hai i numeri**, non alla fine. Il 15 agosto due
sessioni si sono piantate su una connessione morta con il codice buono sul disco e
**nessuna conclusione scritta**: le conclusioni sono l'ultima cosa che una sessione
scrive, e quindi la prima che si perde.
