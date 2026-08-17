# Incarico: lavorare in simbiosi con opencode, non a colpi di `opencode run`

Scritto il 17 agosto 2026, dopo che **tre sessioni in parallelo si sono piantate
per 5h57m** e hanno perso le conclusioni. Ricerca sul web: **non tocchi codice**,
produci un solo file, `RICERCA-simbiosi.md`.

Chiesto dal proprietario: *«Trova un modo per lavorare in simbiosi con opencode.
Probabilmente sul web qualcosa c'e' gia'.»* Ha ragione: qualcosa c'e', e sotto ti
dico da dove partire.

## Come lavoriamo oggi, e perche' non va

Claude scrive un `INCARICO-*.md`, poi lancia `opencode run -m <modello> "<prompt>"`
in background con un `timeout` esterno, e poi **guarda un file di log** per capire
se sta lavorando. E' fuoco-e-dimentica, e oggi ha prodotto questi guasti, tutti
misurati:

| guasto | misura |
|---|---|
| stallo su `epoll` senza timeout proprio | 3 sessioni ferme **5h57m**, CPU 0,1%, TCP `ESTAB` con code a zero |
| `timeout` non uccide | `timeout 3600` manda **SIGTERM**, opencode lo intercetta e si blocca uscendo; serviva `-k 60` |
| l'exit code mente | `opencode run` esce **0** anche quando non ha fatto niente (endpoint giu') |
| il cwd non si eredita | ha cercato l'incarico in `$HOME` invece che nel repo |
| le conclusioni si perdono | il codice era sul disco e **verde**, il rapporto no: e' l'ultima cosa che scrive |
| non vedo cosa sta facendo | solo `tail` su un log, nessun evento |
| non posso intervenire | ne' correggere, ne' chiedere «scrivi il rapporto adesso», ne' fermare |

**La domanda a cui devi rispondere**: esiste un modo *supportato* di pilotare
opencode in modo che chi lo lancia **veda gli eventi mentre accadono** e possa
**intervenire**, invece di leggere un log a posteriori?

## Da dove partire: la pista c'e' gia'

Ho gia' visto — verifica e approfondisci, non ripartire da zero:

- **`opencode serve`**: modalita' server headless, porta di default **4096**,
  hostname `127.0.0.1`, spec **OpenAPI 3.1** su `/doc`, password via
  `OPENCODE_SERVER_PASSWORD`. https://opencode.ai/docs/server/
- **`@opencode-ai/sdk`**: client TS/JS tipizzato; `createOpencode()` avvia server
  e client, `createOpencodeClient()` si attacca a un'istanza gia' viva.
  https://opencode.ai/docs/sdk/
- **Endpoint gia' visti**: `POST /session`, `GET /session`, `GET /session/:id`,
  `DELETE /session/:id`, `POST /session/:id/message` (aspetta la risposta),
  `POST /session/:id/prompt_async` (non aspetta), `GET /session/:id/message`.
- **Due stream SSE**: `GET /event` e `GET /global/event`, il primo evento e'
  `server.connected`.

## Le domande precise, in ordine di quanto ci servono

### 1. Gli eventi bastano a fare da guardiano? (la piu' importante)

Lo stallo si riconosce **solo** dall'orologio del log. Con `GET /event`:

- **quali tipi di evento** esistono davvero? Elencali coi nomi esatti dallo
  schema OpenAPI o dal codice, non a intuito.
- c'e' un evento per **ogni chiamata a strumento** (lettura file, scrittura, bash)?
- c'e' un evento di **inattivita' / sessione idle / fine turno**, che permetta di
  dire «sono passati N minuti senza un evento, e' piantata»?
- c'e' un evento di **errore** distinguibile da un turno finito bene?

### 2. Si puo' fermare o correggere una sessione viva?

- esiste un endpoint di **abort/interrupt** del turno in corso?
- si puo' **mandare un messaggio a una sessione gia' avviata** e farla
  correggere il tiro (es. «lascia stare X, un'altra sessione ci lavora»)?
- si puo' **riprendere** una sessione interrotta col suo contesto? (`--continue`,
  `--session`, o via API)

### 3. C'e' un client Python, o solo TS/JS?

Elechim e' tutto in **Python**, e non vogliamo Node nel giro se si puo' evitare.
Se l'SDK e' solo TS, l'API HTTP e' comunque parlabile con `requests` e la SSE con
una lettura a righe: **verifica che sia una REST normale** e non qualcosa che
richiede per forza l'SDK. Se esiste un client Python di terze parti, dimmi
licenza e se e' vivo.

### 4. Timeout e robustezza: si configurano da dentro?

- opencode ha una **configurazione di timeout** per le chiamate al modello
  (`opencode.json` o variabili d'ambiente)? Se si', il nostro `timeout` esterno
  diventa una seconda rete, non l'unica.
- e' un **problema noto** che il processo resti su `epoll` con l'endpoint morto?
  Cerca fra le issue del repo: se e' noto, c'e' una versione che lo corregge o una
  configurazione che lo evita?
- opencode intercetta **SIGTERM**? (noi abbiamo dovuto usare `SIGKILL`)

### 5. Guardrail: si possono imporre i confini invece di chiederli

Oggi i confini («non toccare `sbobina.py`») sono **frasi in un prompt**, e reggono
solo se il modello obbedisce. Esiste un modo *meccanico*?

- **permission system**: `opencode.json` ha gia' una sezione `permission` (noi la
  usiamo per `external_directory`). Si possono negare **scritture su file
  specifici**? Documenta la forma esatta.
- **plugin / hook**: opencode ha plugin? Si puo' agganciare un hook che rifiuta
  una scrittura fuori da una lista? Nomi di file, cartelle, API.
- **agent / subagent** definiti in configurazione, con strumenti ristretti.

### 6. Esiste gia' chi ha fatto questo lavoro?

- qualcuno ha scritto un **orchestratore** che lancia piu' sessioni opencode in
  parallelo, sorveglia gli eventi e le riavvia? Nome, URL, licenza, se e' vivo.
- come lo fanno gli ambienti che ci girano sopra (E2B e simili)?
- **cross-check onesto**: c'e' un modo *migliore* di opencode per questo uso, cioe'
  un agente da riga di comando pensato per essere pilotato da un altro programma?
  Non ci interessa cambiare strumento, ci interessa sapere se stiamo remando
  controcorrente.

## Cosa NON fare

- **Non toccare nessun file di codice**, nessun `INCARICO-*`, nessun `RAPPORTO-*`,
  non `AGENTS.md`, non `DA-FARE.md`, non `opencode.json`, non git.
  **L'unico file che scrivi e' `RICERCA-simbiosi.md`.**
- **Non installare niente**, nessun `npm install`, nessun clone, e **non avviare
  `opencode serve`**: qui si legge e si documenta. Se una cosa va provata, scrivila
  come raccomandazione con il comando esatto da lanciare.
- Non inventare endpoint, nomi di eventi, campi o opzioni. **Se non l'hai letto
  nella documentazione o nel codice, dillo.** Un endpoint plausibile e inesistente
  ci fa costruire un orchestratore che non parte.
- Niente dati personali nel rapporto.

## Come cercare

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235
```

Piu' `webfetch` per le pagine di cui hai gia' l'URL. Le fonti migliori sono, in
ordine: la **documentazione ufficiale** (opencode.ai/docs), la **spec OpenAPI**
(`/doc`, e c'e' anche pubblicata), il **codice sorgente** su GitHub, e le **issue**
per i problemi noti. I siti-copia della documentazione valgono meno dell'originale:
se trovi una cosa solo li', segnalalo.

## Come si scrive `RICERCA-simbiosi.md`

Un capitolo per ognuna delle sei domande, e in cima una **sintesi da dieci righe**
che risponda a una domanda sola: **si puo' passare da fuoco-e-dimentica a un
dialogo sorvegliato, si' o no, e con che pezzi?**

Chiudi con:

1. **La ricetta minima**: la sequenza esatta di chiamate per avviare una sessione,
   riceverne gli eventi, accorgersi che e' piantata e ucciderla. Comandi e
   endpoint veri, cosi' com'e' scritto nella documentazione.
2. **Cosa resta scoperto**: le cose che l'API non permette e che dovremo
   continuare a fare a mano.
3. Una sezione **«non trovato»**, che vale quanto il resto.

Scrivi il file **un capitolo alla volta mentre lavori**, non alla fine: oggi tre
sessioni si sono piantate e hanno perso proprio le conclusioni, che sono l'ultima
cosa che una sessione scrive. Non ripetere l'errore che stai studiando.
