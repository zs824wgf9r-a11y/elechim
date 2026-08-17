# RICERCA: `agy` come secondo agente, accanto a opencode

Ricerca sul web del 17 agosto 2026. Non ho lanciato `agy`, non ho toccato codice.
Ogni affermazione ha un URL che ho aperto davvero. Dove non ho trovato nulla
scrivo «non trovato».

---

## Sintesi — dieci righe

`agy` (Antigravity CLI, v1.1.13) e' **pilotabile meglio di opencode** sulle
righe in cui opencode ci ha bruciato la giornata, con **una riserva grave che
annulla parte del vantaggio**. Il lato buono, documentato ufficialmente in
https://antigravity.google/docs/cli/headless: timeout interno di default 5
minuti (`--print-timeout`), formato `stream-json` NDJSON con eventi
`init`/`step_update`/`result`, chiamate a strumento (`tool_info` con parametri,
output ed `error`), fine turno (`result`) e stati di errore nominati
(`ERROR`, `CANCELED`, `INTERRUPTED`, ecc.), exit code documentati (0 su
successo, non-zero con motivo su `stderr` e nei campi `status`/`error`).
Confini meccanici: `permissions.allow/deny/ask` con regole `action(target)`,
`--sandbox`, `--mode plan`, `allowNonWorkspaceAccess:false` di default, e il
nostro `AGENTS.md` viene letto (capitolo 5). Il lato brutto, **nel tracker**:
le issue #594 (hang con prompt ad alta entropia su Gemini, `--print-timeout`
ignorato, retry senza limite, stessa firma della #40330 di opencode), #548
(`--print` ignora `permissions.allow` e non esce al timeout) e #266/#573/#685
sono **tutte aperte** al 17/08/2026. Quindi **l'endpoint morto / l'hang resta
il punto non risolto anche per agy**: il guardiano esterno (`timeout` esterno)
serve comunque, e va previsto che agy possa appendersi ignorando il proprio
timeout. **Verdetto**: usabile come riserva e per eterogeneita' di modelli
(Gemini 3.x, Claude Sonnet/Opus 4.6, GPT-OSS 120B inclusi anche sul piano
gratuito) in incarichi a un turno con output strutturato e confini impostati
nei permessi; non fidarsi del `--print-timeout` come unica rete di sicurezza.

---

## 1. Il formato `stream-json`: basta a sorvegliare?

**Fonte principale aperta**: https://antigravity.google/docs/cli/headless
(sezione "Streaming JSON", "Tool calls in the stream", "Handle exit codes and errors").

### Incapsulamento

E' **NDJSON (newline-delimited JSON)**: una riga JSON per evento, in ordine di
produzione. Citazione della doc: "emit one JSON object per line (NDJSON) as the
run progresses".

### I tre eventi

Ogni riga e' un oggetto il cui campo `event` nomina il tipo. La doc definisce
**tre eventi**:

| evento | campo payload | quando |
|---|---|---|
| `init` | `init` | una volta, all'inizio dello stream |
| `step_update` | `step_update` | per ogni transizione di step o delta di testo |
| `result` | `result` | una volta, alla fine (stessa forma del formato `json`) |

### Campo `init`

Contiene `cwd`, `tools` (array di nomi di tutti i tool disponibili),
`permission_mode` (default `request-review`; `always-proceed` con
`--dangerously-skip-permissions`). `model` e `agent` appaiono solo se forzati
con `--model`/`--agent`; `json_schema` se impostato.

### Campo `step_update`

Un evento per step, con `conversation_id`, `step_index` (zero-based), `state`
(`ACTIVE` o `DONE`), `step_type`. I valori di `step_type` osservati e
documentati: `user_input`, `agent_response`, `tool`, `checkpoint`. Campi
opzionali: `tool_name`, `text_delta`, `duration_seconds`, `usage` (token
per-step), `tool_info`, `subagent_info`.

### Fine turno

**Si', esiste ed e' distinguibile**: l'evento terminale `result` riporta lo
stesso payload del formato `json`: `conversation_id`, `status`, `response`,
`error` (presente solo in caso di errore), `duration_seconds`, `num_turns`,
`structured_output`, `json_schema`, `usage`. E' un evento unico, marcato, non
confondibile con i delta parziali.

### Errore

**Si', distinguibile.** Nei formati `json` e `stream-json` il fallimento appare
nei campi `status` e `error` dell'evento `result`, e il processo esce con
codice non-zero. I valori di `status` documentati:

- `SUCCESS` — completato con risposta
- `ERROR` — finito con errore
- `CANCELED` — cancellato
- `INTERRUPTED` — interrotto (es. `SIGINT`)
- `INVALID` — stato invalido
- `WAITING` — finito in attesa di input
- `RUNNING` — non ha raggiunto uno stato terminale

Nota: `status` "terminal" per la doc significa stato di fine del run. Esempio
reale nella doc: modello inesistente → `status: "ERROR"`, `exit=1`, `error` con
il messaggio completo.

### Chiamate a strumento

**Si', documentato con esempio reale.** Gli step di tipo `tool` portano
`tool_info` con `name`, `parameters` (mappa parametro→valore) e `output`. In
caso di fallimento dello strumento c'e' un oggetto `error` con `type` e
`message`. La doc mostra un esempio di step tool `run_command` con parametro
`CommandLine: echo hello_headless_demo` e output. Gli step che lanciano
subagent portano `subagent_info` con `subagents` (ognuno con `type_name`,
`role`, `conversation_id`, `log_uri`, `workspace_uris`).

### Delta di testo

Gli eventi `agent_response` con `state: ACTIVE` portano frammenti `text_delta`
parziali; lo stesso step chiude con `state: DONE`. La doc suggerisce
`jq -j 'select(.event=="step_update") | .step_update.text_delta // empty'` per
ricostruire il testo. Questo e' l'equivalente di `message.part.updated`.

### Confronto onesto con lo SSE di opencode

| esigenza | opencode SSE (`session.*`, `message.part.updated`) | agy `stream-json` |
|---|---|---|
| stato sessione | `session.status`, `session.idle` | `init` + `step_update` con `state` ACTIVE/DONE |
| errore | `session.error` | evento `result` con `status: ERROR` + campo `error` |
| tool call | `ToolPart.state` | `step_update` con `step_type: tool`, `tool_info` (parametri, output, error) |
| fine turno | evento dedicato | evento dedicato `result` |
| delta testo | `message.part.updated` | `text_delta` su step `agent_response` |

I campi sono **nominati e documentati** in una pagina ufficiale con esempi di
output reale: questo gia' mette `stream-json` sopra lo SSE di opencode come
contratto. Restano da verificare in locale (non l'ho fatto, era vietato
lanciare `agy`): la presenza/assenza di un evento quando il run si blocca senza
produrre nulla, e la granularita' dei `step_index` (per es. se il `step_update`
di tipo `tool` arriva in stato ACTIVE prima dell'esito).

### Domande residue del capitolo

- La doc mostra un esempio dove gli step `user_input` e `checkpoint` appaiono
  nel flusso. Non ho trovato documentazione dell'ordine completo e garantito
  degli step (es. se ogni step compare sempre in coppia ACTIVE→DONE).
- «non trovato»: nessuna documentazione di cosa emette lo stream se il processo
  viene ucciso dal timeout o se il provider muore a meta' (vedi capitolo 2).

---

## 2. `--print-timeout`: cosa fa davvero allo scadere?

**Fonti principali aperte**: https://antigravity.google/docs/cli/headless
(sezioni "Handle exit codes and errors", "Flag reference").

### Cosa dice la documentazione ufficiale

- La tabella flag dice: `--print-timeout`, default `5m`, descrizione **"Maximum
  time to wait for a response"**.
- La doc sul comportamento: "By default, a run waits up to five minutes for a
  response. Adjust the ceiling with `--print-timeout`".
- Sugli exit code: "A successful run exits `0`. A run that fails to produce a
  response exits non-zero and writes the reason to `stderr`. In `json` and
  `stream-json` modes, the failure also appears in the `status` and `error`
  fields."

Quindi **allo scadere il processo NON resta appeso in silenzio**: esce con
codice non-zero e scrive il motivo su `stderr`. Il che e' gia' molto meglio
dell'opencode #40330 (che resta appeso 5h57m).

### Le lacune — quello che la doc NON dice

- **Uccide il processo o smette solo di aspettare?** La doc non lo dice
  esplicitamente. Dice «waits up to five minutes for a response» e «fails to
  produce a response exits non-zero»: l'interpretazione coerente e' che il run
  termina e il processo esce, ma il meccanismo esatto (terminazione della
  chiamata, poi chiusura pulita, o SIGKILL) **non e' documentato**.
- **Codice di uscita esatto al timeout**: la doc documenta `exit=1` per il caso
  «modello inesistente», e in generale non-zero su fallimento, ma **non
  documenta un codice specifico per il timeout** rispetto ad altri errori.
- **Caso endpoint morto**: la doc **non** documenta esplicitamente il
  comportamento con connessione rifiutata dal provider. L'unico caso documentato
  di «non hang» e' l'autenticazione mancante: "a run that is not already
  authenticated exits with an `authentication required` error instead of
  hanging" (in ambiente non interattivo). Questo copre il nostro caso solo per
  analogia, non per dichiarazione.
- **SIGTERM**: non ho trovato nulla nella documentazione. La doc menziona
  `SIGINT` solo come causa dello status `INTERRUPTED`.

### Verdetto provvisorio

`--print-timeout` da solo **sembra** coprire il caso «processo che aspetta per
sempre» (esce non-zero con motivo), ma la copertura esatta del caso endpoint
morto va **collaudata in locale dal proprietario** prima di fidarsene: la
documentazione non lo promette. Il guardiano esterno resta necessario anche per
agy, come per opencode.

### Domande residue

- «non trovato»: documentazione esplicita di (a) codice di uscita dedicato al
  timeout, (b) comportamento con connessione rifiutata, (c) gestione di SIGTERM.
  Ho verificato che queste cose non sono nelle pagine Headless mode, Flag
  reference, Troubleshooting (vedi capitolo 6 per il tracker, in cui le cerco
  nelle issue).

---

## 3. I confini: si impongono meccanicamente?

**Fonti principali aperte**: https://antigravity.google/docs/cli/permissions
(intera pagina, in particolare "Fine-grained permissions", "Supported actions &
matching rules", "Default system behaviors & guardrails") e
https://antigravity.google/docs/cli/sandbox (intera pagina).

Risposta breve: **si', molto meglio di "frasi in un prompt"**. I confini si
impongono con un motore di permessi a tre liste (`deny`/`ask`/`allow`) con
regole `action(target)`, piu' un sandbox di isolamento del sistema operativo.
C'e' anche `--mode plan` (verifico nella pagina dei modi di esecuzione, vedi
sotto).

### `--sandbox`: cosa restringe esattamente

Dalla pagina Sandbox: il **Terminal Sandbox** "restrict destructive shell
operations or unauthorized remote network calls". Non e' un contenitore pesante
ma utilita' di isolamento del kernel nativo:

- **Linux**: `nsjail` — isolatore di processi che confina CPU, memoria e
  **path visibility** (visibilita' dei percorsi).
- **macOS**: `sandbox-exec` — profili di policy che restringono accesso
  assoluto al filesystem e query TCP grezze.
- **Windows**: `AppContainer`.

Si attiva con `"enableTerminalSandbox": true` in
`~/.gemini/antigravity-cli/settings.json` (default `false`), o con il flag
`--sandbox` (come da `--help` e dalla pagina Using). La pagina Sandbox descrive
il sandbox come restrizione **dei comandi eseguiti dal terminale**: il testo
esatto e' "Restricts all local execution commands launched by agents to OS
containment rings". Per la scrittura su file il meccanismo indicato e' la
**policy dei permessi** (sotto), non il sandbox.

### Negare la scrittura su file/cartelle specifiche

**Si, direttamente**: lista `deny` in `~/.gemini/antigravity-cli/settings.json`
con regole `write_file(target)`. Esempi dati nella doc:

```json
{
  "permissions": {
    "deny": ["command(rm -rf)", "command(curl .*)", "command(sudo)",
             "write_file(.git/)", "write_file(/home/user/.ssh)"]
  }
}
```

Il target puo' essere un percorso assoluto, relativo (alla workspace), o `*`.
Azioni supportate: `read_file`, `write_file`, `read_url`, `execute_url`,
`command`, `unsandboxed`, `mcp`. Precedenza **Deny > Ask > Allow**.

Regole implicite documentate:
- **Write implies Read**: allow `write_file` su un path autorizza anche
  `read_file` su quel path.
- **Deny Read implies Deny Write**: deny `read_file` su un path blocca anche
  `write_file` su quel path.

Nota rilevante per il nostro caso («non toccare `sbobina.py`»): si puo'
scrivere una regola `deny` come `write_file(sbobina.py)` o `write_file(directory/)`
che blocca meccanicamente la scrittura, non solo via prompt. (Per la sintassi
esatta di un target relativo, `write_file(src/)` e' l'esempio che la doc usa
nell'allow — da verificare in locale se accetta un file singolo relativo.)

### `--add-dir`: cosa succede scrivendo fuori

La pagina dei permessi da' il comportamento: le operazioni non configurate
**default a `Ask`**; in headless mode non c'e' prompt interattivo e un'azione
che richiederebbe approvazione viene **soft-denied**: il run continua, esce `0`,
e stampa una notifica su `stderr` col nome del tool e come autorizzarlo. La
pagina Headless dice anche: "Reading and writing files inside your active
workspace is auto-allowed".

Dunque: scrivere fuori dalla workspace non da' un errore del run, ma la
scrittura **non avviene** e l'evento e' segnalato su `stderr` (in headless
mode). Nelle pagine aperte non trovo una descrizione esplicita del
comportamento di `--add-dir` nel caso specifico di scrittura fuori workspace —
la regola generale dei permessi copre il caso, ma la doc non nomina `--add-dir`
in quella pagina. Vedere anche la pagina Projects (sotto) per come si definisce
la workspace.

### `--mode plan`: impedisce davvero ogni modifica?

Dalla pagina https://antigravity.google/docs/cli/modes (sezione "Analyze tasks
before editing with plan mode"):

> When `plan` mode is active via `Shift+Tab` cycling or the `--mode` flag, the
> CLI automatically prepends the `/plan` instruction prefix to your prompts.
> The agent investigates relevant files using read-only tools (`code_search`,
> `grep_search`, `view_file`) and presents a structured execution outline for
> your approval **before writing code**.

Quindi `plan` fa due cose: forza il prefisso `/plan` e **dirige l'agente verso
strumenti di sola lettura** per investigare, presentando l'outline prima di
scrivere. Nota onesta: il meccanismo descritto e' «prepends the /plan
instruction prefix» + strumenti read-only presentati — e' un limite che il
modello segue tramite la lista degli strumenti, non un blocco a livello di
sistema tipo il `deny` dei permessi. Per un blocco *meccanico* della scrittura,
lo strumento giusto resta la regola `deny` di `write_file` nel settings (vedi
sopra). La pagina modes conferma anche che le regole di permesso (`/permissions`
o `--dangerously-skip-permissions`) governano i comandi shell `run_command` in
**tutti** i modi di esecuzione.

### Domande residue

- Sintassi esatta dei target relativi in `deny` per file singolo (`sbobina.py`)
  — documentata solo con esempi su directory (`src/`) e percorsi assoluti.
- Se `deny` su un file produce errore visibile nel `stream-json` o solo la
  notifica `stderr` — da verificare in locale.

---

## 4. Costo e quota

**Fonti principali aperte**:
https://antigravity.google/docs/cli/credits (intera),
https://antigravity.google/docs/plans (intera),
https://antigravity.google/docs/models (intera).

### Piano gratuito e limiti

C'e' un livello gratuito, e le quote sono descritte **qualitativamente**, senza
numeri di richieste al minuto/giorno:

- https://antigravity.google/docs/plans: «All plans receive a baseline of...» e
  tre fasce: **Google AI Ultra** (quota piu' alta, rinnovata ogni **cinque
  ore**, rate limit settimanali piu' alti), **Google AI Pro** (quota alta,
  rinnovata ogni cinque ore fino al tetto settimanale), e **chi non ha AI Pro
  ne' Ultra** (quota «meaningful», rinnovata **settimanalmente**, rate limit
  settimanale). Il testo preciso per gli ultimi: "Users not on AI Pro and Ultra
  plans receive: Meaningful quota, refreshed weekly; Weekly rate limit".
- La pagina dice esplicitamente che i limiti **non sono fissi**: "Under the
  hood, the rate limits are correlated with the amount of work done by the
  agent... you may get many more prompts if your tasks are more straightforward".
- https://antigravity.google/docs/models: la colonna dei piani elenca "Free &
  Google AI Plus" come prima fascia, quindi **il modello Gemini e i modelli di
  terze parti sono disponibili anche sul piano gratuito** (vedi sotto).

### Modelli non-Google (`claude-*`, `gpt-oss-*`): compresi o a parte?

**Compresi nel piano, non un pagamento a parte.** Dalla tabella di
https://antigravity.google/docs/models: Claude Sonnet 4.6 (thinking), Claude
Opus 4.6 (thinking) e GPT-OSS-120b hanno tutti **✅ nella colonna "Free &
Google AI Plus"** (e Pro, e Ultra); sono **❌ solo per Enterprise**. La pagina
Plans conferma: "Users on Google AI Ultra receive: ... Access to third-party
models". Nota: **la colonna Free ha i modelli terzi ✅** — quindi non serve un
abbonamento a pagamento per usarli.

### Superamento della quota: errore chiaro o degrado silenzioso?

La pagina Plans descrive gli **overages** solo per Pro/Ultra: si usano **crediti
AI acquistati** (https://antigravity.google/docs/plans sezione "Overages",
link a one.google.com/ai/credits) al "standard Gemini Enterprise Agent Platform
consumption pricing", con una scelta utente (`Never`/`Always`). Per chi e' sul
gratuito **non ho trovato documentazione del messaggio esatto al superamento**
della quota (testo, codice di uscita, o stato `ERROR`). C'e' pero' una
segnalazione di quota: il `/usage` command (Model Quotas,
https://antigravity.google/docs/cli/commands/usage) e lo statusline mostrano
crediti e quota residua; quindi il superamento e' **osservabile a monte**, ma il
comportamento a valle (come si presenta l'errore in headless) resta da
verificare in locale.

### Domande residue

- «non trovato»: numeri esatti dei limiti gratuiti (richieste/giorno o
  settimana, token) e messaggio di errore esatto al superamento della quota.
- Se il superamento della quota su piano gratuito produce uno stato `ERROR`
  nell'evento `result` o un hang: da collaudare in locale.

---

## 5. Convenzioni di progetto

**Fonti principali aperte**: https://antigravity.google/docs/cli/reference
(tabella config keys), https://antigravity.google/docs/cli/using (settings),
https://antigravity.google/docs/cli/headless (sezione `init`),
https://antigravity.google/docs/cli/modes (sezione `agentMode`),
https://antigravity.google/docs/cli/projects (intera).

### File di istruzioni di progetto (AGENTS.md, GEMINI.md, .antigravity/)

**Si': legge `AGENTS.md` e `GEMINI.md`.** Non l'ho trovato nelle pagine di
configurazione ma nella pagina di migrazione da Gemini CLI,
https://antigravity.google/docs/cli/gcli-migration (sezione "Context files and
workspace rules"):

> Both CLI platforms utilize identical workspace context rules. No modifications
> are needed to your existing rule documents:
> - **Workspace local context**: The agent continues to parse and enforce rule
>   constraints defined inside your active directory's `GEMINI.md` and
>   `AGENTS.md` files.
> - **Global developer context**: The agent automatically consults and enforces
>   your global constraints located at `~/.gemini/GEMINI.md`.

Quindi: **il nostro `AGENTS.md` viene letto automaticamente** dall'agente, sia
in locale (`AGENTS.md`/`GEMINI.md` nella directory attiva) sia globale
(`~/.gemini/GEMINI.md`). La stessa pagina conferma la compatibilita' col
"project" e menziona anche i path delle skills (`.agents/skills/` invece di
`.gemini/skills/`). Da verificare in locale: se la regola vale anche in
headless `-p` (la doc non distingue).

### Rispetta il cwd del processo?

Sul cwd, le evidenze sono indirette ma coerenti:

- https://antigravity.google/docs/cli/headless, formato `json`: l'evento `init`
  dello `stream-json` riporta `cwd` e `tools`; nell'esempio l'`init` mostra
  `"cwd":"/home/user/project"`. Questo indica che la workspace **e' derivata
  dal processo che lancia agy** (o da un progetto aperto).
- https://antigravity.google/docs/cli/reference: chiave
  **`allowNonWorkspaceAccess`** (boolean, default `false`): "Permits the
  agent's file read and write tools to navigate outside recognized Git/workspace
  roots". Quindi di default l'agente **non** naviga fuori dalle root Git/workspace
  riconosciute — il che risponde anche alla domanda 3 («cosa succede se scrive
  fuori»): di default non puo', a meno di abilitare la chiave o concedere
  permessi specifici.
- Il riferimento del flag `--add-dir` esiste nel Reference come `/add-dir <path>`
  (slash command: "Add a directory path to the active workspace").

Verdetto onesto: la doc non dice in una riga «agy usa il cwd del processo come
workspace». Ma l'`init.cwd` nello stream e la chiave `allowNonWorkspaceAccess`
insieme indicano che la workspace parte dal percorso di lancio e che uscire da
essa e' **impedito di default**. Il comportamento esatto con un percorso
assoluto (il caso che a opencode e' costato una sessione) va collaudato in
locale.

### File di configurazione e dove

**`~/.gemini/antigravity-cli/settings.json`**, confermato da tre pagine:
https://antigravity.google/docs/cli/using ("Configuration File: Stored in a
plain JSON file `~/.gemini/antigravity-cli/settings.json`"),
https://antigravity.google/docs/cli/permissions (permessi in tre liste,
`deny`/`ask`/`allow`), https://antigravity.google/docs/cli/reference (tabella
delle chiavi: `colorScheme`, `toolPermission`, `enableTerminalSandbox`,
`allowNonWorkspaceAccess`, `agentMode` — vedi https://antigravity.google/docs/cli/modes —
`useG1Credits`, `verbosity`, ecc.). Le chiavi sono sovrascrivibili da flag CLI
per sessione (es. `--sandbox`, `--mode`).

### Domande residue

- Se `AGENTS.md` viene applicato anche in headless `-p` (la pagina di migrazione
  non distingue): da collaudare in locale.
- Se il percorso assoluto fuori cwd viene trattato come external directory
  (caso opencode) o bloccato da `allowNonWorkspaceAccess`: da collaudare.

---

## 6. Cos'e' esattamente, e guasti noti

**Fonti principali aperte**: https://antigravity.google/docs/cli/gcli-migration
(intera), https://antigravity.google/changelog (release note CLI 1.1.x),
il tracker https://github.com/google-antigravity/antigravity-cli/issues.

### agy / Antigravity / Gemini CLI: che rapporto?

`agy` e' **il successore di Gemini CLI sotto il marchio Antigravity**: la pagina
di migrazione (https://antigravity.google/docs/cli/gcli-migration) si intitola
"Migrating from Gemini CLI" e dice che Antigravity CLI "preserves backward
compatibility with the core developer-experience constructs popularized by
Gemini CLI". Google annuncia il passaggio: "Transitioning Gemini CLI to
Antigravity CLI" (titolo dell'articolo Google Developers Blog, visto nel
risultato di ricerca searxng:
https://developers.googleblog.com — non ho aperto l'articolo, riporto il titolo
come compare nei risultati).

Punti di continuita' dichiarati dalla pagina di migrazione:
- **stesse regole di contesto**: `GEMINI.md` e `AGENTS.md` (capitolo 5);
- **conversione dati automatica** al primo avvio: estensioni, token in keyring,
  settings; piu' `agy plugin import gemini` per la migrazione esplicita;
- **path aggiornati**: skills globali in `~/.gemini/antigravity-cli/skills/`
  (prima `~/.gemini/skills/`), skills di workspace in `.agents/skills/` (prima
  `.gemini/skills/`); MCP in `~/.gemini/config/mcp_config.json` con chiave
  `serverUrl`.

Rapporto con il vecchio `gemini` CLI: condividono la directory `~/.gemini/`
(settings, OAuth, `GEMINI.md` globale) ma sono binari diversi; agy e'
l'evoluzione che sostituisce gemini (la migrazione e' unidirezionale
gemini → agy). Il proprietario dice che `gemini` non funziona: coerente con la
sostituzione. La doc non presenta agy come dipendente dal vecchio gemini.

### Issue note di blocco/stallo — il punto che decide tutto

**Si', agy ha la stessa famiglia di difetti di opencode #40330**, e le issue
sono **aperte** al momento di questa ricerca. La piu' importante:

- **#594 — «agy --print hangs indefinitely when high-entropy prompts hit Gemini
  backends, ignoring --print-timeout ... evidence of silent retries draining
  weekly quota»** (https://github.com/google-antigravity/antigravity-cli/issues/594,
  aperta, 13/07/2026). Con prompt ad alta entropia su backend Gemini il
  processo **non esce mai**, superando il `--print-timeout` di 3.3x e 2.5x, e va
  ucciso con SIGTERM esterno. Con lo stesso prompt su GPT-OSS esce `0` in 3.9s:
  il difetto e' nel percorso di gestione della richiesta Gemini. Testo
  dell'issue: "the Gemini backend rejects the high-entropy prompt server-side
  and agy retries that rejection in an unbounded loop that also suppresses/
  resets the `--print-timeout`". **E' esattamente il nostro caso #40330.**

- **#548 — «--print (headless) mode ignores permissions.allow entirely; ...
  stalls silently and permanently in headless mode — and the process does not
  exit at --print-timeout»** (aperta, 06/07/2026). Doppio guasto: permessi
  `allow` non consultati in headless, e di nuovo il processo non esce al timeout.

- **#266 — «Print mode (-p) times out when the agent generates long <thinking>
  blocks»** (aperta, 02/06/2026): con thinking lungo, print mode va in timeout
  per un **limite hardcoded di 5 minuti** (`printmode.go:263`, "timed out after
  1496 polls"), indipendente dal `--print-timeout`.

- **#573 — «agy -p hangs indefinitely when launched concurrently with 3+ other
  CLI processes»** (aperta, 09/07/2026): hang completo con 3+ processi
  concorrenti; un'istanza e' rimasta appesa 4,5 ore.

- **#134 — busy-loop al 100% CPU dopo lo stream; il processo non esce alla
  disconnessione del terminale** (aperta, 22/05/2026).

- **#685 — `view_file` non emette risultato in print mode ripresa; il processo
  resta in attesa finche' il watchdog esterno non lo termina** (aperta,
  25/07/2026).

- **#779 — «Cancellation and status for long-running non-interactive runs»**
  (aperta, 11/08/2026): chiede esplicitamente un modo per sapere se un run e'
  ancora vivo e per cancellarlo; l'autore nota che l'unica leva oggi e'
  `--print-timeout`, "a deadline chosen before the work starts, not a control
  during it", e che uccidere con SIGTERM/SIGKILL non garantisce nulla di
  strutturato in stdout.

Guasti storici **risolti** (cadenza di riparazione):
- **#76 — stdout vuoto in non-TTY** (chiusa): serie 1.0.x su Windows non
  scriveva nulla su stdout quando era una pipe; fix `1.0.15` (redirect
  `CONOUT$` su Windows) e `1.1.1` (errori server-side → `stderr` + exit
  non-zero invece di exit 0 silenzioso). Dal thread e dal changelog.
- **#408 — stdout vuoto / exit 0 su pipe** (stesso filone di #76).

Sintesi onesta: **se `agy` incontra un backend che rifiuta in un certo modo o
un errore che attiva un retry, puo' appendersi ignorando il `--print-timeout`,
proprio come opencode.** Il numero di issue aperte di questa famiglia indica che
non e' un caso isolato. Il guardiano esterno serve comunque; la differenza e'
che agy ha piu' spesso un comportamento pulito documentato (exit non-zero con
motivo), ma non lo garantisce.

### E' vivo? Ultima release, cadenza

**Si', molto vivo.** Versione corrente **1.1.13** (14/08/2026,
https://github.com/google-antigravity/antigravity-cli/releases/tag/1.1.13),
coerente con quella installata dal proprietario. Dal changelog ufficiale
(https://antigravity.google/changelog) cadenza **settimanale** (1.1.13 il
14/08, 1.1.12 l'11/08, 1.1.11 il 07/08, 1.1.10 il 03/08, 1.1.9 il 31/07,
1.1.8 il 28/07). Fix recenti rilevanti per noi:
- **1.1.13**: supporto `GEMINI_API_KEY` + `GOOGLE_GEMINI_BASE_URL` per endpoint
  custom; fix "hung sandbox initialization prevented subsequent messages";
- **1.1.12**: output `json`/`stream-json` anche per i sottocomandi
  `models`/`agents`; fix "headless `-p` runs so the agent settles a choice
  itself ... instead of stalling on a question nobody is there to answer"; fix
  `--mode` ignorato in headless;
- **1.1.10**: "honoring the server-supplied retry delay instead of the client's
  own backoff".

Nota: il changelog e' della piattaforma Antigravity (IDE + CLI); le note CLI
sono sotto la voce "Antigravity CLI v1.1.x".

### Domande residue

- Stato dei fix per #594/#548/#266: **aperte** al 17/08/2026. Da ricontrollare
  prima di affidare lavoro reale.
- «non trovato»: dichiarazione ufficiale su come agy gestisce SIGTERM (se fa
  flush del transcript, se esce pulito); #779 la chiede, quindi non e'
  documentato.
- «non trovato»: limite meccanico al numero di retry o budget di errore interno.

---

## Ricetta minima — lanciare, sorvegliare, uccidere

Basata solo su documentazione aperta; **da collaudare dal proprietario**, perche'
le issue #594/#548 mostrano che il comportamento documentato non e' sempre
quello reale.

```bash
# 1. Lanciare un incarico non interattivo, output machine-readable, timeout
#    interno 10m, piano di sola lettura:
agy --print "testo incarico" \
    --output-format stream-json \
    --print-timeout 10m \
    --mode plan \
    > run.ndjson 2> run.err

# 2. Leggere gli eventi (una riga JSON per evento):
#    init (config: cwd, tools, permission_mode) / step_update (stato step,
#    tool_info con parametri+output+error, text_delta) / result (fine turno,
#    status: SUCCESS|ERROR|CANCELED|INTERRUPTED|..., response, usage).
jq -c 'select(.event=="result") | .result.status' run.ndjson
jq -c 'select(.event=="step_update" and .step_update.step_type=="tool")
      | .step_update.tool_info' run.ndjson

# 3. Accorgersi che e' piantato:
#    - nessun nuovo evento su stdout per N secondi: lo stream-json NON
#      garantisce un heartbeat quando il run e' piantato (#594/#548/#685);
#    - exit code: 0 = risposta; non-zero = fallimento con motivo su stderr
#      (ma attenzione ai bug dove esce 0 con output vuoto o non esce affatto).
#    - stati non-terminali documentati: RUNNING, WAITING.

# 4. Ucciderlo: il guardiano esterno resta la rete di sicurezza.
timeout 660 agy --print "..." --output-format stream-json \
    --print-timeout 10m > run.ndjson 2> run.err
#    exit 124 = scattato il timeout esterno. SIGTERM a agy: non documentato
#    (#779); SIGINT -> status INTERRUPTED.

# 5. Confini meccanici consigliati in settings.json
#    (~/.gemini/antigravity-cli/settings.json):
#    "permissions": {"deny": ["write_file(<file da proteggere>)", ...],
#                     "allow": ["command(git)", ...]},
#    "allowNonWorkspaceAccess": false, "enableTerminalSandbox": true
```

## Confronto: `agy` vs `opencode run` vs `opencode serve` + SSE

| riga (quella che ci e' costata oggi) | `agy --print` | `opencode run` | `opencode serve` + SSE |
|---|---|---|---|
| timeout interno | si, `--print-timeout` default 5m — **ma ignorabile per bug aperti (#594, #548, #266)** | **no** (#40330, not planned) | **no** |
| eventi di progresso | `stream-json` NDJSON: `init`/`step_update`/`result`, documentati con campi esatti | SSE `session.status`/`session.idle` | SSE `session.status`/`session.idle`, `message.part.updated` |
| evento di fine turno | `result` (unico, con `status` e `response`) | `session.idle`/fine sessione | `session.idle` |
| evento di errore | `result.status: ERROR` + campo `error` + exit non-zero | `session.error` **non pubblicato** (#40330) | `session.error` non sempre emesso |
| dettaglio tool call | `step_update.step_type: tool` + `tool_info` (name, parameters, output, error) | `ToolPart.state` | `ToolPart.state` |
| abort da host | kill esterno; SIGTERM non documentato (#779), SIGINT→`INTERRUPTED` | kill esterno; SIGTERM non gestito (#24658) | kill esterno |
| confini meccanici | `permissions.allow/deny/ask` con regole `action(target)`, `allowNonWorkspaceAccess:false` di default, `--sandbox`, `--mode plan` — con bug aperti in headless (#548, #45) | solo permessi di sessione; niente deny meccanico per file | come `run` |
| file istruzioni progetto | `AGENTS.md` + `GEMINI.md` (locale) e `~/.gemini/GEMINI.md` (globale), documentato | `AGENTS.md` | `AGENTS.md` |
| cwd rispettata | workspace dal processo (`init.cwd`); fuori root bloccato di default | **no** (path assoluto = external directory) | come `run` |
| costo | piano gratuito con quota settimanale; Gemini 3.x + Claude 4.6 + GPT-OSS inclusi (anche su Free) | dipende dal modello scelto | come `run` |
| errore quota | `/usage` + statusline; messaggio esatto su Free non documentato; storicamente esaurimento quota = hang silenzioso in -p (#76 thread, #56) | errori provider in `session.error` (quando pubblicato) | come `run` |

Verdetto: sulle righe che ci sono costate oggi **agy e' superiore sulla carta**
(timeout interno, errori nominati, confini meccanici, cwd), ma il divario si
assottiglia sulle issue aperte: la stessa famiglia di hang esiste anche qui
(#594, #548). Quindi **il guardiano esterno non si risparmia** — si risparmia
la parte «aspettare 5 ore», perche' il timeout interno documentato e gli exit
code fanno accorgere prima.

## «Non trovato»

- Documentazione esplicita del meccanismo esatto di `--print-timeout` allo
  scadere (uccisione vs attesa abbandonata) e di un codice di uscita dedicato
  al timeout.
- Comportamento documentato con **connessione rifiutata dal provider**
  (endpoint morto): la doc copre solo l'autenticazione mancante.
- Documentazione della gestione di **SIGTERM** (flush del transcript, exit
  pulito); #779 la chiede come "a documented answer for the kill case".
- Numeri esatti dei limiti del piano gratuito (richieste al giorno/settimana,
  token) e messaggio di errore esatto al superamento quota su piano gratuito.
- Una dichiarazione ufficiale su limiti di retry o budget di errore interni.
- File `.antigravity/` come fonte di istruzioni: non trovato; le istruzioni di
  progetto sono `AGENTS.md`/`GEMINI.md`.
- `agy status`/`cancel`: non esistono (richiesti in #779, aperta).

## Fonti aperte in questa ricerca

- https://antigravity.google/docs/cli/headless (capitoli 1, 2, ricetta)
- https://antigravity.google/docs/cli/permissions (capitolo 3)
- https://antigravity.google/docs/cli/sandbox (capitolo 3)
- https://antigravity.google/docs/cli/modes (capitolo 3)
- https://antigravity.google/docs/cli/reference (capitoli 3, 5)
- https://antigravity.google/docs/cli/credits, .../plans, .../models (capitolo 4)
- https://antigravity.google/docs/cli/using (capitolo 5)
- https://antigravity.google/docs/cli/projects (capitolo 5)
- https://antigravity.google/docs/cli/gcli-migration (capitoli 5, 6)
- https://antigravity.google/changelog (capitolo 6)
- Tracker: https://github.com/google-antigravity/antigravity-cli/issues
  (issue #594, #548, #266, #573, #134, #685, #779, #76, #45, #408, #56;
  release 1.1.8–1.1.13)
