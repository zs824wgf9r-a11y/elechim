# Incarico: titoli e indice dall'indice del PDF

Riscritto il 15 agosto 2026 dopo una scoperta che cambia l'approccio. Leggi
prima `AGENTS.md`. **Questo viene prima della sbobina**: riscrivere
magnificamente una sezione intitolata `reface` non serve a niente.

## La scoperta: il documento contiene gia' il proprio indice

Stavamo ricostruendo la struttura con euristiche sul corpo dei font. **Non
serve: l'editore l'ha scritta dentro il PDF.**

```
$ pypdf → r.outline su DSML.pdf
223 voci, 223 risolte a un numero di pagina, 0 fallimenti

- Preface                                        (pag 1)
- Notation                                       (pag 1)
- Importing, Summarizing, and Visualizing Data   (pag 19)
  - Introduction                                 (pag 19)
  - Structuring Features According to Type       (pag 21)
  - Summary Tables                               (pag 24)
  - Visualizing Data                             (pag 26)
    - Plotting Qualitative Variables
    - Plotting Quantitative Variables
```

Titoli **esatti** (`Preface`, non `reface`), gerarchia **gia' annidata su tre
livelli**, pagine **esatte**, e nessuna dedica ne' pagina di `contents`.

Tutti e tre i difetti su cui stavamo per lavorare — la lettera mangiata, i
frammenti, il frontespizio promosso a sezione — **spariscono**, perche' erano
tutti artefatti del ricostruire a occhio una cosa gia' dichiarata.

Vale anche la pena saperlo: la ricerca sugli strumenti del settore (Docling,
Marker, MinerU) dice che **tutti e tre sbagliano proprio la gerarchia dei
titoli**. Nessuno di loro avrebbe risolto questo. L'indice incorporato si'.

## Il lavoro

**1. L'indice del PDF diventa la fonte primaria della struttura.**

`pypdf` e' gia' installato a livello di sistema ma **non nel venv**: serve
`uv pip install --python .venv/bin/python pypdf`.

Da ogni voce si prende titolo, livello di annidamento e pagina di destinazione.
I confini di una sezione sono: dalla sua pagina fino alla pagina della voce
successiva. Pulito, deterministico, senza euristiche.

**2. Le euristiche restano, come ripiego.**

Molti PDF non hanno l'indice incorporato — le scansioni quasi mai, i documenti
generati da Word spesso no. Il codice attuale (`sezioni_xml`, corpo dei font)
**non si butta**: diventa il percorso alternativo quando l'indice manca o ha
meno di 3 voci.

Il campo `struttura` nel rapporto deve dire **quale dei due e' stato usato**:
`outline` oppure `font-size`. Serve a leggere il rapporto e sapere quanto
fidarsi.

**3. Se resti sul percorso di ripiego, correggi comunque questi due difetti**,
perche' sui PDF senza indice si ripresenteranno identici:

- **La lettera mangiata.** Causa gia' trovata, non ricercarla: e' tipografia a
  maiuscoletto, iniziale grande e resto piu' piccolo come due elementi `<text>`
  distinti con `top` diverso di pochi pixel.
  ```
  pag9  top=315 font=13 size=37.0 -> 'P'
  pag9  top=321 font=14 size=30.0 -> 'REFACE'
  ```
  `sezioni_xml` raggruppa con `round(top)`, cioe' confronto **esatto**, e li
  separa. **La funzione gemella nello stesso file lo fa gia' giusto**:
  `righe_geometriche` usa `tol = max(0.5, media * 0.4)`. Due modi diversi di
  raggruppare righe nello stesso file, uno corretto e uno no.
- **Dediche e frontespizio** promossi a sezione perche' scritti in grande.
  Filtro sulla quantita' di testo sotto il titolo. Cio' che scarti va **contato
  nel rapporto** (`sezioni scartate: N`), mai fatto sparire in silenzio: e' la
  differenza fra un filtro e una perdita. **L'integrale non si tocca mai**.

**4. L'indice diventa un sommario vero.**

Con l'albero dell'outline non serve nessuna regex sulla numerazione: la
gerarchia c'e' gia'. La nota indice diventa un sommario annidato con i wikilink
alle note atomiche, i capitoli come intestazioni.

**5. I nomi delle note.**

`dsml-sezione-100-5-2-linear-regression` e' illeggibile, e in Obsidian il nome
del file **e' il titolo che vedi**. Proponi una convenzione e motivala nel
README — un punto di partenza e' `DSML 5.2 Linear regression` con `aliases` nel
frontmatter per la ricerca. Il progressivo di pipeline (`100`) fuori dal nome
visibile.

**Vincolo duro**: i wikilink devono risolvere **tutti**. Oggi sono 642/648 su
`dsml`: **i sei rotti vanno capiti**, non arrotondati. Rinominare senza
aggiornare i link romperebbe il vault.

**6. Formattazione.** Obsidian sara' il secondo cervello del proprietario, la resa
conta quanto il contenuto: frontmatter coerente, `aliases`, tag utili, e **via
l'estratto troncato a meta' parola** che c'e' adesso nelle note atomiche.

## Ordine di lavoro — questo e' vincolante

Le ultime tre sessioni si sono consumate in analisi e sono finite **senza
scrivere il file**. Quindi:

1. **Prima scrivi il codice che funziona** sul percorso outline, e fallo girare
   su `DSML.pdf`.
2. **Poi** misura, confronta e rifinisci.

Non invertire. Un modulo grezzo che gira vale piu' di un'analisi perfetta senza
modulo.

## Come si prova

Vale la regola di `AGENTS.md`: il contenuto dei documenti del proprietario **non entra
nel tuo contesto**. Ma **titoli, struttura, nomi dei file e conteggi sono
metadati** e puoi guardarli: e' l'unico modo di verificare questo lavoro. Il
corpo delle note no.

Arricchisci il PDF sintetico con un **indice incorporato** (cosi' il percorso
primario ha un collaudo) e con un **titolo a maiuscoletto** piu' una **pagina di
dedica** (cosi' il ripiego resta coperto). Un difetto trovato una volta e non
messo nel collaudo torna: e' gia' successo stamattina con le colonne.

## Criterio di uscita

- `DSML.pdf` produce sezioni dall'outline: **223 voci**, titoli esatti,
  `Preface` e `Notation` corretti, nessuna dedica;
- il rapporto dichiara `struttura: outline`;
- la nota indice e' un sommario annidato su tre livelli;
- **wikilink tutti risolti**, e i sei rotti di oggi spiegati;
- il ripiego `font-size` funziona ancora su un PDF senza indice (il sintetico);
- `prova_documenti.py` verde, coi casi nuovi dentro;
- `DEFINIZIONI` intatta: `1160ec454b8b9998`.
