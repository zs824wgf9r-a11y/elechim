# Elechim

Assistente personale. Dal 11 agosto 2026 **il bot vive sul Mac mini**, accanto al
modello; sul fisso resta il lavoro sporco.

## Chi fa cosa

| | Mac mini | PC fisso |
|---|---|---|
| gira | bot Telegram, loop dei tool, `stato.db` | gateway, SearXNG, whisper, visione |
| costa | ~7W, sempre acceso | 60-90W, spegnibile |
| se manca | Elechim non risponde | Elechim risponde, senza strumenti |

Il turno di conversazione non passa piu' dalla rete: il bot chiama il modello su
`127.0.0.1:8080`, sulla stessa macchina.

## Il tunnel, nelle due direzioni

Un solo `ssh`, avviato dal fisso (`macmini-tunnel.service`):

- `-L 8080` dal fisso al modello. Ormai serve solo per diagnostica.
- `-R 8090` dal Mac al gateway degli strumenti sul fisso.

**Il forward inverso lo apre il fisso, ed e' il punto di tutto**: quando il fisso
e' spento la porta 8090 sul Mac non esiste, quindi il bot riceve un rifiuto
immediato invece di restare appeso trenta secondi. Elechim continua a
rispondere, dice che non ha potuto controllare, e riprende gli strumenti da solo
quando il fisso torna su. Niente firewall da aprire: l'unico modo di entrare
resta la chiave ssh.

**Col fisso spento i tool NON vanno tolti dalla lista.** La cache del Mac
pretende `entry.tools == request.tools` byte per byte: togliere `cerca`
azzererebbe il prefill dell'intera conversazione. Restano definiti sempre, ed e'
l'esecutore a rispondere che il fisso e' spento. Verificato il 2026-08-11
staccando il tunnel: turno da 7,1s con **cache al 99%**.

## Avvio

Sul **fisso**, quattro servizi utente con linger attivo:

```bash
systemctl --user status macmini-tunnel    # ssh nelle due direzioni
systemctl --user status searxng           # metamotore (quadlet podman)
systemctl --user status crawl4ai          # scaricamento pagine (quadlet podman)
systemctl --user status ollama            # modello di visione sulla 4060 Ti
systemctl --user status elechim-gateway   # il gateway degli strumenti
journalctl --user -u elechim-gateway -f   # tempi di ogni chiamata
```

Sul **Mac**, un LaunchDaemon (non un LaunchAgent: la macchina e' headless e non
fa autologin, quindi non esiste una sessione GUI in cui un agent potrebbe
partire):

```bash
sudo launchctl print system/com.elechim.assistente
tail -f ~/assistente/elechim.log
```

CLI sulla **stessa** conversazione del bot:

```bash
ssh macmini-plain '~/assistente/.venv/bin/python ~/assistente/cli.py'
```

## File

I sorgenti del Mac stanno **qui sul fisso**, in `mac/`, e si copiano con
`./sincronizza.sh`. Si modificano in un posto solo: due copie modificabili sono
il modo piu' rapido di correggere un bug da una parte e lasciarlo vivo
dall'altra.

| file | dove gira | ruolo |
|---|---|---|
| `mac/core.py` | Mac | prompt di sistema, parametri, stato SQLite, chiamate al modello |
| `mac/bot.py` | Mac | Telegram in long polling: testo, vocali, immagini |
| `mac/strumenti.py` | Mac | definizioni dei tool + client del gateway |
| `mac/cli.py` | Mac | terminale |
| `gateway.py` | fisso | server su 127.0.0.1:8090 |
| `strumenti.py` | fisso | `cerca` e `leggi`, con compressione |
| `web.py` | fisso | client di crawl4ai: testo per la ricerca, markdown per il vault |
| `voce.py` | fisso | trascrizione con faster-whisper |
| `visione.py` | fisso | descrizione e OCR delle immagini |
| `energia.py` | fisso | sospensione, VRAM contesa col gioco, risveglio |
| `sospendi.py` | fisso | il controllo periodico che decide se dormire |
| `documenti.py` | fisso | la corsia veloce: PDF -> markdown integrale -> note su Obsidian |
| `prova_documenti.py` | fisso | il collaudo dei documenti, su PDF sintetici generati da lui |
| `mac/risveglio.py` | Mac | il magic packet che sveglia il fisso |

## Perche' e' scritto cosi'

Tutto discende dal collo di bottiglia misurato il 2026-08-10: sul Mac il
**prefill** costa ~14ms/token e degrada coi prompt lunghi (23,6 tok/s a 8K).
Rileggere il contesto e' molto piu' caro che generarlo.

La cache del prompt del Mac (`ServerPromptCache.swift`) lo compensa, ma solo in
una forma stretta:

- **una sola slot**: una conversazione alla volta. Per questo Telegram e CLI
  condividono lo stesso `stato.db` invece di avere due chat separate.
- `matchTextContinuation` riusa la cache solo se arriva **esattamente un**
  messaggio nuovo con ruolo `user`. Vocali e immagini diventano testo *prima* di
  entrare nella conversazione, proprio per questo.
- il prompt di sistema deve restare **stabile**: cambiarlo invalida tutto.

In pratica: primo turno ~7s, quelli dopo ~2s con il 95% di cache.

## Vocali e immagini

Mandi un vocale o una foto, il **fisso** li macina e al Mac arriva solo testo.
Da qui parte soltanto il `file_id`: e' il fisso a scaricare l'allegato dai
server di Telegram, quindi i byte non attraversano mai il tunnel e non toccano
la macchina che ospita il modello.

- **vocali**: `faster-whisper large-v3` in `int8_float16`, ~1,6GB di VRAM,
  0,3-0,6s a modello caldo.
- **immagini**: `qwen3-vl:4b` in ollama, ~3,5GB. Legge il testo dentro le
  immagini e descrive le scene. Con una didascalia la risposta esce mirata
  invece che esaustiva: e' la stessa compressione che `leggi` fa sui paragrafi.

Di entrambi ti rimando indietro quello che ha capito (`🎤 «...»`, `🖼 «...»`),
cosi' se ha letto male te ne accorgi subito.

**Le immagini vengono rimpicciolite a 1536px prima di darle al modello, e non e'
solo per risparmiare.** Misurato il 2026-08-10 su una schermata 3840x2160: a
piena risoluzione legge `AROSAKA` dove c'e' scritto `ARASAKA`, ridotta lo legge
giusto. La risoluzione dinamica di Qwen spezza l'immagine grande in riquadri e
le lettere finiscono a cavallo dei tagli.

I due modelli convivono sugli 8GB della 4060 Ti perche' ollama scarica il suo
dalla VRAM dopo 5 minuti di inerzia (`OLLAMA_KEEP_ALIVE=5m`): la prima immagine
dopo una pausa paga ~50s di caricamento, quelle dopo stanno sotto i 7s. Il
keep-alive corto e' voluto anche perche' quella scheda serve pure per giocare.

## Trappole gia' pagate

- **`Wants`, non `BindsTo`, sul tunnel.** Con `BindsTo` la caduta del tunnel
  *ferma* il servizio, e siccome e' uno stop ordinato da systemd il
  `Restart=always` non si applica: il tunnel torna su da solo, il servizio resta
  giu' per sempre. Verificato uccidendo l'ssh.
- **Rollback del messaggio utente in caso di errore** (`core.rispondi`). Senza,
  un guasto lascia un `user` senza risposta e al turno dopo ci sono due `user`
  di fila: la cache non aggancia mai piu'.
- **Markdown Telegram con fallback.** Senza `parse_mode` i backtick si vedono
  letterali; con `parse_mode` Telegram risponde 400 se i marcatori sono
  malformati o se lo split a 4000 caratteri taglia un blocco di codice.
- **Il prompt di sistema usa esempi, non aggettivi.** Con 4B di parametri
  attivi "cinico" non basta: servono due scambi D/R di esempio.
- **Un solo bot alla volta sul token.** Due processi in long polling si rubano
  gli update a vicenda: il bot sul fisso va fermato *prima* di avviare quello
  sul Mac, e `stato.db` va copiato in quel momento (contiene `offset_telegram`).

## Ricerca web

Due soli tool, `cerca` e `leggi`. SearXNG gira in un container podman (quadlet in
`~/.config/containers/systemd/searxng.container`) su `127.0.0.1:8888`; il formato
JSON delle API va abilitato a mano in `searxng/settings.yml`, e quel file
appartiene all'utente del container: si modifica con `podman unshare`.

La compressione e' **estrattiva, senza LLM**: si scelgono i paragrafi piu'
pertinenti con un punteggio a parole chiave. Tetti a 1400 e 1600 caratteri
(~350-400 token): una pagina grezza sarebbe 2000+ token, cioe' un minuto di
prefill sul Mac.

### Gli snippet non bastano (12 agosto)

Fino al 12 agosto `cerca` restituiva solo titoli, snippet e url, sul
presupposto che gli snippet di SearXNG bastassero quasi sempre. Alla richiesta
esplicita "mi fai una ricerca web sui migliori integratori naturali" il modello
ha chiamato lo strumento — quindi la lezione dell'11 agosto sul prompt di
sistema aveva funzionato — e poi **ha risposto ignorando quello che era
tornato**: cinque righe di marketing da e-commerce ("al miglior prezzo
garantito: approfitta delle offerte"), zero fatti da citare. Lo strumento
funzionava e non serviva a niente, che e' il modo peggiore in cui una cosa puo'
rompersi: nei log non c'e' nessun errore da cercare.

Ora `cerca` **apre da sola le prime tre pagine** ed estrae i passaggi
pertinenti, invece di aspettare che il modello incateni una `leggi`: un secondo
giro di tool costa un altro turno sul Mac (10-30s) e comunque il modello non lo
faceva. Il tetto resta 1400 caratteri, cambia cosa c'e' dentro. Le pagine si
aprono in parallelo, sei secondi a testa; chi non risponde in tempo lascia il
posto al suo snippet, e una ricerca passa da 0,7s a ~2s — invisibili accanto ai
37s del turno sul Mac.

Tre correzioni minori nate dalla stessa giornata:

- **Un risultato per dominio.** Con tre soli slot, due pagine dello stesso sito
  sono uno slot buttato (`ilprodottomigliore.it` due volte di fila).
- **Le vetrine in fondo.** Un url senza percorso e' quasi sempre la homepage di
  un negozio. Non si scartano, si mandano in coda.
- **La boilerplate vale zero.** Il punteggio a sole parole chiave, su una pagina
  che parla proprio di quello che hai cercato, premiava i disclaimer: il primo
  passaggio estratto era "questo articolo ha uno scopo puramente informativo".
  Ora quelle frasi sono azzerate e, a parita' di pertinenza, vince il paragrafo
  piu' in alto: negli articoli la sostanza sta prima e i cookie stanno dopo.

**Le `DEFINIZIONI` non sono cambiate di un byte**, in tutte e due le copie: sotto
`cerca` e' successo di tutto, ma la descrizione che viaggia a ogni richiesta e'
identica, o la cache dell'intera conversazione salta.

### crawl4ai davanti, statico dietro (15 agosto)

Il tubo sotto `_scarica` e' cambiato: prima `requests` + `trafilatura`, ora
**crawl4ai** (container podman su `127.0.0.1:11235`, quadlet
`crawl4ai.container`) con la corsia statica come ripiego. La catena resta
*SearXNG trova -> si scarica ed estrae -> il punteggio sceglie i passaggi*;
sopra `_scarica` non e' cambiato niente (punteggio, tetti, cache, vetrine,
boilerplate). Se crawl4ai non risponde — container ripartito dopo il risveglio
del fisso, timeout, 403 — si riprova con `requests`+`trafilatura`; se cade
anche quella, resta lo snippet. Il client e' `web.py`, che espone i due usi:
`testo_pulito` per la ricerca (testo senza marcature) e `markdown_integrale`
per il vault (markdown con i link conservati, per le note future di `ricorda`/
`salva`: la funzione c'e', non e' ancora collegata a nessun tool).

**Il filtro anti-navigazione e' il cuore del lavoro.** Il browser rende 2,6x
caratteri in piu' di trafilatura, ma su una homepage quasi tutto il guadagno e'
menu: contando le righe di solo link nel markdown `fit` veniva 69% su tgcom24,
39% su macitynet, 36% su ilmeteo. Dare 1400 caratteri di menu a un modello da
4B e' il guasto del 12 agosto in forma nuova. `web.py` butta le righe che,
tolte le marcature di link e i gettoni `%javascript%`, non dicono piu' niente
— attenzione alle quadre annidate dei titoli italiani
(`[Meteo: svolta [Parla Gussoni] ](url)`: una regex ingenua le lascia passare
con l'url dentro). Risultato dello stesso metro, dopo il filtro: **0% su tutte
e tre**.

Numeri misurati il 15 agosto sulle stesse 40 pagine (8 query reali via
SearXNG, prime 5 per query, un dominio ciascuna):

```
              pagine   tempo medio   caratteri medi (sulle 37 comuni)
statico        37/40      0,59s          8.029
crawl4ai+filtro 38/40      1,30s         12.704   (1,6x; il grezzo era 2,6x)
integrata      38/40      1,07s          -
```

- Disponibilita': crawl4ai batte il statico di una pagina (galaxus, che
  trafilatura non estraeva); zero pagine dove funziona solo il statico. Le due
  mai (hdblog, segugio) sono 403 anti-bot per entrambe: crawl4ai li riconosce
  e non si aggirano.
- Una ricerca completa passa da ~2s a **2,4-3,4s** (tre pagine in parallelo):
  invisibile accanto ai 10-37s del turno sul Mac.
- **Il primo colpo a container freddo** (dopo `systemctl --user restart
  crawl4ai`): `/health` pronto in 3,0s, prima pagina in 1,42s contro 0,82s a
  caldo. Ben dentro il tetto: nessun riscaldamento del browser, nessun tetto
  speciale.
- **Memoria del container**: ~800-950MB a riposo e sotto carico, picco 1,2GB
  (1,5% dei 67GB): non e' un problema di capienza.
- `TIMEOUT_PAGINA` resta 6s per entrambe le corsie: tutte le pagine del
  benchmark stanno sotto 4s. Il caso brutto e' la pagina lenta per tutti
  (vista: blog.giallozafferano.it con la rete fiacca, 6s + 6s): costa fino a
  ~12s *su quella pagina*, in parallelo alle altre — e il difetto esisteva
  gia' con la sola corsia statica, che di `timeout` ne rispetta uno per
  lettura di socket, non uno totale.

L'autenticazione e' il token Bearer (`crawl4ai.env`): dalla 0.9.0 senza token
il server si lega a 127.0.0.1 *dentro* il container e la porta pubblicata non
arriva — la scelta e' motivata nel quadlet. L'estrazione e' deterministica:
niente chiavi LLM, il filtro `fit` di pruning e le regex di `web.py`.

## La data

Il prompt di sistema include la data odierna, altrimenti il modello cerca
notizie "di oggi" nell'anno del suo addestramento (visto in uso reale il 10
agosto 2026, con query generate su "February 2025").

**Non va ricalcolata a ogni chiamata**: il prompt di sistema e' il prefisso del
contesto, quindi cambiarlo invalida la cache. Si congela alla prima chiamata
della conversazione (`meta.prompt_sistema`) e si rinnova solo con `/nuova`. I
nomi dei mesi sono scritti a mano: `%B` dipende dal locale del processo.

## L'archivio delle conversazioni

`/nuova` **archivia prima di cancellare**: la conversazione finisce nelle tabelle
`conversazioni` e `archivio` dentro lo stesso `stato.db`, nella stessa
transazione della cancellazione, e il bot risponde quanti messaggi ha salvato.
`/stato` mostra il totale archiviato.

Fino all'11 agosto `azzera()` faceva solo `DELETE FROM messaggi`: ogni `/nuova`
distruggeva per sempre la materia prima del dreaming (una serata intera persa
alle 00:10 di quel giorno). L'archivio e' il presupposto della fase 3.

## Le tre lezioni dell'11 agosto, prima giornata di uso vero

Ventisette turni misurati hanno detto tre cose che a tavolino non si vedevano.

**La verbosita' e' la latenza.** 4.581 token generati, 310s di attesa totale, di
cui ~275 di sola generazione: il 90% del tempo percepito non e' prefill, e'
lunghezza della risposta. Nel prompt di sistema gli aggettivi ("conciso") il
modello li ignora appena il contesto cresce; un tetto numerico ("massimo 8
righe") e un esempio di risposta breve su un tema sostanzioso reggono. Misurato
dopo: stessa domanda sugli integratori, da 481 token a 163.

**Le descrizioni degli strumenti dicono cosa fanno, non quando usarli.** In
tutta la giornata zero chiamate a `cerca`, con due richieste esplicite di
ricerca web. La regola su *quando* chiamare gli strumenti va nel prompt di
sistema — non nelle `DEFINIZIONI`, che viaggiano a ogni richiesta e devono
restare identiche byte per byte o la cache salta.

**Il modello non sa cosa succede fuori dalla sua finestra**, e se non glielo
dici lo inventa: "il Mac mini e' in standby, il PC fisso e' pronto", senza aver
controllato niente. Ora il prompt gli dice di rimandare a `/stato`, e un
allegato che il bot non sa leggere lo dice **il bot**, che lo sa per certo,
invece di lasciarlo indovinare al modello.

## Energia: quando il fisso dorme, e di chi e' la VRAM

Il fisso **si sospende da solo dopo tre ore** e il Mac lo risveglia col magic
packet quando serve uno strumento. Il Mac resta sempre acceso: sono 7W contro
60-90.

La sospensione non e' un timer, e' un elenco di ragioni per restare svegli
(`energia.motivi_per_restare_svegli`), controllato ogni dieci minuti da
`elechim-sospensione.timer`. Si dorme quando l'elenco e' vuoto. Il motivo per
cui NON si e' dormito finisce **sempre** nel journal, perche' la domanda vera e'
"perche' stanotte e' rimasto acceso":

```
journalctl --user -u elechim-sospensione -n 20
.venv/bin/python sospendi.py --spiega     # cosa farebbe adesso, senza farlo
```

Le ragioni sono: una richiesta al gateway nelle ultime tre ore, qualcuno alla
scrivania, un lavoro lungo che ha preso un blocco (`energia.blocco`, che serve
alla coda documenti della fase 4), una sessione ssh aperta, o un risveglio
appena avvenuto.

**L'inerzia della scrivania si legge da XScreenSaver via ctypes**, non
dall'IdleHint di logind: su X11 con KDE quell'hint non viene mai aggiornato
(resta `no` con `IdleSinceHintMonotonic=0` anche a sessione ferma), quindi la
strada idiomatica di systemd qui non funziona. `xprintidle` non e' pacchettizzato
su Fedora 44; `libXss.so.1` c'e' gia'. DISPLAY e XAUTHORITY si pescano
dall'ambiente di plasmashell: un servizio avviato dal linger non le ha, e
indovinarle funziona finche' SDDM non cambia idea.

Il controllo copre anche il gioco senza andare a caccia di processi di Steam: se
stai giocando stai dando input, quindi la scrivania non e' inerte.

### Il giro vizioso del risveglio

Il Mac sveglia il fisso, il controllo parte dieci minuti dopo, trova l'ultima
attivita' vecchia di tre ore — che e' l'ora in cui ci si era addormentati — e lo
rimanda a dormire. Si evita confrontando i due orologi: CLOCK_MONOTONIC si ferma
durante la sospensione, CLOCK_BOOTTIME no, quindi la loro differenza che cresce
vuol dire che nel mezzo si e' dormito. Niente hook di sistema, niente root.

### VRAM: `/gioco` e `/amici`

Con visione e whisper entrambi caricati la scheda sta a **7717 MiB su 8188**
(misurato): non c'e' spazio per un gioco a 4K. Quindi:

- `/gioco` scarica i modelli (7717 -> 1367 MiB, misurato) e alza una bandiera
  che **impedisce di ricaricarli**. Senza la bandiera, la prima foto che arriva
  su Telegram rimetterebbe in VRAM qwen3-vl a meta' partita.
- `/amici` la abbassa e li rimette in caldo (11s a file gia' in cache).
- `/energia` dice VRAM, modelli caricati e perche' la macchina e' ancora sveglia.

Finche' la bandiera e' su, vocali e immagini rispondono che la GPU e' occupata
**dicendo come liberarla**. La degradazione silenziosa e' l'errore che questo
progetto ha gia' pagato una volta, con un PDF sparito senza un messaggio.

### Perche' niente di tutto questo e' un tool

`/gioco`, `/amici` e il risveglio non stanno nelle `DEFINIZIONI`. Un tool in piu'
costa il prefill di **ogni** conversazione futura (`entry.tools ==
request.tools`), e sono decisioni che il modello non deve prendere: le prende
il proprietario dal bot, o le prende l'esecutore quando trova la porta chiusa. Il
rifiuto immediato sulla 8090 e' gia' la prova che il fisso non c'e', quindi
`strumenti._chiama` manda il pacchetto da solo e lo racconta al modello.

### Cose da sapere

- **La VRAM al suspend non va configurata: ci pensa gia' il kernel.** Sembra il
  contrario, perche' `nvidia-suspend.service` risulta `Skipped due to
  'exec-condition'`. Ma quella condizione e'
  `grep -qs 'UseKernelSuspendNotifiers: 0' /proc/driver/nvidia/params`, e qui
  vale **1**: il servizio userspace e' il percorso *legacy* e viene saltato
  perche' non serve piu'. Il conf di sistema lo dice a chiare lettere — *"the
  kernel handles video memory preservation directly"*. `PreserveVideoMemoryAllocations`
  vale **2**, che e' il default del driver in questa modalita'.

  Forzarlo a 1 sarebbe **peggio di un no-op**: riporterebbe al salvataggio
  esplicito su `TemporaryFilePath`, che qui e' vuoto e ricadrebbe su `/tmp`,
  che su Fedora e' **tmpfs** — cioe' scaricare gigabyte di VRAM nella RAM,
  esattamente cio' contro cui avverte il commento del pacchetto. Un conf del
  genere e' stato scritto e poi **rimosso** il 12 agosto prima che facesse
  danni. E' lo stesso errore di `NVreg_UsePageAttributeTable` del 5 agosto:
  su questo driver, prima di aggiungere un parametro si legge
  `/proc/driver/nvidia/params`.
- Una regola polkit (`/etc/polkit-1/rules.d/50-elechim-sospensione.rules`)
  permette la sospensione da un servizio utente: col linger non c'e' una
  sessione "attiva" e la richiesta finirebbe in `auth_admin`, appesa per sempre.
- Nel BIOS servono **Power On By PCI-E = Enabled** ed **ErP Ready = Disabled**.
  Con ErP attivo il +5VSB alla scheda di rete viene tagliato e da spegnimento
  completo il magic packet non arriva. Da S3 la scheda resta alimentata e il
  carrier non cade, che e' un motivo in piu' per sospendere invece di spegnere.
- Il risveglio da S3 sono pochi secondi contro **1m32s** di avvio completo.

## Documenti: la corsia veloce (fase 4)

Un PDF con livello di testo va da `documenti/in/` alle note di Obsidian senza
che nessun modello tocchi il contenuto. `documenti.py`, poppler, deterministico.
Misura del 15 agosto: **`DSML.pdf`, 533 pagine, 70 secondi**, 223 sezioni.

La catena: coda sorvegliata -> estrazione integrale in `markdown/<slug>.md`
(fuori dal vault, con ancore `<!-- pag N -->`) -> sezionamento -> nota indice in
`20-Documenti/<slug>/` e una nota atomica per sezione in `30-Note/` -> rapporto
di copertura. L'integrale e' la verita', le note sono l'indice: se una nota e'
imprecisa, il testo e' a un link di distanza.

Le note si chiamano `DSML 10.1 Vector Spaces, Bases, and Matrices`, con gli
`aliases` nel frontmatter per la ricerca. In Obsidian il nome del file **e'** il
titolo che vedi, e il progressivo di pipeline li' dentro non ci va.

### Le quattro lezioni, con la misura

**1. `-layout` rovina la prosa a due colonne.** Il piano prescriveva
`pdftotext -layout`. Su un documento a due colonne affianca le colonne riga per
riga e produce prosa illeggibile:

```
$ pdftotext -layout -f 1 -l 1 Basic_Statistics_2007.pdf
Statistics is a relatively new science with         scribing the information being studied. Ran-
most of the important developments occurring        dom variables can be further described by the
```

Ma `-layout` **serve** per le tabelle, che sono l'unica cosa che tiene allineate
le colonne di numeri. Quindi si usano **tutte e due**, scelte per regione: prosa
senza `-layout` (ordine di lettura), tabelle con.

**2. Il documento contiene gia' il proprio indice, e batte qualsiasi euristica.**
Stavamo ricostruendo la struttura dal corpo dei font. Non serviva: `pypdf` legge
l'outline incorporato e su `DSML.pdf` da' **223 voci, 223 risolte a una pagina,
0 fallimenti**, con titoli esatti e gerarchia gia' annidata su tre livelli.

Tutti i difetti su cui stavamo lavorando erano artefatti del ricostruire a
occhio una cosa gia' dichiarata: `Preface` letto come `reface` (tipografia a
maiuscoletto, iniziale e resto come due elementi con `top` diverso di pochi
pixel), le dediche promosse a sezione, i frammenti. Con l'outline **spariscono
tutti insieme**. Il ripiego font-size resta per i PDF che l'indice non ce
l'hanno, e il campo `struttura` nel rapporto dichiara quale dei due ha lavorato.

**3. La coda vuole un lock, perche' il path unit le corre addosso.**
`elechim-documenti.path` sorveglia `documenti/in/*.pdf` e il servizio svuota
proprio quella cartella spostando i file che finisce: la condizione cambia
mentre il lavoro e' in corso, e systemd fa ripartire il servizio sopra quello
vivo. Successo il 15 agosto, **due processi nello stesso secondo**: il secondo
ha fatto `glob()` su una lista che il primo stava svuotando e si e' ritrovato il
PDF sparito a meta' elaborazione, dentro `pdfinfo`.

Il rimedio e' `flock` non bloccante in `_coda_esclusiva`: chi arriva secondo
esce con **codice 0**, perche' non e' un guasto. `energia.blocco` non serviva
allo scopo — scrive il proprio PID sopra quello di chi c'era, visto che il suo
mestiere e' tenere sveglio il fisso, non escludere.

E il gestore d'errore aveva lo stesso difetto al contrario: spostava in
`falliti/` un file che `processa` aveva gia' portato in `elaborati/`, e quel
secondo `FileNotFoundError` partiva da dentro il gestore, dove non lo prendeva
nessuno. Il servizio usciva 1 e **la coda si fermava per il guasto che quel
gestore esiste per evitare**. Adesso `_scarta` controlla prima, e scrive accanto
al file la ragione per cui ci e' finito.

**4. Due sintomi lontani, una causa sola.** `markdown/prova-due-colonne.md`
conteneva **18 marcatori di pagina per 11 pagine**, le pagine 5-11 scritte due
volte. Sembrava un difetto di idempotenza nella ripresa — `genera_markdown`
riparte da `ultima = max(pagine gia' presenti)` — ed e' stato cercato li' per un
po'. Non era li'.

Era **la stessa corsa** di sopra vista dall'altro capo: il collaudo scriveva i
PDF in `documenti/in/` senza prendere il lock, il path unit faceva partire il
servizio in parallelo, e due processi scrivevano lo stesso markdown. Le pagine
non erano riscritte da una ripresa difettosa: erano scritte **due volte da due
processi diversi**. Risolte insieme, senza toccare `genera_markdown`.

Lo stesso vale per il collaudo rosso sulle tabelle: `tabelle_conservate == 2`
sul sintetico non era il rilevatore che sbagliava, era la **pagina duplicata**
contata due volte. Un difetto di concorrenza si presenta lontano da dove sta.

**Il modo sbagliato di verificarlo**, che ha fatto dichiarare risolto il difetto
due volte: contare i marcatori **distinti** e confrontarli con le pagine. Torna
sempre 11 su 11 e non puo' vedere nulla. L'asserzione giusta conta le
**occorrenze**: `md.count("<!-- pag ") == pagine_totali`. Era gia' scritta in
`test_interruzione`, ma il collaudo si fermava prima, sul rosso delle tabelle:
**un test che non viene raggiunto non protegge niente.**

**5. Le tabelle: il vuoto fra le colonne non e' una tabella.** `_e_tabella`
dichiarava tabella una riga con due o piu' spazi ampi, cioe' trovava
l'impaginazione. Su `Basic_Statistics_2007.pdf`: **42 tabelle su 10 pagine**, di
cui 26 per piu' del 50% lettere. Aggiunta una densita' minima di cifre
(`SOGLIA_DENSITA_TABELLA = 0.10`) quando i vuoti ampi sono due o piu' — la prosa
a due colonne ne ha **uno solo**, sempre alla stessa x. Falsi positivi **da 42 a
13**, e la tabella vera del sintetico continua a essere trovata.

**6. Una scansione va rifiutata, non archiviata vuota.** Prima la pipeline
estraeva 3 caratteri contro 3.610 e non diceva niente: il modo peggiore di
fallire, perche' te ne accorgi mesi dopo. Ora `classifica()` misura la mediana
di caratteri per pagina e sotto `SOGLIA_CARATTERI_PAGINA = 100` il documento
finisce in `falliti/` con la ragione scritta, senza produrre note. La soglia e'
misurata: sintetico **770**, DSML **1.606**, scansione **0**.

### Cosa non regge ancora

- **Le figure non vengono estratte**: `90-Allegati/` e' vuota. Sul PDF di prova
  `pdfimages -list` non trova niente perche' sono vettoriali, quindi andranno
  rese con `pdftocairo` a livello di pagina.
- **Le scansioni vengono rifiutate, non lette.** Il rifiuto e' onesto e
  dichiarato, ma un OCR non c'e': serve la seconda corsia (docling).
- **Le tabelle con intestazioni di solo testo** possono cadere sotto la soglia
  di densita' e non essere riconosciute. Bilancio accettabile sui documenti
  provati, da rimisurare se capita un documento che ne e' pieno.
- **Le note atomiche sono ancora segnalibri** nel vault, con un estratto
  troncato a meta' parola. `sbobina.py` sa riscriverle — collaudo verde sul
  sintetico, 6 sezioni su 6 — ma non e' ancora stato passato sui documenti veri.

## Limiti attuali

Legge i PDF con livello di testo (sopra), ma non le scansioni. Non ha memoria
fra conversazioni diverse (fase 3, ma adesso almeno l'archivio non si perde). Il
contesto e' 65536 token; oltre ~52000 il bot avvisa, e a saturazione serve
`/nuova`.

## Installazione

Da zero a un bot che risponde. Elechim e' fatto per due macchine: il **fisso**
(desktop: gateway, ricerca, voci, immagini) e il **Mac mini** (modello di testo
+ bot Telegram). Il fisso raggiunge il modello sul Mac con un tunnel ssh
(`-L 8080`), il Mac raggiunge il gateway col forward inverso (`-R 8090`). Se il
fisso dorme, il bot continua a rispondere ma senza ricerca, voci e immagini.

### Prerequisiti

- **Python 3.12** (il 3.14 e' troppo nuovo per lo stack ML).
- **ollama**, per il modello delle immagini (`qwen3-vl:4b`).
- **podman**, per i container di ricerca web e scraping (SearXNG, crawl4ai).
- **ffmpeg**, per i comandi vocali (faster-whisper).
- **poppler** (`pdftotext`), per la corsia veloce dei documenti.

### 1. Ambiente e dipendenze

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` elenca le uniche dipendenze di terze parti, ricavate dagli
import veri; tutto il resto e' stdlib o moduli locali.

### 2. Configurazione

```bash
cp .env.example .env
cp mac/.env.example mac/.env
cp crawl4ai.env.example crawl4ai.env
cp searxng/settings.yml.example searxng/settings.yml
```

Riempi i segnaposto. Sul fisso: `TELEGRAM_TOKEN` da @BotFather,
`TELEGRAM_ALLOWED_IDS` (a chi mandare il rapporto di verifica dopo un riavvio),
`MAC_BASE_URL` e `MAC_MODEL` verso il modello del Mac. Sul Mac (in `mac/.env`):
le stesse, ma `MAC_BASE_URL` locale e `GATEWAY_URL` verso il gateway del fisso,
piu' **`PROPRIETARIO`**, il nome con cui il modello si rivolge a te.

`PROPRIETARIO` sta nel `.env` e non nel codice per due ragioni, e la seconda
costa: il codice e' pubblico, e il prompt di sistema e' il **prefisso della
cache** del modello — cambiarne una parola azzera il prefill di ogni
conversazione viva, che a 8K token sono ~340 secondi. Se lasci il segnaposto il
bot parte lo stesso, ma ti chiamera' "Nome".

Chi puo' parlare col bot non si configura: il **primo** chat id che scrive
diventa il proprietario, viene registrato nello stato, e da li' in poi gli altri
sono ignorati.

### 3. Modelli

```bash
ollama pull qwen3-vl:4b
```

sul fisso, per le immagini. Il modello di testo (per esempio
`gemma-4-26b-a4b-it`) si carica sul Mac, che lo serve su `MAC_BASE_URL`.

### 4. Avvio

Servizi systemd utente gia' esistenti:

```bash
systemctl --user start elechim-gateway crawl4ai searxng
```

Per provare a mano, senza systemd: sul fisso `.venv/bin/python gateway.py`, poi
sul Mac `.venv/bin/python bot.py`.

### 5. Verifica

`verifica_avvio.py` (gia' nel repo) controlla che i servizi rispondano:
lancialo dopo l'avvio.

### Cosa non funziona ancora

- Le scansioni senza livello di testo non sono supportate, e **falliscono in
  silenzio**: la pipeline estrae il vuoto senza dire che e' vuoto.
- Il rilevatore di tabelle scambia l'impaginazione a due colonne per una
  tabella. Vedi "Cosa non regge ancora" nella sezione sui documenti.
- Le figure non vengono estratte, e le note atomiche sono ancora segnalibri.
- La ripresa dopo un'interruzione **duplica le pagine** nell'integrale.
- Nessuna memoria fra conversazioni diverse: la fase 3 non e' iniziata.
