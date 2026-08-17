# Incarico: un solo posto per gli MCP, invece di tre

Scritto il 17 agosto 2026. Ricerca sul web: **non tocchi codice e non tocchi
nessuna configurazione**. Produci un solo file, `RICERCA-mcp.md`.

## Il problema, misurato oggi

Tre agenti lavorano sullo stesso progetto e ognuno ha la sua configurazione MCP,
in un file diverso, mantenuta a mano:

| agente | file | server MCP |
|---|---|---|
| Claude Code | `~/.claude.json` | `megamemory`, `web-forager`, `codegraph` |
| opencode | `~/.config/opencode/opencode.json` | `megamemory` (oggi aggiunti gli altri due a mano) |
| agy (Antigravity CLI) | `~/.gemini/antigravity-cli/settings.json` | **nessuno**, e il formato non e' verificato |

Sono tutti e tre server **stdio locali** senza segreti:
`megamemory`, `/usr/local/bin/codegraph`, `web-forager serve`.

Il danno concreto: `codegraph` tiene la memoria dei fallimenti e delle decisioni
(`recall_failures`, `recall_patterns`, `add_decision`). Finche' ce l'aveva un
agente solo, gli altri ripetevano errori gia' pagati. E ogni server aggiunto va
scritto tre volte, in tre sintassi diverse, senza che niente garantisca che
restino allineate — che e' la stessa classe di difetto di due costanti che devono
restare coerenti e nessuno lo garantisce.

## Le domande

Per ognuna: **URL davvero aperto**, licenza, se il progetto e' vivo (ultima
release o commit), e «non trovato» dove non c'e' niente.

### 1. Esiste un modo standard di dichiarare i server MCP una volta sola?

- La specifica MCP (modelcontextprotocol.io) definisce un **percorso o formato di
  configurazione condiviso** fra client diversi? O ogni client fa come gli pare?
- Esiste una convenzione emergente tipo `.mcp.json` di progetto, o una variabile
  d'ambiente, che piu' client rispettino **davvero**? Quali client la leggono?
- I tre client che ci interessano (Claude Code, opencode, Antigravity/Gemini CLI)
  sanno **includere** un altro file di configurazione, o importarlo?

### 2. I gateway / proxy / aggregatori MCP

E' la soluzione che mi aspetto esista: **un solo server MCP** davanti a tutti gli
altri, cosi' ogni client punta a una cosa sola e i server veri si dichiarano in un
posto solo.

- Quali progetti esistono? Cerca almeno: `mcp-proxy`, MCP **gateway**, MCP **hub**,
  MCP **router**, MCP **aggregator**, e la roba di Docker (MCP Gateway/Toolkit).
- Per ciascuno: cosa fa esattamente, **licenza**, se e' vivo, e se e' un progetto
  serio o un esperimento di tre settimane.
- **Il punto che decide**: un gateway puo' esporre server **stdio locali** (i
  nostri lo sono) e presentarsi ai client come **un server solo**? Con che
  trasporto verso i client — stdio, HTTP, SSE?
- I nostri tre client accettano un server MCP **remoto/HTTP**, o solo stdio?
  Verificalo per ognuno nella sua documentazione: e' la condizione senza la quale
  il gateway non serve a niente.

### 3. Cosa si perde o si rischia con un gateway

Voglio il rovescio della medaglia, non solo i pregi.

- Diventa un **singolo punto di guasto**: se il gateway non parte, tutti e tre gli
  agenti perdono tutti gli strumenti in una volta. Qualcuno lo affronta?
- I **nomi degli strumenti** collidono fra server diversi? C'e' un prefisso?
- Si perde qualcosa nel passaggio (risorse, prompt, notifiche, campionamento)?
- Costo in **token**: piu' strumenti visibili = piu' definizioni nel contesto di
  ogni turno. Un gateway permette di **filtrare** quali strumenti esporre a quale
  client? Sarebbe il vero guadagno, non solo l'unificazione.

### 4. Il formato MCP di agy (Antigravity CLI) — serve comunque

Anche col gateway, agy va configurato almeno una volta.

- Dove si dichiarano i server MCP per **Antigravity CLI**? Nome esatto del file e
  della chiave. `~/.gemini/settings.json`, `~/.gemini/antigravity-cli/settings.json`,
  o altro? Riporta un esempio **preso dalla documentazione**, non dedotto da
  Gemini CLI.
- `agy plugin import claude` cosa importa davvero: skill, server MCP, o entrambi?
- Se la documentazione non lo dice, **scrivilo chiaro**: e' la cosa che ci
  blocca, e preferiamo un «non trovato» onesto a un formato dedotto.

### 5. Una memoria sola per piu' agenti

La domanda sotto la domanda. Noi abbiamo la conoscenza del progetto sparsa in
**quattro** posti: un file `MEMORY.md`, `megamemory`, `codegraph`, e i documenti
condivisi `AGENTS.md`/`DA-FARE.md`.

- Esiste un modello consolidato per «una memoria, molti agenti»? Nomi di
  progetti, o almeno di pattern documentati.
- Qualcuno ha scritto sul problema di **quale memoria usare per cosa** quando ce
  ne sono piu' d'una? Se non c'e' letteratura, dillo: e' utile sapere che tocca
  decidere a noi.

## Cosa NON fare

- **Non modificare nessuna configurazione**: ne' `~/.claude.json`, ne'
  `~/.config/opencode/opencode.json`, ne' niente sotto `~/.gemini/`. Qui si legge
  e si riporta.
- **Non installare niente** e non lanciare `agy`.
- Non toccare file di codice, altri `INCARICO-*`, `RAPPORTO-*`, `AGENTS.md`,
  `DA-FARE.md`, git. **L'unico file che scrivi e' `RICERCA-mcp.md`.**
- Non inventare nomi di progetti, percorsi di configurazione o chiavi. Se non
  l'hai letto, dillo.

## Come cercare

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235
```

piu' `webfetch` per gli URL che hai gia'. Fonti valide in ordine: la **specifica
MCP** ufficiale, la **documentazione** dei tre client, i **repo** dei gateway.

## Come si scrive `RICERCA-mcp.md`

Un capitolo per domanda, e in cima una **sintesi da dieci righe** che risponda a
una cosa sola: **esiste una soluzione pronta per dichiarare gli MCP una volta e
usarli da tre agenti, si' o no, e quale conviene a noi che abbiamo tre server
stdio locali e nessun segreto?**

Chiudi con:

1. **La raccomandazione**: cosa faresti tu, con il costo del cambio (cosa si
   installa, cosa si configura, cosa si butta).
2. **L'alternativa pigra**: se la soluzione pronta non convince, tenere tre file
   allineati a mano e' cosi' grave? Cosa costerebbe uno script che li rigenera da
   una sorgente sola.
3. Una sezione **«non trovato»**.

Scrivi il file **un capitolo alla volta mentre lavori**, non alla fine.
