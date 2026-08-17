# Incarico: il lock GPU vero, e due correzioni che stanno negli stessi file

Scritto il 17 agosto 2026 sera. Tre cose piccole, tutte in `energia.py`,
`sbobina.py`, `documenti.py` e i loro collaudi. Stanno **insieme** perche'
toccano gli stessi file: due sessioni sullo stesso file e' l'errore del 15
agosto, e non lo rifacciamo per risparmiare mezz'ora.

Leggi prima `AGENTS.md`, poi le sezioni **1-ter**, **1-quater** e **9** di
`DA-FARE.md`, che descrivono i tre difetti da correggere.

---

## 1. Il lock GPU e' una bandiera, non un mutex — ed e' il piu' importante

**Il difetto.** `gpu_della_sbobina()` in `sbobina.py` (e ora anche
`gpu_delle_figure()` in `documenti.py`) fanno cosi':

```python
gia_in_gioco = energia.in_gioco()
creato = False
if not gia_in_gioco:
    print(energia.libera_vram(), flush=True)
    creato = True
```

Chi arriva **secondo** trova la bandiera `stato/gioco` gia' alzata, quindi:

- **non** libera la VRAM — crede che l'abbia gia' fatto qualcun altro;
- uscendo **non** abbassa la bandiera e **non** ricarica;
- e quando il **primo** esce, ricarica `qwen3-vl` e whisper **sotto i piedi del
  secondo**, sfrattandogli il modello a meta' lavoro.

Lo stato non si corrompe in modo permanente (chi alza la bandiera la abbassa),
ma il lavoro del secondo si', in silenzio. E' il motivo per cui oggi non si sono
potute lanciare due sessioni in parallelo che usassero la GPU.

**La correzione**: mutua esclusione vera con **`flock`**, esattamente come
`_coda_esclusiva()` in `documenti.py` — quel codice esiste, funziona, ed e'
gia' provato in esercizio (12 avvii in 2 secondi, tutti corretti). Va messa in
**`energia.py`**, perche' serve a due chiamanti diversi.

Differenza importante rispetto alla coda: qui chi arriva secondo **non deve
uscire**, deve **aspettare** — sta per fare un lavoro lungo e legittimo. Quindi
`flock` **bloccante**, con un timeout generoso e dichiarato, e un messaggio che
dica «aspetto la GPU, occupata da <chi>» invece di restare muto. Un'attesa
silenziosa di venti minuti e' indistinguibile da un blocco.

Chi entra per primo libera la VRAM e la ricarica uscendo, **come adesso**. Chi
aspetta, quando tocca a lui, si comporta da primo: la bandiera `stato/gioco`
resta per il gateway, che la usa per i fatti suoi, ma **non e' piu' lei a
decidere chi possiede la GPU**.

**Casi di collaudo, e il punto e' che devono poter fallire:**

1. due processi che chiedono la GPU insieme: il secondo **aspetta** e parte solo
   quando il primo ha finito. Non basta verificare che finiscano entrambi:
   **verifica l'ordine** — che il secondo non abbia cominciato prima che il primo
   chiudesse;
2. chi aspetta oltre il timeout esce con un errore **chiaro**, non resta appeso;
3. un processo che muore male (`SIGKILL`) **rilascia** il lock: e' la proprieta'
   per cui si usa `flock` invece di un file con dentro un PID;
4. la VRAM viene liberata **una volta sola** e ricaricata **una volta sola**, non
   una per processo.

---

## 2. `CAR_PER_TOKEN` va **abbassato** a 2,7444

**Non e' un refuso: il rapporto precedente ha il numero giusto e la conclusione
rovesciata.** `RAPPORTO-sbobina-formule.md` misura 2,7444 car/token nel caso
peggiore e raccomanda di tenere 3,06 «per prudenza». E' l'opposto: nella formula

```
caratteri = (num_ctx - prompt - risposta) x (1 - margine) x CAR_PER_TOKEN
```

`CAR_PER_TOKEN` **moltiplica il budget di caratteri**, quindi un valore piu' alto
concede **piu'** testo. A 3,06 i 17.190 caratteri concessi valgono **6.264
token** invece dei 5.618 preventivati: dei 624 token di margine ne restano **47**,
e reggono solo perche' `TOKEN_PROMPT` e' sovrastimato (150 assunti, 81 misurati).

**Correzione**: `CAR_PER_TOKEN = 2.7444`. Il budget scende a ~15.417 caratteri
(**-10,3%**), cioe' ~10% di pezzi in piu' e il margine che torna.

Aggiungi un **collaudo che protegga il segno**, non solo il valore: un'asserzione
che verifichi che il budget calcolato, riconvertito in token al tasso peggiore
misurato, **stia dentro `num_ctx`** con il margine previsto. Cosi' il giorno che
qualcuno tocca `num_ctx` o i tetti di generazione, il collaudo lo dice.

---

## 3. Il collaudo dell'imbottitura non puo' fallire

`SEGNAPOSTO_TABELLA` e `SEGNAPOSTO_FORMULA` sono **entrambi 77 caratteri**,
perche' «tabella» e «formula» hanno lo stesso numero di lettere. L'imbottitura
per tipo (`marca.ljust(len(SEGNAPOSTI[tipo]), "_")`) e' **giusta**, ma il test
che dovrebbe proteggerla non esercita mai l'asimmetria: con lunghezze uguali,
imbottire all'una o all'altra da' lo stesso risultato.

E' la **terza volta** in questo progetto (sezione 1-quater di `DA-FARE.md`): una
verifica verde per costruzione. Rendila capace di fallire — sostituisci
temporaneamente `SEGNAPOSTI` con due segnaposti di **lunghezza diversa** dentro
il test, e verifica che la contabilita' del budget resti esatta. Se togli
l'imbottitura per tipo, quel test **deve** diventare rosso: provalo, e scrivi nel
rapporto che l'hai provato.

---

## Cosa NON fare

- **Non toccare** `fusione.py`, `strumenti.py`, `gateway.py`, `web.py`,
  `visione.py`, `mac/`, `README.md`, `README.it.md`, `AGENTS.md`, `DA-FARE.md`,
  gli `INCARICO-*`, i `RAPPORTO-*` esistenti, `unita/`, git.
- **`DEFINIZIONI` non si tocca.**
- **Non lanciare `sbobina.py` sul libro vero** e non generare note nel vault: le
  4 ore le lancia il proprietario.
- Non cambiare `num_ctx`, i tetti di generazione o il margine: qui si corregge
  **solo** `CAR_PER_TOKEN`, e il resto si misura.
- Niente dipendenze nuove.
- **Non “migliorare” la bandiera `stato/gioco`**: il gateway la usa, resta dov'e'.
  Qui si aggiunge un lock accanto, non si sostituisce un meccanismo altrui.

## Criterio di uscita

- `prova_sbobina.py` e `prova_documenti.py` **entrambi TUTTO VERDE**, coi casi
  nuovi dentro;
- `RAPPORTO-lock-gpu.md` con: il timeout scelto per l'attesa e **perche'**, la
  prova che il secondo processo aspetta davvero (con i tempi, non a parole), la
  prova che il test dell'imbottitura diventa rosso togliendo la correzione, e il
  budget nuovo in caratteri;
- `DEFINIZIONI` intatta, e dichiaralo.

Scrivi il rapporto **appena hai i numeri**, non alla fine.
