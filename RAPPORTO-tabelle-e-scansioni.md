# Rapporto — tabelle false e scansioni mute

Incarico: `INCARICO-tabelle-e-scansioni.md`, eseguito il 15 agosto 2026.

## Cosa e' stato fatto

1. **Reprodotto il collaudo rosso.** `prova_documenti.py` falliva con
   `tabelle_conservate == 2` perche' il test scriveva i PDF in `documenti/in/`
   senza lock e il servizio `elechim-documenti.service` (path unit) partiva in
   parallelo, duplicando la pagina 5 nel markdown. Il codice di rilevamento
   tabelle sul sintetico era gia' corretto: il problema era nel collaudo.
   Risolto facendo acquisire il lock `_coda_esclusiva()` *prima* di creare i
   PDF e finche' si macina.

2. **Ridotti i falsi positivi sulle tabelle.** `_e_tabella` adesso richiede
   anche una densita' minima di cifre quando trova due o piu' gap ampi:
   la prosa a due colonne ha un solo vuoto ampio e densita' < 1%, una tabella
   ha piu' gap ed e' ricca di cifre.

   - Soglia aggiunta: `SOGLIA_DENSITA_TABELLA = 0.10`.
   - Il collaudo sintetico trova ancora `tabelle_conservate == 1`.
   - Su `Basic_Statistics_2007.pdf` i falsi positivi passano da **42 a 13**.

3. **Aggiunta la classificazione e il rifiuto onesto per le scansioni.**
   - `caratteri_pagina()` estrae i caratteri non-spazio per pagina con una
     sola chiamata `pdftotext -layout`.
   - `classifica()` calcola mediana, media, livello di testo e presenza di
     outline.
   - Se la mediana di caratteri per pagina e' sotto `SOGLIA_CARATTERI_PAGINA =
     100`, il documento viene scartato in `documenti/falliti/` con un file
     `.ragione.txt` e non produce note.

4. **Aggiornato il rapporto di copertura.** Il dizionario del rapporto include
   ora `corsia` (`veloce`/`scansione`) e `caratteri_per_pagina_mediana`;
   `formatta_rapporto()` li stampa.

5. **Aggiunto il caso scansione al collaudo.** `prova_documenti.py` genera una
   scansione sintetica rasterizzando il PDF con `pdftoppm` e ricomponendo con
   Pillow, verifica che venga rifiutata, che finisca in `falliti/` con la
   ragione e che non lasci note nel vault.

## Misure usate per decidere la soglia

| documento | pagine | caratteri totali | mediana caratteri/pagina | esito |
|-----------|--------|------------------|--------------------------|-------|
| PDF sintetico `prova-due-colonne.pdf` | 11 | 7.835 | 770 | corsia veloce |
| `DSML.pdf` | 533 | 848.711 | 1.606 | corsia veloce |
| scansione sintetica da `pdftoppm`+Pillow | 11 | 0 | 0 | **rifiutata** |

La soglia di 100 caratteri/pagina e' molto al di sotto del sintetico e di
DSML, e molto al di sopra di una scansione senza livello di testo.

## Collaudo

```
$ .venv/bin/python prova_documenti.py
...
TUTTO VERDE
```

I due nuovi casi sono dentro: tabelle sul sintetico e scansione rifiutata.

## DEFINIZIONI

Non toccate. Confronto AST delle descrizioni dei tool:

- `strumenti.py`: `85675fce242a7d1df8ee9dd24dd170abec7969d4231661da22168b1383564677`
- `mac/strumenti.py`: `85675fce242a7d1df8ee9dd24dd170abec7969d4231661da22168b1383564677`

Identiche.

## File modificati

- `documenti.py`
- `prova_documenti.py`

## Cosa e' rimasto fuori (perche' fuori confine o perche' serve un altro giro)

- **Numero di colonne**: `classifica()` non lo stima ancora. Servira' quando ci
  sara' una seconda corsia che gestisce layout diversi, ma oggi la corsia
  veloce e' l'unica in esercizio.
- **Tabelle con righe di intestazione di puro testo**: la soglia sulla densita'
  di cifre potrebbe scartarle. Per ora e' misurata sui casi reali e il
  bilancio e' accettabile (13 falsi positivi su `Basic_Statistics_2007.pdf`).
- **OCR / Marker**: non e' stato toccato. Una scansione viene rifiutata, non
  passata a un motore OCR.
- `sbobina.py`, `README.md`, `AGENTS.md`, `mac/`, `strumenti.py`, `gateway.py`
  e git sono stati lasciati intatti, come richiesto.

## Decisioni da confermare

1. **Soglia caratteri/pagina = 100** va bene come punto di rifiuto per tutti i
   PDF che arriveranno, o va resa configurabile per classe di documento?
2. **Soglia densita' tabelle = 0.10** e' sufficientemente conservativa per i
   documenti del proprietario, o va abbassata per tabelle con intestazioni
   testuali?
3. Il percorso `documenti/falliti/` e' corretto anche per i rifiuti lanciati
   direttamente da `processa()` (non da `_macina()`)?
