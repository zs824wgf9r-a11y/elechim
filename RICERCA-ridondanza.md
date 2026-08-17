# RICERCA-ridondanza.md — dimostrare che stiamo reinventando la ruota

Scritto il 17 agosto 2026 da opencode, su `INCARICO-ricerca-ridondanza.md`.

## Sintesi (10 righe)

Domanda: cosa dovremmo smettere di scrivere noi, e adottare?

Risposta corta: **nessun progetto da adottare oggi; tre pezzi da studiare.**
- `book-to-skill` (22.5k stelle) e' il piu' vicino alla fase 4, ma la struttura
  della «skill» la genera l'LLM dell'agente host, **in cloud di default**: per
  il nostro veto (i documenti non escono dalle due macchine) e' fuori.
- `needle` non c'entra: e' un modello di tool-calling da 14MB per dispositivi
  minuscoli, non recupero ne' memoria.
- **Pezzo 1**: `VaultForge` e' il concorrente diretto (PDF → atomic notes +
  wikilink + MOC su Obsidian), ma tutta la strutturazione e' LLM in cloud. Il
  suo `double-link-builder.py` (imbuto deterministico: struttura → TF-IDF →
  euristiche → solo in ultimo l'LLM) e' il pezzo che vale la pena rubare.
- **Pezzo 2**: nessuno riscrive una sezione tenendo tabelle/formule intatte;
  `groundguard` impacchetta invece la verifica «numeri contro la fonte» (da
  guardare a runtime).
- **Pezzo 3**: la coda su cartella e' un pattern risolto (persist-queue, huey)
  ma non vale la pena adottare niente per un produttore/consumatore singolo.
- **Pezzo 4**: il debate multi-ruolo esiste solo come ricerca o demo in cloud.
- **Pezzo 5**: il guardiano si costruisce; da rubare il *disegno* di CAO
  (orchestrazione), agent-monitor (kill switch), Microsoft AGT (confini
  deterministici). Nessuno sorveglia un processo CLI esterno con escalation.
- **Pezzo 6**: la memoria runtime ha un mercato maturo (mem0, Graphiti, cognee,
  e il nostro Honcho); nessuno unifica i file di contesto, e non deve.
- Il nostro raro: la corsia veloce **senza LLM** (533 pagine in 70s) e i tre
  vincoli insieme (tutto locale, documenti che non escono, tabelle/formule mai
  da un modello) — nessun candidato li rispetta tutti.

---

## Capitolo 1 — `virgiliojr94/book-to-skill` (segnalato dal proprietario)

**Cosa e'.** Un convertitore che trasforma un libro o un insieme di documenti in
una «skill» per agenti nel formato **Agent Skills** (`SKILL.md` + `chapters/` +
`glossary.md` + `patterns.md` + `cheatsheet.md`), leggibile da Claude Code,
GitHub Copilot CLI e Amp. Quando poi chiedi qualcosa sul libro, l'agente carica
il capitolo giusto e risponde dal contenuto.

**Come funziona davvero (dal codice).** Due meta' ben distinte:

1. **Estrattore deterministico in Python** (`scripts/extractor/`): PDF via
   `pdftotext` (poppler) → `pypdf` → `pdfminer.six`, oppure **`docling`** per i
   libri tecnici (~1.5s/pagina, conserva tabelle e blocchi di codice come
   markdown); EPUB via `ebooklib`, DOCX/HTML/RTF/MOBI con altri tool. Prima
   chiede all'utente «tecnico o testuale?». Scrive `full_text.txt` +
   `metadata.json` in `/tmp/book_skill_work/`. Qui nessun LLM.
2. **Generatore: NON e' codice, e' un prompt.** La `SKILL.md` (il file che
   l'agente esegue) istruisce l'agente host a fare riassunti per capitolo,
   glossario, patterns, cheatsheet e la `SKILL.md` finale, con un budget di
   token per file (chapters 800–3000 token, `SKILL.md` sotto 4000). E' quindi
   l'**agente host** che legge `full_text.txt` e scrive i file.

**La domanda decisiva: manda il contenuto a un modello in cloud?** Il tool in
se' no: l'estrazione gira in locale e il README lo dichiara («Processing is
local. Your files are never uploaded by this tool»). Ma **il passo di
generazione lo esegue l'agente host**, che nel caso normale e' **in cloud**
(Claude Code, GitHub Copilot CLI, Amp). Il README lo ammette senza giri: «If
your agent's model runs in the cloud, the text you feed it follows that
provider's normal data terms». La tabella dei costi parla di ~1$ a libro su
Claude Sonnet 4.5. Quindi: per il nostro vincolo assoluto (i documenti del
proprietario non escono dalle due macchine) questo progetto funziona solo se
eseguito sotto un agente locale, ma e' progettato per l'opposto e nessun file
della distribuzione lo garantisce.

**Cosa copre del nostro lavoro e cosa no.**

| Nostro | book-to-skill |
|---|---|
| `documenti.py`: PDF → markdown con tabelle/formule recintate, deterministico, senza LLM | Estrazione locale (pdftotext/docling), ma **tutta la strutturazione passa dall'LLM** |
| Note atomiche in vault Obsidian con wikilink risolti e indice | Output **non Obsidian**: skill per agenti. Capitoli on-demand, nessun wikilink, nessun vault |
| `sbobina.py`: riscrittura sezione per sezione, modello locale, **numeri verificati contro la fonte** | Nessuna verifica di numeri: riassume, non controlla |
| Regola «le tabelle e le formule non passano mai da un LLM» | **La viola per disegno**: in modo tecnico le tabelle estratte da docling vengono riassunte dall'LLM |
| Coda su cartella con ripresa dopo interruzione | Non c'e' — si usa in una sessione interattiva |

**Metriche.** Licenza MIT. 146 commit su `master`, ultimo commit **13 agosto
2026** (4 giorni fa, molto attivo). 22.5k stelle, 2.4k fork, 110 watching.
Manutentore singolo (virgiliojr94) + sponsor. Suite pytest presente. ~1$ a
libro di costo LLM se usato in cloud.

**VERDETTO: TENERE IL NOSTRO — ma l'ipotesi di ridondanza regge su un pezzo.**
Il pattern «estrazione locale deterministica + l'agente legge solo il capitolo
giusto» e' esattamente la nostra regola 3 e 5 (handle, non contenuti; capitoli
on-demand). Ma l'implementazione e' ferma a un punto che per noi e' veto: la
generazione delle note e' un LLM, e di default in cloud; non protegge tabelle e
formule; non produce note Obsidian; non verifica i numeri. Il pezzo riusabile
e' il design del suo estrattore a cascata (`pdftotext` → `pypdf` →
`pdfminer`/`docling` con `--check`), che e' gia' nostro con `pdftotext -layout`.

**Costo del cambio.** Si dovrebbero buttare: il determinismo del nostro
`genera_markdown` (qui la struttura la decide un LLM), la garanzia tabelle/formule,
la verifica numerica di `sbobina.py`, la destinazione Obsidian. Si adotterebbe
un'altra infrastruttura (skill per agenti cloud) che non c'entra col vault. Non
conviene.
---

## Capitolo 2 — `cactus-compute/needle` (segnalato dal proprietario)

**Cosa e' davvero.** Needle 2 e' un **modello di fondazione da 45M di parametri
per il tool calling** — non un motore di recupero, non un indice vettoriale,
non una libreria di memoria. Intero modello in un binario da 14MB che gira
una sessione in ~28MB di RAM, su JAX/Flax (dipendenze: `jax`, `flax`, `optax`,
`sentencepiece`, `huggingface_hub`), engine caricato via ctypes, pesi scaricati
una volta da Hugging Face e poi inferenza senza rete. Chiamate in stile OpenAI
per un agente minuscolo: `Needle(tools=[...]).run(query)` decide quale tool
chiamare, `extract(text, schema)` estrae dati strutturati.

Le due cose che sembrano «memoria» sono **interne al modello** e non ci servono:
- «Tool retrieval» = una testa di rete che, dato un catalogo di tool dichiarati,
  ne rende i top-5 per turno e vincola la grammatica a quel sottoinsieme.
  Serve a non passare 500 descrizioni di tool al prompt. Non e' un indice
  vettoriale su documenti.
- «Bounded memory» = una finestra scorrevole di 256 token con i tool pinnati
  come KV sink, per tenere la RAM ~28MB a prescindere dalla conversazione.
  Non e' memoria episodica, non e' un vault, non persiste nulla.

**A quale nostro problema risponde.** A nessuno, onestamente. La fase 3 (Honcho
con Postgres+pgvector, Redis, `bge-m3`) e' memoria episodica e modello
dell'utente su documenti; needle non indicizza, non recupera, non persiste. Il
nostro problema non e' fare tool calling su un dispositivo da 28MB di RAM: il
gateway e' gia' su un PC con 62GB. E' un progetto interessante nel suo ambito
(on-device AI, wearables, smart home), ma e' un altro ramo.

**Metriche.** Licenza Apache-2.0. 267 commit su `main`, ultimo commit **17
agosto 2026** (oggi, molto attivo). 7.1k stelle, 454 fork, 43 watching. Team
Cactus Compute Inc. (7 autori citati nel paper, arXiv:2607.18363).

**VERDETTO: NON C'ENTRA.** Nessun pezzo del nostro codice si cancellerebbe
adottandolo. Se in futuro servisse un modello locale minuscolo per decisioni
tipo «quale strumento chiamare» su un dispositivo a bassissima risorsa, si
valutera', ma non e' il nostro problema oggi.

**Costo del cambio.** Zero, perche' non c'e' niente da cambiare.

---

## Capitolo 3 — Pezzo 1: da libro a note collegate (PDF → note atomiche Obsidian con wikilink + indice)

Domanda: esistono progetti fatti per Obsidian che fanno PDF di centinaia di
pagine → note atomiche con wikilink risolti e un indice?

### I candidati trovati

**`Easonnotsing/VaultForge`** — il concorrente diretto, e il piu' vicino che
abbiamo trovato a quello che facciamo noi. E' un «agent skill» (una `SKILL.md`
che istruisce Claude Code / Codex / Cursor) che trasforma PDF, Markdown, Word e
PowerPoint in un vault Obsidian: note atomiche, wikilink bidirezionali a 5 tipi
di relazione (derivazione/analogia/contraddizione/applicazione/contesto), MOC
per tema, learning roadmap, domande guida. Pipeline a 7 fasi con **ripristino
dopo interruzione** (campo `status`: draft→filling→filled→reviewed) e **scrittura
atomica** (`.md.tmp` → verifica → rename). MIT, 190 commit, ultimo commit **1
giugno 2026** (2 mesi e mezzo fa, semiactivo), **10 stelle, 0 fork, un solo
manutentore**. Il codice Python (`scripts/double-link-builder.py`,
`scripts/context-extractor.py`) e' solido e senza dipendenze esterne.

Ma le differenze decisive:
- **La strutturazione e' tutta LLM.** Fase 1 (roadmap), fase 3 (riempimento
  note), fase 5 (review), e il terzo stadio del wikilink (classificazione LLM):
  il contenuto passa interamente dal modello dell'agente host. Claude Code / Codex
  / Cursor sono **in cloud di default**; non c'e' supporto dichiarato per un
  modello locale. La fase 6 (deep research) usa addirittura Firecrawl/Exa in
  cloud. Per il nostro veto e' **non adottabile come e'**.
- **Non protegge tabelle e formule**: riassume tutto, non recinta nulla.
- **Non verifica i numeri** contro la fonte.
- L'estrazione e' `pypdf` (testo pieno) o il Read dell'agente: niente
  `pdftotext -layout`, niente gestione formule, niente scansioni.

Il pezzo davvero riusabile e' `double-link-builder.py`: un imbuto a tre stadi
(affinita' strutturale per cartella → TF-IDF → euristiche di keyword → solo in
ultimo l'LLM classifica i candidati) con un **modo strict deterministico** a
copertura ~40-50% e zero chiamate LLM. E' il nostro stesso principio «il fisso
comprime, il modello non vede tutto» applicato ai wikilink.

**`brianpetro/obsidian-smart-connections`** — plugin Obsidian, 5.4k stelle, 339
fork, 1906 commit, ultimo commit **12 agosto 2026**, un manutentore (Brian).
Embedding **in locale** (modello bundled, zero setup, niente API key, privacy
per design), superficie note correlate e ricerca semantica sul vault. **Non
crea note da PDF** e non genera indice: collega e ritrova note che gia'
esistono. MIT.

**`kenforthewin/atomic` + plugin `obsidian-atomic`** — server (self-hosted) +
plugin Obsidian. Ricerca semantica ibrida, sync del vault, note simili, «wiki
articles» sintetizzate da LLM, chat RAG, canvas del grafo. Richiede un server
`atomic-server` e un LLM (OpenRouter **o ollama locale**): puo' girare tutto in
locale. Ma **non produce note da PDF**: organizza note esistenti. MIT, plugin
459 download, aggiornato ~3 mesi fa; server attivo (ultimo commit 9 agosto
2026).

**`MarkerAnn/pdf-to-obsidian-notes`** — script singolo, trasforma PDF di
lezioni in una nota Obsidian con le slide come immagini. Ultimo commit **dic
2024** (morto), nessun LLM, nessun wikilink intelligente. Non rilevante.

**`arodriguez47/obsidian-atomic-notes-plugin`** — non trovato (404).

Altri plugin visti in passaggio (PDF++, Omnisearch, Smart Lookup, Copilot,
Text Generator, Claudian, Agent Client, Fast Note Sync) o fanno altro o non
fanno la conversione PDF→note.

### Verdetto

**TENERE IL NOSTRO sulla conversione; il link-building e' un pezzo da prendere
in prestito.** Nessun progetto fa la corsia veloce come la nostra: determinismo
senza LLM (533 pagine in 70s con `pdftotext -layout`, tabelle/formule recintate,
outline in 223 voci). VaultForge e' l'unico che fa lo stesso *prodotto finale*
(atomic notes + wikilink + MOC), ma lo fa **interamente con un LLM in cloud**:
adottarlo significherebbe mandare i documenti del proprietario su Claude — il
veto assoluto — e perdere la garanzia tabelle/formule e la verifica numerica.
Il suo `double-link-builder.py` (imbuto deterministico) e' invece un buon
candidato da studiare quando costruiremo i wikilink della fase 4.

**Costo del cambio.** Adottare VaultForge: si butta `documenti.py` (determinismo,
corsia veloce), la garanzia tabelle/formule, la privacy dei documenti, la
verifica numerica; si installano Claude Code/Codex (cloud) o un agente locale
che non e' previsto. Si guadagna: roadmap, MOC e un'organizzazione piu' ricca —
tutta affidata al modello. Smart Connections/Atomic invece non coprono la
conversione, quindi non cancellano nulla di `documenti.py`.

---

## Capitolo 4 — Pezzo 2: riscrittura di una sezione con un modello locale, senza toccare tabelle e formule, verificando i numeri contro la fonte

Domanda: il pattern di `sbobina.py` (riscrivere una sezione spiegandola, con
modello locale, tabelle/formule recintate, numeri verificati) e' un pattern che
qualcuno ha impacchettato?

La riscrittura «spiega questa sezione» con un modello locale e' un pattern
generico e diffusissimo — ogni plugin di chat su Obsidian con Ollama lo fa
(obsidian-copilot, Summairize, Paper Summary, e decine di tutorial identici
trovati). Ma nessuno di questi fa le tre cose che ci distinguono:
- **recintare tabelle e formule** e passarle verbatim senza LLM (tutti fanno
  riassumere tutto al modello);
- **verificare i numeri** della riscrittura contro la fonte;
- girare **tutto in locale** senza offrire altro.

Due progetti, pero', impacchettano pezzi del problema in modo onesto:

**`pulkitj/groundguard`** — una «verification layer» che controlla se un output
generato da LLM e' effettivamente supportato dai documenti sorgente, **dopo**
la generazione (una backward pass: `output → verify against sources`). Non
chiede all'LLM «e' vero?», ma «e' supportato da questi paragrafi?», con vincolo
di non usare conoscenza di training. Il dettaglio che lo rende serio: un tier
**BM25 lessicale** risolve 60-70% delle affermazioni (numeri, date, citazioni
dirette, parafrasi vicine) **senza un solo token di LLM**; l'LLM gira solo sui
casi ambigui, e i pareggi finiscono in `NOT_GROUNDED`. MIT, ultimo commit **4
luglio 2026**, libreria su PyPI (`pip install groundguard`). Nei suoi esempi
usa modelli cloud (`gpt-4o-mini`), ma e' via `litellm` quindi accetta anche
endpoint locali. E' esattamente il concetto di verifica che noi facciamo nel
collaudo di `prova_sbobina.py` (numeri verificati contro il sintetico), ma
impacchettato come servizio da inserire a runtime.

**`google/langextract`** — libreria Google (research) che estrae dati
strutturati da testi non strutturati con un LLM, **agganciando ogni valore
estratto allo span di caratteri esatto della fonte** (grounding). Supporta
modelli locali via Ollama. MIT, ultimo commit **11 agosto 2026**, attivo. E'
orientata all'estrazione di entita' (note cliniche, report), non alla
riscrittura di sezioni di un libro; il grounding per span e' pero' una tecnica
di verifica ben fatta.

**Gli altri candidati** (Paper Summary, Summairize, e i plugin «AI summarize»
di Obsidian) sono riassuntori generici: cloud di default, niente verifica, le
tabelle le riassumono. Non cancellano nulla di nostro.

### Verdetto

**PRENDERE UN PEZZO — ma solo l'idea della verifica, non il tool.** La
riscrittura con modello locale senza toccare tabelle/formule: nessuno la fa, si
tiene `sbobina.py`. La verifica dei numeri contro la fonte: esiste come pattern
impacchettato (`groundguard`) e vale la pena guardarlo quando la fase 3/4
maturera', per decidere se la nostra verifica numerica nel collaudo basta o se
serve un passaggio di verifica a runtime. Non lo adottiamo ora perche':
progettato per risposte RAG (non note), LLM-as-judge sui casi ambigui (noi
vogliamo il determinismo), e di default punta al cloud.

**Costo del cambio.** Adottare groundguard: si installa il pacchetto, si
aggiunge una chiamata di verifica a runtime con modello locale, si perde la
semplicita' dell'attuale verifica statica nel collaudo; si guadagna un
controllo continuo su ogni sezione prodotta. Da valutare con una prova, non con
un'altra ricerca.

---

## Capitolo 5 — Pezzo 3: la coda su cartella (file che arriva → elaborazione → archivio, con ripresa e stato per documento)

Domanda: esiste gia' una libreria per questo? Sì, ed e' un pattern molto piu'
vecchio del nostro: le «persistent queue» e i «task queue» sono soluzioni
consolidate da anni. Le opzioni reali:

- **`persist-queue`** (peter-wangxu) — queue persistenti su file o SQLite per
  Python, thread-safe, sopravvivono a crash e riavvii, con serializzazione
  pickle/msgpack/cbor/json e API async. E' il piu' vicino al nostro caso: coda
  su disco, niente broker. Ma l'ultimo commit e' del **25 ottobre 2025** (~10
  mesi fa): dormiente. Basata su `queuelib` (Scrapy) e `python-pqueue`.
- **`watchdog`** — monitoraggio filesystem (notifiche su eventi), non e' una
  coda: risolve il «quando qualcosa arriva» ma non lo stato ne' la ripresa. E'
  cio' che oggi facciamo con il path unit systemd (`elechim-documenti.path`).
- **`huey`** — coda di task **durable con storage SQLite**, molto attiva
  (ultimo commit **16 agosto 2026**), leggera, senza broker. Pero' porta una
  architettura consumer/worker/scheduler che per noi e' infrastruttura in piu'.
- **`arq` / `RQ` / `celery` / `taskiq`** — code classiche, ma **tutte con
  broker** (Redis/AMQP): aggiungerebbero servizi che oggi non girano da nessuna
  parte. Fuori discussione finche' non arrivano Redis/Postgres (fase 3).

### Verdetto

**TENERE IL NOSTRO — con una ragione tecnica.** Il nostro caso e' un produttore
singolo (documenti che arrivano da Telegram in `documenti/`) e un consumatore
singolo (`documenti.py`), gia' innescato da un path unit systemd, con
`_coda_esclusiva()` (flock non bloccante) e stato per documento. Il pattern
«coda duratura» esiste eccome, ma adottare `persist-queue` significa prendere
una dipendenza dormiente da 10 mesi per sostituire ~50 righe che gia'
funzionano; adottare `huey` significa introdurre un worker e uno scheduler dove
oggi c'e' un path unit che riparte il servizio. La parte che non e' risolta
dalle librerie e' comunque nostra: lo stato *per documento* (che cosa e' stato
estratto, cosa e' fallito e perche') e la ripresa dal punto esatto — quello non
lo fa nessuna coda generica.

**Costo del cambio.** Zero guadagno netto, solo dipendenze e infrastruttura in
piu'. Se in futuro la coda diventera' multi-consumatore o dovra' durare oltre
un riavvio del fisso, si rivalutera' `persist-queue` (in quel caso: prima
verificare che sia di nuovo vivo).

---

## Capitolo 6 — Pezzo 4: il ragionamento a piu' ruoli su un pensiero (`/pensa`, `INCARICO-pensieri.md`)

Domanda: esiste un progetto che prende un appunto e ne produce obiezioni e
domande, come la nostra pipeline a cinque ruoli (chi ascolta → chi chiede →
chi obietta → chi porta un precedente → la sintesi)?

Il concetto generale esiste ed e' molto studiato: si chiama **multi-agent
debate** (collaborazione avversaria tra LLM per ridurre le allucinazioni),
formalizzato in ricerca (es. «Multi-LLM Debate: Framework, Principals, and
Interventions», NeurIPS 2024; Society of Mind). Quello che esiste **in pratica**:

- **`muthuspark/multi-agent-debate`** — demo leggera con LangGraph: due agenti
  che dibattono su una domanda e un terzo giudice. E' per **domande**, non per
  pensieri personali; modelli cloud (Claude); ultimo commit **ott 2025** (morto).
  E' la dimostrazione didattica del pattern, non uno strumento da adottare.
- **`Skytliang/Multi-Agents-Debate` (MAD)** — repo di ricerca, il primo lavoro
  sul debate tra agenti. Codice accademico, non un prodotto.
- **`m4vic/socratic`** — una skill per agenti (Claude/Codex) di
  «self-interrogation»: 697 domande su 15 domini di ingegneria + 60 carte di
  decisione, il tutto selezionato dall'agente (~3000 token a run). Ultimo commit
  **13 agosto 2026** (attivo). Ma e' pensato per *interrogare un task di
  ingegneria prima di eseguirlo*, non per elaborare un pensiero personale, e
  gira su Claude/Codex (cloud).
- **Agent Patterns Catalog** (`agentpatternscatalog.github.io`) — un catalogo di
  pattern per agenti (tra cui «Socratic Questioning Agent»): utile come
  riferimento di disegno, non come dipendenza.
- **plugin Obsidian** (Copilot, Text Generator ecc.): nessuno fa il «ragionamento
  a ruoli» con isolamento delle chiamate e nota finale in vault.

### Verdetto

**TENERE IL NOSTRO.** Il pattern e' accademico o didattico: nessun progetto fa
«pensiero → obiezioni + domande → nota su Obsidian» con le nostre tre condizioni
(tutto locale, ruoli isolati a chiamate separate e corte, sintesi che non
risolve). I framework di debate (LangGraph) presuppongono il cloud e una
cronologia condivisa, che e' proprio cio' che i nostri vincoli 3 e 4 escludono.
Cio' che vale la pena leggere, quando scriveremo i prompt dei cinque ruoli,
sono `m4vic/socratic` (come si scrivono domande che non sono un modulo) e il
catalogo dei pattern (il «Socratic Questioning Agent»).

**Costo del cambio.** Non c'e' niente da cambiare: i candidati non coprono la
destinazione (nota nel vault) ne' i vincoli (locale, isolamento).

---

## Capitolo 7 — Pezzo 5: orchestrazione di agenti da CLI con sorveglianza e confini (il «guardiano»)

Domanda: esiste gia' un guardiano — un supervisore che lancia agenti CLI, ne
sorveglia l'esecuzione, impone timeout e confini, e ferma quelli bloccati? Oggi
tre sessioni `opencode run` sono morte per 5h57m su un endpoint morto
(riconosciuto, chiuso not planned), quindi il nostro guardiano nasce da una
ferita vera.

I candidati trovati, divisi per il pezzo che coprono:

**Orchestrazione di agenti CLI — `awslabs/cli-agent-orchestrator` (CAO).**
Supervisore che coordina piu' CLI di agenti di codice (Claude Code, Codex,
Copilot, **opencode CLI** e altri) lanciandoli in sessioni **tmux isolate** e
delegando lavoro in parallelo o in sequenza. Ultimo commit **17 agosto 2026**
(oggi, molto attivo), su PyPI, MIT. E' il piu' vicino a «orchestrazione da riga
di comando», ma e' fatto per **delegare a piu' specialisti**, non per sorvegliare
una run singola bloccata: non osserva lo stream di eventi per timeout o
escalation di kill, e gli agenti coordinati sono quelli in cloud.

**Watchdog/anomalie/kill — `Cohorte-ai/agent-monitor` (theaios).** Libreria
in-process: registra ogni evento dell'agente, metriche realtime su finestre
scorrevoli, **anomalie con z-score** e **kill switch** per fermare agenti che si
comportano male, export di report di conformita'. ~0.1ms per evento, niente
servizi esterni. Apache-2.0, PyPI. Ultimo commit **29 marzo 2026** (~4 mesi,
semiactiva). E' il concetto giusto (osserva e agisce, non solo traccia), ma
sorveglia l'*interno* del suo agente, non un processo CLI esterno.

**Watchdog dei tool call — `ivanpaghubasan/agent-watchdog`.** Proxy che
intercetta ogni tool call dell'agente (loop sullo stesso tool, nomi di tool
inesistenti, consumo di token oltre il budget), registra tutto su **PostgreSQL**
e alza flag con severita'. Ultimo commit 14 giugno 2026. Ma richiede Postgres e
si aggancia all'API Anthropic: e' per agenti che controlliamo, non per CLI.

**Confini deterministici — `microsoft/agent-governance-toolkit` (AGT).**
Policy enforcement, identita', sandboxing e SRE per agenti autonomi: intercetta
ogni tool call in **codice applicativo deterministico** prima che l'intento del
modello tocchi il mondo reale. «Le azioni che il kernel nega sono
strutturalmente impossibili», non «improbabili». MIT, molto attivo (ultimo
commit **12 agosto 2026**), Public Preview. E' la risposta piu' seria al
«confini», ma e' pensata per agenti di produzione in ecosistema Azure, non per
due CLI locali.

### Verdetto

**TENERE IL NOSTRO — il guardiano si costruisce; ma i pezzi del disegno si
rubano.** Nessun candidato copre il nostro caso esatto: sorvegliare *un processo
CLI esterno* (opencode/agy), osservarne lo stream di eventi (SSE / `stream-json`),
rilevare l'endpoint morto, e fare escalation SIGTERM→SIGKILL con budget di
retry. CAO orchestra ma non sorveglia; agent-monitor sorveglia ma solo agenti
propri; agent-watchdog vuole Postgres e un proxy API; AGT impone i confini ma
su scala enterprise/Azure. Dai primi due si prende il *disegno*: isolamento
(tmux), detection di anomalie (z-score) e kill switch. La novita' che non esiste
impacchettata e' la sorveglianza dello stream di eventi con escalation — ed e'
proprio quella che oggi manca (la lezione delle 5h57m).

**Costo del cambio.** Adottare CAO: si butta l'isolamento casalingo, ma si
aggiunge tmux e una costellazione di CLI cloud, senza guadagnare la sorveglianza
che ci serve. Adottare agent-monitor: va integrato *dentro* il loop dell'agente,
ma il nostro guardiano guarda l'esterno. Nessuno dei quattro va installato oggi;
tutti e quattro vanno letti mentre si progetta.

---

## Capitolo 8 — Pezzo 6: la memoria condivisa fra piu' agenti (MEMORY.md + megamemory + codegraph + AGENTS.md/DA-FARE.md)

Domanda: esiste un progetto che unifica i nostri quattro posti di memoria?

Risposta onesta: **no, perche' la domanda copre due cose diverse che nessuno
unifica.**

**1. La memoria di contesto del progetto** — `AGENTS.md` + `DA-FARE.md` +
`MEMORY.md` + `.codegraph/`. Sono file di istruzioni e stato, leggibili da
uomini e agenti. Il solo «standard» emergente qui e' il formato **AGENTS.md**
(Anthropic/OpenAI, file multipli `AGENTS.md` annidati): unifica la *forma*,
non il contenuto, e non esiste un prodotto che fonde file di istruzioni con
memoria di runtime. E' corretto che resti cosi': le istruzioni procedurali e
la coda dei task sono contesto di lavoro, non fatti da ricordare.

**2. La memoria di runtime** — i fatti estratti dalle conversazioni (la nostra
fase 3). Qui il mercato e' maturo e affollato. Tre candidati solidi, tutti
**Apache-2.0** e tutti molto attivi (ultimo commit la settimana scorsa):

- **`mem0ai/mem0`** — «universal memory layer»: estrae fatti da conversazioni e
  li mette in un mix di vector store + graph store, con memoria episodica,
  semantica e procedurale. Puo' girare in locale (Ollama + vector DB locale).
  E' il piu' popolare del trio. E' il concetto che Honcho impacchetta in modo
  piu' esplicito per il nostro caso (episodic + user model).
- **`getzep/graphiti`** — knowledge graph **temporale**: i fatti hanno un
  intervallo di validita', le contraddizioni si registrano e si superano, mai si
  cancellano. Richiede un grafo (Neo4j/FalkorDB) + vector store, supporta LLM
  locali via endpoint OpenAI-compatibili. **E' esattamente il principio del
  nostro dreaming mode** («datare e superare, mai cancellare») gia'
  implementato.
- **`topoteretes/cognee`** — piattaforma di memoria a knowledge graph per agenti,
  local-first.

### Verdetto

**TENERE IL NOSTRO sui file di contesto; PRENDERE UN PEZZO e' la fase 3, che
cambia bersaglio.** Nessun progetto unifica i quattro posti — e non conviene
nemmeno provarci: `AGENTS.md`/`DA-FARE.md` sono istruzioni e task, la memoria
runtime e' un database. La scoperta vera e' che la scelta di Honcho per la fase
3 **non e' l'unica** e va verificata al momento giusto: il confronto onesto da
fare prima di Postgres+pgvector e' **Honcho vs Graphiti vs Mem0**, con l'occhio
particolare sul fatto che Graphiti implementa gia' il nostro principio del
dreaming mode (fatti datati, superati mai cancellati). Ma questo e' lavoro della
fase 3, non una ragione per cancellare nulla oggi.

**Costo del cambio.** Non c'e' nulla da cancellare: adottare Mem0/Graphiti oggi
aggiungerebbe un database e un LLM di ingestion senza toccare `AGENTS.md`. La
verifica Honcho-vs-alternative e' la prima cosa da fare quando si apre la fase 3.

---

## Capitolo 9 — Le tre cose piu' promettenti, in ordine

1. **L'imbuto di link-building di VaultForge** (`scripts/double-link-builder.py`,
   deterministico, zero dipendenze). E' il pezzo piu' riusabile che abbiamo
   trovato: i nostri wikilink della fase 4 possono diventare un imbuto (struttura
   → TF-IDF → euristiche → LLM solo sui candidati) invece che una decisione
   tutta del modello. **Primo passo concreto**: replicare l'imbuto strict-mode su
   una copia di 30 note del vault e confrontare i link che produce coi nostri —
   se la copertura ~40-50% con zero LLM regge sui nostri testi, il guadagno e'
   misurato subito.
2. **`groundguard` come verifica numerica a runtime della sbobina**. Ha gia'
   il tier lessicale BM25 che risolve numeri/dati senza LLM e il pareggio che
   finisce in `NOT_GROUNDED`. **Primo passo concreto**: installarlo in un venv
   di prova (non nel progetto), verificare 10 sezioni della sbobina sintetica con
   numeri alterati di proposito e misurare quanti errori prende. Se prende tutto,
   si decide se entrare nella pipeline.
3. **Il confronto Honcho vs Graphiti per la fase 3.** Graphiti implementa gia'
   il nostro principio del dreaming mode (fatti datati, superati, mai cancellati)
   ed e' Apache-2.0 e attivo. **Primo passo concreto**: prima di installare
   Postgres+pgvector, una prova con Graphiti embedded (Kuzu) + `bge-m3` su un
   mese di `archivio/`, e valutare se il grafo temporale gestisce le
   contraddizioni delle conversazioni vere meglio dell'episodic memory di Honcho.

## Capitolo 10 — Dove abbiamo davvero qualcosa di raro

Nessun progetto trovato rispetta i nostri tre vincoli insieme: **tutto locale,
i documenti non escono dalle due macchine, le tabelle e le formule non passano
mai da un LLM**. book-to-skill e VaultForge mandano il contenuto al modello
(cloud di default) e riassumono le tabelle; gli altri non fanno conversione. In
particolare la **corsia veloce deterministica senza LLM** (un PDF di 533 pagine
in 70s con `pdftotext -layout`, tabelle e formule recintate, outline in 223
voci) non l'ha fatta nessuno: tutti strutturano con un LLM. E la **verifica
numerica deterministica** contro la fonte sintetica (`prova_sbobina.py`) come
asserzione esatta, non giudizio a occhio, non e' il default di nessuno dei
progetti visti. Questo e' il motivo — tecnico, non affettivo — per tenere il
nostro su fase 4: non e' «fatto meglio da qualcun altro», e' fatto da nessuno
con questi vincoli.

## Capitolo 11 — Non trovato

- Un progetto che fa **PDF → markdown con tabelle/formule recintate e indice
  senza nessun LLM** (corsia veloce come la nostra): non trovato.
- Un plugin Obsidian che produce **note atomiche con wikilink da un PDF senza
  LLM**: non trovato (VaultForge lo fa, ma tutto con LLM cloud).
- Un guardiano che **sorveglia lo stream di eventi di un processo CLI esterno**
  (SSE/stream-json) e fa escalation SIGTERM→SIGKILL con budget di retry: non
  trovato.
- Un progetto che **unifica i file di contesto** (AGENTS.md + DA-FARE.md +
  memoria runtime) in un solo posto: non trovato — e il motivo e' che sono due
  cose diverse.
- `arodriguez47/obsidian-atomic-notes-plugin`: non trovato (404).
- book-to-skill su Show HN: non trovato (nessun item specifico emerso nella
  ricerca; presente solo materiale di studio HN non correlato).
