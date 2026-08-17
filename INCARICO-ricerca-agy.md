# Incarico: `agy` come secondo agente, accanto a opencode

Scritto il 17 agosto 2026. Ricerca sul web: **non tocchi codice**, produci un solo
file, `RICERCA-agy.md`.

Contesto: oggi tre sessioni `opencode run` si sono piantate **5h57m** su un
endpoint morto, e la causa e' riconosciuta ma **chiusa come not planned**
(issue #40330: retry senza budget, `session.error` mai pubblicato, nessun flag
`--timeout`). Serve un secondo agente, sia come riserva sia per **eterogeneita' di
modelli**, che `RICERCA-stato-arte.md` capitolo 5 indica come l'unico «antidoto
universale» **misurato** contro la convergenza fra ruoli.

## Quello che gia' sappiamo, misurato in locale (non rifarlo)

`agy` versione **1.1.13**, installato, gia' autenticato (`~/.gemini/oauth_creds.json`).
Da `agy --help`:

- `--print` / `-p`: prompt singolo non interattivo. `--prompt` e' un alias.
- **`--print-timeout`, default `5m0s`** — timeout interno, che a opencode manca.
- `--output-format`: `text`, `json`, **`stream-json`**.
- `--json-schema`: schema per forzare output strutturato.
- `--add-dir`: aggiunge una cartella alla workspace (ripetibile).
- `--sandbox`: «run in a sandbox with terminal restrictions enabled».
- `--dangerously-skip-permissions`: auto-approva tutte le richieste di permesso.
- `--mode`: `accept-edits`, `plan`.
- `--continue` / `-c`, `--conversation <ID>`: riprendere una conversazione.
- `--effort`: `low|medium|high`. `--model`, `--agent`.
- sottocomandi: `agent(s)`, `models`, `plugin(s)`, `install`, `update`, `changelog`.

Modelli offerti da `agy models`: `gemini-3.7-flash-{high,medium,low}`,
`gemini-3.6-flash-*`, `gemini-3.5-flash-*`, `gemini-3.1-pro-{high,low}`,
`claude-sonnet-4-6`, `claude-opus-4-6-thinking`, `gpt-oss-120b-medium`.

## Le domande, in ordine di quanto ci servono

Per ognuna: **URL davvero aperto**, e «non trovato» dove non c'e' niente.

### 1. Il formato `stream-json`: basta a sorvegliare? (la piu' importante)

E' il pezzo che deciderebbe tutto, perche' ci darebbe la sorveglianza **senza**
un server.

- **Che eventi contiene**, coi nomi esatti dei campi? Documentazione o schema.
- C'e' un evento di **fine turno** e uno di **errore** distinguibili?
- Ci sono eventi per le **chiamate a strumento** (lettura, scrittura, comando)?
- E' una riga JSON per evento (JSON Lines) o un altro incapsulamento?
- **Confronto onesto**: e' piu' o meno informativo dello stream SSE di opencode
  (`session.status`, `session.idle`, `session.error`, `message.part.updated` con
  `ToolPart.state`)? Vedi `RICERCA-simbiosi.md` capitolo 1.

### 2. `--print-timeout`: cosa fa davvero allo scadere?

Il default e' `5m0s`. Ma un timeout che non uccide non serve — e' la lezione di
oggi, dove `timeout 3600` mandava SIGTERM a un processo che non ha handler.

- Allo scadere **termina il processo** o smette solo di aspettare?
- Con che **codice di uscita**? Si distingue da un fallimento vero?
- Il timeout copre anche il caso «endpoint del provider morto / connessione
  rifiutata», che e' esattamente quello che ci ha bruciato la giornata?
- `agy` gestisce **SIGTERM**? (opencode no, issue #24658, chiusa not planned)

### 3. I confini: si impongono meccanicamente?

Oggi i confini («non toccare `sbobina.py`») sono frasi in un prompt e reggono solo
se il modello obbedisce.

- **`--sandbox`**: cosa restringe esattamente? Solo il terminale, o anche le
  scritture su file? Documentazione, non intuizione.
- Esiste un modo di **negare la scrittura** su file o cartelle specifiche
  (configurazione, allowlist/denylist, permessi)?
- `--add-dir` definisce la workspace: **cosa succede** se il modello prova a
  scrivere fuori? Errore, richiesta, o silenzio?
- `--mode plan` impedisce davvero ogni modifica?

### 4. Costo e quota

Decide quanto possiamo usarlo.

- C'e' un **piano gratuito**? Con che limiti (richieste al minuto/giorno, token)?
- I modelli non-Google della lista (`claude-opus-4-6-thinking`,
  `gpt-oss-120b-medium`) sono compresi o si pagano a parte?
- Cosa succede al superamento della quota: errore chiaro o degrado silenzioso?

### 5. Convenzioni di progetto

- `agy` legge un file di istruzioni di progetto? **`AGENTS.md`** (che noi usiamo
  gia'), `GEMINI.md`, `.antigravity/`, altro? Nome e posizione esatti.
- Rispetta il **cwd** del processo che lo lancia? (opencode no: e' costato una
  sessione morta in 4 secondi per un percorso assoluto trattato come
  *external directory*.)
- Ha un file di configurazione, e dove?

### 6. Cos'e' esattamente, e guasti noti

- Che rapporto c'e' fra **`agy`**, **Antigravity** e il vecchio **Gemini CLI**?
  E' un rinominamento, un prodotto diverso, o due strumenti che convivono? Il
  proprietario dice che il `gemini` CLI **non funziona** e non va usato: verifica
  se `agy` e' indipendente da quello.
- **Issue note di blocco/stallo**, come la #40330 di opencode: cerca nel tracker
  ufficiale. Se `agy` ha lo stesso difetto, il guardiano esterno serve comunque.
- E' **vivo**? Ultima release, cadenza degli aggiornamenti.

## Cosa NON fare

- **Non tocchi nessun file di codice**, nessun altro `INCARICO-*`, nessun
  `RAPPORTO-*`, non `AGENTS.md`, non `DA-FARE.md`, non git.
  **L'unico file che scrivi e' `RICERCA-agy.md`.**
- **Non lanciare `agy`**, per nessun motivo: consuma quota del proprietario e
  potrebbe scrivere file. Qui si legge documentazione. Le prove le facciamo noi.
- **Non installare niente**, nessun `npm install`, nessun clone, nessun `agy update`.
- Non inventare flag, eventi, campi o limiti di quota. Se non l'hai letto nella
  documentazione ufficiale o nel tracker, **dillo**. Un flag plausibile e
  inesistente ci fa costruire un guardiano che non parte.
- Niente dati personali nel rapporto.

## Come cercare

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235
```

piu' `webfetch` per gli URL che hai gia'. Le fonti valide, in ordine: la
**documentazione ufficiale**, il **tracker delle issue**, il **changelog**
(`agy changelog` esiste come sottocomando, quindi da qualche parte e' pubblicato).
Un blog che riassume vale meno dell'originale: se una cosa la trovi solo li',
segnalalo.

## Come si scrive `RICERCA-agy.md`

Un capitolo per domanda, e in cima una **sintesi da dieci righe** che risponda a
una cosa sola: **`agy` e' pilotabile meglio di opencode, si' o no, e per quali
lavori conviene usarlo al posto suo?**

Chiudi con:

1. **La ricetta minima**: il comando esatto per lanciare un incarico non
   interattivo, leggerne gli eventi, accorgersi che e' piantato e ucciderlo.
2. **Il confronto**, in una tabella: `agy` contro `opencode run` contro
   `opencode serve` + SSE, sulle righe che ci sono costate oggi — timeout
   interno, eventi, abort, confini meccanici, gestione di SIGTERM, costo.
3. Una sezione **«non trovato»**.

Scrivi il file **un capitolo alla volta mentre lavori**, non alla fine.
