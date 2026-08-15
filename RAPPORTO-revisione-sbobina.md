# Rapporto di revisione — `sbobina.py` e `prova_sbobina.py`

Data: 16 agosto 2026  
Revisione fatta su: `sbobina.py`, `prova_sbobina.py`  
Riferimenti letti: `AGENTS.md`, `INCARICO-sbobina.md`, `sbobina.py`, `prova_sbobina.py`, `energia.py`, `voce.py`  
Modello usato nel collaudo: `qwen3:8b` (digest `500a1f067a9f`)

Il contenuto di `dsml` NON e' entrato nel contesto di questa sessione. Tutte le verifiche sono state fatte sul PDF sintetico di `prova_documenti.py`.

## Cosa e' cambiato

Ho modificato `sbobina.py` e `prova_sbobina.py` per risolvere i punti sollevati. Non ho toccato `documenti.py`, `prova_documenti.py`, `README.md`, `AGENTS.md`, `mac/`, `strumenti.py`, `gateway.py` ne' fatto operazioni git.

Modifiche principali:

1. **Divisione in chunk delle sezioni lunghe** (`_chunk_fonte`, `_riscrivi_chunked`).
2. **Verifica dei numeri sulla fonte completa**, tabelle incluse.
3. **Salvataggio dello stato dopo ogni sezione**, per una ripresa corretta.
4. **Lock GPU piu' robusto**: la bandiera `stato/gioco` viene rimossa anche se ollama e' impiantato.
5. **Timeout e retry sulle chiamate a ollama** (600 s, due tentativi).
6. **Gestione del content vuoto per `done_reason: length`**, con secondo tentativo e marcatura della sezione come saltata se persiste.
7. **Collaudo esteso** in `prova_sbobina.py` per la suddivisione e per i numeri di tabella.

## La domanda principale: saltare, alzare o dividere?

**Raccomandazione: dividere.**

Con `MAX_FONTE=9000` vengono saltate 46 sezioni su 223, cioe' il 20% del libro, e sono le piu' lunghe (quelle sopra il 90° percentile). Alzare la soglia a 20000 ne salverebbe 43, ma:

- con `num_ctx=8192` una fonte di 20000 caratteri (~5000 token) piu' l'output di 1800 token va vicino o oltre il limite, con alto rischio di `done_reason: length` e output vuoto;
- il prefill di un contesto piu' lungo costa piu' tempo reale e piu' VRAM su una scheda gia' stretta;
- una sezione di 36000 caratteri non starebbe comunque in 20000.

Dividere in chunk coerenti (paragrafi, poi frasi, poi parole) mantiene ogni passaggio entro il contesto, non perde sezioni, e lascia `MAX_FONTE=9000` come guardia di sicurezza. I chunk non spezzano i recinti di tabella: i recinti sono trattati come blocchi indivisibili.

Ho quindi implementato la divisione.

## Risposte ai sei punti di verifica

### (1) La verifica dei numeri produce falsi allarmi accettabili?

Sul PDF sintetico il collaudo ha dato **0 allarmi su tutte e 6 le sezioni**.

La funzione `verifica_numeri`:

- normalizza separatore decimale e zeri iniziali;
- non considera le parole ("due" non suona come "2");
- confronta ora il testo generato con la **fonte completa**, tabelle incluse.

Quest'ultima correzione era necessaria: prima confrontava con `per_modello` (la fonte privata delle tabelle), quindi una cifra citata correttamente dalla tabella sarebbe stata segnalata come non verificata. Ora i numeri delle tabelle non producono falsi allarmi.

I falsi allarmi legittimi che possono ancora capitare su `dsml` sono numeri **derivati** o **introdotti** dal modello (somme, percentuali ricalcolate, date, numeri di sezione): questi sono voluti, perche' e' meglio un allarme in piu' che un numero sbagliato che passa.

### (2) Le tabelle escono davvero verbatim e il modello non le vede mai?

Si'. `_dividi` isola i recinti `<!-- tabella pag N blocco M --> ... ```...```` e li sostituisce con il segnaposto prima di mandare il testo al modello. Il collaudo verifica che:

- il segnaposto arrivi al modello, non il blocco;
- il blocco originale finisca in "Materiale originale";
- tutte le 25 cifre di tabella siano presenti nel verbatim.

Il test passa. Il limite e' che questo vale per le tabelle **gia' marcate** da `documenti.py`. Se una tabella non e' racchiusa nel recinto, passerebbe al modello: quella e' una questione di `documenti.py`, non di `sbobina.py`.

### (3) La ripresa dopo interruzione funziona davvero a meta' di un lavoro da 3 ore?

Ora si', a livello di sezione.

Prima lo stato veniva salvato solo alla fine dell'intero ciclo. Ora `_salva_stato` viene chiamato **dopo ogni sezione** processata. Se il processo viene interrotto con `Ctrl-C` o un'eccezione, le sezioni gia' completate sono salvate e al riavvio si riparte dalla prossima.

Granularita': sezione, non chunk. Se una sezione lunga e' a meta' chunk, al riavvio quella sezione viene **rifatta dall'inizio**. Questo e' accettabile perche' le sezioni corte restano atomiche e non complicano lo stato; perdere al massimo una sezione e' preferibile a perdere ore di lavoro.

### (4) Il lock GPU sfratta e rimette qwen3-vl e whisper anche se il processo muore male o viene interrotto con Ctrl-C?

Con `Ctrl-C` o un'eccezione Python: **si'**, perche' il `finally` del context manager `gpu_della_sbobina`:

1. manda `keep_alive: 0` al modello della sbobina;
2. rimuove la bandiera `stato/gioco`;
3. chiama `energia.carica_vram()` per ricaricare `qwen3-vl:4b` e `whisper`.

Ho reso il passo 2 **indipendente** dal successo del passo 3: anche se ollama e' impiantato e `carica_vram()` fallisce, la bandiera viene comunque rimossa, quindi il fisso non resta bloccato in modalita' gioco.

Con `kill -9` (SIGKILL) o un crash del kernel: **no**, perche' il processo non esegue il `finally`. Resterebbe `stato/gioco` alzato. Questo e' un limite intrinseco di un lock file-based in user-space. Il blocco `stato/blocca/sbobina` viene pulito dagli orfani da `energia.blocchi_attivi()`, ma `stato/gioco` no. Se dovesse succedere, serve un intervento manuale (`/amici` o cancellare `stato/gioco`).

### (5) C'e' un timeout sulle chiamate a ollama?

Si'. `_chiedi` ha ora `timeout=600` (10 minuti) e **due tentativi** in caso di `Timeout` o `ConnectionError`. Se ollama non risponde dopo due tentativi, la sezione viene marcata come saltata con il motivo dell'errore, ma il lavoro continua.

600 secondi sono abbondanti per una sezione/chunk (il collaudo ha misurato 12-28 tok/s; 1800 token in output stanno sotto i 150 s anche al caso peggiore) ma impediscono un blocco eterno.

### (6) Cosa succede se ollama restituisce `content` vuoto con `done_reason: length`?

`_chiedi` logga `done_reason` e torna stringa vuota. `riscrivi` prova un **secondo tentativo con l'istruzione minima** (`PROMPT_MINIMO`), che consuma meno token di prompt e lascia piu' margine per la risposta. Se anche il secondo tentativo e' vuoto, la sezione viene marcata come saltata con `errore nel modello: RuntimeError: modello ha restituito spiegazione vuota per due volte`.

Lo stesso meccanismo vale per i punti chiave: se la chiamata per i punti torna vuota, si riprova con un prompt piu' corto; se persiste, si usa il placeholder `(punti chiave non disponibili)` senza far saltare la sezione.

## Metriche dal collaudo su `qwen3:8b`

Eseguito `.venv/bin/python prova_sbobina.py qwen3:8b`.

| sezione | secondi | tok/s | allarmi numeri |
|---------|---------|-------|----------------|
| 4 (tabella) | 27.2 | 28.7 | 0 |
| 1 | 43.6 | 13.8 | 0 |
| 2 | 70.4 | 13.3 | 0 |
| 3 | 62.9 | 13.6 | 0 |
| 5 | 107.1 | 12.6 | 0 |
| 6 | 44.9 | 13.2 | 0 |

- **Tempo totale 6 sezioni**: 356 s (~6 min).
- **VRAM durante la sbobina**: 6813 MiB su 8188 (X11 + `qwen3:8b`).
- **VRAM dopo `carica_vram`**: ~7239-7756 MiB (`qwen3-vl:4b` + `whisper` + residui).
- **Collaudo**: `COLLAUDO VERDE`.

Stima per `dsml` (223 sezioni):

- se si assumesse 60 s a sezione: ~3.7 h;
- con le 46 sezioni lunghe divise in 2-4 chunk ciascuna, il tempo reale sara' probabilmente piu' vicino a **4-5 ore**.

## Raccomandazioni prima del lancio su `dsml`

1. **Fai una prova su una singola sezione lunga di `dsml`** (una sopra il 95° percentile, ~16000-28000 caratteri) con `sbobina.py dsml --sezione N --modello qwen3:8b`, leggi solo le metriche e il percorso, non il testo. Verifica che la divisione in chunk sia ragionevole e che il tempo per chunk sia sostenibile.
2. **Avvia con `--tutte` solo se la prova singola regge.**
3. **Tieni d'occhio la VRAM**: durante la sbobina si usano ~6800 MiB; lo spazio e' stretto. Se arriva un'altra richiesta che usa la GPU mentre `stato/gioco` e' alzato, il gateway la rifiuta; se invece la bandiera dovesse restare alzata per un crash, i vocali/immagini resterebbero fermi.
4. **Non usare `kill -9`** sul processo della sbobina: preferisci `Ctrl-C` per avere il `finally`.
5. **Considera di alzare leggermente `MAX_FONTE`** solo se la divisione in 4+ chunk risulta troppo frammentata. Io lascerei 9000 e accetterei piu' chunk.

## Cosa non ho toccato

- `documenti.py`, `prova_documenti.py`, `README.md`, `AGENTS.md`, `mac/`, `strumenti.py`, `gateway.py`.
- `DEFINIZIONI` non e' stata toccata.
- Non ho letto il contenuto di `dsml` ne' delle note prodotte.

## Esito del collaudo

```
OK controllo dei numeri: prende i cambiati, tace sui legittimi.
OK suddivisione: chunk coerenti, recinti intatti.
...
COLLAUDO VERDE
```

Il codice, dopo le correzioni, regge per il lancio su `dsml`.
