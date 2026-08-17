# RICERCA: un solo posto per gli MCP, invece di tre

Ricerca sul web del 17 agosto 2026. Non ho toccato nessuna configurazione
(`~/.claude.json`, `~/.config/opencode/opencode.json`, `~/.gemini/`), non ho
installato nulla, non ho lanciato `agy`. Ogni affermazione ha un URL che ho
aperto davvero. Dove non ho trovato nulla scrivo «non trovato».

---

## Sintesi — dieci righe

**Esiste una soluzione pronta per dichiarare gli MCP una volta e usarli da tre
agenti: si'.** E' un **gateway MCP che aggrega**: un solo server davanti a
`megamemory`, `codegraph` e `web-forager` (tutti stdio locali), e ogni client
punta a una sola URL. La condizione che decideva tutto e' verificata in tutte e
tre le documentazioni: **Claude Code, opencode e Antigravity CLI accettano
tutti server MCP remoti/HTTP**, non solo stdio. Il candidato piu' completo e
vivo e' **1MCP** (`1mcp-app/agent`, Apache-2.0, 484★, aggiornato al 15/08/2026):
`1mcp serve` aggrega upstream stdio e presenta un solo endpoint HTTP streamable,
con **filtri per client** (preset/tag) che tengono basso il costo in token —
il guadagno vero, non solo l'unificazione. Alternative piu' piccole: se basta
un port solo senza aggregare i tool, `sparfenyuk/mcp-proxy` (MIT, 2711★) espone
piu' server stdio dietro un solo processo con `--named-server-config`. E la cosa
che ci bloccava e' risolta dalla documentazione ufficiale: per Antigravity CLI i
server MCP si dichiarano in **`~/.gemini/config/mcp_config.json`** (globale) o
**`.agents/mcp_config.json`** (workspace), chiave **`mcpServers`** — non nel
`settings.json` delle preferenze. Nessun progetto risolve la domanda 5
(quale memoria per cosa): quella resta una decisione nostra.

---

## 1. Esiste un modo standard di dichiarare i server MCP una volta sola?

**Fonte principale aperta**: https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2218
e la tabella che riporta, confronto reale dei client.

### La specifica MCP non definisce un formato di configurazione condiviso

No, e' il motivo per cui la discussione #2218 esiste. Il suo titolo e'
«Proposal: Universal MCP Configuration File Standard» — cioe' una **proposta
aperta, non ancora uno standard**. La tabella che riporta e' la prova dello
stato di fatto:

| Tool | file | chiave radice | campo trasporto | formato |
|---|---|---|---|---|
| Claude Code | `.mcp.json` | `mcpServers` | `type: "stdio"` | JSON |
| VS Code | `.vscode/mcp.json` | `servers` | `type: "stdio"/"sse"` | JSON |
| Gemini CLI (legacy) | `.gemini/settings.json` | `mcpServers` | — | JSON |
| OpenAI Codex | `.codex/config.toml` | `mcp_servers` | — | **TOML** |
| OpenCode | `opencode.json` | `mcp` | `type: "local"/"remote"` | JSON |
| Copilot CLI | `.copilot/mcp-config.json` | `mcpServers` | — | JSON |
| Kimi CLI | `~/.kimi/mcp.json` | `mcpServers` | — | JSON |
| IntelliJ | `.idea/mcp.json` | `mcpServers` | — | JSON |

Citazione del problema (dalla #2218): «every tool that supports MCP uses a
different configuration file format. Even though all of them configure the same
thing — MCP servers — each one invented its own schema, root key, field names,
and file location». Quindi: **la specifica MCP non definisce nulla** — ogni
client fa come gli pare, e anche i nomi di file sono diversi (`.mcp.json`,
`mcp.json`, `mcp_config.json`, `settings.json`, `config.toml`).

### La convenzione emergente `.mcp.json` di progetto

Esiste, ma **non e' universale** e non e' uno standard: e' una convenzione che
parte da Claude Code e che altri adottano per interoperare con lui.

- **Claude Code la legge davvero**: `.mcp.json` alla radice del progetto, scope
  "project", condiviso via version control. Documentazione ufficiale aperta:
  https://code.claude.com/docs/en/mcp (sezione "Project scope").
- **VS Code la legge per il suo Agent Host**: la documentazione ufficiale
  aperta https://code.visualstudio.com/docs/agents/reference/mcp-configuration
  dice: «for portable configuration, use a workspace `.mcp.json` or user
  `~/.copilot/mcp-config.json` file, which the Agent Host reads natively».
  Nota: il file *dello* workspace per l'estensione resta `.vscode/mcp.json`,
  con chiave `servers` e non `mcpServers` — un'altra divergenza.
- **opencode NON legge `.mcp.json`.** Verificato sul tracker: issue
  https://github.com/anomalyco/opencode/issues/1910 («Does opencode support
  claude code `.mcp.json` config?», chiusa), issue
  https://github.com/anomalyco/opencode/issues/14888 («Read MCP configuration
  from Claude Code's .mcp.json config file») **chiusa il 26/04/2026 con
  state_reason `not_planned`**, e due PR che lo implementavano chiuse senza
  merge: https://github.com/anomalyco/opencode/pulls/1170 e
  https://github.com/anomalyco/opencode/pulls/14717 (la 14717 implementava sia
  `.mcp.json` sia la cartella `mcps/*.json` per l'issue
  https://github.com/anomalyco/opencode/issues/10737, e resta non mergiata).
  La documentazione corrente aperta https://opencode.ai/docs/mcp-servers/
  dichiara solo `opencode.json` chiave `mcp`, con `type: "local"` o
  `type: "remote"`.
- **Antigravity CLI NON legge `.mcp.json`**: usa `mcp_config.json` (capitolo 4).

### Includere o importare un altro file di configurazione

- **Claude Code**: ha il flag `--mcp-config` per passare una configurazione
  diversa da quella di default, citato nella documentazione ufficiale (sezione
  "Add MCP servers from JSON configuration" e "Disable claude.ai connectors").
  C'e' un bug storico segnalato (il flag ignorato, issue
  https://github.com/anthropics/claude-code/issues/10787, del 01/11/2025) — il
  flag esiste e viene citato, ma va collaudato sulla versione che usiamo.
  In piu' `claude mcp add-json` importa una configurazione JSON direttamente.
- **opencode**: non ha un "include", ma il config merge da piu' sorgenti
  (documentazione https://opencode.ai/docs/config/, sezione precedenza), tra cui
  variabili d'ambiente e file di progetto; niente che importi un file MCP di
  Claude Code.
- **Antigravity CLI**: nessun include; la migrazione si fa con
  `agy plugin import gemini|claude` (capitolo 4).

---

## 2. I gateway / proxy / aggregatori MCP

### Verificato: i nostri tre client accettano server MCP remoti/HTTP

Questa era la condizione senza la quale il gateway non serve a niente.
Verificata in tutte e tre le documentazioni ufficiali:

- **Claude Code: si'.** Documentazione aperta
  https://code.claude.com/docs/en/mcp : «Option 1: Add a remote HTTP server»,
  con `claude mcp add --transport http` e, nei file JSON, `"type": "http"`
  (alias `streamable-http`); supporta anche `sse` e `ws`.
- **opencode: si'.** Documentazione aperta
  https://opencode.ai/docs/mcp-servers/ : sezione "Remote", `"type": "remote"`
  con `url` (e `headers`, `oauth`, `timeout` opzionali).
- **Antigravity CLI: si'.** Documentazione aperta
  https://antigravity.google/docs/cli/mcp : per i server remoti la proprieta' e'
  `serverUrl`, «URL for remote Streamable HTTP or SSE servers».

Quindi un gateway che parla **Streamable HTTP** va bene per tutti e tre. Nessuno
dei tre richiede stdio.

### I progetti trovati, uno per uno

Metadati (licenza, stelle, ultimo push) letti dalle API GitHub; README aperti
dove indicato.

| progetto | cosa fa | licenza | ★ | vivo? |
|---|---|---|---|---|
| [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) | ponte stdio↔SSE/StreamableHTTP; espone server stdio locali su una porta HTTP; supporta piu' server con `--named-server`/`--named-server-config` | MIT | 2711 | si, push 2026-07-20 |
| [punkpeye/mcp-proxy](https://github.com/punkpeye/mcp-proxy) | proxy TS: un server stdio in HTTP streamable + SSE; CORS; revisioni protocollo 2025 e 2026-07-28 | MIT | 281 | si, push 2026-08-17 |
| [1mcp-app/agent](https://github.com/1mcp-app/agent) | **aggregatore** MCP: `1mcp serve` mette molti server dietro un solo runtime; filtri/preset per client; lazy loading; `1mcp proxy` per client stdio | Apache-2.0 | 484 | si, push 2026-08-15 |
| [domdomegg/mcp-aggregator](https://github.com/domdomegg/mcp-aggregator) | **aggregatore di server HTTP remoti** dietro un solo endpoint con OAuth e namespace `gmail__send_email` | MIT | 7 | si, push 2026-08-12 |
| [dwillitzer/mcp-aggregator](https://github.com/dwillitzer/mcp-aggregator) | aggregatore universale, config `~/.mcp/aggregator/config.json`, modalita' `--stdio` | **nessuna** (NOASSERTION) | 7 | **no, morto** (push 2025-06-26) |
| [docker/mcp-gateway](https://github.com/docker/mcp-gateway) | plugin CLI / gateway MCP di Docker: gestisce server MCP come container | MIT | 1534 | si, push 2026-08-13 |
| [microsoft/mcp-gateway](https://github.com/microsoft/mcp-gateway) | reverse proxy e livello di gestione MCP, orientato a Kubernetes (descrizione dal metadata GitHub) | MIT | 786 | si, push 2026-08-12 |
| [lasso-security/mcp-gateway](https://github.com/lasso-security/mcp-gateway) | gateway a plugin che orchestra altri MCP (descrizione dal metadata GitHub) | MIT | 385 | rallentato, push 2026-01-22 |
| [matthisholleville/mcp-gateway](https://github.com/matthisholleville/mcp-gateway) | proxy gateway con middleware, permessi, rate limiting (descrizione dal metadata GitHub) | Apache-2.0 | 13 | no, push 2025-08-06 |

### Il punto che decide: esporre server stdio locali e presentarsi come uno solo

- **sparfenyuk/mcp-proxy** (README aperto:
  https://raw.githubusercontent.com/sparfenyuk/mcp-proxy/master/README.md) ha
  proprio il nostro caso come caso d'uso numero 2: «Run a proxy server from
  stdio that connects to a remote SSE server» e l'inverso «SSE to stdio» —
  esporre un server stdio locale via HTTP/SSE. Con `--named-server` o
  `--named-server-config` **espone piu' server stdio dietro un solo processo**
  su `http://127.0.0.1:8080/servers/<nome>/sse` (+ endpoint `/status`). Il file
  di config usa il formato `mcpServers` (`command`, `args`, `env`). Limite: non
  **fonde** i tool in un unico server — ogni server ha la sua URL, quindi ogni
  client continua a vedere piu' server (ma dichiarati in un posto solo).
- **punkpeye/mcp-proxy** (README aperto:
  https://raw.githubusercontent.com/punkpeye/mcp-proxy/master/README.md) e'
  uno-a-uno: un processo = un upstream stdio, esposto su `/mcp` (streamable
  HTTP) e `/sse`. Multiplexa piu' connessioni downstream su un solo upstream.
  Per tre server servirebbero tre processi, non unisce.
- **1MCP** (README aperto:
  https://raw.githubusercontent.com/1mcp-app/agent/main/README.md) e' l'unico
  che fa **aggregazione vera**: `1mcp serve` aggrega gli upstream e presenta un
  solo endpoint streamable HTTP (`http://127.0.0.1:3050/mcp?app=<client>`), e
  con `1mcp proxy` puo' parlare anche stdio ai client che non sanno fare HTTP.
  Documenta esplicitamente il caso dei tre nostri client: nel README, il
  client opencode/Cursor si collega con un entry `url` e Claude Code con
  `claude mcp add -t http 1mcp "http://127.0.0.1:3050/mcp?app=claude-code"`.
  Supporta upstream **stdio** e remoto. E' npm (`npm install -g @1mcp/agent`).
- **domdomegg/mcp-aggregator** (README aperto:
  https://raw.githubusercontent.com/domdomegg/mcp-aggregator/master/README.md)
  aggrega ma solo **upstream HTTP remoti** (i suoi esempi sono Gmail, Calendar,
  Airtable come servizi remoti); unifica i tool con prefisso `gmail__...` e fa
  OAuth 2.1. Per i nostri tre server stdio locali **non si applica**.
- **dwillitzer/mcp-aggregator** aggregherebbe stdio, ma e' **morto** (ultimo
  push 2025-06-26) e **senza licenza dichiarata** (NOASSERTION): non va toccato.
- **docker/mcp-gateway** e **microsoft/mcp-gateway**: il primo e' pensato per
  eseguire server come container Docker (servizio Docker richiesto), il secondo
  per ambienti Kubernetes enterprise. Non adatti a tre processi stdio locali.

**Risposta al punto decisivo**: si', un gateway puo' esporre i nostri server
stdio locali e presentarli ai client. Il trasporto verso i client e' Streamable
HTTP (tutti e tre i client lo accettano, verificato sopra). La scelta tra
"piu' server, un port solo" (sparfenyuk) e "un solo server aggregato" (1MCP) e'
la domanda di fondo del capitolo 3.

---

## 3. Cosa si perde o si rischia con un gateway

### Singolo punto di guasto

Rischio reale e non affrontato dai progetti piccoli. `punkpeye/mcp-proxy` e
`sparfenyuk/mcp-proxy` sono processi singoli: se il gateway non parte, tutti i
client perdono tutti gli strumenti insieme. I progetti enterprise
(microsoft/mcp-gateway, docker/mcp-gateway) parlano di alta disponibilita'
perche' sono pensati per Kubernetes/container — per noi e' sovradimensionato e
non risolve comunque il caso "il fisso dorme": **il gateway girerebbe sul
fisso, quindi quando il fisso si sospende gli strumenti spariscono tutti in
una volta** — oggi invece ogni client gestisce da solo la connettivita'.
Nessuno dei candidati affronta il caso "upstream locale che si sospende".

### Nomi degli strumenti: collisioni e prefissi

- I due mcp-proxy sono uno-a-uno (o per-nome): **non ci sono collisioni**,
  perche' ogni upstream resta a se'.
- Gli aggregatori invece **devono** disambiguare: `domdomegg/mcp-aggregator`
  usa il prefisso `server__tool` (esempio ufficiale `gmail__send_email`,
  `calendar__create_event`). 1MCP raggiunge lo stesso scopo con un livello di
  filtri/namespace e una CLI che ispeziona `server` e `server/tool`
  (`1mcp inspect <server>/<tool>`, `1mcp run <server>/<tool>`).

### Cosa si perde nel passaggio

`punkpeye/mcp-proxy` e' il piu' onesto: documenta esplicitamente «What does not
cross the proxy». Tradotto dalla sua README: **elicitation, sampling e roots**
(qualsiasi richiesta che chiede input al client), **i log lato 2026-07-28**,
`logging/setLevel` upstream, e **l'identita' del client** (l'upstream vede
`mcp-proxy` come suo client, non il chiamante reale). I nostri tre server sono
stdio semplici senza sampling/elicitation, quindi per noi si perde poco — ma e'
il genere di cosa da sapere prima. `sparfenyuk` non documenta perdite di
protocollo nel suo caso d'uso stdio→HTTP.

### Costo in token e il vero guadagno: filtrare per client

Il problema e' reale e documentato anche dai client stessi:
https://opencode.ai/docs/mcp-servers/ («When you use an MCP server, it adds to
the context. This can quickly add up if you have a lot of tools»). La
documentazione MCP ufficiale sui client
(https://modelcontextprotocol.io/docs/2026-07-28/develop/clients/client-best-practices)
raccomanda la **scoperta progressiva** dei tool invece di caricarli tutti: una
host naive che carica tutte le definizioni upfront consuma ~150.000 token solo
di definizioni, contro ~2.000 con la scoperta progressiva.

Qui sta la differenza tra i candidati:

- **1MCP permette di filtrare per client, ed e' un suo punto venduto**: preset,
  filtri e tag decidono quali server/tool esporre a quale client o sessione
  (documentazione aperta https://docs.1mcp.app/guide/advanced/server-filtering e
  https://docs.1mcp.app/commands/proxy). Ha anche **lazy loading** (carica i
  tool on-demand, "reduces the initial schema payload"). Questo **e'** il vero
  guadagno oltre l'unificazione: i nostri client hanno budget di contesto e
  velocita' diversi, e con 4-6 tool grossolani per definizione (regola 1 del
  progetto) sapere *quali* strumenti esporre a chi conta.
- I due mcp-proxy **non filtrano** per client: espongono tutto cio' che
  l'upstream offre.
- opencode ha gia' un meccanismo di filtro nativo per-agent sui server MCP
  (documentazione https://opencode.ai/docs/mcp-servers/, sezioni "Global" e
  "Per agent", con glob type `"my-mcp*"`): se si va di aggregatore, questo
  aiuta a tenere il contesto basso lato opencode anche senza filtri sul gateway.

---

## 4. Il formato MCP di agy (Antigravity CLI) — serve comunque

**Fonte principale aperta**: https://antigravity.google/docs/cli/mcp
(sezioni "Global and Workspace Server Configs", "MCP Configuration Structure",
"MCP Configuration Properties") e https://antigravity.google/docs/cli/gcli-migration
(sezione "MCP config formatting changes").

### Dove si dichiarano i server MCP per Antigravity CLI

**Non** nel `settings.json`. La documentazione ufficiale (gcli-migration,
sezione "MCP config formatting changes") lo dice esplicitamente:

- **Legacy Gemini CLI**: i server erano inline dentro `~/.gemini/settings.json`.
- **Antigravity CLI**: i server stanno in un file dedicato `mcp_config.json`:
  - **globale**: `~/.gemini/config/mcp_config.json`
  - **workspace**: `.agents/mcp_config.json` (dentro il progetto)

Citazione: «Unlike legacy setups, Antigravity CLI separates MCP definitions into
dedicated, sparse configurations». Il `~/.gemini/antigravity-cli/settings.json`
(confermato come file delle preferenze dalla pagina ufficiale
https://antigravity.google/docs/cli/settings) e' per impostazioni di
rendering, permessi, editor — **non** per gli MCP.

### La chiave e la struttura, prese dalla documentazione

La chiave radice e' **`mcpServers`**. Esempio **verbatim** dalla documentazione
ufficiale (https://antigravity.google/docs/cli/mcp):

```json
{
  "mcpServers": {
    "sqlite-explorer": {
      "command": "node",
      "args": ["/usr/local/bin/sqlite-mcp-server.js"],
      "env": {
        "SQLITE_DB_PATH": "/var/data/app.db"
      }
    },
    "my-remote-server": {
      "serverUrl": "https://api.example.com/mcp/",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

Proprieta' per server (dalla tabella "MCP Configuration Properties"):
trasporto uno dei due obbligatori — `command` (stdio) oppure `serverUrl`
(Streamable HTTP o SSE) — e opzionali `args`, `env`, `cwd`, `headers`,
`authProviderType` (`"google_credentials"` per ADC), `oauth`, `disabled`
(bool), **`disabledTools`** (array di nomi di tool da nascondere al modello —
analogo al filtro per client di 1MCP). La migrazione da Gemini CLI richiede il
rename `url`/`httpUrl` → `serverUrl` (gcli-migration).

Per il nostro caso (tre server stdio locali senza segreti) l'entry per ciascuno
sara' del tipo `"command"` + `"args"`, con `disabledTools` disponibile per
tenere basso il contesto. Se si adotta un gateway HTTP, l'entry sara' una sola
con `serverUrl` che punta al gateway.

### `agy plugin import claude` cosa importa davvero

**Non trovato nella documentazione ufficiale.** La pagina ufficiale
https://antigravity.google/docs/cli/plugins documenta solo i sottocomandi
`plugin list / install / disable / enable / uninstall` e le skill, e
https://antigravity.google/docs/cli/gcli-migration documenta **solo
`agy plugin import gemini`** (con l'output di esempio che mostra skills, agents,
commands e mcpServers convertiti). Nessuna pagina ufficiale apre che
`agy plugin import claude` importi skill, server MCP o entrambi.

Due fonti di terze parti, aperte:
- https://docs.claude-mem.ai/antigravity-cli/setup (documentazione di
  claude-mem) riporta `agy plugin {list,import,install,...}` e «agy plugin
  import gemini|claude suggests native cross-tool plugin migration» — indica
  che il sottocomando `import claude` esiste e fa una migrazione "cross-tool",
  senza dettagli su cosa includa.
- https://github.com/winnorton/cairn/blob/main/docs/notes/NOTE_AGY_DISTRIBUTION_IMPORT_GAP_2026-06-13.md
  (nota empirica del 13/06/2026): testando `agy plugin import claude` su plugin
  in formato marketplace, il comando **non li riconosce** e risponde
  «No claude extensions found», perche' scansiona il *vecchio* formato di
  estensioni Claude (skills/agents/MCP dentro un bundle di estensioni), non i
  plugin del marketplace nuovo.

**Conclusione onesta**: la documentazione ufficiale non dice cosa importa
`agy plugin import claude`. Le fonti di terze parti indicano che (a) il
comando esiste, (b) migra il formato estensioni "tradizionale", e (c) coi
plugin marketplace nuovi puo' non trovare nulla. Prima di affidarsi alla
migrazione va collaudato su una copia vera. Il formato da scrivere a mano,
invece, e' certo e documentato: `mcp_config.json` + chiave `mcpServers`.

---

## 5. Una memoria sola per piu' agenti

### Pattern consolidati «una memoria, molti agenti»

Esistono e hanno nomi. La fonte principale aperta e'
https://mem0.ai/blog/multi-agent-memory-systems (blog del team dietro mem0):
il problema e' noto come **multi-agent memory**, e le architetture si
classificano per **dove vive lo stato condiviso**: una memoria centralizzata/
condivisa che tutti gli agenti leggono e scrivono, contro memorie per-agente
che si sincronizzano. Il post cita anche i dati di un paper sulle pipeline
multi-agente (Cemri et al.) che misurano l'allineamento fallito tra agenti
(36,9% dei failure dovuti a disallineamento inter-agente) — cioe' il problema
esatto che abbiamo visto con `codegraph` ripetuto.

Risultati di ricerca per il tema (snippet di ricerca, non testi aperti):
architetture documentate come "centralized", "shared memory", "event-driven /
blackboard" per multi-agent system. Un articolo di zylos.ai sul tema
(«AI Agent Memory Architectures for Multi-Agent Systems») appare nei risultati
ma **non l'ho aperto** e non ne riporto il contenuto.

**Per il nostro caso concreto** (un file `MEMORY.md`, `megamemory`, `codegraph`
e i documenti `AGENTS.md`/`DA-FARE.md`): il pattern consolidato e' la **memoria
centralizzata condivisa raggiungibile come servizio MCP** — esattamente il
ruolo che `codegraph` (fallimenti e pattern) e `megamemory` (concetti del
progetto) gia' giocano, e che il gateway del capitolo 2 rende raggiungibile da
tutti e tre gli agenti con una dichiarazione sola.

### «Quale memoria per cosa» quando ce ne sono piu' d'una

**Non trovata letteratura specifica.** I post che ho aperto (mem0) e i risultati
di ricerca che ho visto affrontano "come condividere UNA memoria", non "come
decidere QUALE memoria usa quale agente o quale dato". Nessun progetto o paper
che ho trovato definisce una partizione di competenze tra piu' memorie
(cooperative di esse). E' utile saperlo: **la decisione di quale memoria usa
cosa tocca a noi**, e il progetto ne ha gia' i germi — `codegraph` tiene
fallimenti/pattern/decisioni (procedurale), `megamemory` tiene concetti e
architettura (sistemico), `MEMORY.md`/`AGENTS.md`/`DA-FARE.md` sono i documenti
condivisi che i modelli leggono all'apertura. L'assenza di letteratura e'
anch'essa un risultato: non stiamo reinventando qualcosa di gia' risolto.

---

## 1. La raccomandazione

Adottare **1MCP** (`1mcp-app/agent`, Apache-2.0, 484★, push 2026-08-15) come
gateway aggregato, perche' e' l'unico candidato vivo e serio che:
1. **aggrega i nostri tre server stdio locali** in un solo endpoint HTTP
   streamable — ogni client punta a una URL sola;
2. **filtra per client** (preset/tag/lazy loading), che e' il vero guadagno in
   token su un sistema dove il contesto del Mac costa secondi di prefill;
3. e' esplicitamente provato per Claude Code (`claude mcp add -t http 1mcp
   "http://127.0.0.1:3050/mcp?app=claude-code"`), e il trasporto HTTP e'
   supportato anche da opencode (`type: "remote"`) e Antigravity CLI
   (`serverUrl`) — tutte e tre le capacita' verificate nelle documentazioni
   del capitolo 2.

Costo del cambio:
- **si installa**: `npm install -g @1mcp/agent` (runtime Node; va verificato
  che Node sia presente sul fisso, altrimenti aggiungerlo);
- **si configura**: un `1mcp mcp add <nome> -- <comando>` per ognuno dei tre
  server (`megamemory`, `codegraph`, `web-forager`), poi `1mcp serve` come
  servizio utente systemd sul fisso; poi, per ogni client, una sola riga: in
  `opencode.json` un `"mcp": { "nome": { "type": "remote", "url": ... } }`, in
  `.mcp.json` di Claude Code un entry `type: "http"` con la stessa URL, in
  `~/.gemini/config/mcp_config.json` un entry `serverUrl`;
- **si butta**: la triplice dichiarazione manuale dei tre server nei tre file
  (restano tre righe al posto di nove), non i server veri.
- Vincolo da rispettare (regola non negoziabile del progetto): prima di
  toccare `DEFINIZIONI` e i tool dei client, e prima di puntare i client al
  gateway, serve che fase 3 e fase 4 siano pronte — questo incarico **non
  chiede** di applicare nulla, solo di decidere.

Rischio da gestire esplicitamente: il gateway e' un singolo punto di guasto sul
fisso; quando il fisso dorme, tutti i client perdono gli strumenti insieme. Va
previsto il comportamento documentato: gli agenti rispondono "il fisso e'
spento" come gia' fanno oggi, ma per *tutti* i server insieme.

**Variante minima** (se il runtime di 1MCP sembra troppo): `sparfenyuk/mcp-proxy`
con `--named-server-config` — un processo solo, un port solo, formato
`mcpServers` gia' pronto, ma ogni server mantiene la sua URL (`/servers/<nome>/`)
e non si ha il filtro per client. Resta comunque "dichiarato in un posto solo".

## 2. L'alternativa pigra

Se la soluzione pronta non convince, tenere tre file allineati a mano e'
**gestibile, ma e' esattamente la classe di difetto che il progetto ha gia'
dichiarato di non volere** (due costanti che devono restare coerenti e nessuno
lo garantisce). Il costo della triplice dichiarazione e' basso **finche' i
server non cambiano**: oggi e' 3 server x 3 client, e due dei tre client
(opencode e agy) non hanno ancora i server configurati per intero.

Uno **script che rigenera i tre file da una sorgente sola** e' la via di mezzo
economica: una sola definizione canonica (per esempio un file `mcp-servers.json`
versionato, nel formato piu' comune `mcpServers`), e un piccolo generatore che
produce:
- il blocco `mcp` per `opencode.json`;
- il blocco `mcpServers` per `~/.gemini/config/mcp_config.json`;
- il blocco `mcpServers` per il `.mcp.json` di Claude Code.

Questo **non richiede di installare nulla e non introduce un singolo punto di
guasto**: la sorgente canonica vive nel repo, i file generati si rilanciano a
ogni modifica. E' il compromesso che tiene il controllo a mano senza la
triplicazione. Limite: non risolve il "server remoto vs stdio" (ogni client
continua a spawnare i processi stdio da solo) ma per tre server locali senza
segreti non serve.

## 3. Non trovato

- **Uno standard di configurazione MCP condiviso**: non esiste; e' una proposta
  aperta (#2218) alla data del 17/08/2026.
- **`agy plugin import claude`**: la documentazione ufficiale non dice cosa
  importa (solo `import gemini` e' documentato); fonti di terze parti indicano
  che non gestisce i plugin marketplace. **Da collaudare prima di fidarsi.**
- **Letteratura su "quale memoria per cosa" con piu' memorie**: non trovata.
- **Filtro per client nei proxy uno-a-uno** (sparfenyuk/punkpeye): non esiste;
  solo 1MCP lo offre.
- **Contenuto effettivo di lasso-security/mcp-gateway e matthisholleville/
  mcp-gateway**: riportato solo dal metadata GitHub, README non aperto.