# Rapporto: proteggere le formule nella sbobina

17 agosto 2026, dopo l'esecuzione di `INCARICO-sbobina-formule.md`.
Codice in `sbobina.py`, collaudo in `prova_sbobina.py` (TUTTO VERDE).
`prova_documenti.py` e' rimasto verde: i marcatori di `documenti.py` non sono
stati toccati.

## Cosa e' stato costruito

1. **Un solo `RE_BLOCCO` per tabelle e formule**, con un gruppo di cattura
   `(tabella|formula)` che sceglie il segnaposto giusto.
2. **Segnaposto dedicato per le formule** (`SEGNAPOSTO_FORMULA`), diverso da
   quello delle tabelle: il modello legge testo coerente col contenuto che ha
   di fronte.
3. **Lista unica di blocchi** in `_chunk_fonte`: ogni recinto e' un elemento di
   `blocchi` con `(tipo, originale)`. Il ripristino usa una sola regex
   `__BLOCCO_(\d+)__+` per tutti i tipi.
4. **Imbottitura misurata sul segnaposto giusto**: ogni marca interna si
   allunga fino alla lunghezza del segnaposto che quel blocco ricevera'
   davvero (`SEGNAPOSTI[tipo]`), non a una lunghezza unica.
5. **Materiale originale distinto per tipo**: ogni recinto riportato verbatim
   porta l'intestazione `**Tabella**` o `**Formula**`, in ordine di documento.
6. **Avviso di sezione in gran parte recinti**: quando la frazione di caratteri
   sostituiti da segnaposto supera la soglia, la nota lo dichiara invece di
   fingere una spiegazione completa.

## Scelta di struttura: una lista sola, non due parallele

Seguito il consiglio dell'incarico. Una lista sola con `(tipo, originale)`
toglie la simmetria fra due contatori, due regex di ripristino e due passaggi
sul testo. Il rischio di applicare due regex in sequenza — che si pestano i
piedi sull'imbottitura del punto 2 — e' eliminato: `RE_BLOCCO` scorre la fonte
una volta sola, `finditer` mantiene l'ordine del documento, e il ripristino e'
generico.

## Misura A: quanta parte della sezione diventa segnaposto

Misurato sulle **223 sezioni** di `dsml`, contando come `RE_BLOCCO`
(tabelle + formule) i caratteri che `_dividi` sostituisce con segnaposto.

| metrica | valore |
|---|---|
| sezioni | 223 |
| mediana | 17,73% |
| 90° percentile | 33,72% |
| caso peggiore | 78,38% |
| sopra soglia 50% | 8 sezioni |

**Soglia scelta: 50%**. Motivo: oltre la meta' della sezione e' verbatim,
quindi una spiegazione generale e' per forza incompleta. Con questa soglia
solo 8 sezioni su 223 ricevono l'avviso, che non diventa rumore di sottofondo.

**Comportamento deciso**: quando `frazione_segnaposti > 0,50`, `scrivi_nota`
aggiunge `avviso_segnaposti: true` nel frontmatter e questo avviso sotto
"La spiegazione":

> ⚠ Questa sezione e' in gran parte formule e tabelle: la spiegazione copre
> solo la prosa.

Il campo `frazione_segnaposti` viene scritto sempre, perche' il numero serve
anche quando non scatta l'avviso.

## Misura B: `CAR_PER_TOKEN` dopo la sostituzione

Rimisurato su cinque sezioni dense dopo aver sostituito tabelle e formule con
i segnaposti. Modello: `qwen3:8b`. Per ogni sezione: caratteri del testo che
va al modello divisi per `prompt_eval_count` riportato da ollama (token di
input totali, prompt incluso).

| sezione | caratteri | token | car/token |
|---|---:|---:|---:|
| 59 | 16.832 | 6.116 | 2,7521 |
| 105 | 16.613 | 5.961 | 2,7869 |
| 102 | 16.376 | 5.967 | 2,7444 |
| 97 | 15.737 | 5.513 | 2,8545 |
| 55 | 15.558 | 4.640 | 3,3530 |

**Caso peggiore (piu' basso): 2,7444 car/token** nella sezione 102.

Se si sottrae il costo fisso del prompt (`prompt_eval_count` del solo
`PROMPT_SPIEGAZIONE` = 81 token), il caso peggiore sale a circa **2,78**
car/token, ma resta sotto il 3,06 attuale.

**Raccomandazione**: non alzare `CAR_PER_TOKEN`. La nuova misura e' piu'
bassa, non piu' alta: togliere i recinti non ha trasformato il testo in prosa
quasi pura, perche' resta molta matematica inline e i segnaposti lunghi
tokenizzano peggio della prosa. Tenere il valore attuale di **3,06** resta
la scelta conservativa e sicura; un budget piu' generoso rischierebbe di far
tagliare la fonte a ollama in silenzio.

## Criteri di uscita

- `prova_sbobina.py` **TUTTO VERDE**, con i sei casi dell'incarico e il test
  aggiuntivo sull'avviso di sezione in gran parte recinti.
- `prova_documenti.py` **verde**: i marcatori non sono stati modificati.
- `DEFINIZIONI` **intatta e non toccata**.
- Nessun lancio di `sbobina.py` sul libro vero, nessuna nota generata nel
  vault da questa sessione.
