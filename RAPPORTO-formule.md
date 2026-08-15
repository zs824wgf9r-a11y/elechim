# Rapporto: apici, pedici e recinti formula

16 agosto 2026, dopo l'esecuzione di `INCARICO-formule.md`.
Codice in `documenti.py`, collaudo in `prova_documenti.py` (TUTTO VERDE).
Tutte le misure che seguono sono prese da `DSML.pdf` (533 pagine) e dal PDF
sintetico del collaudo. Le soglie sono misurate, non inventate: gli
istogrammi completi sono negli script di misura della sessione, qui stanno
i numeri che le giustificano.

## Cosa e' stato costruito

1. **Ricostruzione di apici e pedici dalle coordinate** (`_marca_apici_pedici`),
   resi nella notazione `x^2` / `x_i` dentro i recinti formula.
2. **Recinti formula** (`recinti_formula`): stesse modalita' delle tabelle —
   commento `<!-- formula pag N blocco M -->` + recinto ``` — con testo
   ricostruito dalle coordinate di `pdftotext -bbox`, marcatori compresi.
3. **Il rapporto di copertura dichiara** `formule_marcate`,
   `apici_ricostruiti`, `pedici_ricostruiti` (`_conteggi_formule`).

## La scelta di progetto che va letta prima delle soglie

**Il testo semplice non e' stato toccato.** L'incarico chiedeva di
ricostruire apici e pedici; la difficol' vera e' *dove* scriverli. La via
ovvia — sincronizzare le parole di `pdftotext -bbox` con i token del testo
semplice e correggere in place — e' stata misurata e bocciata:

```
allineamento token testo semplice vs parole -bbox (5 pagine dense):
  pag 443: 10.1%   pag 145: 20.3%   pag 142: 46.3%
  pag  67: 10.5%   pag 467: 10.1%
provato anche -bbox-layout e la ricomposizione per gap: picco 31%.
```

Le due segmentazioni divergono proprio sulle pagine matematiche (il testo
semplice unisce base e apice, o li mette su righe diverse). Correggere il
testo con quell'allineamento voleva dire inventare. Quindi vale la regola
dell'incarico presa alla lettera: **dove il rilevamento e' incerto si lascia
il testo com'e'** — e la ricostruzione vive nei recinti, che sono l'unico
posto del markdown costruito per intero dalle coordinate. E' la stessa
dualita' prosa/recinto che le tabelle gia' usano, e da' alla sbobina il
veicolo per tenere le formule lontane dal modello (lo scopo del punto 2).

## Notazione scelta: `x^2` e `x_i`, non unicode

- L'unicode copre quasi tutto per gli apici ma **non per i pedici**: non
  esistono pedici di b, c, d, f, g, q, w, y, z. In un libro di statistica
  `x_ij`, `β_0`, `a_1` sono la norma: metta' unicode avrebbe voluto dire
  mezza notazione unicode e mezza ASCII nello stesso recinto.
- `^` e `_` sono ASCII, sopravvivono a ogni copia-incolla e grep, e chi
  legge li riconosce. In Obsidian un `^` o `_` singolo non attiva ne'
  evidenziazione ne' corsivo (servono coppie).
- Niente LaTeX: l'incarico lo esclude, e giustamente — qui si salva
  l'informazione di posizione, non si riscrive la formula.
- Script consecutivi dello stesso tipo si fondono in un marcatore unico
  (`x^ab`); gli spazi interni allo script cadono (caso raro, dichiarato).

## Soglie misurate

### Corpo ridotto e spostamento (accoppiamento a coppie)

Il rilevamento e' **a coppie** (base→script), non per righe: poppler mette
gli apici in blocchi propri, separati dalla base (misurato su PDF sintetico:
l'apice finisce in un `<block>` dedicato), quindi nessun raggruppamento per
righe di poppler e' affidabile. Una parola e' script della parola che la
precede se:

| soglia | valore | da dove viene |
|---|---|---|
| corpo | `h_script ≤ 0.80 × h_base` | gli script reali stanno a 0.60-0.80; il maiuscoletto ('D'+'OCUMENTO') sta a ~0.80 con centro allineato, e resta fuori per lo spostamento, non per l'altezza |
| spostamento del centro | `|dc| ≥ 0.16 × h_base` | istogramma sulle 5 pagine dense: i due cluster (apici sopra, pedici sotto) partono a ~0.15; i run ridotti in baseline comune (unia', citazioni) stanno dentro ±0.12 |
| gap orizzontale | `-0.9 … +0.7 × max(h)` | gli apici reali stanno a -0.2…+0.4; il mino negativo ammette i limiti di sommatoria, sovrapposti al simbolo |
| stessa riga visiva | `|Δ yMax| ≤ 1.0 × h_script` | un apice si sposta di 0.3-0.6 altezze, la riga sotto sta a un interlinea (~1.1-1.5). Con 1.3 la riga successiva passava e produceva ~300 pedici fantasma: misurato e corretto |

Con questi valori, sulle 5 pagine dense: **723 coppie candidate, 372 script
marcati, 351 scartati in zona morta**. Su 8 pagine di sola prosa: 15 coppie,
**tutte** in zona morta, zero marcature. La catena `x_i^2` funziona: la base
di uno script puo' essere uno script.

Le parole senza caratteri alfanumerici (virgole, punti) non sono mai script:
senza questo filtro ogni virgola, piu' bassa del suo vicino, sarebbe un
pedice.

### Riconoscimento delle formule (righe ricostruite, non poppler)

Le righe si ricostruiscono da noi: cluster per baseline delle parole
normali, script attaccati alla loro base, taglio a colonne dove il vuoto
orizzontale supera `2.2 × h` mediana. Su ogni frammento valgono i segnali
(lunghezza compatta, simboli matematici, parole normali, non-alfabetici,
numerazione finale `(N.N)`). Una riga e' formula se:

- `math ≥ 2` e `parole ≤ 6` (un'equazione con due simboli e sei pezzi);
- oppure `math ≥ 1` e `parole ≤ 3` e `len ≤ 42` e `nonalfa ≥ 0.4`;
- oppure `math ≥ 2` e `parole ≤ 9` e `nonalfa ≥ 0.50` (frammenti densi);
- oppure termina con `(N.N)` e `math ≥ 1` (equazione numerata in riga).

L'insieme dei simboli e' calibrato sul libro: `+` entra (24 occorrenze nelle
dense, **zero** in prosa), `-` e `/` no (22 e 3 occorrenze in prosa:
parole composte e date). Il libro reale estrae `∑ − ≤` come codepoint
matematici, non come ASCII: l'insieme e' costruito su quelli.

**Sbagliare per difetto**: le regole piu' larghe provate (densita' ≥ 0.10,
math≥2 senza limite di parole) aggiungevano ~40 recinti per pagina densa ma
catturavano anche le ultime righe di paragrafo con matematica inline. La
regola di attacco della numerazione `(N.N)` alla sua equazione e' stata
provata e tagliata: nel libro reale la numerazione sta sempre in un
frammento proprio (10 casi su 10), mai in riga con l'equazione.

## Risultati su DSML (sola lettura, il markdown non e' stato rigenerato)

```
5 pagine dense (443, 145, 142, 67, 467):   28 recinti, 37 apici, 21 pedici
8 pagine di sola prosa:                     0 recinti,  0 apici,  0 pedici
4 pagine di prosa con matematica inline:    4 recinti (profilo: 1-2 parole,
                                            7-14 caratteri, nonalfa ~0.5:
                                            display vere, non ultima riga)
libro intero (533 pagine):               1815 recinti, 1718 apici,
                                         1374 pedici, 434 pagine con formule
tempo: 35 ms/pagina (bbox + tabelle + recinti), ~19s su tutto il libro
```

I falsi positivi dichiarati: **zero su prosa pura** (409 righe), e la riga
ombra del collaudo — una frase di prosa che contiene l'espressione della
formula e un numero di equazione — non viene recintata. Il collaudo lo
impone come asserzione permanente.

## Limiti, con i numeri

Delle 372 parole marcate come script sulle pagine dense:

- **61 (16%) cadono nei recinti** e arrivano alla nota come `x^2`/`x_i`;
- **140 (38%) stanno dentro tabelle**: le tabelle restano verbatim per
  progetto (`pdftotext -layout`), quindi i loro apici non vengono marcati;
- **171 (46%) stanno su righe non recintate**: matematica inline nella prosa
  o righe di formula senza simboli dell'insieme. Restano nel testo semplice
  appiattite, cioe' il comportamento di ieri.

Il conteggio degli apici/pedici dal markdown e' esatto perche' `^` e `_`
sono **zero** nel testo estratto dell'intero libro (misurato); l'unica
eccezione possibile e' un accento circonflesso letterale dentro una
formula: caso dichiarato, non presente in DSML.

## Per chi proseguira' (protezione delle formule nella sbobina)

I recinti seguono esattamente lo schema delle tabelle: la sbobina li puo'
togliere dal testo che va al modello e ricopiarli verbatim con la stessa
regex che gia' usa, cambiando `tabella` in `formula`. I marcatori `^`/`_`
sono pensati per essere stripping-facili (`\^` / `_`) se servisse.
