# RAPPORTO-lingua.md

## Obiettivo

Verificare se aggiungere un'istruzione di lingua esplicita al prompt del deriver
Honcho chiude la deriva verso l'inglese su conversazioni italiane. Una sola
variabile per confronto: il prompt. Stesso modello, stesso campione di 90
messaggi, stesso criterio di rilevamento lingua, stessa temperatura.

## Metodo

- Prompt base: `minimal_deriver_prompt` di Honcho, revisione
  `f88892b0715adbd852c6b846532cc39a335d2de4`, con l'aggiunta dell'istruzione di
  formato "bullet list, one observation per line" gia' usata in
  `prova_estrazione.py`.
- Modello: `qwen3:8b` su ollama del fisso (`127.0.0.1:11434`).
- Temperatura: `0.0`; seed: `42`.
- Campione: 3 conversazioni in `archivio/`, 90 messaggi totali (6, 54, 30).
- Lock GPU e blocco sospensione via `energia.riserva_gpu` e `energia.blocco`.
- Criterio di lingua: parole funzione italiane/inglesi; italiano se >=2 parole
  italiane e rapporto it/en > 1.5; inglese se >=2 parole inglesi e en/it > 1.5;
  altrimenti misto/indeterminato (identico a `prova_estrazione.py`).
- Script: `prova_estrazione_lingua.py` (variante di `prova_estrazione.py`).
- Output: `stato/prova-estrazione-lingua/` (ignorato da git).

### Varianti testate

| variante | istruzione aggiunta |
|---|---|
| A | `Write every conclusion in the same language as the messages.` |
| B | `Scrivi tutte le conclusioni in italiano, la stessa lingua dei messaggi.` |

## Risultati prima (prompt originale, da RAPPORTO-prova-estrazione.md)

| misura | valore |
|---|---|
| conversazioni | 3 |
| messaggi totali | 90 |
| osservazioni totali | 35 |
| osservazioni in italiano | 23 (65,7%) |
| osservazioni in inglese | 4 (11,4%) |
| osservazioni miste/indeterminate | 8 (22,9%) |
| prompt tokens totali | 5382 |
| output tokens totali | 2919 |
| tempo totale | 343,97 s |

Distribuzione per conversazione:

| conversazione | messaggi | osservazioni | italiano | inglese | misto |
|---|---:|---:|---:|---:|---:|
| 6 messaggi | 6 | 10 | 0 | 4 | 6 |
| 54 messaggi | 54 | 8 | 8 | 0 | 0 |
| 30 messaggi | 30 | 17 | 15 | 0 | 2 |

## Risultati dopo (prompt + istruzione di lingua)

### Variante A

| misura | valore |
|---|---|
| conversazioni | 3 |
| messaggi totali | 90 |
| osservazioni totali | 39 |
| osservazioni in italiano | 27 (69,2%) |
| osservazioni in inglese | 11 (28,2%) |
| osservazioni miste/indeterminate | 1 (2,6%) |
| prompt tokens totali | 5406 |
| output tokens totali | 3154 |
| tempo totale | 358,46 s |

### Variante B

| misura | valore |
|---|---|
| conversazioni | 3 |
| messaggi totali | 90 |
| osservazioni totali | 30 |
| osservazioni in italiano | 30 (100,0%) |
| osservazioni in inglese | 0 (0,0%) |
| osservazioni miste/indeterminate | 0 (0,0%) |
| prompt tokens totali | 5420 |
| output tokens totali | 3243 |
| tempo totale | 368,48 s |

## Confronto per conversazione

| conversazione | prompt | osservazioni | italiano | inglese | misto |
|---|---:|---:|---:|---:|---:|
| 6 messaggi | originale | 10 | 0 | 4 | 6 |
| 6 messaggi | + A | 11 | 0 | 11 | 0 |
| 6 messaggi | + B | 1 | 1 | 0 | 0 |
| 54 messaggi | originale | 8 | 8 | 0 | 0 |
| 54 messaggi | + A | 10 | 10 | 0 | 0 |
| 54 messaggi | + B | 8 | 8 | 0 | 0 |
| 30 messaggi | originale | 17 | 15 | 0 | 2 |
| 30 messaggi | + A | 18 | 17 | 0 | 1 |
| 30 messaggi | + B | 21 | 21 | 0 | 0 |

## Verdetto

**Si', ma solo con la formulazione B e con un costo di recall.**

- Variante A (`Write every conclusion in the same language as the messages.`):
  **non chiude la crepa**. La conversazione corta (6 messaggi) peggiora: passa
  da 0/10 italiane a 0/11 italiane. Il totale sale solo dal 65,7% al 69,2%
  italiano.
- Variante B (`Scrivi tutte le conclusioni in italiano, la stessa lingua dei
  messaggi.`): **chiude la crepa sulla lingua**: 0 osservazioni in inglese, 0
  miste, 30/30 italiane (100% contro il 65,7% di prima).

Il numero decisivo e' nella conversazione da 6 messaggi: con il prompt
originale 0/10 osservazioni erano italiane; con la variante B 1/1 lo e'.
Tuttavia la variante B riduce drasticamente il numero di osservazioni estratte
nella stessa conversazione (da 10 a 1), quindi fissa la lingua a scapito del
recall. Per le altre due conversazioni il recall resta stabile o migliora.
