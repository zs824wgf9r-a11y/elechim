# RICERCA-memoria.md — Graphiti contro Honcho per la fase 3

> Confronto scritto il 17 agosto 2026 per decidere quale motore di memoria
> installare nella fase 3 di Elechim. Il criterio che decide: **quanti token
> restituisce la memoria a ogni turno** (target ~300 token, perche' il prefill
> del Mac va a 23 tok/s e ogni 1.000 token in piu' costano ~43 secondi).
> Nessuna installazione, nessun clone: solo lettura di documentazione, sorgenti
> e confronti indipendenti. L'unico file scritto e' questo.

## Come ho cercato

Le query sono ripetibili. Infrastruttura: **searxng** su `127.0.0.1:8888`
(curl `format=json`), **crawl4ai** su `127.0.0.1:11235` (POST `/crawl`, token da
`crawl4ai.env`) per leggere le pagine in markdown, e **GitHub API** con
`GITHUB_TOKEN` da `.env` (mai stampato) per metadati, contributor, ultimi commit
e issue. Ricerche su searxng (titolo della query tra virgolette):

- `"graphiti kuzu deprecated"` — ha portato a The Register su Kuzu abbandonato.
- `"honcho vs graphiti agent memory"` — confronti indipendenti (cosmohub, glukhov, vectorize).
- `"mem0 ollama local setup"`, `"cognee ollama local LLM provider"` — le doc locali dei due "terze vie".
- `"honcho plastic labs ollama local LLM self-host"` — doc self-hosting + gist "fully local con 3 patch".
- `"graphiti structured output local model ollama qwen"` — doc LLM configuration di Graphiti.
- `"graphiti temporal invalidation contradiction example"` — DeepWiki sul modello bi-temporale.
- `"mem0 non-English Italian memory extraction"` — issue sulle lingue.
- `"theregister kuzudb abandoned graph database community"` — URL corretto di The Register.
- `"mem0 vector store qdrant chromadb pgvector redis configuration"`, `"cognee recall function docs top_k"`.

Sorgenti letti direttamente via `raw.githubusercontent.com` (stesso commit di
oggi, 17 agosto 2026): README di Graphiti, Honcho, mem0, cognee; `config.toml.example`,
`docker-compose.yml.example` e `.env.template` di Honcho; SDK Python di Honcho
(`session.py`, `peer.py`, `conclusions.py`, `client.py`); sorgenti Graphiti
(`graphiti.py`, `edges.py`, `search_config.py`, `search_filters.py`,
`driver/kuzu_driver.py`); `src/deriver/prompts.py` di Honcho.

Pagine web lette per intero: `honcho.dev/docs/v3/contributing/self-hosting`,
`help.getzep.com/graphiti/configuration/llm-configuration`,
`deepwiki.com/getzep/graphiti/3.2-temporal-awareness-and-bi-temporal-model`,
`docs.mem0.ai/cookbooks/companions/local-companion-ollama`,
`docs.mem0.ai/components/vectordbs/overview`,
`docs.cognee.ai/setup-configuration/llm-providers`, `docs.cognee.ai/python-api/recall`,
`techblog.cosmohub.work/agent-memory-systems-compared-honcho-vs-zep-vs-mem0-vs-cognee/`,
`www.glukhov.org/ai-systems/memory/agent-memory-providers/`,
`www.theregister.com/software/2025/10/14/kuzudb-graph-database-abandoned-community-mulls-options/1142229`,
gist `oangelo/c3012e6cd5a7d5872a312d8592f5c4d5`.

Issue GitHub lette sul campo (numero, stato): `getzep/graphiti#1141`,
`plastic-labs/honcho#748`, `mem0ai/mem0#4884`, `mem0ai/mem0#6717`.

Metadati GitHub (17 agosto 2026, con token): repo di graphiti, honcho, mem0,
cognee, con stars/forks/license/ultimo commit/ultima release, contributore
principale e totale contributori. Le release di Honcho: nessuna trovata (l'API
non restituisce `latest`, il progetto pubblica sul branch `main`).

«Non trovato» e' scritto dove non c'e' niente: e' distinto da «non cercato».
Su 403/429 (nessuno incontrato con il token) si sarebbe cambiata fonte.

---

## Sintesi — quale dei due installiamo, e cosa rischiamo

1. **Il criterio decisivo lo vince Honcho**: `session.context(summary=True, tokens=N)`
   ha il limite di token di prima classe e restituisce esattamente il contesto
   che chiedi, messaggi + riassunto + rappresentazione del peer
   (https://github.com/plastic-labs/honcho/blob/main/sdks/python/src/honcho/session.py).
   Graphiti restituisce **liste di fatti** (`EntityEdge`, default 10, senza
   budget di token): si tronca a mano o si ricompatta con un LLM
   (https://github.com/getzep/graphiti/blob/main/graphiti_core/graphiti.py).
2. **Installazione**: Honcho vuole **davvero Postgres+pgvector** (obbligatorio),
   ma **Redis e' opzionale** (`[cache] ENABLED=false` di default;
   https://github.com/plastic-labs/honcho/blob/main/config.toml.example).
   Graphiti **non gira piu' embedded con Kuzu**: Kuzu e' deprecato e il progetto
   upstream e' abbandonato (https://github.com/getzep/graphiti/blob/main/README.md,
   https://www.theregister.com/software/2025/10/14/kuzudb-graph-database-abandoned-community-mulls-options/1142229).
   L'embedded attuale e' **FalkorDB Lite** (`graphiti-core[falkordblite]`, Python 3.12+).
3. **Entrambi accettano un ollama locale** via endpoint OpenAI-compatible: Honcho
   con `overrides.base_url` su ogni sezione, Graphiti con `OpenAIGenericClient`
   e `base_url=http://localhost:11434/v1`. Nessuno dei due tocca il modello del Mac.
4. **Italiano: nessuno ha prove, solo promesse**: Graphiti ha i prompt "all in
   English" (issue #1141 aperta), Honcho genera i riassunti in inglese di default
   (issue #748 aperta). Va provato in locale, e' il primo rischio.
5. **Tempo e contraddizioni**: qui vince **Graphiti**, con il modello
   bi-temporale (`valid_at`/`invalid_at`/`expired_at`) e invalidazione automatica
   dei fatti contraddetti — il matching perfetto col nostro dreaming mode. Honcho
   tiene solo `created_at`, niente "X era vero fino a marzo".
6. **Maturita'**: Graphiti 30k stelle, Apache-2.0, release regolari, ~58
   contributori. Honcho 6,7k stelle, **AGPL-3.0**, nessuna release, deriver
   "finicky" (gotcha documentato: `FLUSH_ENABLED=false` di default e a basso
   volume le osservazioni non nascono; https://techblog.cosmohub.work/agent-memory-systems-compared-honcho-vs-zep-vs-mem0-vs-cognee/).
7. **Terze vie fuori**: mem0 ha BM25 ed entity extraction hardcoded in inglese
   (https://github.com/mem0ai/mem0/issues/4884); cognee e' pesante (Postgres +
   grafo), senza budget di token in `recall()`. Nessuno dei due regge il criterio.
8. **La domanda scomoda**: per ricordare fatti datati sul proprietario e
   ritrovarli a ~300 token **un grafo non serve** — e Honcho non e' un grafo, e'
   un DB di osservazioni/conclusioni con ricerca semantica. Anche il bi-tempo
   che ci serve si puo' fare in uno schema piatto (fatto, da-quando, fino-a-quando).
9. **Raccomandazione**: **provare Honcho** con Postgres+pgvector (senza Redis),
   LLM ed embedding su ollama del fisso (`qwen3:8b` / `bge-m3`), `FLUSH_ENABLED=true`,
   e **prima di tutto** verificare l'estrazione su conversazioni italiane vere.
   E' il solo che soddisfa il criterio dei token senza dover troncare a mano.
10. **Cosa rischiamo se scegliamo male**: Honcho e' AGPL-3.0 e non sa
    invalidare un fatto nel tempo (lo scriviamo noi nello schema o lo perdiamo);
    se dopo sei mesi ci servisse il bi-tempo completo di Graphiti, il modello
    dati e' diverso e **si riparte da capo** (nessun export documentato).
    Con Graphiti il rischio opposto: risposta lunga per turno, che e' esattamente
    il criterio che ci fa escludere un progetto.

---

## 1. Cosa serve per farli girare, davvero

### Honcho: Postgres+pgvector si', Redis no

- **Postgres con pgvector e' obbligatorio.** Il self-hosting dice testualmente:
  "A PostgreSQL database with pgvector extension" e il server **non parte** senza
  un LLM configurato
  (https://honcho.dev/docs/v3/contributing/self-hosting). La connessione e'
  `postgresql+psycopg://...` in `[db] CONNECTION_URI`
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example) e il
  `docker-compose.yml.example` monta `pgvector/pgvector:pg15` e applica
  `database/init.sql` (https://github.com/plastic-labs/honcho/blob/main/docker-compose.yml.example).
- **Redis e' opzionale, non richiesto.** `[cache] ENABLED = false` di default con
  URL a `redis://localhost:6379/0`; e' il `docker-compose` a mettere
  `CACHE_ENABLED=true` (https://github.com/plastic-labs/honcho/blob/main/config.toml.example,
  https://github.com/plastic-labs/honcho/blob/main/docker-compose.yml.example).
  Quindi la voce "Postgres+pgvector+Redis" del nostro piano va corretta: **i primi
  due si', Redis si puo' lasciare spento**.
- **Si puo' far girare piu' leggero?** Si, in parte: il vector store puo' essere
  `lancedb` embedded (`VECTOR_STORE_TYPE=lancedb`, `INSTALL_LANCEDB=true` alla
  build, dati su `lancedb_data/`), oppure `turbopuffer` (cloud, per noi escluso)
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example,
  https://github.com/plastic-labs/honcho/blob/main/docker-compose.yml.example).
  **Restano comunque Postgres+pgvector obbligatori** per lo store relazionale:
  LanceDB sostituisce solo il vector store. Modalita' "tutta embedded senza
  Postgres": **non esiste** per Honcho.
- **Risorse**: il server e' un'app FastAPI + un worker background ("deriver").
  Niente GPU propria: le chiamate LLM/embedding vanno al provider che le puntiamo.
  Postgres su 62 GB di RAM del fisso non e' un problema; il deriver con
  `WORKERS=1` e polling adattivo e' pensato per uso personale
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example).
- **Un avvertimento operativo dal campo** (confronto indipendente): con
  `FLUSH_ENABLED=false` (default) le osservazioni si accumulano finche' non si
  raggiunge la soglia di batch (`REPRESENTATION_BATCH_WORK_UNIT_TARGET_TOKENS=512`,
  `REPRESENTATION_BATCH_TARGET_INPUT_TOKENS=1024`); **in uso personale a basso
  volume le osservazioni possono non venire mai create**. Va messo
  `FLUSH_ENABLED=true` (https://techblog.cosmohub.work/agent-memory-systems-compared-honcho-vs-zep-vs-mem0-vs-cognee/,
  confermato dal default in https://github.com/plastic-labs/honcho/blob/main/config.toml.example).
- Un gist di maggio 2026 documenta che per far girare Honcho tutto locale
  servivano **3 patch** (dimensione embedding 1536→768, nome modello, `base_url`
  dell'embedding hardcoded): https://gist.github.com/oangelo/c3012e6cd5a7d5872a312d8592f5c4d5.
  La `config.toml.example` attuale pero' **espone gia'** `[embedding.model_config.overrides] base_url`
  e `VECTOR_DIMENSIONS`, quindi su quelle tre patch il gist sembra superato.
  Da verificare in locale, non promesso.

### Graphiti: Kuzu e' morto, l'embedded ora e' FalkorDB Lite

- **La voce "Graphiti gira embedded con Kuzu" e' falsa oggi.** Il README ufficiale:
  "Kuzu is deprecated and will be removed in a future release — the upstream
  Kuzu project is no longer maintained", con `DeprecationWarning`
  (https://github.com/getzep/graphiti/blob/main/README.md). The Register (14
  ottobre 2025) documenta l'abbandono di KuzuDB da parte di Kùzu Inc e il fork
  comunitario "bighorn" di Kineviz
  (https://www.theregister.com/software/2025/10/14/kuzudb-graph-database-abandoned-community-mulls-options/1142229,
  https://github.com/Kineviz/bighorn).
- **Backend supportati**: Neo4j 5.26, FalkorDB 1.1.2, Amazon Neptune
  (+ OpenSearch per il full-text), Kuzu 0.11.2 (deprecato)
  (https://github.com/getzep/graphiti/blob/main/README.md).
- **Il vero embedded** e' **FalkorDB Lite**: `pip install graphiti-core[falkordblite]`
  (richiede **Python 3.12+**; il nostro venv e' 3.12, ok) e si costruisce il
  driver da `redislite.async_falkordb_client`
  (https://github.com/getzep/graphiti/blob/main/README.md). Cosa si perde con
  quello embedded rispetto a Neo4j/FalkorDB pieno: la stessa libreria backend ma
  in-process, senza server esterno; per il resto le query (Cypher/FalkorDB) sono
  le stesse (https://github.com/getzep/graphiti/blob/main/graphiti_core/driver/kuzu_driver.py
  mostra che con Kuzu gli embedding vivono **dentro il grafo** come colonne
  `FLOAT[]`, senza vector store separato).
- **Risorse**: Graphiti e' una libreria Python pura; il "database" e' quello che
  scegliamo (FalkorDB Lite embedded non vuole server, Neo4j vuole una JVM con
  qualche GB). Niente GPU propria: LLM, embedding e cross-encoder vanno a un
  provider configurabile (https://github.com/getzep/graphiti/blob/main/README.md,
  https://help.getzep.com/graphiti/configuration/llm-configuration).

**Verdetto cap. 1**: il piano "Honcho = Postgres+pgvector+Redis" era quasi giusto
(Redis via), e "Graphiti embedded con Kuzu" e' una voce da **scartare**: l'embedded
vero e' FalkorDB Lite, e Kuzu e' un progetto abbandonato che Graphiti sta per
rimuovere. Onestamente: la premessa su cui il proprietario voleva "provare
Graphiti" (l'embedded leggero) oggi non esiste piu' come era stata pensata.

---

## 2. Il modello di ingestione

Il veto: il modello che estrae i fatti deve essere un **ollama locale sul fisso**,
mai il modello del Mac (sfratterebbe la conversazione dall'unica slot di cache).

### Honcho

- **Endpoint OpenAI-compatibile su ogni sezione.** La config espone
  `overrides.base_url` per deriver, summary, dialectic e dream: basta un
  `*_MODEL_CONFIG__TRANSPORT=openai` + `*_MODEL_CONFIG__OVERRIDES__BASE_URL` per
  puntare a un ollama qualsiasi
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example).
  Il self-hosting dice: "Any OpenAI-compatible endpoint works too — OpenRouter,
  Together, Fireworks, Ollama, vLLM, or LiteLLM. **Models must support tool
  calling (function calling)**" (https://honcho.dev/docs/v3/contributing/self-hosting).
  Il gist di maggio 2026 mostra una installazione completa con `qwen3.6:27b` via
  endpoint OpenAI-compatibile (https://gist.github.com/oangelo/c3012e6cd5a7d5872a312d8592f5c4d5).
- **Embedding locali**: `[embedding.model_config.overrides] base_url` e
  `VECTOR_DIMENSIONS` (default 1536) sono parametri di config; con un embedding
  OpenAI-compatibile locale (bge-m3 via ollama) si imposta
  `VECTOR_DIMENSIONS` al valore giusto
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example).
  Attenzione a un'issue aperta: tokenizer dell'embedding che causava fallimenti
  silenziosi con modelli non-OpenAI (#827)
  (https://github.com/plastic-labs/honcho/issues/827).
- **Costo in tempo**: il deriver processa le osservazioni a batch di input
  (~1024 token per chiamata LLM) e poi deriva conclusioni/rappresentazioni; con
  `FLUSH_ENABLED=true` processa subito. Per ingerire una conversazione servono
  piu' chiamate LLM, ma piccole e sul fisso. Non c'e' una misura pubblicata in
  minuti per conversazione: va misurata in locale.
- **Italiano: prove no.** L'unica evidenza e' negativa: i riassunti di sessione
  sono generati da prompt inglesi hardcoded e ignorano `custom_instructions`
  anche se gli dici di scrivere in tedesco — issue aperta #748
  (https://github.com/plastic-labs/honcho/issues/748). Il deriver, pero',
  accetta `custom_instructions` nel suo prompt
  (https://github.com/plastic-labs/honcho/blob/main/src/deriver/prompts.py):
  la strada per l'italiano c'e', ma e' da **verificare con un test reale**, non
  promessa.

### Graphiti

- **Endpoint OpenAI-compatibile**: `OpenAIGenericClient` con
  `base_url="http://localhost:11434/v1"`, `api_key="ollama"` (fittizio). Esempio
  ufficiale: `deepseek-r1:7b` come LLM e `nomic-embed-text` (768 dim) come
  embedding, entrambi da ollama
  (https://help.getzep.com/graphiti/configuration/llm-configuration).
- **Attenzione sul veto**: Graphiti usa un **cross-encoder/reranker** per
  riordinare i risultati; l'esempio ufficiale lo punta allo stesso
  `llm_client` locale, quindi anche il reranker puo' restare sul fisso
  (https://help.getzep.com/graphiti/configuration/llm-configuration).
- **Avviso esplicito sui modelli piccoli**: "Graphiti works best with LLM
  services that support Structured Output... Using other services may result in
  incorrect output schemas and ingestion failures. This is particularly
  problematic when using smaller models" e "avoid smaller local models as they
  may not accurately extract data or output the correct JSON structures"
  (https://github.com/getzep/graphiti/blob/main/README.md,
  https://help.getzep.com/graphiti/configuration/llm-configuration). Sul nostro
  qwen3:8b (sbobina) l'estrazione di grafi JSON potrebbe essere fragile: da
  provare, ma e' un segnale che Graphiti su un 8B locale e' piu' a rischio di
  Honcho, che con `gpt-5.4-mini` e tool-calling gestisce output strutturati
  (https://honcho.dev/docs/v3/contributing/self-hosting).
- **Costo in tempo**: ogni episodio passa da estrazione nodi+relazioni,
  deduplicazione e building delle community; piu' chiamate LLM per episodio.
  Nessuna misura pubblicata: da verificare in locale. Il rate limiting e'
  documentato (deepwiki: "Concurrency and Rate Limit Management")
  (https://deepwiki.com/getzep/graphiti/10.6-concurrency-and-rate-limit-management).
- **Italiano: prove no.** Issue aperta #1141 "Multi-language support":
  "Today, prompts are all in English"
  (https://github.com/getzep/graphiti/issues/1141). Esiste
  `custom_extraction_instructions` in `add_episode` che permette di dare
  istruzioni (anche in italiano) all'estrazione
  (https://github.com/getzep/graphiti/blob/main/graphiti_core/graphiti.py),
  ma il prompt di base resta inglese e le prove italiane mancano.

**Verdetto cap. 2**: entrambi passano il veto — si puo' puntare un ollama del
fisso, senza toccare il Mac. Ma **nessuno dei due ha prove in italiano**: entrambi
hanno issue aperte che dicono che l'inglese e' hardcoded nei prompt. La prova va
fatta in locale (sintetico prima, poi conversazioni vere). Sul criterio del
modello piccolo, Honcho sembra piu' robusto (tool-calling strutturato), Graphiti
mette in guardia esplicitamente sui modelli piccoli.

---

## 3. Il tempo e le contraddizioni

Il principio del nostro dreaming mode: **fatti datati, superati, mai cancellati**.

### Graphiti: e' il suo punto di forza

- Modello **bi-temporale** a quattro dimensioni: `created_at` (quando e' entrato
  nel grafo, tempo di sistema), `valid_at` (quando il fatto e' accaduto nella
  realta'), `invalid_at` (quando il fatto ha smesso di essere vero), `expired_at`
  (quando il sistema ha invalidato l'arco)
  (https://deepwiki.com/getzep/graphiti/3.2-temporal-awareness-and-bi-temporal-model).
- **Invalidazione automatica**: in `add_episode` la risoluzione degli archi
  restituisce `(resolved_edges, invalidated_edges, new_edges)` — se il nuovo
  contenuto contraddice un fatto esistente, l'arco vecchio viene segnato come
  invalidato (soft delete, mai cancellato): "X era vero fino a marzo, poi e'
  diventato Y" e' il caso d'uso nativo
  (https://github.com/getzep/graphiti/blob/main/graphiti_core/graphiti.py).
- **Query puntuali nel tempo**: `SearchFilters` con `valid_at`/`invalid_at`
  permette di chiedere "cosa sapevamo al giorno X" e di filtrare per intervallo
  di validita' — l'esatto "da quando lo sa, e cosa sapeva a quella data"
  (https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_filters.py).

### Honcho: solo memoria episodica, niente validita' temporale

- Le conclusioni hanno `created_at` (quando sono state derivate), ma **non
  esiste `valid_at`/`invalid_at`**: non c'e' un concetto di "fatto vero fino a
  quando", ne' invalidazione automatica
  (https://github.com/plastic-labs/honcho/blob/main/sdks/python/src/honcho/conclusions.py).
- La memoria e' **additiva**: le osservazioni si accumulano e le conclusioni le
  riassumono; una contraddizione ("il lavoro cambia a marzo") non invalida
  l'osservazione precedente, si affianca. E' il modello "episodico + derivazione",
  non "fatti con finestre di validita'"
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example,
  https://techblog.cosmohub.work/agent-memory-systems-compared-honcho-vs-zep-vs-mem0-vs-cognee/).
- Il consolidamento notturno esiste ma si chiama **dream**, ed e' a eventi non a
  orologio: sezione `[dream]` con `DOCUMENT_THRESHOLD`, `IDLE_TIMEOUT_MINUTES`,
  `MIN_HOURS_BETWEEN_DREAMS` e `schedule_dream` nell'SDK — simile per spirito al
  nostro dreaming mode, ma senza il "datare e superare" sui singoli fatti
  (https://github.com/plastic-labs/honcho/blob/main/config.toml.example,
  https://github.com/plastic-labs/honcho/blob/main/sdks/python/src/honcho/client.py).

**Verdetto cap. 3**: sul tempo vince **Graphiti**, di netto: e' l'unico dei due
che sa dire "quando era vero" e che invalida (senza cancellare) i fatti
contraddetti. Honcho non ha un modello temporale dei fatti: sa che cosa ha
derivato e quando, ma non gestisce "X e' diventato Y". Se il dreaming mode deve
essere "datare e superare, mai cancellare", **Honcho richiede di costruire quello
strato da soli** (es. una colonna `superato_da` o una conclusione che fa fede),
Graphiti ce l'ha gia' dentro.

---

## 4. Maturita' e rischio

Metadati GitHub raccolti il 17 agosto 2026 con token (fonte: API
`api.github.com/repos/<repo>`):

| Progetto | Stars | Fork | Licenza | Creato | Ultimo commit | Ultima release | Contributori (tot/~top) |
|---|---|---|---|---|---|---|---|
| getzep/graphiti | 30.011 | 3.041 | Apache-2.0 | ago 2024 | 16 ago 2026 | v0.29.3 | ~58 / 347 |
| plastic-labs/honcho | 6.685 | 820 | **AGPL-3.0** | set 2023 | 17 ago 2026 | nessuna trovata | ~52 / 191 |
| mem0ai/mem0 | 63.457 | 7.418 | Apache-2.0 | giu 2023 | 14 ago 2026 | ts-v3.1.6 | ~397 / 453 |
| topoteretes/cognee | 30.080 | 2.931 | Apache-2.0 | ago 2023 | 16 ago 2026 | v1.5.0 | ~279 / 2.829 |

(URL: https://github.com/getzep/graphiti, https://github.com/plastic-labs/honcho,
https://github.com/mem0ai/mem0, https://github.com/topoteretes/cognee.
Ultimo commit e release via `/commits?per_page=1` e `/releases/latest`.)

### Chi c'e' dietro e la cadenza

- **Graphiti** e' il motore di **Zep** (azienda che fa anche la piattaforma cloud
  di memoria); paper: "Zep: A Temporal Knowledge Graph Architecture for Agent
  Memory" (https://arxiv.org/abs/2501.13956). Release regolari (v0.29.3 a agosto
  2026), ~58 contributori, molto attivo.
- **Honcho** e' di **Plastic Labs** (Autonomy, il fondatore e' un ex-ricercatore
  di riallineamento) (https://honcho.dev/, https://github.com/plastic-labs/honcho).
  **Nessuna release taggata trovata**: si usa il branch `main` — segno di progetto
  giovane e a evoluzione rapida (ultimo commit 17 ago 2026). Confronto indipendente:
  "Honcho is what I'm running now... It's a dialectic memory system"
  (https://techblog.cosmohub.work/agent-memory-systems-compared-honcho-vs-zep-vs-mem0-vs-cognee/).

### Il costo di sbagliare

- **Export**: non e' documentato un percorso di export per Honcho
  (la doc di export che esiste e' per **mem0**,
  https://docs.mem0.ai/cookbooks/essentials/exporting-memories). Per Graphiti i
  dati vivono nel grafo (Neo4j/FalkorDB): l'export e' possibile a livello di
  database, ma il re-ingresso in un altro motore richiede di ri-eseguire
  l'estrazione. In entrambi i casi, **cambiare sistema dopo sei mesi significa
  ripartire dall'estrazione** (i markdown integrali di Elechim restano la fonte
  vera, vedi regola "l'integrale e' la verita'").
- **Licenza**: Honcho e' **AGPL-3.0** (https://github.com/plastic-labs/honcho):
  se Elechim resta un servizio interno personale non e' un problema pratico, ma
  se un giorno la distribuzione esterna del repo dovesse includere Honcho come
  componente, l'AGPL impone di rilasciare il sorgente dell'intera combinazione.
  Graphiti e' Apache-2.0, piu' permissiva.
- **Il confronto indipendente che il proprietario ha gia' letto**
  (`RICERCA-ridondanza.md`) citava mem0 e cognee: nessuno dei due regge i nostri
  vincoli (vedi cap. 5).

**Verdetto cap. 4**: Graphiti e' piu' maturo come forma (release, licenza
permissiva, paper, azienda dietro); Honcho e' piu' giovane (no release, AGPL,
deriver "finicky" documentato) ma il solo che ha il limite di token in query.
Su "costo di sbagliare": alto per entrambi, perche' il modello dati e' diverso e
si riestrae da capo — per questo il collaudo in locale prima di scegliere non e'
un lusso ma il piano B.

---

## 5. Esiste una terza via — e serve davvero un grafo?

### mem0 e cognee, con lo stesso metro

- **mem0**: tutto locale e' documentato ufficialmente — vector store Qdrant
  locale + LLM ollama (`llama3.1`) + embedding ollama (`nomic-embed-text`)
  (https://docs.mem0.ai/cookbooks/companions/local-companion-ollama). Vector
  store supportati: Qdrant, Chroma, PGVector, Redis, Milvus, Elasticsearch e
  altri (https://docs.mem0.ai/components/vectordbs/overview). **Criterio token**:
  restituisce le memorie piu' simili (top-k), senza budget di token di prima
  classe. **Italiano**: elimina — BM25 ed entity extraction sono hardcoded su
  spaCy inglese (`en_core_web_sm`), e per il non-inglese **BM25 diventa
  silenziosamente un no-op** (#4884, aperta;
  https://github.com/mem0ai/mem0/issues/4884; crash su lingue non-EN #6717,
  https://github.com/mem0ai/mem0/issues/6717). Tempo: add-only, niente
  invalidazione. **Fuori.**
- **cognee**: LLM locale via ollama e' documentato (`LLM_PROVIDER=ollama`,
  `LLM_ENDPOINT=http://localhost:11434/v1`, embedding locale, un 8B a 4 bit ~6 GB
  di VRAM) (https://docs.cognee.ai/setup-configuration/llm-providers). **Criterio
  token**: `recall(top_k=15)` restituisce chunk/grafo, con opzione `only_context`
  ma **senza budget di token** (https://docs.cognee.ai/python-api/recall). E'
  piu' pensato per documenti che per conversazioni ("Cognee doesn't replace
  conversational memory — it complements it",
  https://techblog.cosmohub.work/agent-memory-systems-compared-honcho-vs-zep-vs-mem0-vs-cognee/).
  Italiano: nessuna prova trovata. Tempo: esiste un esempio di `temporal_recall`
  (https://github.com/topoteretes/cognee/blob/main/examples/guides/temporal_recall.py),
  ma il sistema e' piu' pesante (Postgres+grafo). **Fuori** per il criterio token.

### La domanda scomoda: serve davvero un grafo?

No, per quello che serve a Elechim oggi: **un database di fatti datati con una
ricerca lessicale basterebbe**. Le ragioni:

- Il criterio che decide e' la lunghezza della risposta, non la profondita' dei
  collegamenti: a ~300 token per turno non si sfrutta la potenza di un grafo
  multi-hop; si usa al massimo la ricerca semantica + i fatti piu' recenti.
- Le nostre domande sono "che cosa so sul proprietario?", non "quali entita'
  sono collegate a distanza 2 da quest'altra". Un grafo risolve il secondo tipo,
  che non abbiamo.
- **Honcho non e' un grafo**: e' esattamente "Postgres+pgvector con osservazioni
  e conclusioni datate". Quindi scegliere Honcho e' gia' di fatto scegliere la
  strada "meno di un grafo".
- Anche il pezzo temporale che Graphiti fa bene si puo' replicare in uno schema
  piatto: `fatti(fatto, valid_at, invalid_at, fonte)` + ricerca ibrida
  (lessicale FTS + embedding). E' piu' lavoro nostro, ma e' lavoro semplice e
  determinista, coerente con la filosofia "l'integrale e' la verita'".

Se la risposta onesta alla domanda e' questa, **la decisione si semplifica**:
Honcho e' il candidato che incarna gia' la via "poco piu' di un database di fatti"
e che passa il criterio dei token. Il grafo vero (Graphiti) resta un'opzione solo
se dopo il collaudo in locale scopriamo che le contraddizioni temporali servono
native e frequenti.

---

## La raccomandazione e il primo passo concreto

**Raccomandazione**: provare **Honcho** — non perche' sia piu' bello, ma perche'
e' l'unico dei quattro che ha il limite di token di prima classe
(`session.context(tokens=N)`), ed e' di fatto "poco piu' di un database di fatti
datati", cioe' la risposta alla domanda scomoda. Graphiti resta la riserva: se il
collaudo in italiano mostra che le contraddizioni temporali sono un'esigenza
frequente e reale, allora il grafo bi-temporale vale la complicazione.

**Primo passo concreto per provarla in locale** (comandi esatti, da NON eseguire
ora, ma pronti):

1. Postgres con pgvector sul fisso (oppure un container):
   ```
   podman run -d --name pg-vector --pod elechim-pod \
     -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
     -p 127.0.0.1:5432:5432 pgvector/pgvector:pg16
   ```
2. Scaricare Honcho da `main` e creare il venv (senza installare, solo preparare):
   ```
   git clone https://github.com/plastic-labs/honcho /tmp/opencode/honcho-prova
   cd /tmp/opencode/honcho-prova && uv sync
   ```
3. Creare `config.toml` con le parti non di default:
   - `[db] CONNECTION_URI = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"`
   - `[cache] ENABLED = false`
   - `[embedding] VECTOR_DIMENSIONS = 768` (nomic-embed-text) oppure 1024 (bge-m3),
     con `[embedding.model_config.overrides] base_url = "http://127.0.0.1:11434/v1"`
     e `transport = "openai"`, `model = "<embedding-ollama>"`
   - `[deriver] FLUSH_ENABLED = true`
   - `[deriver.model_config] transport = "openai"`,
     `[deriver.model_config.overrides] base_url = "http://127.0.0.1:11434/v1"`,
     `model = "qwen3:8b"` (modello del fisso, MAI quello del Mac)
   - idem per `[summary.model_config]`, `[dialectic.levels.*.model_config]`,
     `[dream.deduction_model_config]`, `[dream.induction_model_config]`
4. Avviare il server (api + deriver) e provare con **una conversazione italiana
   sintetica** (come `prova_sbobina.py` fa per la sbobina): ingerire qualche
   messaggio, poi chiamare `session.context(summary=True, tokens=300)` e misurare
   (a) quanti token escono davvero, (b) se l'estrazione in italiano produce
   osservazioni sensate, (c) quanti secondi costa l'ingestion di un giorno di chat.
5. Solo se il collaudo sintetico passa, provare con un frammento di conversazione
   vera in locale, e a leggerlo sara' il proprietario (mai un modello remoto).

Il file `INCARICO-fase3-memoria.md` e' gia' il riferimento del piano (Honcho +
Postgres+pgvector+`bge-m3`): questa ricerca conferma il piano su Postgres/pgvector
e lo corregge su Redis (opzionale, non obbligatorio).

---

## Cosa NON vale la pena

- **Graphiti con Kuzu**: il backend "embedded leggero" che il proprietario voleva
  provare e' deprecato e abbandonato a monte. Non vale la pena costruire sopra un
  progetto che Graphiti stesso sta per rimuovere.
- **Graphiti per il criterio dei token**: senza budget di token in query, ogni
  turno dovrebbe troncare o ricompattare fatti a mano — lavoro nostro, che si
  ripete e che costa prefill. Non vale il vantaggio temporale finche' il collaudo
  non mostra che il bi-tempo serve davvero.
- **mem0**: e' il piu' "rifinito" dei quattro, ma BM25 ed entity extraction
  hardcoded in inglese (#4884) sono un veto diretto sulle conversazioni italiane.
  Non si sceglie un motore di memoria che per lingua "silenziosamente non
  funziona".
- **cognee**: pensato per documenti, senza budget di token in `recall()`, piu'
  pesante. E' l'eventuale strato per i documenti, non per le conversazioni.
- **Perdersi nella potenza del grafo**: costruire relazioni multi-hop che a ~300
  token per turno non useremo mai. Il piano "Honcho = poco piu' di un DB di fatti
  datati" e' una forza, non una rinuncia.

---

## Non trovato

- **Prove di estrazione in italiano**: per Honcho, Graphiti, mem0 e cognee non
  esiste nessuna prova documentata che l'estrazione funzioni in italiano — esistono
  solo issue aperte che dicono il contrario. La parola spetta al collaudo locale.
- **Costo in tempo di ingestion per conversazione**: nessuno dei due pubblica una
  misura in minuti/conversazione. Da misurare.
- **Export ufficiale per Honcho**: non e' documentato un percorso di export dei
  dati (la doc di export esistente e' di mem0).
- **Release taggate di Honcho**: l'API `/releases/latest` non restituisce una
  release; il progetto si usa da `main`.
- **Uso di GPU da parte di Honcho/Graphiti**: nessuno dei due dichiara requisiti
  GPU propri; tutto il carico va al provider (per noi ollama del fisso). Il
  budget VRAM del fisso resta quello gia' noto (qwen3:8b sbobina + qwen3-vl:4b
  visione + whisper), e l'ingestion si mette in coda col lock GPU gia' presente.
- **Modalita' tutta-embedded senza Postgres per Honcho**: non esiste; LanceDB
  sostituisce solo il vector store, Postgres+pgvector restano obbligatori.