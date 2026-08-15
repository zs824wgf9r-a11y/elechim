# Incarico: rendere il progetto usabile da terzi

> **CONSEGNATO il 15 agosto 2026.** Il repo e' pubblico su
> `github.com/zs824wgf9r-a11y/elechim`, i `.example` ci sono tutti e il README
> ha la sezione Installazione. **Strascico**: la depersonalizzazione ha toccato
> anche file che girano — vedi "La trappola della depersonalizzazione" in
> `AGENTS.md`. Restava fuori scopo git, e infatti il commit l'ha fatto Claude.

Scritto il 15 agosto 2026. Leggi prima `AGENTS.md`.

Il proprietario vuole pubblicare Elechim su GitHub come repo pubblico, **perche' chiunque
possa usarlo**. Il repo e' gia' inizializzato e il `.gitignore` e' gia' scritto e
verificato: segreti, conversazioni, memoria e documenti di terzi sono fuori.

**Quello che manca e' il divario fra "il codice c'e'" e "un estraneo riesce ad
avviarlo".** Oggi chi clona il repo trova moduli che leggono variabili
d'ambiente di cui non conosce ne' i nomi ne' il formato, e due file di
configurazione con dentro i percorsi della macchina del proprietario.

## L'esplorazione e' gia' fatta: questi sono i fatti, scrivi e basta

Un primo tentativo del 15 agosto e' fallito **esplorando invece di consegnare**:
ha letto `pip list`, unit systemd e container, ha sbattuto su un permesso
negato, ed e' finito senza scrivere un solo file. Vale qui la regola gia'
scritta in `INCARICO-qualsiasi-documento.md`: *le sessioni che hanno consegnato
sono quelle che hanno scritto per prime.* **Scrivi il primo file entro il primo
minuto.**

Non ti serve leggere niente fuori da `~/assistente`. Ecco tutto:

**Dipendenze di terze parti** (ricavate dagli import veri, il resto e' stdlib o
moduli locali) — versioni installate e funzionanti:

    faster-whisper==1.2.1
    pypdf==6.16.1
    requests==2.34.2
    trafilatura==2.2.0

**Chiavi di configurazione**, coi rispettivi file (valori mai letti):

- `.env` (fisso): `TELEGRAM_TOKEN`, `MAC_BASE_URL`, `MAC_MODEL`,
  `TELEGRAM_ALLOWED_IDS`, `STATO_DB`
- `mac/.env` (Mac mini): le stesse cinque piu' `GATEWAY_URL`; il commento dice
  «Il modello gira su QUESTA macchina: nessun tunnel di mezzo»
- `crawl4ai.env`: `CRAWL4AI_API_TOKEN`, `SECRET_KEY`
- `searxng/settings.yml`: `server.secret_key`, piu' `image_proxy`, i formati
  `html`/`json` e i motori (`startpage` disabilitato, `mojeek` e `qwant` attivi)

**Variabili opzionali con default nel codice**: `OLLAMA_VLM` (`qwen3-vl:4b`),
`WHISPER_MODELLO` (`large-v3`), `WHISPER_QUANT` (`int8_float16`),
`CRAWL4AI_URL` (`http://127.0.0.1:11235`), `SFRATTO_WHISPER` (`600`).

**Servizi**: unit utente `elechim-gateway`, `crawl4ai`, `searxng`, `ollama`.
crawl4ai e searxng sono quadlet podman su loopback (`127.0.0.1:11235` e
`127.0.0.1:8888`); il gateway ascolta su `127.0.0.1:8090`. Python 3.12.

## Regola che viene prima di tutto

**Non leggere, non stampare, non copiare i valori dentro `.env`,
`.env.bak-20260812`, `mac/.env`, `crawl4ai.env` e `searxng/settings.yml.**

Sono token veri: Telegram, crawl4ai, la secret key di SearXNG. Ti servono **i
nomi delle chiavi e il loro significato**, che ricavi dai commenti dei file e
soprattutto da come il codice le consuma (`os.environ.get`, `_leggi_token` in
`web.py`, `ENV[...]` in `gateway.py`). Il valore non ti serve mai: negli esempi
ci va un segnaposto.

Se sbagli qui, il segreto finisce in un file versionato e su un repo pubblico non
si ritira piu'. E' lo stesso principio dell'articolo 5 di `AGENTS.md`.

## 1. I file di esempio

Crea, accanto agli originali e **versionabili**:

- `.env.example` — le chiavi del fisso
- `mac/.env.example` — le chiavi del Mac mini
- `crawl4ai.env.example`
- `searxng/settings.yml.example`

Per ogni chiave: il nome esatto, un segnaposto che si capisca
(`TELEGRAM_TOKEN=inserisci-qui-il-token-di-@BotFather`), e **una riga che dice a
cosa serve e dove si ottiene**. I commenti che spiegano i guasti gia' pagati —
tipo quello in `crawl4ai.env` sul server che si lega a 127.0.0.1 dentro il
container — vanno conservati: sono la parte piu' utile del file.

## 2. I due file cuciti sulla macchina

- `mac/com.elechim.assistente.plist`: cinque percorsi `/Users/NOME_UTENTE/...`,
  piu' `UserName` e il `Label`. Mettici segnaposto evidenti e
  scrivi **nel commento in testa** che vanno sostituiti prima di installarlo in
  `/Library/LaunchDaemons`. Il commento che spiega perche' e' un LaunchDaemon e
  non un LaunchAgent **resta**: e' esattamente il tipo di sapere che vale.
- `opencode.json`: la riga `/home/NOME_UTENTE/.config/containers/systemd/*`.

## 3. La sezione di installazione nel README

In coda al `README.md`, una sezione **"Installazione"** che porti un estraneo da
zero a un bot che risponde. Deve coprire, nell'ordine in cui servono:

1. i prerequisiti reali, con le versioni che sai essere quelle giuste (Python,
   ollama, podman per crawl4ai, ffmpeg se serve alle voci);
2. `python -m venv .venv` e le dipendenze — **ricavale dagli import veri**, non
   inventarle, e se non esiste un `requirements.txt` scrivilo;
3. copiare i `.example` e riempirli;
4. `ollama pull qwen3-vl:4b`;
5. l'avvio: i servizi systemd utente che esistono gia' (`elechim-gateway`,
   `crawl4ai`, `searxng`) e come si lancia a mano per provare;
6. **come verificare che funziona**: `verifica_avvio.py` esiste gia', dillo.

Sii onesto su cosa **non** funziona ancora: la duplicazione delle pagine di
`INCARICO-qualsiasi-documento.md` e' un difetto aperto, le scansioni senza
livello di testo non sono supportate. Un README che promette piu' del vero fa
perdere tempo a chi ci prova.

## Fuori scopo

- **Non toccare git**: niente `git add`, `commit`, `push`, `remote`. Il repo lo
  pubblica Claude con l'account del proprietario. Tu scrivi solo i file.
- Non toccare `DEFINIZIONI` in `strumenti.py` (impronta `1160ec454b8b9998`).
- Non rinominare moduli ne' riorganizzare cartelle: il repo pubblico deve restare
  lo stesso progetto, non una riscrittura.
- Non risolvere la duplicazione: e' un altro incarico, qui va solo documentata.

## Alla fine

Elenca i file creati e modificati, e **dichiara esplicitamente che nessun valore
di segreto e' stato copiato in un file versionabile**.
