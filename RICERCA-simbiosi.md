# Ricerca: lavorare in simbiosi con opencode, non a colpi di `opencode run`

Ricerca web del 17 agosto 2026. Ogni affermazione ha un URL aperto durante la
ricerca; dove una cosa non e' stata trovata, c'e' la sezione «non trovato».
Percorsi relativi al repo.

## Sintesi (10 righe)

**Si, si puo' passare da fuoco-e-dimentica a un dialogo sorvegliato**, con la
pila che esiste gia': `opencode serve` espone una REST normale + due stream SSE
(`GET /event`, `GET /global/event`), e tutti gli eventi di sorveglianza
necessari sono nel contratto (`session.status` busy/idle, `session.idle`,
`session.error`, `message.part.updated` con le parti `tool`/`step-finish`).
Intervenire si puo': `POST /session/:id/abort` interrompe il turno,
`POST /session/:id/message` manda un messaggio a una sessione viva, e le
risposte alle richieste di permesso si mandano con
`POST /session/:id/permissions/:permissionID`. **Il client Python ufficiale
esiste** (`opencode-ai`, MIT, httpx, SSE incluso): non serve Node. I guasti che
ci hanno bruciato 5h57m hanno una causa riconosciuta nelle issue (il client CLI
si arresta per un `session.status: idle` che puo' arrivare prima della fine vera
del turno, e `opencode run` si appende in silenzio quando l'endpoint del
provider muore); il timeout provider si configura da dentro
(`provider.<id>.options.timeout`, default 300000 ms), quindi il nostro
`timeout` esterno diventa una seconda rete, non l'unica. Restano scoperti:
nessun endpoint «stall watchdog» nativo oltre agli eventi, e le convalide
meccaniche piu' forti passano dai permessi configurati o da plugin (JS/TS) che
girano nel processo opencode, non dal client Python.

## 1. Gli eventi bastano a fare da guardiano? (la piu' importante)

**Risposta breve: si.** Il contratto degli eventi, letto dallo schema OpenAPI
generato nel client ufficiale, contiene tutti i segnali per dire «e' piantata»
senza guardare l'orologio del log: uno stato di sessione `busy`/`idle`, un
evento `session.idle` esplicito, un evento `session.error` separato dai turni
finiti bene, e le parti `tool` con stato `pending`/`running`/`completed`/`error`.

### Elenco completo dei tipi di evento (nomi esatti)

Fonte primaria: lo schema OpenAPI del server, esportato come tipi TypeScript in
`packages/sdk/js/src/gen/types.gen.ts` sul ramo `dev` del repo ufficiale
(`anomalyco/opencode`). L'unione `Event` (righe ~704-736) elenca 32 tipi:

- `server.connected` — primo evento del flusso (confermato anche dalla doc
  server: «First event is server.connected, then bus events»).
- Sessione: `session.created`, `session.updated`, `session.deleted`,
  `session.status`, `session.idle`, `session.compacted`, `session.diff`,
  `session.error`.
- Messaggi e parti: `message.updated`, `message.removed`,
  `message.part.updated`, `message.part.removed`.
- File: `file.edited`, `file.watcher.updated`, `vcs.branch.updated`.
- Todo e comandi: `todo.updated`, `command.executed`.
- Permessi: `permission.updated`, `permission.replied`.
- Strumenti di sistema: `lsp.client.diagnostics`, `lsp.updated`,
  `installation.updated`, `installation.update-available`,
  `server.instance.disposed`.
- TUI: `tui.prompt.append`, `tui.command.execute`, `tui.toast.show`.
- PTY: `pty.created`, `pty.updated`, `pty.exited`, `pty.deleted`.

Sorgenti verificate:
- Schema dei tipi: https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts
- Doc server (stream `/event` e `/global/event`, primo evento `server.connected`):
  https://opencode.ai/docs/server/
- Doc SDK (`event.subscribe()`, esempio `for await (const event of events.stream)`):
  https://opencode.ai/docs/sdk/

### C'e' un evento per ogni chiamata a strumento?

**Si, ma come «parte», non come evento dedicato.** Non esiste un evento
`tool.*` nel flusso SSE (l'ho verificato: nessun tipo `tool.` nell'unione
`Event`). Le chiamate a strumento viaggiano come parti del messaggio assistant,
consegnate dagli eventi `message.part.updated`: il tipo `ToolPart` (righe
~294-306) ha campo `type: "tool"`, `tool` (nome), `state` che puo' essere
`pending` | `running` | `completed` | `error` (i quattro `ToolState*`), e
`callID`. Il tipo `ToolStateError` (righe ~277-290) trasporta anche `error:
string`. Quindi una lettura file, una scrittura, un comando bash compaiono
ciascuna come una `ToolPart` con `tool` = nome dello strumento e stato
aggiornato man mano.

La doc dei plugin conferma la stessa tassonomia a livello di hook (eventi
`tool.execute.before` / `tool.execute.after`), ma quegli hook sono interni al
processo, non nel flusso SSE: https://opencode.ai/docs/plugins/

### C'e' un evento di inattivita' / fine turno?

**Si, due.** Il tipo `SessionStatus` (righe ~455-473) e' un'unione:
`{type:"idle"} | {type:"retry", attempt, message, next} | {type:"busy"}`, e
l'evento `session.status` lo trasporta col `sessionID`. Esiste poi l'evento
esplicito `session.idle` (righe ~475-479), `{type:"session.idle",
properties:{sessionID}}`. Questo e' esattamente il segnale da cui un guardiano
puo' derivare «sono passati N minuti senza un `session.idle` o un
`session.status` a `idle`, quindi e' piantata». Come alternativa al solo SSE,
c'e' anche `GET /session/status` (elencato nella doc server), che restituisce
`{ [sessionID: string]: SessionStatus }`: polling che dice per ogni sessione se
e' `idle`, `busy` o `retry`.

### C'e' un evento di errore distinguibile?

**Si.** L'evento `session.error` (righe ~591-597) trasporta
`properties.error` tipato come unione di errori: `ProviderAuthError`,
`UnknownError`, `MessageOutputLengthError`, `MessageAbortedError`, `ApiError`
(righe ~70-106, `ApiError` con `message`, `statusCode`, `isRetryable`).
`MessageAbortedError` e' il nome che probabilmente vedremo quando il turno viene
interrotto da `POST /session/:id/abort`.

### Attenzione: un bug noto rende `session.idle` un falso «fine turno»

C'e' una trappola documentata nelle issue: in certe versioni (1.14.44 e
dintorni, e ancora in 1.17.20/1.18.4 in `--attach`), `session.status: idle`
puo' arrivare **prima** che il turno sia davvero finito — in particolare tra un
passo con tool e il passo successivo — e i client che lo trattano come fine
turno escono perdendo gli eventi finali (`text` e `step-finish`).

- Issue #26635: `prompt_async` scartava le richieste in v1.14.44 e
  `session.status: idle` arrivava gia' al connect prima del prompt.
  https://github.com/anomalyco/opencode/issues/26635
- Issue #26697: lo stream `/event` si chiudeva subito dopo `server.connected`
  (regressione 1.14.42-1.14.46, sospetta compressione HTTP); risolto tornando a
  1.14.41. https://github.com/anomalyco/opencode/issues/26697
- Issue #38661: `opencode run --attach --format json` esce 0 dopo il primo
  `step_finish (reason: "tool-calls")` e non emette gli eventi del secondo
  passo, anche se il server ha salvato tutto nel DB. Causa sospetta indicata:
  il `break` nel loop del CLI su `session.status === idle`.
  https://github.com/anomalyco/opencode/issues/38661
- PR #31446 (poi chiusa per pulizia automatica): tentativo di correggere la
  corsa «idle arriva prima delle parti finali» nel formato JSON.
  https://github.com/anomalyco/opencode/pull/31446

Per un guardiano, la lezione e': **non trattare il primo `session.idle` come
fine turno assoluto** — usarlo come soglia di inattivita' (es. N minuti di idle
o di silenzio senza nessun evento) e/o incrociarlo con `step-finish` e
`message.updated`. Il polling `GET /session/status` non ha questo problema di
corsa perche' legge lo stato corrente.

## 2. Si puo' fermare o correggere una sessione viva?

**Si, tutti e tre: interrompere, correggere, riprendere.** E ci sono prove di
progetti che lo fanno in produzione (vedi cap. 6).

### Interrompere il turno in corso

Endpoint documentato nella pagina server ufficiale: **`POST /session/:id/abort`**
— «Abort a running session», risposta `boolean`. Nel SDK TS il metodo e'
`session.abort({ path })`. Quando un turno viene interrotto, il nome di errore
atteso nel flusso eventi e' `MessageAbortedError` (uno dei tipi dell'unione di
`session.error`, vedi cap. 1).

- Doc endpoint: https://opencode.ai/docs/server/ (sezione Sessions)
- Doc SDK, metodo `session.abort`: https://opencode.ai/docs/sdk/
- Tipo `MessageAbortedError`:
  https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts

### Mandare un messaggio a una sessione gia' avviata

Si', con gli stessi due endpoint dei messaggi:

- **`POST /session/:id/message`** — «Send a message and wait for response». Body:
  `{ messageID?, model?, agent?, noReply?, system?, tools?, parts }`.
- **`POST /session/:id/prompt_async`** — «Send a message asynchronously (no
  wait)», risposta `204 No Content`.

Quindi «lascia stare X, un'altra sessione ci lavora» si manda con una `POST
/session/:id/message` con una nuova `part` di testo sulla stessa sessione.
Attenzione a un bug noto: la #26635 diceva che `prompt_async` in v1.14.44
accettava la richiesta (204) ma non avviava mai il modello (chiusa, ma da
verificare sulla nostra versione).
https://github.com/anomalyco/opencode/issues/26635

C'e' anche **`POST /session/:id/command`** («Execute a slash command», body
`{ messageID?, agent?, model?, command, arguments }`) per lanciare comandi
slash da fuori, e **`POST /session/:id/shell`** per eseguire un comando shell
in-sessione.

### Rispondere alle richieste di permesso (approvare/negare in tempo reale)

**`POST /session/:id/permissions/:permissionID`** — «Respond to a permission
request», body `{ response, remember? }`. Quando il modello chiede un permesso,
il flusso eventi pubblica `permission.updated` con l'oggetto `Permission`
(campi `id`, `type`, `pattern?`, `title`, `metadata`, `time`); un guardiano
esterno puo' rispondere allow/deny con questo endpoint. Questo e' il punto in
cui i guardrail meccanici (cap. 5) diventano **interattivi**, non solo statici.

### Riprendere una sessione interrotta

Tre strade documentate:

- **CLI**: `opencode run --continue` (ultima sessione), `--session <id>`
  (sessione specifica), `--fork` (fork della sessione). Valide anche per
  `opencode attach` e per il TUI (`-c` / `-s`). Doc CLI: https://opencode.ai/docs/cli/
- **API**: riusare la stessa sessione con `POST /session/:id/message`, oppure
  creare una **figlia** con `POST /session` body `{ parentID?, title? }` (il
  campo `parentID` nel tipo `Session` e `GET /session/:id/children` esistono).
- **`GET /session/:id/message`** con `limit?` per rileggere lo storico di una
  sessione interrotta prima di decidere come riprenderla.

## 3. C'e' un client Python, o solo TS/JS?

**C'e' un client Python ufficiale, MIT, e — indipendente da quello — l'API HTTP
e' una REST normale parlata con `requests`, con la SSE come flusso
`text/event-stream` puro.** Nessuna delle due richiede Node.

### Il client ufficiale: `opencode-ai` (anomalyco/opencode-sdk-python)

- Repo: https://github.com/anomalyco/opencode-sdk-python — MIT, 272 star, 106
  commit, generato con Stainless. README: «The Opencode Python library provides
  convenient access to the Opencode REST API from any Python 3.8+ application»,
  powered by httpx, client sincrono `Opencode` e asincrono `AsyncOpencode`.
- Installazione (dal README): `pip install --pre opencode-ai`.
- Streaming SSE incluso: `client.event.list()` restituisce uno stream iterabile
  (`for events in stream: print(events)`), identico in async.
- Timeout configurabili a livello client (`timeout=` float o `httpx.Timeout`,
  default 1 minuto), `max_retries`, retry automatici su 408/409/429/>=500.
- **Caveat importanti**:
  - Il pacchetto PyPI `opencode-ai` risulta fermo alla **0.1.0a36 del
    2025-08-27** (verificato su PyPI): e' in pre-release ed e' rimasto indietro
    di quasi un anno rispetto al server, che si muove in fretta. Il repo GitHub
    e' vivo (106 commit), ma i tipi generati nel pacchetto pip possono non
    coprire eventi/endpoint nuovi. Per un guardiano, meglio parlare l'HTTP
    direttamente e usare il pacchetto solo dove serve comodita'.
  - Il README del repo punta a `sst/opencode-sdk-python` in un link interno:
    il progetto ha cambiato organizzazione (sst → anomalyco). Da tenere
    presente se trovate fork sotto `sst/`.

### L'API HTTP e' parlata con `requests` e basta

Si. Tre evidenze indipendenti:

1. Nelle riproduzioni delle issue, lo stream si apre con **`curl -N
   http://localhost:4096/event`** e riceve `server.connected` — e' SSE puro su
   HTTP, nessun handshake speciale.
   https://github.com/anomalyco/opencode/issues/26635
2. La documentazione ufficiale di **E2B** pilota opencode da **Python con
   `requests` puri**: `requests.post(f"{base_url}/session")`,
   `requests.post(f"{base_url}/session/{id}/message", json={...})`.
   https://docs.e2b.dev/agents/opencode
3. Lo schema OpenAPI 3.1 esposto su `/doc` e' la base da cui il client TS e'
   generato; non c'e' alcuna dipendenza lato client da un runtime specifico.

Quindi: `requests` per le chiamate, `requests.get(..., stream=True)` (o
`httpx`) con lettura a righe per la SSE. Il lettore deve gestire il formato
SSE (`data: {...}` su righe, separati da blank line) e la riconnessione.

### Client Python di terze parti

- `opencode-client` su PyPI: versione 0.1.1, `requires-python >=3.13`,
  description segnaposto («Add your description here»), nessuna licenza
  dichiarata. Sembra un pacchetto immaturo/placeholder: **non affidabile**.
  https://pypi.org/project/opencode-client/
- `skislyakow/opencode-py` (GitHub): «Python SDK for Opencode», apparso nei
  risultati; **non verificato** in questa ricerca (licenza e stato non
  controllati). https://github.com/skislyakow/opencode-py

## 4. Timeout e robustezza: si configurano da dentro?

### Timeout per le chiamate al modello: si'

Nella sezione `provider` di `opencode.json` (doc config ufficiale):

```
"provider": {
  "anthropic": {
    "options": {
      "timeout": 600000,
      "chunkTimeout": 30000,
      "setCacheKey": true
    }
  }
}
```

- `timeout` — timeout di richiesta in millisecondi, **default 300000**; `false`
  per disabilitare.
- `chunkTimeout` — timeout **fra** i chunk di uno stream: se un chunk non
  arriva entro quel limite, la richiesta viene abortita. E' il piu' vicino a un
  «watchdog di stallo» nativo.
- C'e' anche `OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS` (timeout default
  dei comandi bash) e `OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX`.

Doc: https://opencode.ai/docs/config/ (sezione Models/Providers)
Variabili d'ambiente: https://opencode.ai/docs/cli/ (sezione Environment variables)

**Limitazione documentata**: questi timeout si armano solo su una connessione
**gia' stabilita**. Con l'endpoint del provider morto (TCP refused) falliscono
prima, come spiega l'issue #40330 qui sotto.

### E' un problema noto che il processo resti appeso con l'endpoint morto?

**Si, ed e' esattamente il nostro guasto.** Issue #40330: «`opencode run` hangs
forever (and silently) when the provider's baseURL refuses the TCP connection».
https://github.com/anomalyco/opencode/issues/40330

Causa radice (descritta nella issue stessa, verificata sul sorgente v1.18.11):

- ogni errore di rete (incluso `ECONNREFUSED`) viene marcato `isRetryable:
  true`; il retry non ha mai limite (un tentativo ogni 30s, per sempre);
- `session.error` non viene mai pubblicato e la sessione non arriva mai a
  `idle`, perche' `retry` avvolge `halt` prima;
- la modalita' non interattiva (`opencode run`) non ha nessun percorso di
  uscita: rompe solo su `session.status === "idle"`, e lo stato `retry` viene
  consumato solo dalla TUI, non da `run` (neppure con `--format json`);
- `run` attende `client.session.prompt(...)` senza timeout lato client;
- non esiste un flag `--timeout`/`--max-retries` su `opencode run`.

La issue e' **chiusa come not planned** (nessuna correzione prevista a breve),
con assignee. E' il pezzo che ci ha tenuto 5h57m su `epoll`: la causa e'
riconosciuta, la soluzione non c'e' ancora nel prodotto, quindi il guardiano
esterno (SSE + abort) non e' un lusso ma l'unica difesa per quel caso.

Nota onesta: l'incarico registrava anche «`opencode run` esce 0 quando non ha
fatto niente (endpoint giu')». Nella ricerca ho trovato documentato l'opposto
(hang infinito silenzioso). Entrambi i sintomi sono compatibili con le due
issue da hang note (#40330 e #17516, «opencode run hangs after completing tool
calls», citata dentro #40330): l'exit code 0 non l'ho trovato descritto come
issue separata. Da verificare a casa con la nostra versione.

### opencode intercetta SIGTERM?

Di fatto si, nel senso peggiore. Issue #24658: «SIGTERM hangs, does not output
anything». https://github.com/anomalyco/opencode/issues/24658

- Nel TUI solo `SIGHUP` e' agganciato al percorso di uscita pulito
  (`exit()`); `SIGINT` e `SIGTERM` **non hanno handler**: il main thread muore
  ma il worker Bun resta, orfano (runtimes Effect, MCP, LSP, PTY, file
  watcher). Chiusa come not planned.
- Esiste anche l'issue #319 «handle sigterm» (piu' vecchia):
  https://github.com/anomalyco/opencode/issues/319

Conferma cio' che abbiamo misurato: `timeout 3600` che manda SIGTERM non basta,
serve `-k` (SIGKILL) — oppure, con il server, si puo' evitare del tutto di
uccidere il processo usando `POST /session/:id/abort`.

## 5. Guardrail: si possono imporre i confini invece di chiederli

### Permission system: si', inclusa la negazione di scritture su file specifici

La doc ufficiale delle permissions e' completa e attuale:
https://opencode.ai/docs/permissions/

- Ogni regola si risolve in `"allow"` | `"ask"` | `"deny"`.
- Sintassi a oggetti per regole granulari sui path di `edit` e sui comandi di
  `bash`, con **wildcard** `*` (zero o piu' caratteri) e `?` (un carattere),
  espansione `~`/`$HOME`, e «last matching rule wins» (mettete il catch-all
  `*` per primo e le regole specifiche dopo):

```
"permission": {
  "edit": { "*": "deny", "packages/web/src/content/docs/*.mdx": "allow" },
  "bash": { "*": "ask", "git *": "allow", "rm *": "deny" }
}
```

  Per negare una scrittura su `sbobina.py` in modo meccanico:
  `"edit": { "*": "allow", "**/sbobina.py": "deny" }` (sintassi wildcard
  documentata; il pattern esatto di path per i file della worktree va
  verificato in locale).
- `external_directory` (gia' usato da noi) per i path fuori dal worktree,
  `doom_loop` (stessa tool call 3 volte identiche → `ask` di default) come
  guardia anti-loop.
- Config inline via variabile d'ambiente `OPENCODE_PERMISSION` (doc CLI).
- **Interattivo**: quando una regola e' `ask`, il permesso diventa un evento
  `permission.updated` nel flusso SSE e si risponde con
  `POST /session/:id/permissions/:permissionID` (cap. 2): il guardiano esterno
  puo' negare in tempo reale.

### Plugin / hook: si', ma girano nel processo opencode (JS/TS)

Doc plugin: https://opencode.ai/docs/plugins/

- Plugin = moduli JS/TS in `.opencode/plugins/` o `~/.config/opencode/plugins/`
  (o pacchetti npm in `opencode.json` → `plugin`), caricati dal processo
  opencode (Bun) all'avvio.
- Hook disponibili: `tool.execute.before` / `tool.execute.after` (nomi nella
  doc), `shell.env`, `command.executed`, `experimental.session.compacting`. Per
  bloccare un'azione basta `throw new Error(...)` in `tool.execute.before` —
  l'esempio ufficiale «.env protection» fa esattamente questo per `read` su
  file `.env`.
- **Limite per noi**: gli hook girano dentro il server opencode, non nel
  client. Un orchestratore Python esterno non li installa a runtime; puo'
  pero' contare su: permessi statici (qui sopra), sull'endpoint di risposta ai
  permessi, e su agenti con strumenti ristretti (qui sotto).

### Agent / subagent con strumenti ristretti

- In `opencode.json`: `agent.<nome>` con `tools` che disabilitano i tool
  (`"write": false, "edit": false` per un agente review-only) e con
  `permission` per-agente che ha precedenza sul globale.
  https://opencode.ai/docs/config/
- In markdown (`~/.config/opencode/agents/*.md`): frontmatter con `mode:
  subagent`, `permission`, `tools`. Esempio nella doc permissions.
  https://opencode.ai/docs/permissions/
- `subagent_depth` limita la profondita' di annidamento dei subagent.
  https://opencode.ai/docs/config/
- `opencode agent create` genera agenti «Anything you don't allow is denied».
  https://opencode.ai/docs/cli/

**Verdetto cap. 5**: i confini meccanici esistono e sono robusti a livello di
permessi configurabili + risposta programmatica alle richieste; gli hook di
plugin offrono il rifiuto a runtime ma vivono dentro il server e non sono
gestibili dal nostro client Python. Il «non toccare sbobina.py» si puo' quindi
rendere meccanico con la regola `edit`/deny o con un agente dedicato.

## 6. Esiste gia' chi ha fatto questo lavoro?

**Si, e in piu' forme.** Il pattern «server opencode + SSE + intervento via
API» e' esattamente quello che diversi progetti gia' fanno in produzione.
Nessuno di questi e' un «orchestratore di N sessioni opencode sorvegliate» gia'
bello e pronto da copiare in Python puro, ma tutti dimostrano che la strada e'
battuta e supportata.

### Progetti verificati (nome, URL, licenza, stato)

- **opencode-orchestrator** (`agnusdei1207/opencode-orchestrator`): plugin
  opencode multi-agente (Commander / Planner / Worker / Reviewer) con loop di
  verifica. MIT, 224 star, 899 commit, v1.7.10, npm `opencode-orchestrator`.
  Gira **dentro** opencode (usa subagent interni), non e' un guardiano esterno.
  https://github.com/agnusdei1207/opencode-orchestrator
- **opencode-manager** (`chriswritescode-dev/opencode-manager`): web UI PWA
  mobile-first per «Manage, control, and code with multiple OpenCode agents
  from any device». Backend Bun+Hono con «OpenCode process management, SSE,
  schedules, push notifications». MIT, 858 star, 781 commit, Docker.
  E' il piu' vicino a un orchestratore esterno: gestisce piu' processi opencode
  e ne streamma gli eventi via SSE.
  https://github.com/chriswritescode-dev/opencode-manager
- **kimaki** (`remorses/kimaki`): orchestratore collaborativo su Discord.
  MIT, 1.3k star, 2295 commit (molto vivo). Usa la stessa pila: «Every message
  you send starts a thread that maps to one OpenCode session», con `/abort`,
  `/resume`, `/btw` (fork parallelo), coda messaggi, e — la cosa piu' utile per
  noi — un meccanismo di **interrupt**: «if the current step is still going
  after ~3 seconds, Kimaki aborts it and force-sends your message, then
  resumes». Cioe' abort + rimessaggio + riprendi, tutto via API.
  https://github.com/remorses/kimaki
- **E2B**: non un orchestratore, ma l'ambiente in cui si pilotano agenti
  headless. Template ufficiale `opencode` con `opencode serve` dentro la
  sandbox; lifecycle (timeout, auto-pause, kill) e accesso dall'app col client
  SDK (TS) o con `requests` (Python). E' la conferma che pilotare opencode via
  HTTP e' un uso previsto.
  https://docs.e2b.dev/agents/opencode

### Come lo fanno gli ambienti che ci girano sopra (E2B e simili)

Dal doc E2B letto: creano una sandbox col template `opencode`, avviano
`opencode serve --hostname 0.0.0.0 --port 4096` in background, aspettano
`GET /global/health`, poi creano sessione e mandano il prompt via API; il
lifecycle (`timeoutMs`, `onTimeout: pause|kill`, `auto_pause`) fa da guardiano
a livello di sandbox. E' il nostro stesso problema (fare da watchdog a un
agente) risolto spostando il watchdog un livello sotto (il runtime della
sandbox).

### Cross-check onesto: remiamo controcorrente?

No. La doc ufficiale dichiara esplicitamente che il server esiste per essere
pilotato: «Use the opencode server to interact with opencode programmatically»
e l'SDK «for building integrations and controlling opencode programmatically».
https://opencode.ai/docs/server/ · https://opencode.ai/docs/sdk/

Per completezza, gli altri agenti da CLI hanno gia' una modalita' da
«programma pilotato da un programma»:

- **Claude Code** ha la modalita' headless `claude -p` con `--output-format
  json` / `stream-json`, exit code 0/non-zero, `--allowedTools`/permission
  modes, e — a differenza di opencode oggi — gestisce **SIGTERM** (abortisce il
  turno e esce con 143), e un **Agent SDK ufficiale in Python**.
  https://code.claude.com/docs/en/headless
  Rilevante per noi: mostra che la gestione del segnale e l'exit code onesto
  sono fatti *per* chi pilota dall'esterno.
- L'ecosistema opencode (pagina Ecosystem) conta comunque gia' decine di
  progetti di integrazione: https://opencode.ai/docs/ecosystem/

Quindi: non stiamo remando controcorrente, stiamo usando il server API di
opencode per lo scopo dichiarato. Il costo e' che alcuni pezzi di robustezza
(timeout/retry/segnali) non sono ancora risolti dentro opencode (cap. 4) e
vanno gestiti dal nostro guardiano.

## La ricetta minima

Sequenza esatta, endpoint e comandi come scritti nella documentazione e nelle
riproduzioni delle issue (senza avviare nulla: da provare in locale).

```
# 1. Avvio del server (headless)
opencode serve --port 4096
#    (se serve la password: OPENCODE_SERVER_PASSWORD=... opencode serve)

# 2. Creazione sessione  ->  risponde { id, ... }
curl -X POST http://127.0.0.1:4096/session \
  -H "Content-Type: application/json" -d '{}'

# 3. Aprire lo stream eventi (SSE) PRIMA di lanciare il prompt,
#    per non perdere i primi delta  ->  primo evento: server.connected
curl -N http://127.0.0.1:4096/event
#    (per piu' progetti: /global/event, ogni evento ha il campo directory)

# 4. Lanciare il lavoro senza aspettare  ->  risponde 204
curl -X POST http://127.0.0.1:4096/session/$SESSION/prompt_async \
  -H "Content-Type: application/json" \
  -d '{"parts":[{"type":"text","text":"<incarico>"}]}'

# 5. Sorvegliare gli eventi:
#    session.status: busy -> idle | retry  |  session.idle
#    message.part.updated (parte type=tool / step-finish / text)
#    session.error (ProviderAuthError | ApiError | ... | MessageAbortedError)
#    Alternativa senza SSE: GET /session/status  ->  { "<id>": {type:"idle"|"busy"|"retry"} }

# 6. Se lo stallo (N minuti senza eventi, o status stuck su busy/retry):
curl -X POST http://127.0.0.1:4096/session/$SESSION/abort   # -> boolean

# 7. Correggere il tiro su una sessione viva:
curl -X POST http://127.0.0.1:4096/session/$SESSION/message \
  -H "Content-Type: application/json" \
  -d '{"parts":[{"type":"text","text":"Lascia stare X, scrivi il rapporto adesso"}]}'

# 8. Riprendere dopo: stesso id con --continue/--session, oppure figlia:
curl -X POST http://127.0.0.1:4096/session \
  -H "Content-Type: application/json" -d '{"parentID":"<id-sessione>"}'
```

Nota: con la password attiva, ogni richiesta vuole il basic auth (utente
`opencode` o `OPENCODE_SERVER_USERNAME`, password `OPENCODE_SERVER_PASSWORD`).

## Cosa resta scoperto

Cose che l'API oggi non permette e che dovremo continuare a fare a mano:

- **Nessun watchdog nativo**: non esiste un timeout/stallo lato server che
  uccida un turno appeso. L'unica difesa per il caso «endpoint del provider
  morto» resta esterna (SSE + `abort`), perche' la causa e' nota ma non
  corretta (#40330, chiusa not planned).
- **Nessun limite ai retry** sul connection-refused: il retry policy non ha
  budget di tempo/numero (#40330). I timeout `provider.options.timeout`/
  `chunkTimeout` si armano solo a connessione stabilita.
- **`session.idle` non e' un «fine turno» affidabile**: per la corsa
  documentata (#26635, #38661) il primo idle puo' precedere gli eventi finali.
  Per chiudere bene una sessione serve aspettare anche `step-finish`/
  `message.updated`, o interrogare `GET /session/:id/message` prima di
  dichiarare finito.
- **Nessuna sottoscrizione SSE per-sessione**: i flussi sono `/event`
  (progetto) e `/global/event` (globale); il filtro per `sessionID` si fa dal
  client (issue #7451 chiusa not planned).
- **Nessun hook a runtime dal client**: i plugin sono JS/TS dentro il
  processo; un orchestratore Python non li installa a runtime. Per i confini
  dinamici restano i permessi + l'endpoint di risposta ai permessi.
- **SIGTERM non gestito** (#24658): uccidere il processo resta da fare con
  SIGKILL o, meglio, con `abort` e senza uccidere il server.
- **exit code onesto**: per `opencode run` il comportamento con endpoint giu'
  non e' risolto ne' documentato in modo coerente (#40330 vs l'exit 0 che
  abbiamo visto). Da misurare sulla nostra versione.
- **Da testare in locale (non provato in questa ricerca)**: il pattern
  esatto di path nelle regole `edit`/deny sulla nostra worktree; il
  comportamento di `prompt_async` sulla nostra versione (la #26635 era su
  v1.14.44); l'endpoint `/tui/control/next` (richieste di controllo alla TUI)
  e il comando `opencode acp` (Agent Client Protocol) come vie alternative di
  pilotaggio.

## Non trovato

- Un'issue che descriva «`opencode run` esce 0 con endpoint giu'»: ho trovato
  il sintomo opposto (hang infinito silenzioso, #40330) e un hang post-tool
  (#17516, citata dentro #40330). L'exit code 0 non e' documentato come issue
  separata.
- Eventi di tipo `tool.*` nel flusso SSE: non esistono; le chiamate a
  strumento sono parti (`ToolPart`, state pending/running/completed/error)
  dentro `message.part.updated`.
- Un client Python ufficiale aggiornato: il pacchetto PyPI `opencode-ai` e'
  fermo alla 0.1.0a36 (2025-08-27); il repo GitHub del SDK Python e' vivo ma i
  tipi generati possono essere in ritardo.
- Un'opzione di configurazione tipo «idle timeout»/«stall watchdog» in
  `opencode.json`: non trovata (l'unico meccanismo vicino e' `chunkTimeout`).
- Il repo `OdairFTeixeira/opencode-multisession` (apparso nei risultati): 404
  al momento della verifica, non verificabile.
- `opencode-client` su PyPI (0.1.1) non ha licenza ne' descrizione seria:
  considerato placeholder, non una risorsa.
- Licenza e stato di `skislyakow/opencode-py`: non verificati.
