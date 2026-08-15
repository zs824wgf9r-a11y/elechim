# Incarico: fase 3, memoria (Honcho + embedding)

Scritto il 15 agosto 2026. **Non iniziare finche' la fase 4 non e' consegnata.**
Leggi prima `AGENTS.md` e `TOOL-DEFINITIVI.md`.

## Cosa deve esistere alla fine

Un modulo `memoria.py` in `~/assistente/` che espone **due funzioni**, e sono le
stesse due che un giorno staranno dietro i tool `ricorda` e `salva`:

```python
def ricorda(query: str) -> dict   # passaggi pertinenti + riferimento, compressi
def salva(testo: str, titolo: str | None = None) -> dict  # dove l'ha messo
```

**Non collegarle a `DEFINIZIONI` e non toccare `strumenti.py`.** Il collegamento
si fa dopo, in un colpo solo, quando anche la fase 4 e' pronta: la procedura sta
in `TOOL-DEFINITIVI.md` e la decide il proprietario. Qui si costruisce il motore, non il
cruscotto.

## L'infrastruttura

- **Postgres con pgvector** e **Redis**, entrambi come **quadlet podman** in
  `~/.config/containers/systemd/`, sul modello di `searxng.container` che e' gia'
  li' e funziona. Il precedente vale come regola: un servizio con
  `ExecStart=podman start -a` su un container gia' avviato fallisce con 125 in
  loop, il quadlet possiede il container per intero. In ascolto **solo su
  `127.0.0.1`**.
- **Honcho**: leggi la sua documentazione attuale prima di decidere come
  installarlo (hai `web-forager`), non andare a memoria. Ha bisogno di Postgres,
  Redis, un endpoint di embedding e un LLM di ingestion.
- **Embedding: `bge-m3` via ollama** (`ollama pull bge-m3`), che e' gia' un
  servizio attivo. Buono in italiano. **`keep_alive` corto**, o mangia VRAM che
  serve altrove.
- **LLM di ingestion: Qwen3 4B sul 4060 Ti, via ollama.** Per l'output
  strutturato usa il **JSON schema** di ollama (`format`), mai chiedere il JSON a
  parole.

## Il vincolo che non si negozia

**L'LLM di ingestion non deve MAI essere il modello del Mac.** Ogni chiamata
sfratterebbe la conversazione dall'unica slot di cache di TurboFieldfare, e il
messaggio dopo pagherebbe il prefill pieno — minuti invece di secondi. Se in
qualche punto della configurazione di Honcho compare un endpoint OpenAI-compatibile
e la scelta comoda sembra `127.0.0.1:8080`, **quella e' la porta del Mac: e'
l'errore**. L'ingestion va su ollama, in locale.

## VRAM — il conto e' stretto

8188 MiB in tutto, e ci vivono gia': X11+plasma 1353, qwen3-vl:4b **4529**,
whisper 1835. Insieme sono 7717, il 94%. `bge-m3` e il modello di ingestion
**non ci stanno** accanto a quelli.

Quindi: `keep_alive` corto su entrambi, **lock GPU** (c'e' gia' in
`gateway.py`, riusalo, non farne un secondo), e la possibilita' di forzare
`bge-m3` su CPU con `num_gpu: 0` quando la scheda serve. Misura il consumo vero
con `nvidia-smi` e **scrivi i numeri nel README**: le stime a memoria su questa
macchina si sono gia' rivelate sbagliate di 1000 MiB.

## Cosa fa `ricorda`, e perche' e' uno solo

Fan-out su tre archivi, fatto **dal fisso**: i fatti sul proprietario in Honcho, le
note del vault `~/Obsidian`, i documenti ingeriti dalla fase 4. Il modello non
sceglie l'archivio — chiedere a un 4B di scegliere significa chiedergli di
sbagliare, e ogni scelta sbagliata costa un giro di tool da 10-30s.

In uscita: **passaggi compressi con il loro riferimento**, non documenti interi.
Vale lo stesso tetto di `cerca` (~1400 caratteri): il Mac maneggia handle, non
contenuti. Guarda come `strumenti.py` comprime le pagine web — la compressione
estrattiva senza LLM li' ha funzionato meglio del riassunto con modello.

**Come fondere i tre archivi: Reciprocal Rank Fusion.** Il fan-out produce tre
elenchi ordinati con punteggi che **non sono confrontabili** fra loro — una
distanza coseno di pgvector e un punteggio full-text non stanno sulla stessa
scala, e normalizzarli a mano e' il punto in cui la ricerca ibrida di solito si
rompe. RRF risolve ignorando i punteggi e usando solo la **posizione**:

```python
punteggio(doc) = somma su ogni elenco di  1 / (k + posizione(doc))   # k ~ 60
```

Venti righe, nessuna dipendenza, nessuna taratura per archivio. Va misurato
contro l'alternativa banale (concatenare e troncare) sul collaudo sintetico.

Riferimento esterno, guardato il 16 agosto 2026: **SurfSense**
(`github.com/MODSetter/SurfSense`, Apache 2.0 tranne `app/proprietary/` che e'
BSL 1.1 e da cui **non si prende niente**) fa esattamente questo — pgvector piu'
full-text fusi con RRF, sopra Postgres e Redis, cioe' lo stesso stack prescritto
qui. Non si adotta: e' un'applicazione da sette servizi con la sua interfaccia
web, e vuole essere il cervello, che qui e' il Mac. Ma la sua esistenza dice che
l'architettura scelta e' quella giusta, e il suo **RAG a due livelli**
(riassunto per documento + embedding per chunk) e' la stessa cosa che
`PIANO-DOCUMENTI.md` chiama "il Mac vede una sintesi da ~300 token e un handle":
ci sono arrivati per accuratezza, noi per il prefill.

## Cosa fa `salva`

Scrive una nota o registra un fatto, e **risponde dove l'ha messo**. La
destinazione la decide il fisso secondo le regole dell'autogestione — contano i
tag nel frontmatter, non le cartelle — mai il modello, e **mai chiedendo il
permesso**.

Divisione del lavoro fra i due archivi, che e' la parte concettuale di questa
fase:

- in **Honcho** va il fatto sulla persona, **con una data**: "dal 1 agosto:
  2.400 kcal, 180g proteine". Fra tre mesi verra' **superato, non cancellato**:
  un fatto cancellato porta via il perche' del cambiamento.
- nel **vault** va il contenuto: note, appunti, documenti.

Due archivi, due mestieri, un solo database.

## Come si prova — vale la regola di `AGENTS.md`

**Il contenuto delle conversazioni del proprietario non entra nel tuo contesto.**
In `archivio/` ci sono conversazioni vere: **non aprirle, non stamparle, non
importarle come prova.**

Il collaudo si fa con **conversazioni sintetiche scritte da te**, con fatti
inventati e verificabili ("Marco corre il martedi'", "dal 3 marzo beve caffe'
decaffeinato"). Cosi' le asserzioni sono esatte:

1. `salva` di un fatto noto, poi `ricorda` con una domanda formulata **in modo
   diverso** dal fatto: deve tornare lo stesso. E' la ricerca ibrida che si sta
   provando, non un `LIKE`.
2. Un fatto **superato** da uno piu' recente: `ricorda` deve dare il nuovo e
   **conservare** il vecchio con la sua data.
3. `ricorda` su qualcosa che non c'e' torna vuoto, **non inventa**.
4. Il fan-out trova un fatto in Honcho **e** una nota nel vault nella stessa
   risposta, con riferimenti distinti.
5. Postgres e Redis risalgono da soli dopo un riavvio del fisso, e dopo una
   **sospensione** (che qui e' il caso normale: il fisso dorme da solo dopo tre
   ore). Provalo davvero con `systemctl --user restart`, non a ragionamento.

L'importazione dell'archivio vero e' l'ultimo passo e **non lo fai tu**: lascia
uno script pronto e documentato, lo lancia il proprietario in locale.

## Quando hai finito

Aggiorna `README.md` con la fase 3: architettura, i numeri di VRAM misurati, la
divisione Honcho/vault, e come si lancia l'importazione dell'archivio. Nel
rapporto finale elenca cosa hai lasciato indietro e le decisioni da far
confermare.
