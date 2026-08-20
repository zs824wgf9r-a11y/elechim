# Ronda — revisione del codice, 20 agosto 2026

Ruolo: revisore, non muratore. Nessun file di codice è stato modificato.
I rilievi sono ordinati per gravità: in cima i difetti che possono produrre
un risultato sbagliato o un guasto silenzioso, poi efficienza, semplificazione,
upgrade, e infine le cose che sembrano difetti ma non lo sono.

Ho letto tutto il Python elencato nel perimetro (`documenti.py`, `sbobina.py`,
`guardiano.py`, `energia.py`, `estrazione_deterministica.py`, `strumenti.py`,
`gateway.py`, `lavoro.py`, `fusione.py`, `visione.py`, `web.py`, `voce.py`,
`sospendi.py`, `verifica_avvio.py`, `misura_attribuzioni.py`, i `prova_*.py`,
`mac/`) e le unit in `unita/`.

Non ho eseguito i collaudi: richiedono servizi attivi (ollama, searxng,
crawl4ai), GPU e fixture PDF. I rilievi derivano dalla lettura del codice.

---

## Difetti

### `documenti.py:236` — `figure_raster` perde figure quando `pdfimages -list` contiene righe non-image

**Cosa c'è che non va.** Il ciclo su `pdfimages -list` usa `idx` (indice della
riga nel list) per costruire il nome del file PNG estratto da `pdfimages -png`:
`img-{idx:03d}.png`. Però salta le righe il cui `tipo != "image"` (smask,
stencil, ecc.). Se tra due immagini "image" c'è una riga di altro tipo, `idx`
salta un numero mentre `pdfimages -png` numera i file PNG in ordine sequenziale
di estrazione. Il file cercato non esiste e la figura viene silenziosamente
scartata.

**Scenario di guasto.** Su un PDF con 3 immagini raster intervallate da
maschere alfa, `pdfimages -list` produce 6 righe ma il ciclo ne considera 3.
Per la terza immagine `idx=5` ma il file estratto è `img-002.png`, quindi
`src.exists()` è falso e la figura non finisce negli allegati.

**Correzione proposta.** Non usare l'indice della riga del list come nome del
file, oppure filtrare prima le righe e poi enumerare solo quelle estratte. La
corrispondenza più robusta è estrarre le immagini con `pdfimages -png` e poi
associare ogni PNG alla riga corrispondente confrontando dimensioni/pagina, o
semplicemente ignorare `pdfimages -list` e leggere i metadati dai PNG estratti.

---

### `energia.py:334` — `riserva_gpu` tronca il file del lock e cancella l'identità di chi occupa la GPU

**Cosa c'è che non va.** `f = open(GPU_LOCK, "w")` tronca il file prima che il
processo in attesa abbia preso il lock. Quindi, mentre aspetta, sovrascrive il
nome di chi tiene la GPU con un file vuoto. Il messaggio "GPU occupata da ..."
mostra sempre "altro processo" invece del nome/PID vero, rendendo
indistinguibile un'attesa normale da un blocco.

**Scenario di guasto.** Una sbobina parte mentre un'altra sessione tiene la GPU.
Il processo in attesa apre `GPU_LOCK` in scrittura, tronca il file, e il loop di
attesa legge un file vuoto. L'utente vede ripetutamente "GPU occupata da altro
processo" anche se il lock conteneva l'identità del processo che precede.

**Correzione proposta.** Aprire in append (`"a"`) prima del lock e troncare il
file **dopo** aver acquisito `flock`, come già annotato in `DA-FARE.md`
sezione 7-octies.

---

### `gateway.py:55-66` — `carica_env` fa crashare `gateway.py` all'importazione se manca `.env`

**Cosa c'è che non va.** `gateway.py` legge `.env` al top-level e usa subito
`ENV['TELEGRAM_TOKEN']`. Se il file `.env` manca o non contiene la chiave,
l'importazione del modulo fallisce con `FileNotFoundError` o `KeyError`. Questo
blocca anche operazioni che non usano Telegram (es. `/ping`, `/salute`).

**Scenario di guasto.** Su una nuova installazione o worktree senza `.env`,
`verifica_avvio.py` importa `gateway` per leggere `SFRATTO_WHISPER` e muore prima
di poter segnalare qualsiasi cosa. Anche `python -c "import gateway"` fallisce.

**Correzione proposta.** Rendere `carica_env` tollerante: se `.env` manca
restituisce dict vuoto, e le variabili obbligatorie vengono controllate solo
nelle funzioni che le usano (con messaggio chiaro). Per `SFRATTO_WHISPER` basta
un default in `verifica_avvio.py` invece di importare `gateway` solo per quello.

---

### `mac/core.py:32-44` — `carica_env` fa crashare il bot e la CLI all'importazione se manca `.env`

**Cosa c'è che non va.** Stesso difetto di `gateway.py`: `mac/core.py` legge
`.env` al top-level. Se il file manca, `Conversazione` non si può istanziare e
`bot.py`/`cli.py` non partono.

**Scenario di guasto.** Un clone pulito del repo sul Mac, prima di creare
`mac/.env`, non può nemmeno avviare `python mac/cli.py --help`.

**Correzione proposta.** Come sopra: leggere `.env` in modo tollerante e
controllare le chiavi obbligatorie solo nei punti d'uso, con messaggi espliciti.

---

### `web.py:46-56` — `_leggi_token` fa crashare `strumenti.py` all'importazione se manca `crawl4ai.env`

**Cosa c'è che non va.** `_leggi_token` legge `crawl4ai.env` senza gestire
`FileNotFoundError`. Se il token non è in env e il file non esiste, l'import di
`strumenti.py` (che importa `web.py`) fallisce. Di nuovo, anche operazioni che
non usano crawl4ai (es. la ricerca statica) diventano impossibili.

**Scenario di guasto.** Su una macchina senza crawl4ai configurato, `python -c
"import strumenti"` muore invece di permettere almeno il fallback `requests`+
`trafilatura`.

**Correzione proposta.** Catturare `FileNotFoundError` e ritornare stringa vuota
(o lanciare un errore solo quando `web._richiesta` viene effettivamente usata).

---

### `documenti.py:1196-1202` — `_note_del_documento` può perdere note con frontmatter lungo

**Cosa c'è che non va.** Per trovare le note di un documento, la funzione legge
i primi 400 caratteri di ogni nota e cerca `documento: "[[{nome}]]"`. Se il
frontmatter è più lungo di 400 caratteri (per esempio molti alias o campi
aggiuntivi), la stringa cercata cade oltre il pezzo letto e la nota non viene
riconosciuta come appartenente al documento.

**Scenario di guasto.** Un utente aggiunge 30 alias a una nota. `pulisci_vault`
e `_wikilink_risolti` perdono quella nota: restano orfani nel vault e il
rapporto segna wikilink non risolti che in realtà lo sono.

**Correzione proposta.** Leggere solo fino alla fine del frontmatter (la seconda
riga `---`) invece di un numero fisso di caratteri, oppure usare un parser YAML
minimale.

---

### `verifica_avvio.py:89-92` — percorsi di rete hardcoded su `enp6s0`

**Cosa c'è che non va.** Il rapporto post-riavvio legge
`/sys/class/net/enp6s0/device/power/wakeup` e interroga `ip -4 -br addr show
enp6s0`. L'interfaccia `enp6s0` è il nome attuale, ma `AGENTS.md` avvisa che il
montaggio/smontaggio della GTX 1050 ha già rinumerato i bus e cambiato nome
all'interfaccia una volta. Se il nome cambia di nuovo, il rapporto dice
"interfaccia assente!" anche se la scheda e il Wake-on-LAN funzionano.

**Scenario di guasto.** Dopo aver tolto la GTX 1050, l'interfaccia col Mac
passa da `enp6s0` a un altro nome. Il rapporto di avvio segnala
"interfaccia assente!" e l'IP non torna, anche se il collegamento fisico c'è.

**Correzione proposta.** Risolvere l'interfaccia dal MAC address della scheda
che collega il Mac (come già fatto per la connessione di NetworkManager), o
almeno elencare tutte le interfacce e segnalare quella con il link up.

---

### `unita/elechim-gateway.service:3` — dipendenza da `ollama.service` che non esiste

**Cosa c'è che non va.** La unit dichiara `After=... ollama.service` e
`Wants=... ollama.service`. `AGENTS.md` dice esplicitamente che "ollama non è un
servizio systemd". systemd ignorerà probabilmente la dipendenza inesistente, ma
è una contraddizione documentata: la unit assume un servizio che il progetto
sceglie di non avere.

**Scenario di guasto.** Su una nuova installazione, `systemctl --user daemon-reload`
potrebbe segnalare un warning per l'unit inesistente, o peggio ritardare
l'avvio del gateway in attesa di `ollama.service` che non arriverà mai.

**Correzione proposta.** Rimuovere `ollama.service` dalle dipendenze del gateway
(e dal commento che lo giustifica). Il gateway deve partire anche se ollama è
avviato manualmente o in modo diverso, e rispondere "strumento non disponibile"
se non c'è.

---

### `documenti.py:295-298` — `figure_vettoriali` non distingue crash con output valido da crash con output corrotto

**Cosa c'è che non va.** Il difetto latente di `DA-FARE.md` sezione 9 è noto:
`pdftocairo -svg` aborta su ~15% delle pagine ma l'SVG spesso è completo. Il
codice conta il crash nelle statistiche ma, se il file esiste, lo legge
comunque. Tuttavia non verifica che l'SVG sia ben formato prima di contare gli
elementi: `_conta_elementi_vettoriali` ritorna 0 su XML malformato, e la pagina
viene classificata come "senza figure vettoriali" anche se in realtà ne aveva.

**Scenario di guasto.** Su una pagina con molti elementi vettoriali, cairo
aborta e lascia un SVG troncato. `_conta_elementi_vettoriali` restituisce 0,
quella pagina non viene considerata figura, e il grafico non viene reso.

**Corretto proposta.** Dopo un exit code != 0, verificare esplicitamente che il
file termini con `</svg>` prima di contare; se non è ben formato, segnalarlo
come crash con output inutilizzabile (distinto da "crash ma output valido").

---

### `mac/risveglio.py:36` — il timer del magic packet è per-processo, non globale

**Cosa c'è che non va.** `_ultimo_invio` è una variabile globale del modulo, in
memoria. `bot.py` e `cli.py` sono processi separati sul Mac, quindi ognuno ha il
proprio timer. Inoltre, se uno dei due processi si riavvia, `_ultimo_invio`
ritorna a 0. Questo consente invii ravvicinati oltre la soglia di 120 secondi.

**Scenario di guasto.** Il proprietario usa sia Telegram sia CLI: due processi
possono mandare magic packet a distanza di pochi secondi, riempiendo il log e
stressando inutilmente la scheda di rete. Non è grave, ma è la stessa forma del
problema che il timer dovrebbe risolvere.

**Correzione proposta.** Salvare `_ultimo_invio` in un file in `stato/` (come
fa già `energia` per i blocchi), così il timer è condiviso tra tutti i processi
e sopravvive ai riavvii.

---

### `documenti.py:806` — `genera_markdown` rilegge l'intero markdown solo per contare le pagine

**Cosa c'è che non va.** Dopo il loop di scrittura, la funzione fa
`md.read_text(encoding="utf-8")` e cerca le ancore con una regex, solo per
restituire `max(letto)`. Su `dsml.md` (1,4 MB) questa è un'operazione O(n)
inecessaria: il loop sa già qual è l'ultima pagina scritta.

**Scenario di guasto.** Su un libro grosso, l'ultima operazione del
`genera_markdown` rilegge l'intero file da 1,4 MB. Moltiplicata dalle
interruzioni/ripetizioni, è I/O puramente sprecato.

**Correzione proposta.** Tenere una variabile `ultima_scritta` durante il loop e
restituirla, evitando la seconda lettura.

---

### `sbobina.py:227-236` e `sbobina.py:773-776` — `_fonte` e `rapporto_dati` rileggono l'integrale per ogni sezione

**Cosa c'è che non va.** `_fonte` legge l'intero file markdown (`dsml.md`, 1,4
MB) per ogni sezione. Viene chiamato una volta in `processa_sezione` e di nuovo
in `rapporto_dati` per ogni sezione. Su 214 sezioni sono centinaia di letture di
un file grosso.

**Scenario di guasto.** Una sbobina completa di `dsml` legge più volte lo
stesso file di 1,4 MB. L'OS probabilmente lo mette in cache, ma è I/O e parsing
ripetuto che si poteva evitare.

**Correzione proposta.** Caricare il markdown una sola volta in `lavora` e
passarlo alle funzioni che ne hanno bisogno, oppure usare seek su un file
aperto per estrarre i pezzi senza rileggere tutto.

---

### `misura_attribuzioni.py:195-222` — `analizza_file` è codice morto

**Cosa c'è che non va.** La funzione `analizza_file` è definita ma mai chiamata
in `main()`. `main()` ha il proprio loop quasi identico. Il codice morto confonde
il lettore e potrebbe divergere dal loop attivo se qualcuno lo modifica.

**Scenario di guasto.** Uno sviluppatore corregge un bug in `main()` ma non in
`analizza_file`. La prossima persona che tenta di usare `analizza_file` trova
una versione obsoleta e produce misure sbagliate.

**Correzione proposta.** Eliminare `analizza_file` oppure farla usare da `main()`
per evitare la duplicazione.

---

## Semplificazione e riuso

### `prova_estrazione.py`, `prova_estrazione_lingua.py`, `prova_estrazione_filtro_user.py` — codice massivamente duplicato

**Cosa c'è che non va.** I tre script sono copia-incolla: stesse funzioni di
classifica lingua, caricamento messaggi, chiamata ollama, scrittura output,
aggregati. Anche `estrazione_deterministica.py` e `misura_attribuzioni.py`
ripetono `carica_messaggi` e logica di parsing simile.

**Scenario di guasto.** Una correzione al criterio di lingua va fatta in tre
posti; se si dimentica uno, le misure non sono confrontabili. Già ora i tre
script condividono lo stesso set di parole italiane/inglesi, ma ognuno ha la sua
copia.

**Correzione proposta.** Estrarre in un modulo condiviso (`misura/estrattore.py`
o simile) le funzioni comuni: `carica_messaggi`, `classifica_lingua`,
`formatta_messaggi`, `chiama_ollama`, aggregazione. I tre script diventano
wrapper che cambiano solo il prompt e il nome della cartella di output.

---

### `documenti.py:1176` e `sbobina.py:537` — `_escapa` duplicata

**Cosa c'è che non va.** La stessa funzione (escape delle doppie quadre per
Evitare wikilink finti nella notazione matematica) è copiata in due moduli.

**Scenario di guasto.** Se si decide di cambiare la regola di escape (per
eccesso, es. anche le parentesi graffe), si rischia di aggiornare solo uno dei
due posti e ottenere note incoerenti.

**Correzione proposta.** Spostare `_escapa` in un modulo condiviso (per esempio
in `documenti.py` e importarla da `sbobina.py`), o in un piccolo `ossidian.py`.

---

### `documenti.py:349-375` e `sbobina.py:611-647` — `gpu_delle_figure` e `gpu_della_sbobina` sono quasi identici

**Cosa c'è che non va.** Entrambe le funzioni fanno: riserva GPU, controlla
`in_gioco()`, libera VRAM se necessario, yield, scarica il modello, e se ha
liberato lui ricarica i modelli. La logica è duplicata.

**Scenario di guasto.** Una correzione nel teardown (per esempio l'ordine di
rimozione della bandiera e ricarica) va fatta in due posti.

**Correzione proposta.** Una funzione factory o un contextmanager generico in
`energia.py` che accetta il nome del modello e il flag "ricarica alla fine".

---

## Upgrade

### `requirements.txt` — `requests==2.34.2` ha avvisi di sicurezza noti

**Cosa c'è che non va.** `requests` 2.34.2 è una versione vecchia con
vulnerabilità note (CVE per l'invio di cookie tra domini, e problemi di parsing
URL). Il progetto usa `requests` per tutte le chiamate HTTP/Telegram/ollama.

**Scenario di guasto.** A parte il rischio di sicurezza, versioni vecchie di
`requests` possono avere bug di timeout o di connessione che si manifestano in
produzione.

**Correzione proposta.** Aggiornare a `requests>=2.32.0` (o alla più recente
testata in locale) e rieseguire i collaudi che fanno chiamate HTTP.

---

## Collaudi deboli (veri per costruzione o quasi)

Questa sezione risponde al punto **1-quater** di `DA-FARE.md`. Ho cercato
asserzioni che non possano fallire anche col codice rotto. Ne ho trovate poche
nel senso stretto; quelle che seguono sono le più deboli.

### `prova_sbobina.py:327-349` — `assert_budget_derivato`

**Cosa c'è che non va (come collaudo).** `assert grande > piccolo * 3` è vero
per costruzione dato che `budget_caratteri` è una funzione lineare di `num_ctx`
e il rapporto tra 32768 e 8192 (meno le costanti) è >3. L'asserzione non
esercita il vincolo reale: che il budget stia entro `num_ctx`.

**Cosa nasconde.** Se qualcuno cambiasse `budget_caratteri` in modo che non
dipenda più da `num_ctx` ma resti >1000 (es. `return 1500`), il test
`grande > piccolo * 3` passerebbe ancora, ma il contesto traboccherebbe.

**Correzione proposta.** Il test fa anche `assert token < 8192` e
`assert token_peggiore <= 8192`, che sono più utili. Rinforzare quelle due
asserzioni e rendere `grande > piccolo * 3` più stringente (per esempio
verificare che il rapporto sia entro un intervallo atteso, non solo >3).

---

### `prova_fusione.py:93-99` — `test_k_smorza_le_prime_posizioni`

**Cosa c'è che non va (come collaudo).** `assert abs(p0["a"] / p0["b"] - 2.0) < 1e-9`
è un'identità matematica con k=0 e due elementi. Non può fallire se `rrf`
calcola `1/(k+1)` e `1/(k+2)`.

**Cosa nasconde.** Se `rrf` invertisse accidentalmente il denominatore o usasse
un'operazione sbagliata che restituisse comunque 1 e 0.5, il test passerebbe.

**Correzione proposta.** Aggiungere un caso con tre o più elementi dove il
rapporto non è un'identità scontata, oppure verificare anche la somma dei
punteggi.

---

### `prova_documenti.py:290-308` — `pulisci_vault` cancella le fixture versionate

**Cosa c'è che non va.** Questo non è un assert ma un comportamento del
collaudo: `pulisci_vault` cancella i PDF sintetici in `documenti/elaborati/`.
`DA-FARE.md` sezione 9 lo segnala già come difetto latente. Lo confermo: dopo
`python prova_documenti.py`, `git status` mostra `prova-due-colonne.pdf` e
`prova-outline.pdf` come cancellati.

**Scenario di guasto.** Ogni esecuzione del collaudo richiede `git checkout --`
sulle fixture, altrimenti il prossimo run parte con file mancanti o il repo ha
modifiche spurie.

**Correzione proposta.** Come già scritto in `DA-FARE.md`: mettere le fixture
sintetiche in `.gitignore` oppure farle rigenerare ogni volta in una cartella
temporanea senza toccare i file versionati.

---

## Sembra un difetto e non lo è

### `mac/strumenti.py:134-170` — `DEFINIZIONI` duplicata rispetto a `strumenti.py`

È voluto e documentato: la cache del prompt sul Mac richiede che le definizioni
dei tool siano identiche byte per byte. Non si tocca.

### `documenti.py:1522` — `StartLimitIntervalSec=0` nella unit

Sembra una resa, ma è la soluzione corretta per un servizio `oneshot` innescato
da un path unit che sorveglia la cartella che il servizio stesso svuota. Il
commento nella unit lo spiega.

### `documenti.py:1076-1077` — `genera_note` cancella le note atomiche precedenti

Sembra un rischio di perdita dati, ma è coerente con il design: le note
atomiche di `30-Note/` prodotte dalla pipeline sono di proprietà della pipeline.
Se il proprietario le ha modificate, quelle modifiche vengono sovrascritte — è
noto.

### `documenti.py:295-298` — `figure_vettoriali` ignora l'exit code 134 di pdftocairo

Sembra un guasto ignorato, ma è voluto: spesso l'SVG è completo nonostante il
crash di cairo. Il codice non alza eccezione; conta il crash nelle statistiche
e continua. Il punto debole è che non distingue output valido da invalido (vedi
sezione Difetti).

### `energia.py:316-317` — `in_gioco()` è solo una bandiera

Sembra un lock insufficiente, ma è complementare al vero `flock` di
`riserva_gpu`. La bandiera serve a comunicare al gateway (che gira in un altro
processo) che la GPU è riservata al gioco; il mutex vero è `flock`. L'unico bug
nella bandiera è il troncamento del file lock (sezione Difetti).

---

## Difetti latenti di `DA-FARE.md` sezione 9 — conferme

- **Lavori lunghi lanciati a mano non prendono `energia.blocco`.** Confermo.
  `documenti.py` e `sbobina.py` lo fanno, ma `opencode run`, `agy` e script
  generici no. Non ho trovato un wrapper generico.
- **Fixture sintetiche versionate cancellate dal collaudo.** Confermo, vedi
  sopra.
- **`pdftocairo -svg` aborta su ~15% delle pagine.** Confermo che il codice lo
  gestisce, ma non distingue output valido da invalido.
- **Lock GPU bandiera vs mutex.** Confermo parzialmente: `riserva_gpu` è un
  mutex, ma `in_gioco()` è una bandiera. Il difetto vero è il troncamento del
  file lock.
- **957 MB di core dump.** Non è un difetto del codice Python; è un problema di
  pulizia del sistema.

---

## Cosa non ho guardato

- Non ho eseguito i collaudi né verificato che siano verdi in questo momento.
- Non ho letto `INCARICO-*.md`, `RAPPORTO-*.md`, `PIANO-DOCUMENTI.md` oltre a
  `AGENTS.md` e `DA-FARE.md`.
- Non ho analizzato in dettaglio i file di configurazione di opencode/gy/mcp.
- Non ho verificato il contenuto di `.env`, `.env.example` o `crawl4ai.env`.

## Quanto mi fido di questa ronda

Medio-alto sui difetti strutturali (importazioni che crashano, hardcoded,
duplicazioni, lock troncato): sono evidenti dalla lettura. Medio sulla
correttezza di algoritmi più complessi (accoppiamento apici/pedici, chunking,
figure vettoriali): qui servirebbe eseguire i collaudi e qualche caso limite
sintetico per essere sicuro. Ho evitato di segnalare plausibili senza uno
scenario concreto.
