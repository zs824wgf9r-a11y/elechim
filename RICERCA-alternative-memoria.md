# RICERCA-alternative-memoria.md — Oltre Honcho: candidati per la fase 3

> Scritta il 17 agosto 2026, dopo la misura sull'attribuzione del parlante
> (`misura_attribuzioni.py`): il deriver di Honcho con qwen3:8b attribuisce al
> proprietario le frasi dell'assistente. Questa ricerca cerca sostituti o
> correttivi. `RICERCA-memoria.md` ha gia' confrontato Honcho, Graphiti, mem0 e
> cognee: si parte da li', qui si cerca ALTRO.
> Nessuna installazione, nessun clone, nessun tocco a codice/archivio/stato.
> L'unico file scritto e' questo.

## Come ho cercato

SearXNG su `127.0.0.1:8888`, crawl4ai su `127.0.0.1:11235` per leggere le
pagine (markdown con PruningContentFilter), API GitHub con token da `.env` per
stelle/licenza/ultimo commit/release. Ogni affermazione ha un URL aperto.

Query usate:

- "agent memory without LLM extraction deterministic" — ha portato a
  shodh-memory (`https://www.shodh-memory.com/llm-free-memory`).
- "conversation memory speaker attribution" e "memory extraction no LLM hybrid
  deterministic" — conferma del problema e nessun sistema mainstream che ne
  parli.
- "memary kingjulio8238 architecture", "A-MEM memory agent", "txtai agent
  memory", "memobase memory", "LangMem langchain memory", "Letta MemGPT memory
  agent" — schede dei candidati.
- "neo4j agent memory running without an LLM" — modalita' senza LLM di
  neo4j-labs/agent-memory (`https://neo4j.com/labs/agent-memory/how-to/running-without-an-llm/`).
- "supermemoryai supermemory local", "supermemory speaker attribution user
  assistant facts", "supermemory Italian language multilingual", "LongMemEval
  assistant user recall categories" — scheda supermemory e benchmark.
- "shodh-memory review", "shodh-memory Rust memory alternative mem0" — nessuna
  recensione indipendente seria; emerge solo `memayu`, progetto di ieri con 0
  stelle (`https://github.com/savioruz/memayu`).

Metadati GitHub (17 agosto 2026, stelle e stato):

| Progetto | Stelle | Licenza | Ultimo push | Release | Stato |
|---|---|---|---|---|---|
| supermemoryai/supermemory | 28.938 | MIT | 2026-08-17 | server-v0.0.8 | attivo |
| letta-ai/letta | 24.287 | Apache-2.0 | 2026-08-16 | 0.16.8 | attivo |
| neuml/txtai | 12.895 | Apache-2.0 | 2026-08-12 | v9.12.0 | attivo |
| getzep/zep | 4.844 | Apache-2.0 | 2026-08-13 | zep-ingest-v0.2.0 | solo esempi Cloud |
| memodb-io/memobase | 2.845 | Apache-2.0 | 2026-01-11 | nessuna | **stale 7 mesi** |
| kingjulio8238/Memary | 2.638 | MIT | 2024-10-22 | — | **morto** |
| langchain-ai/langmem | 1.612 | MIT | 2026-08-11 | nessuna | attivo |
| agiresearch/A-mem | 1.149 | MIT | 2025-12-12 | — | attivo |
| varun29ankuS/shodh-memory | 272 | Apache-2.0 | 2026-08-17 | gliner-bi-edge-onnx-v1 | attivo, 1.650 commit |
| neo4j-labs/agent-memory | 417 | Apache-2.0 | 2026-08-17 | v0.4.0 | attivo |

## Criterio 1 — Budget di token al recupero (~300 token)

Vincolo: il Mac genera a ~21-23 tok/s, ogni 1.000 token = ~45 s di prefill. Il
recupero deve essere comprimibile a ~300 token. Quello che non si puo'
limitare e' FUORI.

- **supermemory**: il retrieval non ha un budget di token esplicito ma ha un
  numero di risultati (`limit`, default 10) e una soglia di similarita'
  (`threshold`, default 0.5); il profilo utente (static+dynamic) e' costruito
  come riassunto "always ready" (`https://supermemory.ai/docs/concepts/user-profiles`).
  Il benchmark LongMemEval dichiara **95% Recall@15 con ~720 token di contesto
  aggiunti** (`https://supermemory.ai/research/longmembench/`): sopra il target
  ma dello stesso ordine; riducibile con `limit`/`threshold`. Necessita di
  verifica pratica.
- **memobase**: `u.context(max_token_size=500, prefer_topics=...)` — il budget
  di token e' un parametro di primo livello dell'API
  (`https://github.com/memodb-io/memobase`). Vicino al target ma il progetto e'
  stale da 7 mesi.
- **Neo4j agent-memory**: `get_context(query, session_id, user_id, limit=10
  per tipo)` restituisce fino a `limit` elementi per tipo di memoria
  (short/long/reasoning), poi `to_prompt()` li serializza: il limite e' per
  **numero di item**, non per token
  (`https://neo4j.com/labs/agent-memory/how-to/...`, doc in
  `docs/modules/ROOT/pages/` del repo). Non soddisfa il criterio cosi' com'e'.
- **shodh-memory**: `recall`/`proactive_context` prendono `max_results`
  (top-k, non token) ma c'e' un digest di sessione con `token_budget`
  esplicito e un tool MCP `token_status` (`https://www.shodh-memory.com/docs`).
  La compressione a ~300 token e' possibile ma va costruita.
- **Letta/MemGPT**: modello diverso — memory blocks fissi **sempre** nel
  contesto, non retrieval: ogni blocco ha `chars_current`/`chars_limit` (es.
  5.000 char) e l'agente li riorganizza da solo
  (`https://docs.letta.com/v1-sdk/memory/memory-blocks`). Nessun "recupero a
  300 token": sono token fissi permanenti, pagati a ogni turno.
- **LangMem, memary, A-MEM, txtai**: nessun budget di token al recupero
  documentato; retrieval count-based o inesistente.

Esito: nessuno offre un budget di token vero e proprio come memobase; i
sopravvissuti al criterio 2 si comprimono con parametri (limit/threshold/
max_results). Tutto da misurare, ma nessuno e' fuori a priori per il criterio 1.

## Criterio 2 — Attribuzione del parlante (il criterio nuovo)

Il guasto misurato: Honcho con qwen3:8b, etichette [user]/[assistant] nel
testo, deriva "userei MCP per separare il tuo Mac mini" → "il proprietario usa
MCP". Domanda: come distingue ogni candidato **chi ha detto cosa**?

- **supermemory**: e' l'unico che lo dimostra con un benchmark. LongMemEval
  divide i fatti in categorie del parlante e supermemory riporta **92,9%
  single-session User e 100% single-session Assistant**
  (`https://supermemory.ai/research/longmembench/`). Il profilo utente estrae
  "facts about the user" dalle interazioni — ma il dato del benchmark dice che
  le affermazioni dell'assistente vengono comunque recuperate come tali.
  Estrattore a LLM, quindi stesso rischio teorico di Honcho: la mitigazione e'
  la distinzione dimostrata nel benchmark, non un ruolo first-class nel modello
  dati.
- **Neo4j agent-memory**: `add_message(session_id, role, content)` con ruolo
  **first-class** dell'API; le entita' estratte sono collegate al messaggio che
  le ha menzionate (relazione MENTIONS), quindi ogni fatto risale al turno e al
  ruolo che l'ha prodotto (`https://neo4j.com/labs/agent-memory/`). Il ruolo
  e' salvato, non dedotto.
- **shodh-memory**: l'attribuzione e' **per costruzione, non per estrazione**.
  `remember` riceve il contenuto gia' attribuito dal chiamante
  (`source_type`: `user`, `system`, `ai_generated`, `inferred`, ...) e non c'e'
  un estrattore che "decida" il soggetto (`https://www.shodh-memory.com/docs`).
  Il guasto Honcho non puo' esistere perche' il sistema non fa inference
  sull'autore: ma il costo e' che qualcuno a monte (il nostro codice) deve
  passare il contenuto giusto. Non ingesta conversazioni [user]/[assistant]
  da solo.
- **Letta**: i memory blocks (human/persona) sono gestiti dall'agente LLM: lo
  stesso rischio di Honcho, l'LLM decide cosa scrivere nel blocco "human"
  leggendo la conversazione.
- **memobase**: profilo "dell'utente" per costruzione: tutto cio' che estrae
  dalla conversazione finisce nel profilo utente, frasi dell'assistente
  comprese — stessa trappola di Honcho.
- **LangMem, memary, A-MEM, txtai**: nessun concetto di parlante.

Esito: la classifica e' supermemory (dimostrato) = Neo4j (ruolo first-class)
> shodh (attribuzione a monte, deterministico) > memobase/Letta (rischio
  Honcho) > altri (assenti).

## Criterio 3 — Esiste una memoria che NON usa un LLM per estrarre i fatti?

La domanda piu' interessante. Risposta: **si', esistono due strade, entrambe
concrete.**

- **shodh-memory** e' LLM-free per design: "forms, stores, and retrieves
  memories without a large language model anywhere in the loop. Extraction,
  ranking, and recall are deterministic code; small frozen models handle
  perception only" (`https://www.shodh-memory.com/llm-free-memory`). NER con
  GLiNER bi-edge v2.0 (141 tipi, ONNX), embedding MiniLM-L6-v2, ranking
  deterministico, decay matematico (Hebbian, potenza → legge di potenza),
  provenance di ogni memoria (`https://github.com/varun29ankuS/shodh-memory`).
  Zero chiamate LLM in remember e in recall.
- **Neo4j agent-memory** ha una modalita' senza LLM: `MemorySettings.llm=None`
  + extractor locali (spaCy statistico, GLiNER zeroshot, GLiREL per le
  relazioni) + sentence-transformers locale; l'LLM resta disponibile come
  ultimo stadio opzionale
  (`https://neo4j.com/labs/agent-memory/how-to/running-without-an-llm/`).
  In questa modalita' e' un'estrazione deterministica basata su NER
  statistico, non su un modello generativo.
- **txtai** non e' un sistema di memoria conversazionale ma un framework
  (semantic search, RAG, LLM orchestration) usabile senza LLM come base per
  costruirsi la propria estrazione (`https://github.com/neuml/txtai`).
- Tutti gli altri (supermemory, Letta, memobase, LangMem, memary, A-MEM)
  estraggono con un LLM. supermemory richiede **esplicitamente** una chiave
  LLM anche in self-host: "The only thing you bring is a model"
  (`https://supermemory.ai/docs/self-hosting/overview`).

Esito: per questo criterio shodh e Neo4j (modalita' no-LLM) sono soli; il resto
e' fuori.

## Criterio 4 — Ollama locale, italiano, date, installazione, licenza

- **supermemory**: licenza MIT. Self-host a binario unico (`npx supermemory
  local`), motore grafo embedded; accetta qualsiasi endpoint OpenAI-compatible
  per l'estrazione (Ollama incluso, es. gpt-oss-20b) — ma **richiede una chiave
  LLM**, anche self-hosted (`https://supermemory.ai/docs/self-hosting/overview`).
  Embedding locale default `Xenova/bge-base-en-v1.5` (768d) **solo inglese**;
  per multilingue serve `Xenova/bge-m3` (1024d) o un endpoint remoto
  (`https://supermemory.ai/docs/self-hosting/embeddings`). Il grafo e'
  temporale: update, versioning, forgetting (`https://supermemory.ai/docs/concepts/graph-memory`).
- **Neo4j agent-memory**: licenza Apache-2.0. Richiede un'istanza Neo4j in
  esecuzione (bolt://localhost:7687). Estrazione spaCy usa il modello
  `en_core_web_sm` (inglese); GLiNER e' zeroshot, schema-driven, quindi
  linguisticamente piu' neutro; l'LLM puo' essere un Ollama locale
  (`https://neo4j.com/labs/agent-memory/how-to/...`). Date: versionamento e
  timestamp dei messaggi, ma niente politiche di oblio/invalidazione
  dichiarate come supermemory/shodh.
- **shodh-memory**: licenza Apache-2.0. Binario singolo ~30MB, niente
  dipendenze esterne; install `pip install shodh-memory`, server MCP
  `npx @shodh/memory-mcp`, docker `roshera/shodh-memory`. Decay temporale
  matematico (dimentica cio' che non si usa) e provenance. **Embedding
  MiniLM-L6-v2 = inglese**; GLiNER bi-edge e' piu' neutro ma l'embedding resta
  il collo di bottiglia per l'italiano (`https://www.shodh-memory.com/llm-free-memory`).
- **memobase**: Apache-2.0 ma richiede **Postgres + Redis insieme** e il
  progetto e' stale da 7 mesi.
- **Letta**: Apache-2.0, gira con Ollama, ma il modello a memory blocks fissi
  non si sposa col vincolo dei ~300 token.
- **LangMem** (MIT), **memary** (morto), **A-MEM** (MIT, ChromaDB): nessuna
  gestione date di rilievo, nessuna garanzia italiana.
- **Zep**: la Community Edition open source e' **deprecata e non supportata**;
  il repo oggi e' solo "Examples & Integrations" per Zep Cloud (gestito)
  (`https://github.com/getzep/zep`). Fuori dai giochi per il self-host locale.

Esito: supermemory e Neo4j passano il criterio 4 con la scelta bge-m3 per
l'italiano; shodh lo passa su licenza/installazione ma resta debole in
italiano; memobase e' fuori per l'accoppiata Postgres+Redis e lo staleness.

## I candidati, uno per uno

### supermemory — 28.938★, MIT, attivissimo

"State-of-the-art memory, on your machine. One binary. Zero config."
Self-host locale completo, motore grafo embedded, profilo utente statico+
dinamico (buckets), ricerca ibrida su memorie estratte + chunk di documenti.
95% Recall@15 con ~720 token a LongMemEval; distingue fatti user/assistant
(92,9% / 100%). Richiede una chiave LLM anche in locale (estrazione); embedding
di default solo inglese (bge-m3 per multilingue).
`https://github.com/supermemoryai/supermemory` · `https://supermemory.ai/docs`

### Neo4j Agent Memory — 417★, Apache-2.0, nuovo (gennaio 2026), attivo

Memoria a tre livelli (short-term messaggi / long-term entita' POLE+O con
Preference e Fact / reasoning con Trace, Step, ToolCall). `add_message` con
ruolo first-class; entita' collegate al messaggio (MENTIONS). Modalita' senza
LLM: spaCy + GLiNER + GLiREL locali. Prezzo: serve un'istanza Neo4j, e
`get_context` limita per numero di item, non per token.
`https://github.com/neo4j-labs/agent-memory` · `https://neo4j.com/labs/agent-memory/`

### shodh-memory — 272★, Apache-2.0, nuovo (dicembre 2025), attivissimo (1.650 commit)

Il candidato LLM-free: estrazione, ranking e recall deterministici, NER GLiNER
on-device, decay matematico, provenance, MCP server pronto. L'attribuzione
del parlante e' responsabilita' del chiamante (source_type), mai del sistema:
il guasto Honcho e' impossibile per costruzione. Debolezza: embedding inglese
e nessuna ingestion automatica di conversazioni coi ruoli.
`https://github.com/varun29ankuS/shodh-memory` · `https://www.shodh-memory.com/docs`

### Letta/MemGPT — 24.287★, Apache-2.0, attivo

Memory blocks fissi nel contesto (persona/human), riorganizzati dall'agente.
Niente retrieval a 300 token: costo di contesto permanente, e attribuzione
affidata all'LLM. Il README del repo e' una landing page; il codice vero e'
altrove. Non adatto ai vincoli Elechim.
`https://github.com/letta-ai/letta` · `https://docs.letta.com/v1-sdk/memory/memory-blocks`

### memobase — 2.845★, Apache-2.0, stale 7 mesi

Profilo utente sempre pronto nel system prompt, `context(max_token_size=500)`:
il budget token e' first-class. Ma profilo "dell'utente" per costruzione (stessa
trappola di Honcho), richiede Postgres+Redis, progetto fermo da gennaio 2026.
`https://github.com/memodb-io/memobase`

### Zep — 4.844★, Apache-2.0, solo Cloud

Community Edition deprecata e non supportata; il repo e' solo esempi per Zep
Cloud. Graphiti resta l'unico pezzo open (gia' in RICERCA-memoria).
`https://github.com/getzep/zep`

### LangMem — 1.612★, MIT

Estrazione LLM, nessun concetto di parlante, nessun budget token. Solo
interessante per chi e' gia' su LangGraph.
`https://github.com/langchain-ai/langmem`

### memary — 2.638★, MIT, morto (ottobre 2024)

LLM-based, Ollama ok, ma ultimo push 2024-10-22: non un candidato.
`https://github.com/kingjulio8238/Memary`

### A-MEM — 1.149★, MIT

Memoria agentica stile Zettelkasten, LLM-based, ChromaDB. Nessun concetto di
parlante o budget token. Non adatto.
`https://github.com/agiresearch/A-mem`

### txtai — 12.895★, Apache-2.0, attivo

Non e' un sistema di memoria conversazionale: e' un framework (semantic
search, RAG, pipeline). Il suo valore qui e' come fondamento per costruirsi la
memoria da soli.
`https://github.com/neuml/txtai`

### memayu — 0★, MIT, nato il 10 agosto 2026

Rust single binary, embedding multilingue locale (paraphrase-multilingual-
MiniLM-L12-v2), modalita' raw senza LLM. Zero stelle e un giorno di vita:
troppo presto per considerarlo, ma e' l'unico a puntare su multilingue locale
da subito. Da ricontrollare fra qualche mese.
`https://github.com/savioruz/memayu`

## Conclusioni — le tre alternative migliori e cosa costerebbe

I criteri decisivi sono 1 (budget token) e 2 (attribuzione parlante). Il
criterio 3 (niente LLM) e' un vantaggio enorme, non un requisito assoluto.

1. **supermemory** — la scelta piu' matura. Unico con l'attribuzione
   dimostrata (LongMemEval user/assistant), estrazione via modello locale
   (Ollama), profilo utente "sempre pronto" che combacia col modo in cui
   Elechim usa la memoria. Adozione: binario unico, `bge-m3` per l'italiano,
   e una **misura pratica del costo in token** (~720 dichiarati vs ~300
   target): con `limit`/`threshold` e profilo al posto della search il gap e'
   plausibilmente colmabile, ma va verificato sul campo.
2. **Neo4j Agent Memory** — la scelta piu' "corretta" per il criterio 2
   (ruolo first-class in `add_message`, entita' tracciabili al turno) e con
   una vera modalita' senza LLM. Prezzo: un'istanza Neo4j in piu' da
   governare, `get_context` per item (non token) da adattare al budget, e
   modello spaCy inglese da sostituire con `it_core_news_sm`.
3. **shodh-memory** — il candidato che elimina il guasto per costruzione:
   niente LLM nel loop, attribuzione a carico del chiamante, MCP pronto, decay
   e provenance. Prezzo: embedding inglese (italiano debole finche' non si
   scambia il modello), e va scritto il codice che dice al sistema *cosa* e
   *di chi* ricordare — l'onere dell'attribuzione torna a noi, ma deterministico.

**Cosa costerebbe adottare**: supermemory = mezza giornata di installazione e
una giornata di misura del budget token (binario unico, nessun DB nuovo).
Neo4j = installazione/manutenzione di Neo4j piu' l'adattamento del retrieval a
token. shodh = poca installazione ma un ponte di ingestion da scrivere (il
bot che passa i fatti con `source_type`), piu' la questione italiana.

**E se costruissimo noi la memoria?** Con txtai (o direttamente
sentence-transformers con bge-m3, gia' scelto per la fase 3) come motore di
ricerca, un estrattore deterministico stile Neo4j no-LLM (spaCy `it_core_news_sm`
+ GLiNER zeroshot, niente LLM), e l'attribuzione affidata al **nostro** codice
a monte — come shodh, ma senza l'embedding inglese. Vantaggio: tagliato sui
vincoli Elechim (budget token a 300 esatti, italiano vero, nessuna dipendenza
nuova oltre a quelle gia' previste per la fase 3). Costo stimato: una settimana
di lavoro sul fisso, contro i giorni di adozione+misura degli altri. Il punto
a favore del fai-da-te e' che i vincoli decisivi (300 token, italiano,
niente cloud) non sono i vincoli per cui questi progetti sono stati costruiti:
tutti richiedono comunque adattamento, e nessuno ha l'attribuzione del parlante
risolta per un caso reale come il nostro.

Prossimo passo consigliato: misurare su supermemory self-host il costo in token
reale di una domanda simile alla misura Honcho (con Ollama locale e bge-m3), e
in parallelo verificare se shodh accetta senza modifiche il modello multilingue.