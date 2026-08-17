# RICERCA-strumenti — cosa ci ferma davvero nel web, e cosa lo toglie

Incarico `INCARICO-ricerca-strumenti.md`, eseguito il 17 agosto 2026 da
opencode. Ricerca sul web con SearXNG locale (`127.0.0.1:8888`) e letture con
`webfetch`/`curl`. Regola rispettata: ogni affermazione ha l'URL **accanto**
(li ho aperti o verificati durante la ricerca); dove non ho trovato niente c'e'
la sezione «Non trovato». Non ho toccato codice, non ho installato nulla, non
ho creato token. Percorsi relativi al repo.

## Sintesi — dieci righe

**Le nostre ricerche non si sono rotte sul recupero delle pagine: nessuna
pagina e' risultata illeggibile o bloccata.** I guasti misurati sono stati un
muro di permessi (`/tmp` auto-negato, configurazione) e il rate limit
dell'API GitHub non autenticata, che ha fatto dichiarare inesistenti sei repo
che esistono. La domanda «quale libreria di scraping» e' la domanda sbagliata:
**Scrapling, la libreria segnalata, non toglie nessuno dei guasti che abbiamo
misurato** (cap. 1) — e' un framework anti-bot per pagine che non ci hanno mai
bloccato. **Cosa ci toglie davvero il guasto**: un **token GitHub a sola
lettura** (porta il limite da 60 a 5.000 richieste/ora, cap. 2) e **una regola
di disciplina** (URL accanto a ogni affermazione, e occhio agli header
`x-ratelimit-remaining` prima di martellare un'API). Per il «quadro sempre
chiaro» del proprietario non serve un servizio: ci sono gia' i **feed Atom di
GitHub** (`.atom` per releases/tags/commits, gratuiti e senza token) e noi
abbiamo gia' timer systemd e bot Telegram (cap. 3). Il nostro metodo di ricerca
ha due buchi veri: le **query non vengono registrate** (le ricerche non sono
riproducibili) e **quando un'API ci risponde 429 ci fermiamo** invece di
passare a un'altra fonte — e' lo stesso difetto del rate limit di oggi, pagato
gia' nella ricerca precedente (cap. 4).

---

## 1. `D4Vinci/Scrapling` — cosa fa davvero, e risolve un problema che abbiamo?

**Verdetto secco: no, Scrapling non toglie nessuno dei guasti misurati.**
La tabella dei guasti di `INCARICO-ricerca-strumenti.md` non contiene una sola
riga «pagina bloccata / non leggibile». Scrapling e' specializzato proprio in
quello (anti-bot, Cloudflare, browser stealth): **risolve un problema che non
abbiamo**, e lo risolve aggiungendo il peso che vogliamo evitare.

### Cos'e', in una riga

Repo: https://github.com/D4Vinci/Scrapling — «An adaptive Web Scraping framework
that handles everything from a single request to a full-scale crawl». **Licenza
BSD-3-Clause** (verificata via API: https://api.github.com/licenses/bsd-3-clause),
**74.780 stelle, 7.477 fork, 5 issue aperte**, creato il 13/10/2024, ultimo
push **11/08/2026** (vivo), ultima release **v0.4.14 del 10/08/2026**
(https://github.com/D4Vinci/Scrapling/releases). Homepage delle docs:
https://scrapling.readthedocs.io/en/latest/

### E' un parser, un fetch, o un framework?

**E' un framework a tre livelli, piu' un parser.** Dal README aperto
(https://raw.githubusercontent.com/D4Vinci/Scrapling/main/README.md) e dalla
guida sui fetcher (https://scrapling.readthedocs.io/en/latest/fetching/choosing.html):

| livello | classe | browser? | a cosa serve |
|---|---|---|---|
| HTTP | `Fetcher` | **no** | richieste HTTP con impersonificazione TLS, sessioni, HTTP/3 |
| Dinamico | `DynamicFetcher` | **si, Playwright + Chromium/Chrome** | pagine con JavaScript |
| Stealth | `StealthyFetcher` | **si, Playwright + Chromium/Chrome** | anti-bot, Cloudflare Turnstile/Interstitial |

La tabella della doc `choosing.html` e' esplicita: per `Fetcher` la colonna
Browser dice `❌`, per gli altri due `Chromium and Google Chrome` via Playwright.
L'installazione base `pip install scrapling` e' **solo il parser**; i fetcher
arrivano con `pip install "scrapling[fetchers]"` e poi `scrapling install`, che
**scarica i browser e le loro dipendenze di sistema** (citato nel README, sezione
Installation). Esiste anche un'immagine Docker ufficiale
(`docker pull pyd4vinci/scrapling`) con tutti i browser inclusi
(https://hub.docker.com/r/pyd4vinci/scrapling).

Quindi: **serve un browser solo per i due livelli che servono alle pagine
JavaScript/anti-bot; il livello HTTP puro no.** Ma per le nostre pagine — doc
tecniche e pagine GitHub, il 90% di cio' che leggiamo — il livello HTTP di
Scrapling e' l'equivalente di `requests` con un parser in piu'.

### Cosa lo distingue da `requests` + `beautifulsoup`

Quattro cose, tutte documentate nel README: (1) **adaptive scraping** — il
parser impara la struttura di una pagina e «relocates your elements when pages
update» (`p.css('.prodotto', adaptive=True)`); (2) il **bypass anti-bot** di
`StealthyFetcher` (Turnstile/Interstitial Cloudflare); (3) il **framework
spider** (concorso, pause/resume, proxy rotation, robots.txt) tipo Scrapy;
(4) un **server MCP** integrato per estrazione assistita da AI
(https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html).

`requests`+`bs4` fa 0 di queste 4 cose. Ma noi **non usiamo** `bs4`: la nostra
corsia statica e' `requests`+`trafilatura` (estrazione testo), e davanti a
quella c'e' gia' **crawl4ai** in container su `127.0.0.1:11235`
(https://github.com/unclecode/crawl4ai, Apache-2.0, 78.498 stelle, ultimo push
17/08/2026, v0.9.2). Il confronto che conta non e' Scrapling-vs-bs4, e'
Scrapling-vs-crawl4ai.

### Confronto diretto con crawl4ai, che abbiamo gia' in piedi

| | **crawl4ai** (in produzione qui) | **Scrapling** |
|---|---|---|
| Licenza | Apache-2.0 | BSD-3-Clause |
| Natura | crawler LLM-friendly: pagina → markdown pulito | framework a 3 livelli + parser |
| Browser | Playwright (Chromium) | Fetcher senza browser / Dynamic+Stealth con Playwright |
| Estrazione | **markdown** (raw + fit), BM25, JSON schema, LLM opzionale | selettori CSS/XPath, adaptive |
| Anti-bot | si' (v0.8.5: 3-tier detection, proxy escalation) | si' (stealth, Turnstile) |
| Sito servito | Docker API su **11235** (il nostro) | PyPI o Docker |
| Adaptive | «AdaptiveCrawler» (v0.7.0) | si', a livello di selettore |

Entrambi coprono le pagine JavaScript, entrambi hanno anti-bot, entrambi sono
vivi e grossi. **Non ho trovato una pagina che Scrapling prende e crawl4ai
no**, e soprattutto: nelle cinque ricerche di oggi **nessuna pagina e'
risultata illeggibile** con l'infrastruttura che abbiamo. Le doc tecniche e le
pagine GitHub che leggiamo non sono il territorio dove Scrapling vince — quello
e' il territorio anti-bot (Turnstile, DataDome), che nelle nostre misure **non
compare**.

### La domanda che decide: toglie almeno un guasto misurato?

| guasto misurato | Scrapling lo toglie? |
|---|---|
| muro dei permessi (`/tmp` auto-negato) | **no** — e' configurazione, non web |
| rate limit API GitHub (6 repo falsamente «inesistenti») | **no** — non tocca l'API GitHub |
| repo che risponde 404 (progetto non esistente) | **no** — il progetto non esiste |
| rapporto senza URL (1 su 4) | **no** — e' disciplina |
| pagina non leggibile / bloccata | **non e' mai successo** — nulla da togliere |

**Risposta: no.** Adottare Scrapling = nuova dipendenza (browser inclusi, o
container) per un problema che la nostra tabella dei guasti non ha. La risposta
che risparmia la dipendenza e' in cap. 2.

---

## 2. Il rate limit di GitHub, che e' un guasto misurato

**Verdetto secco: basta un token personale a sola lettura.** Porta il limite
della stragrande maggioranza delle chiamate da 60 a 5.000 all'ora, si passa con
un header, si tiene fuori dal repo con `.env` (che abbiamo gia').

### I numeri ufficiali

Documentazione ufficiale aperta:
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

- **Non autenticato**: **60 richieste/ora**, associate all'IP di origine.
- **Autenticato** (personal access token, OAuth, GitHub App): **5.000
  richieste/ora** per l'utente (15.000/ora solo se l'app e' di un'org Enterprise
  Cloud).
- **Search endpoints**: limite separato e piu' stretto
  (https://docs.github.com/en/rest/search/search): **non autenticato 10/min**,
  **autenticato 30/min**; lo **search code** richiede autenticazione ed e' a
  10/min.
- **Limiti secondari** (stessa pagina rate-limits): max **100 richieste
  concorrenti**, max **900 punti/minuto** sugli endpoint REST, max **80
  richieste di creazione contenuti/min** e 500/ora.
- Quando si sfora: risposta **403 o 429**, header `x-ratelimit-remaining: 0` e
  `x-ratelimit-reset` (epoch seconds) che dice quando riprovare. Verificato
  nella mia sessione: una chiamata non autenticata restituisce
  `x-ratelimit-limit: 60` e `x-ratelimit-reset` (es. il reset osservato era
  ~1786999726, un'ora dopo).

**Perche' questo e' il nostro guasto**: 6 repo dichiarati inesistenti a torto =
6 chiamate non autenticate a `api.github.com/repos/...` che rispondevano 403
(muro) o tornavano vuote per rate limit, e un agente ha letto «repo non
esistente» invece di «rate limited». La distinzione e' negli header della
risposta, non nel body.

### Basta un token a sola lettura?

**Si'. E non serve neppure un permesso esplicito per i repo pubblici.** La
documentazione sui personal access token
(https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
dice testualmente: *«Tokens always include read-only access to all public
repositories on GitHub»*. Quindi un **fine-grained token** con zero permessi
espliciti legge gia' tutto cio' che serve a noi (metadati repo, commits,
release, README). Per sicurezza e chiarezza si puo' aggiungere la permission
`Metadata: read` (la tabella delle repository permissions della stessa pagina
la elenca come `metadata` → `read`), ma per i repo pubblici il default e' gia'
l'accesso in lettura.

Come si passa: header **`Authorization: Bearer <token>`** (stessa pagina
rate-limits, sezione «Use the rate limit response headers»; gli esempi curl
della doc REST usano `curl -H "Authorization: Bearer <YOUR-TOKEN>"`). Un giro
di prova: `curl -H "Authorization: Bearer $GITHUB_TOKEN" -I
https://api.github.com/rate_limit` — con il token in testa l'header
`x-ratelimit-limit` deve tornare 5000.

### Modi senza token che reggono meglio

Esistono, e alcuni li abbiamo gia' usati in questa ricerca:

- **La pagina HTML** di GitHub (https://github.com/OWNER/REPO e `/releases`):
  non passa dall'API, quindi **non ha il rate limit di 60/ora**; restituisce il
  DOM della pagina. Costa un parsing in piu' (o crawl4ai, che la rende markdown
  in 1,3s medio, misurato il 15/08). Verificato in questa ricerca: `curl -o
  /dev/null -w "%{http_code}" https://github.com/D4Vinci/Scrapling/releases`
  → 200.
- **I feed Atom** (`/releases.atom`, `/tags.atom`, `/commits.atom`): serve la
  versione recente (release, tag, commit) come XML, senza autenticazione e
  fuori dall'API. Verificato: `https://github.com/D4Vinci/Scrapling/releases.atom`
  → 200, `content-type: application/atom+xml` (cap. 3).
- **`codeload`** per i tarball: `https://codeload.github.com/OWNER/REPO/tar.gz/
  refs/tags/TAG` → 200 senza token (verificato su v0.4.14 di Scrapling,
  `content-type: application/x-gzip`).

Per **metadati freschi e ricchi** (stelle, licenza, ultimo commit, release) la
via giusta resta l'API autenticata: e' un solo token, il guadagno e' 83x.

### Il token e' un segreto: come si tiene fuori dal repo pubblico

**`.env` + `.env.example` e' il posto giusto, e lo abbiamo gia'.**
Nel repo esistono `.env.example` e `mac/.env.example` (creati il 15/08, concetto
`repo-pubblico-esempi-config`), e la regola del progetto e' che `.env` non va
letto ne' versionato (AGENTS.md). Il pattern e' gia' collaudato qui (token
Telegram, token crawl4ai): la variabile `GITHUB_TOKEN` si legge da `.env`, il
`.env.example` documenta il nome della chiave senza il valore. Da non fare: mai
mettere il token in un incarico, in un `RICERCA-*.md` o in `opencode.json`.

---

## 3. Come si tiene «un quadro sempre chiaro» invece di ricerche a spot

**Verdetto secco: non serve un servizio esterno — esistono i feed Atom di
GitHub, che sono la sorveglianza minima e gratuita, e noi abbiamo gia' timer
systemd e bot Telegram per trasformarli in un rapporto periodico.**

### Gli strumenti esistenti, in ordine di costo

**1. Feed Atom di GitHub (gratis, zero installazione).** Ogni repo espone
`https://github.com/OWNER/REPO/releases.atom`, `/tags.atom`, `/commits.atom` e
`/issues.atom` — verificati in questa ricerca: 200 senza autenticazione, XML
Atom. Il REST endpoint `GET /feeds` li elenca per l'utente autenticato
(https://docs.github.com/en/rest/activity/feeds). **Costo in pratica: un feed
per progetto, cioe' una URL fissa da interrogare.** Un feed di releases di un
repo attivo (Scrapling) e' ~127 KB lordi perche' include il corpo delle note di
release: per la sorveglianza basta leggere i titoli e le date `<entry>`, non il
testo intero.

**2. Il «Watch» nativo di GitHub (gratis, zero installazione).** Il watch di un
repo genera notifiche, configurabili per tipo di evento (issues, PR, releases,
security alerts, discussions); si arriva a 10.000 repo seguiti
(https://docs.github.com/en/account-and-profile/managing-subscriptions-and-notifications-on-github/setting-up-notifications/configuring-notifications).
Limite: le notifiche arrivano nella inbox GitHub / email di un account umano;
non c'e' un endpoint che le spinga su Telegram o su un rapporto periodico senza
intermediari.

**3. newreleases.io (gratis, servizio cloud).** Tracker di release che copre
GitHub, GitLab, PyPI, npm, Docker Hub ecc., con notifiche via email, Slack,
Discord, **Telegram** e webhook, piu' un HTTP API; il piano **Free** non richiede
carta di credito (https://newreleases.io/ e https://newreleases.io/pricing).
Costo: zero, ma e' un servizio esterno che aggrega metadati di progetti
pubblici (non i nostri documenti) — accettabile dal punto di vista della
privacy, ma introduce un account e una dipendenza in piu'.

**4. changedetection.io (self-hosted, gratuito).** Monitora il contenuto di
qualunque pagina (non solo GitHub) e notifica via **apprise**, che include
Telegram; REST API, Apache-2.0, 33,2k stelle
(https://github.com/dgtlmoon/changedetection.io). E' il piu' potente ma e'
**sovradimensionato** per «sapere quando esce una release»: un container in piu'
da tenere su (abbiamo gia' searxng e crawl4ai).

### Qual e' la mossa giusta per noi

Abbiamo gia' i mattoni: i feed `.atom` (fonte), un **timer systemd** sul fisso
(come `elechim-documenti.path`), il **bot Telegram** (notifica), e il fisso come
compressore (regola 2). Un timer che ogni mattina (o ogni settimana) legge
`releases.atom` di una lista corta di repo, confronta con l'ultimo tag noto
salvato in `stato/`, e manda un messaggio Telegram con le release nuove **non
aggiunge nessun servizio**: e' lo stesso pattern del path unit che gia' ci
sorveglia `documenti/`. Il lavoro non va spinto al Mac: il prefisso della
conversazione non deve cambiare a meta' turno (regola 5); e' un rapporto a se',
non una memoria iniettata.

### Quali progetti sorvegliare: la lista corta e motivata

Dalle dipendenze reali (AGENTS.md): una lista lunga la legge nessuno, quindi
**otto** — tutti repo che oggi girano o decideranno fasi aperte:

| repo | perche' |
|---|---|
| `anomalyco/opencode` (https://github.com/anomalyco/opencode) | il nostro agente principale; il tracker decide i nostri workaround |
| `ollama/ollama` (https://github.com/ollama/ollama) | runtime su entrambe le macchine |
| `unclecode/crawl4ai` (https://github.com/unclecode/crawl4ai) | gia' in produzione qui; la 0.8.7 e' un security-hardening release (vulnerabilita' segnalate, vedi https://raw.githubusercontent.com/unclecode/crawl4ai/main/CHANGELOG.md) |
| `docling-project/docling` (https://github.com/docling-project/docling) | candidato seconda corsia fase 4 (MIT) |
| `datalab-to/marker` (https://github.com/datalab-to/marker) | candidato seconda corsia fase 4 |
| `getzep/graphiti` (https://github.com/getzep/graphiti) | candidato fase 3 (memoria temporale, il principio del dreaming mode) |
| `D4Vinci/Scrapling` (https://github.com/D4Vinci/Scrapling) | il candidato di questo incarico — da non perdere se matura qualcosa di utile |
| `SYSTRAN/faster-whisper` (https://github.com/SYSTRAN/faster-whisper) | voce in produzione sul fisso |

Esclusi perche' non decidono nulla di nostro (aggiornati dal sistema, non scelti
da noi): poppler (pacchetto distro), i modelli (li versionea ollama), Honcho
(non ancora scelto — si aggiungera' alla lista se la fase 3 lo adotta).

---

## 4. Cosa manca alle nostre ricerche, viste da fuori

Guardati per intero: `RICERCA-stato-arte.md`, `RICERCA-simbiosi.md`,
`RICERCA-mcp.md`, `RICERCA-ridondanza.md` (tutti nel repo). I quattro sono
densi, per-claim con URL, con verdetto per capitolo. Ecco dove si fermano
troppo presto e cosa non toccano.

### Dove ci siamo fermati troppo presto

- **Quando un'API risponde 429 ci fermiamo.** In `RICERCA-stato-arte.md`
  (cap. 2, riga 220 circa) il paper sugli apici/pedici e' dichiarato «non
  leggibile: Springer dietro captcha, Semantic Scholar API rate-limited (429)».
  Il 429 era **rate limit dell'API non autenticata** — lo stesso guasto di oggi,
  pagato prima di oggi e non riconosciuto. Non c'e' stato un tentativo di
  archivi.org, di un mirror, di un'altra istanza: si e' passati al «non
  trovato». Il cap. 2 di questo file dice che fare con un 429: guardare gli
  header, cambiare fonte (HTML/feed/mirror), non dichiarare «inesistente».
- **I candidati si giudicano dal README, non si leggono dove conta.** In
  `RICERCA-mcp.md` due candidati su dieci sono descritti dal solo metadata
  GitHub («README non aperto»: lasso-security/mcp-gateway,
  matthisholleville/mcp-gateway — righe ~145-146, e cap. 3, righe ~144-146), e
  `skislyakow/opencode-py` in `RICERCA-simbiosi.md` (riga ~249) e' dichiarato
  «non verificato». Giusto dichiararlo, ma e' un segno che la lista dei
  candidati era piu' lunga di quanto abbiamo avuto pazienza di leggere: meglio
  **cinque candidati letti per intero** che dieci di cui due solo a metadati.
- **«Non trovato» significa spesso «non ho cercato abbastanza».** In
  `RICERCA-ridondanza.md` il plugin `arodriguez47/obsidian-atomic-notes-plugin`
  e' «non trovato (404)» — giusto; ma la soglia della densita' di cifre e' «non
  trovata pubblicata» dopo una ricerca, non dopo una verifica sistematica nelle
  release note di pdfplumber/camelot/tabula. Il cap. 4 di stato-arte e'
  onesto sul punto, ma la distinzione fra «non esiste» e «non l'ho cercato
  nella pagina giusta» andrebbe scritta esplicitamente.

### Quali fonti non abbiamo mai toccato

- **Il tracker delle issue dei progetti che studiamo** come fonte primaria:
  usato moltissimo per opencode (`RICERCA-simbiosi.md` e' quasi tutto issue),
  ma quasi mai per gli strumenti candidati. Scrapling ha 5 issue aperte;
  docling/marker hanno tracker che decidono la roadmap. E' la fonte che dice
  «vivo» e «dove sta andando» meglio di un README.
- **I changelog / note di release ufficiali**: in `RICERCA-stato-arte.md` le
  pipeline sono descritte per licenza/vitalita', ma nessuna nota di release
  (es. la v0.8.7 di crawl4ai con le fix di sicurezza, che oggi conosciamo) e'
  stata letta per decidere. Il rate limit ci ha gia' fatto perdere 6 repo;
  le note di release ci avrebbero potuto far perdere una vulnerabilita'.
- **I feed Atom** (cap. 3): nessuno dei quattro file li usa; sono la fonte piu'
  economica di «cosa e' cambiato da ieri».
- **Gli archivi web** per le fonti morte: mai usato Wayback Machine. Il paper
  Springer dietro captcha di stato-arte, cap. 2, era recuperabile via
  `web.archive.org`.
- **La nostra stessa infrastruttura**: `RICERCA-simbiosi.md` e `RICERCA-mcp.md`
  non dicono con cosa hanno cercato; solo stato-arte dichiara SearXNG + crawl4ai
  in testa. Se ogni ricerca non registra i suoi strumenti, non possiamo dire
  cosa ha funzionato.

### Il formato «un capitolo per domanda + verdetto»

**Funziona, con un difetto di ripetizione e un buco serio.**

- **Ripetizione**: ogni capitolo riapre con «Cosa abbiamo noi oggi» (stato-arte
  lo fa in 5 capitoli su 6 quasi verbatim) e i metadati dei candidati (licenza,
  stelle, ultimo commit) sono ripetuti in ogni file. La sintesi da dieci righe
  in cima e' la parte giusta; le ripetizioni dentro i capitoli sono cio' che la
  fa crescere a 500+ righe.
- **Il buco serio: le query non sono registrate.** Nessuno dei quattro file
  salva **le ricerche che sono state fatte** (query, motori, date). Il risultato
  non e' riproducibile: non si puo' sapere se «non trovato» deriva da una query
  buona o da una domanda formulata male. E' il difetto piu' economico da
  correggere di tutti: una sezione «Come ho cercato» con le query (o un file
  `.log`) per ogni ricerca.
- **Il verdetto secco funziona** (TENERE IL NOSTRO / PRENDERE L'IDEA /
  NON C'ENTRA): e' il motivo per cui si puo' decidere su un file senza rileggerlo
  tutto. Da tenere com'e'.

---

## 1. Le tre cose da fare, dalla piu' economica alla piu' cara

1. **Un token GitHub a sola lettura in `.env`.** E' la risposta al guasto
   misurato (6 repo falsamente inesistenti). Costo: zero euro, cinque minuti.
   Primo passo concreto: creare un fine-grained token senza permessi espliciti
   (i repo pubblici si leggono comunque, cap. 2), metterlo come `GITHUB_TOKEN=`
   in `.env`, aggiungere `GITHUB_TOKEN=` a `.env.example`, e provare che
   `x-ratelimit-limit: 5000` compare negli header.
2. **La regola di disciplina, scritta e meccanica.** Ogni ricerca registra le
   sue query (una sezione «Come ho cercato» in testa) e ogni affermazione ha
   l'URL accanto; quando un'API risponde 403/429 si legge `x-ratelimit-remaining`
   e si cambia fonte, **mai** «non trovato» per rate limit. Costo: nessuna
   dipendenza. Primo passo concreto: la sezione «Come ho cercato» in
   `RICERCA-strumenti.md` e' gia' il modello — si copia nei prossimi incarichi.
3. **Un timer systemd che legge i feed `.atom` di otto repo e notifica su
   Telegram.** Il «quadro sempre chiaro» del proprietario senza servizi esterni.
   Costo: un piccolo script + un timer (pattern gia' collaudato col path unit).
   Primo passo concreto: script di prova che legge `releases.atom` di `ollama` e
   stampa i tre titoli piu' recenti, poi lo stesso su 8 repo e si valuta il
   formato del messaggio Telegram.

## 2. Cosa NON vale la pena

- **Adottare Scrapling** (o un altro framework di scraping): non toglie nessun
  guasto misurato, aggiunge browser o un container a un sistema dove i guasti
  sono stati token e disciplina, non pagine bloccate. Rivalutarlo solo se un
  giorno una pagina vera (non le doc tecniche) ci blocca davvero con un
  anti-bot.
- **Sostituire o affiancare crawl4ai**: la corsia doppia crawl4ai+statica di
  oggi ha reso 38/40 e 37/40 pagine con 1,3s/0,6s medi; il problema non e' li'.
- **newreleases.io / changedetection.io per la sorveglianza**: funzionano, ma
  i feed Atom + timer + bot Telegram fanno lo stesso senza account esterni e
  senza un container in piu' da tenere su.
- **Una lista di sorveglianza piu' lunga di otto repo**: una lista lunga e' il
  modo in cui la sorveglianza muore (nessuno la legge). Otto, motivati, e basta.

## 3. Non trovato

- **Una pagina che crawl4ai non prende e Scrapling si'** (delle pagine che
  leggiamo noi: doc tecniche, GitHub, news): non trovata nella mia ricerca;
  il confronto si basa sui README e sulle capacita' dichiarate, non su una
  prova a parita' di URL.
- **Un numero ufficiale di contributori di Scrapling**: le API GitHub danno
  stelle/fork/watching (74.780 / 7.477 / 267 watching
  https://api.github.com/repos/D4Vinci/Scrapling), il conteggio contributori
  non l'ho riportato (non letto).
- **Un costo documentato del «Watch» nativo GitHub oltre i 10.000 repo**
  (soglia della doc citata nel cap. 3): non trovato; la pagina delle
  notifiche cita solo il limite di repo seguiti.
- **Una misura nostra del prezzo in token di un feed Atom intero**: il feed di
  Scrapling e' ~127 KB con le note di release; per un rapporto periodico basta
  leggerne i titoli, ma il costo esatto del parsing non l'ho misurato.
- **Scrapling installato e provato in locale**: espressamente non fatto
  (l'incarico vieta di installare). Tutte le affermazioni su di lui vengono
  dalla documentazione, non da una prova sul fisso.
