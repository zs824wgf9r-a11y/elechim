# Incarico: estrarre fatti senza un LLM

Scritto il 18 agosto 2026, dopo che tre esperimenti hanno mostrato che il
problema non e' il prompt.

## Perche'

Misurato stanotte, in ordine:

1. Il deriver di Honcho con `qwen3:8b` **attribuisce al proprietario le frasi
   dell'assistente**: tasso di errore **36,6%** col prompt originale, e sulla
   conversazione piu' lunga **73,7%**. Le etichette `[user]`/`[assistant]` erano
   presenti e sono state ignorate.
2. L'istruzione di lingua (che portava l'italiano dal 65,7% al 100%) **peggiora
   l'attribuzione**: dal 36,6% al **55,6%**, e all'**82,6%** su quella
   conversazione. Le risposte dell'assistente sono in italiano e lunghe, quindi
   imporre l'italiano ha spinto il modello ad appoggiarsi ancora di piu' su di esse.
3. Filtrando ai soli messaggi `[user]` il modello **non termina piu'**: su 424
   caratteri di input genera oltre 600 token senza fermarsi (`done_reason:
   length`) e senza tetto scade dopo **600 secondi**.

Tre correzioni, tre modi diversi di rompersi. **Il problema non e' come si chiede,
e' chi lo fa.**

## L'idea, ed e' il rovesciamento della premessa

Oggi si chiede a un modello di **leggere una conversazione e decidere cosa e' un
fatto**. Da li' vengono l'invenzione e l'attribuzione sbagliata.

L'alternativa: **il fatto e' una frase del proprietario, con la sua data**. Non
una parafrasi, non una sintesi — la sua frase. Zero allucinazioni e zero
attribuzioni sbagliate **per costruzione**, non per obbedienza.

E' lo stesso principio delle tabelle recintate in `sbobina.py`: non si chiede
all'LLM di non rovinare i numeri, glieli si toglie dalle mani.

## Il lavoro

`estrazione_deterministica.py`, **senza nessun modello e senza dipendenze nuove**.

1. **Solo i messaggi `[user]`.** L'attribuzione e' risolta qui, e non si discute piu'.
2. **Taglia in frasi.** Attento alle abbreviazioni e ai numeri decimali: una
   regola ingenua sul punto spezza `3.5` e `ecc.`.
3. **Tieni le frasi che affermano qualcosa sul parlante.** Criteri possibili, e
   **li scegli e li dichiari tu**: prima persona (`uso`, `ho`, `voglio`,
   `preferisco`, `sto`, `mi serve`), o verbi di decisione (`useremo`, `facciamo`,
   `ho deciso`). **Scarta domande e imperativi**: «puoi farmi X?» non e' un fatto
   sul proprietario, ed e' il falso positivo piu' probabile.
4. **Ogni fatto porta**: il testo verbatim, il timestamp del messaggio (la data
   e' gratis, e i tre esperimenti con l'LLM ne hanno prodotte **zero** su 35),
   e l'identificatore del messaggio d'origine.
5. **Niente normalizzazione, niente riscrittura.** Se la frase e' sgrammaticata
   resta sgrammaticata: e' quello che ha scritto lui.

## Come si misura, e il confronto e' il punto

Stesso campione dei tre esperimenti precedenti (i `.db` in `archivio/`), cosi'
i numeri si mettono in tabella accanto agli altri:

| misura | perche' |
|---|---|
| fatti per conversazione | confrontabile con le 8/10/17 osservazioni dell'LLM |
| **tasso di attribuzione sbagliata** | deve essere **0 per costruzione**: verificalo con `misura_attribuzioni.py`, non darlo per scontato |
| fatti con data | l'LLM ne ha prodotti 0 su 35; qui dovrebbero essere tutti |
| frasi scartate, e **per quale regola** | e' il numero che dice se il filtro e' troppo stretto |
| tempo per conversazione | l'LLM impiega ~115s; qui dovrebbe essere millisecondi |

**Il rischio vero e' il silenzio**: un estrattore troppo stretto produce zero
fatti e sembra funzionare. Se una conversazione da 54 messaggi da' due fatti,
**dillo forte**, non seppellirlo in una media.

## Il file da far leggere al proprietario

Come per le prove precedenti: i fatti estratti in `stato/` (ignorato da git),
con accanto il messaggio da cui vengono. **Il percorso nel rapporto, e non
aprirlo.** Il giudizio su cosa e' un fatto utile e' suo.

## Cosa NON fare

- **Nessun modello**, nemmeno per un pezzetto. Nessuna chiamata a ollama.
- **Nessuna dipendenza nuova**: niente spaCy, niente GLiNER, niente
  sentence-transformers. Libreria standard. Se pensi che senza spaCy non si
  possa fare, **scrivilo nel rapporto** invece di installarlo: sapere che serve
  e' un risultato.
- Non leggere `archivio/`, non stamparne pezzi, non citarne nel rapporto.
- Non toccare `energia.py`, `sbobina.py`, `documenti.py`, `guardiano.py`,
  `lavoro.py`, i loro collaudi, `gateway.py`, `mac/`, `unita/`, gli altri
  `INCARICO-*` e `RAPPORTO-*`. **`DEFINIZIONI` non si tocca.**

## Criterio di uscita

- `estrazione_deterministica.py` gira in millisecondi e produce i fatti;
- `RAPPORTO-estrazione-deterministica.md` con la tabella delle misure **accanto
  a quelle dei tre esperimenti con l'LLM**, le regole scelte e il perche', le
  frasi scartate per regola, e il percorso del file da leggere;
- un verdetto secco: **quanti fatti veri per conversazione**, e se il numero e'
  abbastanza da reggere una memoria o se serve altro.

Crea il file del rapporto **prima** di cominciare, coi soli titoli.
