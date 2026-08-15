# Incarico: le formule matematiche

Scritto il 16 agosto 2026, dopo una misura che ha trovato un difetto grosso.
Leggi prima `AGENTS.md` e `INCARICO-chunking-adattivo.md`.

## Il difetto, misurato

`DSML.pdf` e' un libro di statistica: 533 pagine, **8.580 righe che paiono
formule (16% del testo)**, 974 equazioni numerate, 9.397 simboli matematici.

Su pagina 443, la piu' densa, il PDF contiene:

```
41% delle parole in corpo RIDOTTO
28% delle parole FUORI dalla linea di base   <- apici e pedici
```

Nel testo estratto da `pdftotext`:

```
apici unicode: 0        pedici unicode: 0
lettere greche: 68 (sopravvivono)
```

**L'informazione c'e' nel PDF e la buttiamo via noi.** Il risultato e' che `x²`
diventa `x2`, `σ²` diventa `σ2`, e `xᵢ` diventa `xi` — che sembra una variabile
diversa. In un libro di matematica **l'esponente e l'indice sono il contenuto,
non la formattazione**: appiattirli e' la stessa classe di errore del 180 che
diventa 150, applicata pero' a tutto il libro.

E' anche un errore **silenzioso**: il testo resta leggibile e plausibile, quindi
nessuno se ne accorge finche' non prova a usare una formula.

## Il lavoro, e sta tutto in `documenti.py`

### 1. Ricostruire apici e pedici dalle coordinate

Il dato c'e' gia': `pdftotext -bbox` da' `xMin/yMin/xMax/yMax` per ogni parola, e
`documenti.py` **usa gia'** questa famiglia di strumenti (`pdftohtml -xml`) per
riconoscere i titoli dal corpo del font. Stessa tecnica, altro scopo:

- una parola **piu' piccola** della mediana della sua riga **e spostata in alto**
  rispetto alla linea di base e' un **apice**;
- piu' piccola e spostata in **basso** e' un **pedice**;
- le soglie si **misurano** sulle pagine dense (443, 145, 142, 67, 467), non si
  inventano. Sulla 443 la mediana d'altezza e' 13,0 e il 41% delle parole sta
  sotto l'85% di quel valore: i due gruppi sono ben separati, quindi una soglia
  netta esiste.

Come renderli nel markdown: **decidi tu e motiva**. Le opzioni ragionevoli sono
l'unicode (`x²`, `xᵢ`) che e' leggibile in Obsidian ma copre pochi caratteri, e
la notazione `x^2` / `x_i` che copre tutto ed e' quella che chiunque riconosce.
**Non usare LaTeX completo**: qui non si sta ricostruendo la formula, si sta
salvando l'informazione di posizione che oggi si perde.

**Regola che viene prima**: se il rilevamento e' incerto, **lascia il testo com'e'
adesso**. Un apice mancato e' il comportamento di oggi; un apice inventato dove
non c'era e' un peggioramento.

### 2. Marcare le formule, come gia' si fa con le tabelle

`documenti.py` marca i blocchi tabellari con `<!-- tabella pag N blocco M -->` e
un recinto ```` ``` ````, e `sbobina.py` li toglie dal testo che va al modello e
li ricopia verbatim nella nota. **Le formule non hanno niente di tutto questo**,
quindi oggi passerebbero tutte da un modello 8B.

Serve lo stesso trattamento: riconosci le righe/blocchi di formula e marcali,
`<!-- formula pag N blocco M -->` con lo stesso schema di recinto. Il
riconoscimento sta a te, ma il segnale c'e' ed e' forte: densita' di simboli
matematici e di caratteri non alfabetici, righe corte e isolate, presenza di una
numerazione `(1.2)` a fine riga (974 casi nel libro).

Vale la regola delle tabelle al contrario: **sbagliare per difetto**. Una formula
non marcata e' il comportamento di oggi; un paragrafo di prosa marcato come
formula diventa un recinto verbatim in mezzo alla spiegazione, ed e' il difetto
dei falsi positivi delle tabelle che abbiamo appena finito di correggere (erano
26 su 42). **Misura i falsi positivi** su una pagina di sola prosa e riportali.

### 3. Il rapporto lo dichiara

Nel rapporto di copertura: `formule_marcate`, `apici_ricostruiti`,
`pedici_ricostruiti`. Senza numeri non si sa se ha funzionato.

## Cosa NON fare

- **Non toccare `sbobina.py`**: un'altra sessione ci sta lavorando adesso. La
  protezione delle formule dal modello e' il passo successivo e lo fa un altro
  incarico, quando questo avra' prodotto i marcatori.
- **Non toccare** `prova_documenti.py` no — quello **devi** toccarlo, per i test.
  Non toccare invece `fusione.py`, `README.md`, `AGENTS.md`, `mac/`,
  `strumenti.py`, `gateway.py`, git.
- **Niente docling, niente torch, niente OCR**: si lavora con poppler, che c'e'.
- **Non rigenerare il markdown di `dsml`**: quello lo fa il proprietario quando
  il codice e' pronto. Tu lavori sul PDF sintetico e sulle pagine di misura.

## Come si prova

Vale la regola di sempre: **il contenuto di `dsml` non entra nel tuo contesto**.
Coordinate, conteggi, altezze e percentuali sono metriche e le puoi guardare; la
prosa no.

Arricchisci il PDF sintetico di `prova_documenti.py` con **una formula con
apice e pedice noti** (scritti da te, quindi verita' di riferimento) e con
**una riga di prosa che somiglia a una formula**, per misurare i falsi positivi.
Poi:

1. l'apice e il pedice noti si ritrovano nel markdown nella forma scelta;
2. la formula nota risulta **marcata**, la prosa che le somiglia **no**;
3. la prosa normale non guadagna apici che non aveva (nessun falso positivo);
4. sulle cinque pagine dense di `dsml` riporta **solo i conteggi**: quanti apici
   e pedici ricostruiti, quante formule marcate.

## Criterio di uscita

- `prova_documenti.py` resta **TUTTO VERDE**, coi casi nuovi dentro;
- i numeri di apici/pedici ricostruiti e formule marcate sulle pagine dense;
- i falsi positivi misurati su prosa, e sotto una soglia che dichiari tu;
- `RAPPORTO-formule.md` con le soglie scelte, la notazione scelta e il perche';
- `DEFINIZIONI` intatta.
