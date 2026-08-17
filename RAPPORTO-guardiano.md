# Rapporto: il guardiano — sorvegliare un agente invece di sperare

Scritto il 17 agosto 2026 sera, a incarico `INCARICO-guardiano.md` appena
finito. Il motivo: tre sessioni rimaste piantate 5h57m su un endpoint morto,
`timeout` che mandava SIGTERM a processi senza handler, e 4 rapporti su 8 mai
scritti. La causa di fondo (opencode #40330) e' chiusa *not planned*: il
guardiano e' l'unica difesa.

**Stato: consegnato.** `prova_guardiano.py` e' TUTTO VERDE (7 casi su 7, finto
motore, nessuna quota bruciata), la prova vera con `agy` e' andata bene al
primo colpo, `DEFINIZIONI` intatta (verifica in fondo).

## Cosa c'e'

- **`guardiano.py`** — il cuore, scritto una volta: `esegui(incarico, motore,
  file_attesi, silenzio_max, *, nome, durata_max, cartella_diario,
  attese_escalation, **kwargs_motore) -> Esito`. Piu' due adattatori sottili
  che normalizzano il flusso in tre fatti: *e' vivo*, *ha finito*, *ha
  fallito*.
  - `AdattatoreAgy`: NDJSON su stdout (`--output-format stream-json`, chiave
    **`event`**, non `type`). L'abort gentile e' la chiusura dello stdin.
  - `AdattatoreOpencode`: SSE da `GET /event` + REST di controllo. Il flusso
    si apre **prima** del prompt (`prompt_async` solo dopo `server.connected`).
    I permessi ricevono risposta secondo una **politica dichiarata**
    (`politica_permessi`: dict tipo->risposta con `"*"` di ripiego, o
    callable). La fine turno NON e' `session.idle`: si conferma interrogando
    `GET /session/:id/message` (regola 2), con ricontrollo a tempo ogni 3s.
- **`prova_guardiano.py`** — i sette casi dell'incarico, tutti sul finto
  motore (uno script che emette righe da un copione JSON, pause comprese; per
  opencode un server SSE+REST in-process). Leggere e decidere sono separati:
  i casi patologici si riproducono in secondi, senza bruciare quota.

## Il silenzio_max: misurato, non inventato

**Misura sulla prova vera** (agy, `--mode plan`, `gemini-3.7-flash-low`,
prompt banale, 8,8s totali, diario `stato/guardiano/prova-vera-agy.jsonl`):

| tratto | gap |
|---|---|
| avvio -> `init` (boot del processo) | **5,57s** |
| fra `step_update` durante il lavoro | 0,2 – **2,20s** |
| run completo, 7 eventi | 8,8s |

Un multiplo generoso del gap misurato (2,2s) darebbe 30-60s — **sbagliato**:
ucciderebbe le chiamate lunghe legittime. Il silenzio che conta e' quello di
**una singola chiamata al modello**, ed entrambi i motori dichiarano il loro
budget per chiamata: `agy --print-timeout` default **5m** (e la issue #266
mostra che 5 minuti di thinking su una chiamata succedono davvero), opencode
`provider.options.timeout` default **300s**. Quindi:

```
SILENZIO_MAX = 900s   # 3 x il budget di una chiamata (300s), multiplo generoso
```

Sulle 5h57m di stallo il guardiano sarebbe scattato a **15 minuti**: 5h42m
risparmiate. E' un parametro di `esegui`: un incarico veloce puo' stringerlo.
**Limite dichiarato della misura**: la prova vera e' UNA, corta, su un modello
flash; il pavimento di 900s viene dai budget dichiarati dei motori, non da
statistica nostra. Se un giorno i diari accumulati diranno altro, si
ricalcola — i gap sono gia' in ogni diario (`silenzio_s`).

## I tempi dell'escalation

A gradini, ognuno col suo tempo (`ATTESA_ABORT=10s`, `ATTESA_TERM=15s`,
`ATTESA_KILL=5s`):

1. silenzio oltre `silenzio_max` → **abort** (stdin chiuso su agy,
   `POST /session/:id/abort` su opencode);
2. non muore entro 10s → **SIGTERM**;
3. non muore entro 15s → **SIGKILL**, e lo dice.

Il vecchio `timeout -k 60` dava 60s *alla cieca*; il guardiano non e' cieco —
vede il flusso e sa subito se l'abort ha prodotto eventi di chiusura. Caso
patologico (SIGTERM ignorato, misurato nel collaudo): dall'ultimo segno di
vita alla morte `silenzio_max + ~26s`. Nel collaudo con attese corte:
silenzio→sigterm in **3,7s**, silenzio→sigkill in **5,1s**.

C'e' anche `durata_max` (opzionale, spenta di default): il caso «retry
infinito con eventi regolari» — la #40330 pubblica `session.status: retry`
ogni 30s — **riarma l'orologio del silenzio** e senza un tetto assoluto il
guardiano non lo vede. E' il motivo per cui il parametro esiste.

## Il formato del diario

`stato/guardiano/<nome>.jsonl`, un rigo per evento normalizzato, flush a ogni
riga (deve sopravvivere alla morte del sorvegliato):

```json
{"t": 7.978, "ts": "2026-08-17T22:39:11", "fatto": "vivo", "tipo": "step_update",
 "silenzio_s": 2.203, "dettaglio": {"step_index": 2, "state": "ACTIVE",
 "step_type": "agent_response", "text_delta_caratteri": 83}}
```

- `t` secondi dall'avvio, `silenzio_s` secondi dall'ultimo evento vivo —
  e' la misura dei gap, gia' pronta per ricalcolare `silenzio_max`;
- `fatto`: `avvio` | `vivo` | `finito` | `fallito` | `chiuso` | `escalation` |
  `guardiano` | `esito` (sempre l'ultimo rigo, con motivo, escalation,
  file mancanti, exit code);
- l'evento `finito` porta l'**output INTEGRALE**: le conclusioni sono
  l'ultima cosa che una sessione scrive e la prima che si perde — nel diario
  non si perdono.

## Le tre regole, dove vivono

1. **Tre segnali insieme** (nel cuore): stato finale non d'errore + output
   non vuoto + file attesi esistenti. Casi 2 e 3 del collaudo: `SUCCESS` con
   `response` vuota → **fallito**; `SUCCESS` con file mancanti → **fallito**.
2. **`session.idle` non basta** (adattatore opencode): finito solo se
   `/message` mostra un assistant completato con testo; altrimenti ricontrollo
   ogni 3s. Il ricontrollo fallito **non** riarma l'orologio del silenzio
   (non e' un segno di vita del motore).
3. **Escalation a gradini** (nel cuore): sopra. Caso 5: un processo che
   ignora SIGTERM arriva a SIGKILL e l'esito lo dichiara.

## La prova vera con agy

Una sola, corta, come da incarico: prompt banale in `--mode plan`,
`gemini-3.7-flash-low`, cartella di scarto. Esito: **finito_bene**, 8,8s,
exit 0, output 402 caratteri. Il flusso vero coincide col finto: `init`
(56 strumenti, `permission_mode: request-review`), 5 `step_update`
(`user_input`, uno di tipo `unknown` — passato through senza rompere,
`agent_response` ACTIVE→DONE con `text_delta`, `checkpoint`), `result`
SUCCESS con la risposta integrale nel diario. Nessuna prova vera con
opencode, come ordinato.

## Cosa il guardiano NON puo' fare (l'onesta' prima delle funzioni)

- **Il retry infinito "parlante"** (#40330: un `session.status: retry` ogni
  30s) somiglia a un segno di vita. Senza `durata_max` non lo si vede: se si
  usa opencode su endpoint instabili, **passare sempre `durata_max`**.
- **L'abort di agy e' una speranza, non un fatto**: chiudere lo stdin su un
  run appeso non e' documentato (#779); la rete vera e' SIGTERM→SIGKILL.
- **Niente riconnessione SSE**: se lo stream `/event` cade, il run viene
  dichiarato fallito anche se il server lavora ancora. Da aggiungere quando
  opencode sara' in esercizio vero.
- **La conferma di fine opencode assume la forma** `[{info, parts}]` con
  `time.completed` e parti `text`: verificata sul finto, **non sul server
  vero** (nessuna prova vera con opencode oggi). Se la forma differisse, il
  guardiano non dichiarerebbe mai finito: conservativo, ma da verificare.
- **Un guardiano alla volta per macchina non c'e'**: due `esegui` sullo
  stesso `opencode serve` condividono il flusso `/event` e funzionano (il
  filtro per `sessionID` e' nel client), ma non e' collaudato.
- **Non sa distinguere un lavoro lungo da uno stallo dentro una singola
  chiamata**: e' il prezzo del silenzio come unico orologio. 900s e' il
  compromesso dichiarato; sotto quello, niente intervento.

## DEFINIZIONI

Intatta: confronto AST fra `strumenti.py` e `mac/strumenti.py` identico
(sha256 `65badc6424105d76`), e `git diff` su `strumenti.py`,
`mac/strumenti.py`, `gateway.py`, `energia.py`, `sbobina.py`, `documenti.py`
vuoto. File nuovi: `guardiano.py`, `prova_guardiano.py`, questo rapporto.

## Come si usa

```python
import guardiano

esito = guardiano.esegui(
    "Leggi INCARICO-x.md ed eseguilo", "agy",
    file_attesi=["RAPPORTO-x.md"],
    silenzio_max=900,          # default; stringere per incarichi veloci
    mode="plan", model="gemini-3.7-flash-low", print_timeout="10m",
    cwd=".",                   # kwargs dell'adattatore
)
if not esito.ok:
    ...  # esito.motivo, esito.escalation, esito.file_mancanti, esito.diario
```

Per opencode: `guardiano.esegui(incarico, "opencode", ...,
politica_permessi={"*": "reject", "webfetch": "once"})` — avvia lui
`opencode serve` su porta libera e lo spegne alla fine (niente unit systemd:
l'integrazione viene dopo, da incarico).
