# Elechim — contesto per chi lavora su questo progetto

Assistente personale del proprietario, raggiungibile da Telegram e CLI. Due macchine.
Questo file e' la memoria condivisa: contiene il contesto che e' costato
giornate di misure e che non si deduce leggendo il codice. Leggilo prima di
proporre modifiche.

Tutto il progetto e la documentazione interna sono in italiano. La vetrina
pubblica (`README.md`, `CONTRIBUTING.md`) e' in inglese per essere trovata.
Scrivi in italiano nella documentazione interna.

## Topologia — chi fa cosa

- **Mac mini M4 16GB, headless, `10.0.0.2`, sempre acceso a 7W.** Ci girano il
  modello (`gemma-4-26b-a4b-it` su TurboFieldfare, porta 8080) e il bot Telegram
  (`bot.py`, `core.py`, `stato.db`). Sorgenti versionati qui in `mac/`, si
  copiano con `./sincronizza.sh`. Due copie modificabili: se correggi da una
  parte e non sincronizzi, il bug resta vivo dall'altra.
- **PC fisso (questo, Fedora 44, RTX 4060 Ti 8GB, 62GB RAM), spegnibile.** Ci
  gira tutto il lavoro pesante: gateway strumenti (`gateway.py` su `127.0.0.1:8090`),
  ricerca (`strumenti.py` + SearXNG), vocali (`voce.py`, faster-whisper),
  immagini (`visione.py`, qwen3-vl:4b su ollama), energia (`energia.py`).
- **Un solo tunnel ssh**, avviato dal fisso: `-L 8080` (il fisso verso il
  modello) e `-R 8090` (il Mac verso il gateway). Il forward inverso lo apre il
  fisso di proposito: col fisso spento la porta non esiste e il Mac prende un
  rifiuto immediato invece di un timeout.
- **Il fisso dorme dopo tre ore di inattivita' e il Mac lo sveglia col magic
  packet.** Col fisso addormentato Elechim continua a rispondere, senza ricerca
  web, vocali e immagini.

## Stato al 15 agosto 2026, sera — verificato dopo un blackout

**Questa sezione mente appena si lavora. Chi la trova sbagliata la riscrive
prima di consegnare**: e' la fotografia da cui parte ogni altra sessione, e una
fotografia vecchia moltiplica gli errori invece di risparmiare tempo. Fino a
stasera diceva "fase 4 ❌, il vault e' vuoto" con 233 note gia' dentro.

- Fase 0 ambiente ✅ · 1 bot+loop ✅ · 2 gateway+ricerca web ✅ ·
  **3 Honcho+embedding ❌ · 4 documenti: corsia veloce ✅, resto ❌ · 5 Obsidian ✅ (per i documenti)**
- **La fase 4 corsia veloce e' in esercizio.** `documenti.py` porta un PDF con
  livello di testo dalla coda fino alle note, deterministico, senza LLM:
  `DSML.pdf` **533 pagine in 70s**, 223 voci di outline, `struttura: outline`.
  Nel vault ci sono **233 note** in `30-Note/` e 5 documenti in `20-Documenti/`.
- **Il repo e' pubblico**: `github.com/zs824wgf9r-a11y/elechim`, un commit,
  `.gitignore` verificato, i `.example` di ogni chiave, `README.it.md` con Installazione.
  Vedi la trappola della depersonalizzazione qui sotto.
- **crawl4ai e' attivo** (quadlet podman su `127.0.0.1:11235`), davanti alla
  corsia statica `requests`+`trafilatura` che resta come ripiego.
- Servizi attivi e verificati stasera dopo un riavvio da blackout, tutti risaliti
  da soli: `elechim-gateway` (`127.0.0.1:8090`), `macmini-tunnel`, `searxng`,
  `crawl4ai`, `syncthing`, `elechim-documenti.path`, il bot sul Mac via launchd.
- **ollama non e' un servizio systemd** e il binario non e' nel PATH di una shell
  non interattiva: risponde su `127.0.0.1:11434` e basta. C'e' **solo
  `qwen3-vl:4b`**; `bge-m3` non e' stato scaricato.
- Niente Postgres, niente Redis, niente pgvector: la fase 3 non e' iniziata.
- `40-Skills/`, `10-Ricerche/` e `90-Allegati/` sono **vuote**: le figure non
  vengono ancora estratte, e `50-Elaborazioni/` non esiste.
- Il venv e' `.venv`, **Python 3.12** creato con uv: **non ha `pip`**, si usa
  `uv pip install`. Il Python di sistema e' 3.14, troppo nuovo per lo stack ML.
  Non ci sono ne' `torch` ne' `marker`. 784GB liberi su `/home`.

### Riparato la sera del 15 agosto — `prova_documenti.py` e' TUTTO VERDE

- **La coda si fermava** per una corsa fra il servizio e il path unit che lo fa
  ripartire: ora c'e' `_coda_esclusiva()` (`flock` non bloccante, chi arriva
  secondo esce **0**) e `_scarta()` non presume piu' che il file sia in coda.
- **Le pagine duplicate nell'integrale erano lo stesso difetto**, non uno nuovo:
  due processi che scrivevano lo stesso markdown. Nessuna modifica a
  `genera_markdown`. Verificare contando le **occorrenze**, non i marcatori
  distinti — che tornano 11/11 e hanno gia' fatto dichiarare risolto il difetto
  due volte.
- **Tabelle**: aggiunta una densita' minima di cifre. Falsi positivi su
  `Basic_Statistics_2007.pdf` **da 42 a 13**.
- **Scansioni**: `classifica()` piu' rifiuto onesto sotto 100 caratteri/pagina di
  mediana, con la ragione scritta in `falliti/`. Il rapporto dichiara la corsia.

### Cosa manca adesso

- **La sbobina e' scritta ma non consegnata.** `sbobina.py` + `prova_sbobina.py`,
  collaudo **verde** sul sintetico: 6 sezioni su 6, `qwen3:8b` a 13 tok/s, 6.751
  MiB di VRAM, tabelle verbatim, numeri verificati, lock GPU rispettato.
  Mancano il confronto fra piu' modelli, una nota vera su `dsml` e
  `RAPPORTO-sbobina.md`. **Non lanciare le 214 sezioni** prima che il
  proprietario abbia letto una nota.
- **Le figure non vengono estratte**, `90-Allegati/` e' vuota.
- Le note atomiche nel vault sono ancora quelle vecchie, coi segnalibri.

### La trappola della depersonalizzazione — pagata il 15 agosto

Rendere il repo pubblico ha sostituito il nome proprio con "il proprietario" e i
path con `NOME_UTENTE` **anche dentro file che girano**, non solo nella prosa.
Due danni veri, trovati stasera:

- **`mac/core.py`**: il `SYSTEM_PROMPT` versionato diceva "assistente personale
  del proprietario", mentre il Mac in esercizio usava il nome vero.
  `./sincronizza.sh` avrebbe spinto la versione depersonalizzata sul Mac: prompt
  peggiore (il nome e' un dato che serve al modello) **e** prefisso del contesto
  cambiato, cioe' prefill pieno su tutte le conversazioni. Risolto leggendo
  `PROPRIETARIO` da `mac/.env`, che non e' versionato: col valore a posto il
  prompt torna byte per byte quello di prima e la cache non si accorge di nulla.
- **`opencode.json`**: `/home/NOME_UTENTE/.config/containers/systemd/*` non
  agganciava piu' nessun permesso reale. Risolto con `{env:HOME}`, che e'
  neutro e funziona ovunque.

**Regola**: un file eseguibile non si depersonalizza in place. O il dato si
legge da `.env`, o la copia pubblica e' distinta da quella che gira.

`DEFINIZIONI` invece e' **intatta e identica** fra `strumenti.py` e
`mac/strumenti.py`, verificato con confronto AST: due tool, `cerca` e `leggi`.

## Le sette regole, e perche'

Non sono preferenze: vengono dalle misure. Il Mac genera a ~21 tok/s e fa
prefill a ~23 tok/s, quindi **ogni token che gli arriva costa tempo reale** e la
cache del prompt e' l'unica cosa che rende l'assistente usabile (turno in cache
2-4s, turno a cache fredda minuti).

1. **4-6 tool grossolani, sempre identici.** Il gateway fa il fan-out sui veri
   server MCP. 40 tool = 2.600 token = +58s sul primo turno.
2. **Il fisso e' un compressore di contesto, non un esecutore di tool.** Una
   pagina web grezza sono ~2.000 token = un minuto di prefill sul Mac. Si
   comprime qui prima di mandarla.
3. **Il Mac maneggia handle, non contenuti.** Ricerche e documenti hanno un id;
   il testo integrale resta sul fisso (`strumenti.CACHE_PAGINE`).
4. **A scrivere le note su Obsidian e' il fisso**, non il Mac: una nota da 800
   token costerebbe 40s.
5. **Memoria iniettata solo all'apertura della sessione**, mai a meta'.
   Iniettare ricordi per turno cambia il prefisso del contesto e azzera la
   cache. Qui la cronologia lunga e' gratis e i ricordi freschi sono cari.
6. **Telegram e CLI condividono la stessa conversazione** — la cache del Mac ha
   una slot sola.
7. **Lavori lunghi asincroni** con notifica su Telegram.

## Regole non negoziabili — violarle rompe cose che non danno errore

- **`DEFINIZIONI` (le descrizioni dei tool) devono restare identiche byte per
  byte** nelle due copie, fisso e Mac. TurboFieldfare riusa la cache solo se
  `entry.tools == request.tools`: cambiare una virgola azzera il prefill
  dell'intera conversazione. Corollari:
  - Sotto un tool puoi cambiare tutto; la sua descrizione no.
  - **Col fisso spento i tool NON si tolgono dalla lista**: restano definiti ed
    e' l'esecutore a rispondere "il fisso e' spento".
  - I tool mancanti (documenti e memoria) vanno aggiunti **tutti insieme una
    volta sola**. Mai uno per fase. **L'elenco definitivo e' stato deciso il 15
    agosto 2026 ed e' in `TOOL-DEFINITIVI.md`**: quattro tool in tutto, `cerca`,
    `leggi`, `ricorda`, `salva`. Quel file contiene anche le descrizioni gia'
    scritte e la procedura per applicarle. **Non applicarlo di tua iniziativa**:
    si tocca `DEFINIZIONI` solo quando fase 3 e fase 4 sono entrambe pronte da
    collegare.
  - Le descrizioni dicono **cosa** fa un tool, non **quando** usarlo: le regole
    su quando chiamarlo vanno nel prompt di sistema, che viaggia una volta sola.
- **Il contenuto dei documenti e delle conversazioni non esce mai da queste due
  macchine.** Elechim e' tutto in locale per scelta: il modello sta sul Mac,
  l'estrazione, le note e il macinare i PDF li fa il fisso. I modelli in cloud
  che aiutano a *costruire* Elechim — opencode, Claude — sono **architetti e
  muratori**: vedono il codice, i log, le metriche e i messaggi di errore,
  **mai** il contenuto di un documento o di una conversazione del proprietario.
  - **La ricerca sul web si delega sempre a un modello gratuito**
    (`opencode run -m opencode/deepseek-v4-flash-free`), deciso dal proprietario
    il 17 agosto 2026 — anche per le ricerche piccole. E' lavoro voluminoso e a
    basso valore per turno: tante pagine lette per poche righe di conclusione.
    L'infrastruttura c'e' gia' sul fisso: **searxng** su `127.0.0.1:8888` e
    **crawl4ai** su `127.0.0.1:11235`, e vanno indicati nel prompt o il modello
    non sa di averli. Due regole obbligatorie in ogni incarico di ricerca: **ogni
    affermazione con un URL davvero aperto** (piu' licenza e ultimo commit), e
    **mai inventare** repository o costanti — un elenco plausibile e falso e'
    peggio di niente, perche' fa progettare su cose che non esistono. Le
    affermazioni portanti si **verificano a campione**: quella e' di Claude.
  - **La spartizione e' 70% opencode, 30% Claude**, deciso dal proprietario il
    17 agosto 2026. Il codice — implementazioni, refactoring, test nuovi,
    correzioni — lo scrive **opencode**. A Claude restano il disegno e i vincoli
    (gli `INCARICO-*.md`), le misure che decidono le soglie, la verifica di cio'
    che torna, l'integrazione fra piu' sessioni e questa memoria condivisa.
    E' un tetto, non un modo di dire: se Claude sta scrivendo piu' di un terzo
    di quello che si produce, la divisione e' sbagliata e si corregge subito,
    anche a lavoro iniziato. In dubbio su chi fa una cosa, la fa opencode.
  - Corollario pratico: la pipeline documenti si prova su un PDF **sintetico**,
    generato dal codice stesso con testo noto. Cosi' la verifica e'
    un'asserzione esatta invece di un giudizio a occhio, ed e' anche
    ingegneria migliore: un test che confronta con la verita' nota non dipende
    da chi lo guarda.
  - I documenti veri si provano **in locale**, e a leggere l'esito e' il proprietario.
    Un modello remoto puo' vedere i numeri del rapporto di copertura, non il
    testo che ci sta dietro.
- **Le tabelle non passano mai per un LLM.** Macro di un piano alimentare,
  numeri di uno schema: estratti verbatim. E' il punto in cui un 4B ti cambia un
  180 in un 150 e non te ne accorgi mai piu'.
- **Il Mac non vede mai un documento**, nemmeno a pezzi. 80 pagine sono 40-70K
  token contro 65.536 di contesto e 35-50 minuti di prefill. Vede una sintesi da
  ~300 token e un handle.
- **L'integrale e' la verita', le note sono l'indice.** Il markdown estratto
  resta in `markdown/`, fuori dal vault; le note su Obsidian ci puntano. Il
  modello non e' mai l'unica copia dell'informazione.
- **Rollback obbligatorio**: se la chiamata al Mac fallisce, il messaggio `user`
  va rimosso dallo storico, o restano due `user` di fila e la cache non aggancia
  mai piu' (fatto in `core.rispondi`).
- **La data nel prompt di sistema si congela alla prima chiamata**
  (`meta.prompt_sistema`) e si rinnova solo con `/nuova`. Ricalcolarla a ogni
  chiamata cambierebbe il prefisso a mezzanotte. Mesi scritti a mano: `%B`
  dipende dal locale, che sotto systemd non e' italiano.

## Trappole gia' pagate

**systemd**
- `BindsTo=` su una dipendenza che si riavvia ferma il servizio dipendente, e
  siccome e' uno stop ordinato **`Restart=always` non si applica**: resta giu'
  per sempre. Usa `Wants=` + `After=`. Vale per tutto cio' che pende dal tunnel.
- `OnUnitActiveSec` usa CLOCK_MONOTONIC, che **non avanza durante la
  sospensione**: dopo una dormita lunga il primo controllo puo' arrivare 10
  minuti dopo il risveglio. E' voluto, ma va saputo leggendo i log.
- Il risveglio si rileva confrontando CLOCK_MONOTONIC (si ferma dormendo) con
  CLOCK_BOOTTIME. Senza, il controllo trova il fisso "inattivo da tre ore" e lo
  rimanda subito a dormire.
- L'inerzia della scrivania si legge da **XScreenSaver via ctypes**: su X11+KDE
  l'`IdleHint` di logind non viene mai aggiornato, quindi `IdleAction=suspend`
  non funziona. `xprintidle` non e' pacchettizzato su Fedora 44, `libXss.so.1`
  si'. DISPLAY/XAUTHORITY si pescano da `/proc/<plasmashell>/environ`.
- Un servizio utente che sospende ha bisogno di una **regola polkit**: col
  linger non c'e' sessione "attiva" e la richiesta finisce appesa in `auth_admin`.

**nvidia**
- **Prima di aggiungere un parametro al driver si legge
  `/proc/driver/nvidia/params`**, che mostra i valori *effettivi*. `modinfo`
  mostra solo che il parametro esiste e `/sys/module/.../parameters/` non lo
  espone (write-only). Due volte un conf "correttivo" sarebbe stato peggio di un
  no-op: `NVreg_PreserveVideoMemoryAllocations` forzato a 1 avrebbe riportato al
  salvataggio esplicito su `/tmp`, che su Fedora e' **tmpfs**.
- `nvidia-suspend.service` risulta `Skipped due to 'exec-condition'`: **non e' un
  guasto**, e' il percorso legacy, qui la VRAM la preserva il kernel.
- **Mai legarsi a un nome che dipende dalla topologia PCI.** Montare una seconda
  scheda ha rinumerato i bus e l'interfaccia di rete e' passata da `enp9s0` a
  `enp6s0`: la connessione diretta col Mac non e' piu' salita, tunnel in restart
  loop, Elechim senza strumenti col Mac perfettamente acceso. Si lega al MAC.
- La GTX 1050 e' montata ma **senza driver** (Pascal non e' supportato dal branch
  610, che e' open-only e vuole il GSP). Non serve a niente, non fa danni.

**VRAM — il budget e' stretto, 8188 MiB in tutto**
- X11+plasma 1353, qwen3-vl:4b **4529**, whisper large-v3 int8_float16 1835:
  tutti insieme 7717, il 94%. Se aggiungi un modello, rifai il conto.
- La pipeline documenti dovra' andare **a stadi** (tutta l'estrazione, scarico,
  tutte le figure), col lock GPU gia' presente in `gateway.py`.
- `/gioco` scarica i modelli e alza una bandiera che impedisce il ricaricamento
  automatico; `/amici` ricarica in 11s.

**ollama / qwen3-vl (0.32.7)**
- Il modello ragiona prima di rispondere e **il ragionamento consuma
  `num_predict`**: quando sfonda il tetto, `content` torna **vuoto** con
  `done_reason: length`. `think: false` accorcia ma non spegne: serve margine
  piu' un secondo tentativo con l'istruzione minima.
- **Su un 4B l'istruzione complessa peggiora l'accuratezza**: lo mandi a
  ragionare invece che a guardare. Istruzione semplice, sempre.
- Le immagini vanno ridotte a 1536px: a piena risoluzione 4K il modello legge
  `AROSAKA` dove c'e' scritto `ARASAKA` (la risoluzione dinamica spezza
  l'immagine in riquadri e le lettere finiscono a cavallo dei tagli). Serve
  anche `exif_transpose`.
- Per l'output strutturato usa il **JSON schema** (`format`), mai chiederlo a
  parole: un modello piccolo spinto sul JSON via prompt restituisce 500
  `structured_output_failure`.

**venv e librerie**
- Le librerie dei pacchetti `nvidia-*-cu12` stanno nel venv, dove il linker non
  guarda: vanno precaricate con `ctypes.CDLL(..., RTLD_GLOBAL)` o CTranslate2
  fallisce con `libcublas.so.12 is not found`.

**podman**
- SearXNG e' un **quadlet** in `~/.config/containers/systemd/`. Un servizio con
  `ExecStart=podman start -a` su un container gia' avviato fallisce con 125 in
  loop: il quadlet possiede il container per intero.
- Il `settings.yml` appartiene all'utente del container, si modifica con
  `podman unshare`. Il formato JSON delle API va abilitato a mano o risponde 403.

**Telegram**
- `sendMessage` senza `parse_mode` stampa i backtick letterali, ma con
  `parse_mode="Markdown"` risponde 400 se il modello produce marcatori
  malformati: `bot.py` prova Markdown e ricade su testo semplice.
- `sendChatAction` scade dopo ~5s ma il primo turno ne impiega 7: va rinnovato
  ogni 4s, o il bot sembra morto proprio mentre lavora.
- **Un solo bot per token**: due processi in long polling si rubano gli update.

**Il modello sul Mac**
- Con 4B di parametri attivi **gli aggettivi sul tono non funzionano, gli
  esempi si'**: due scambi D/R da 35 token valgono piu' di tre aggettivi.
- Per la lunghezza serve un **tetto numerico** ("massimo 8 righe") piu' un
  esempio di risposta breve su un tema sostanzioso: "conciso" viene ignorato.
  La verbosita' e' il 90% della latenza, non il prefill.
- **Quello che non sa se lo inventa** (ha dichiarato lo stato delle macchine
  senza controllare). Quello che si sa per certo lo dichiara il codice, non il
  modello.

## Regole di ingaggio per te che leggi

- **Non toccare `DEFINIZIONI` senza dirlo esplicitamente al proprietario.** E' la cosa
  piu' facile da rompere e la piu' difficile da accorgersene.
- **Non riavviare ne' fermare i servizi attivi** (`elechim-gateway`,
  `macmini-tunnel`, `searxng`, `ollama`) senza chiedere: il bot e' in uso vero.
- **`.env` contiene il token Telegram e non va letto, stampato ne' copiato.**
- Le modifiche al codice del Mac si fanno in `mac/` e si propagano con
  `./sincronizza.sh`, mai a mano sul Mac.
- Prima di installare qualcosa di grosso (`torch` sono ~3GB) dillo: la scelta
  dell'ordine di costruzione e' gia' stata presa e ha una ragione (vedi sotto).
- **Quello che impari lo scrivi in `README.it.md`**, nella sezione pertinente,
  con la data e la misura che l'ha dimostrato. `README.it.md` e' la memoria
  condivisa in italiano fra chi lavora qui; `README.md` e' la vetrina in inglese
  e non riceve i dettagli operativi. Se una lezione resta solo nel tuo archivio
  interno, per gli altri non esiste.

## Il lavoro che viene adesso

Due fasi aperte, in questo ordine di dipendenza: **Honcho decide dove finiscono
i fatti**, quindi viene prima o insieme alla fase 4.

**Fase 3 — Honcho + embedding.** Postgres+pgvector, Redis, `bge-m3` come
endpoint embedding, Qwen3 4B come LLM di ingestion sul 4060 Ti. **L'LLM di
ingestion non deve MAI essere il modello del Mac**: ogni chiamata sfratterebbe
la conversazione dall'unica slot di cache. Honcho copre memoria episodica e
modello dell'utente; **non copre le skill procedurali**, che restano file
markdown in `~/Obsidian/40-Skills/` selezionati qui e iniettati solo se
pertinenti. Il prerequisito e' fatto: dall'11 agosto `/nuova` archivia prima di
cancellare, quindi la materia prima esiste.

**Fase 4 — documenti.** Il piano completo e operativo e' in
**`PIANO-DOCUMENTI.md`**: leggilo per intero prima di scrivere una riga.
L'ordine di costruzione e' deciso: **prima la corsia veloce**
(`pdftotext -layout`, gia' installato, poppler 26.01) con la catena *completa*
fino alla nota su Obsidian, **poi** Marker come secondo motore. L'ordine inverso
fa passare una giornata su `torch` senza una sola nota nel vault.

**Dreaming mode** (consolidamento notturno) viene dopo Honcho, gira **sul fisso**
ed e' **guidato dagli eventi, non dall'orologio**: un cron alle 3:00 non gira le
notti in cui il fisso dorme. Si definisce per differenza da Honcho: connessioni
fra fonti diverse, contraddizioni e oblio (**datare e superare, mai cancellare**:
un fatto cancellato porta via il perche' del cambiamento), riassunto leggibile su
Obsidian, skill procedurali. Le proposte proattive si scrivono su Obsidian e
**non si recapitano mai**: un assistente che propone tre azioni ogni mattina
diventa insopportabile in una settimana.

## Dove leggere di piu'

- **`README.it.md`** — documentazione operativa completa in italiano, con le misure.
- **`README.md`** — vetrina in inglese: cos'e', perche' e' diverso, topologia,
  stato, installazione, licenza.
- **`CONTRIBUTING.md`** — come segnalare e contribuire, in inglese.
- **`PIANO-DOCUMENTI.md`** — fase 4, punto di ripresa.
- Percorsi: vault `~/Obsidian` (`00-Inbox`, `10-Ricerche`, `20-Documenti`,
  `30-Note`, `40-Skills`, `90-Allegati`); `documenti/` e `markdown/` per
  l'estrazione integrale **fuori** dal vault; `archivio/` per le istantanee
  delle conversazioni; `stato/` per i marcatori dell'energia.
