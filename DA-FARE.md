# Da fare — stato, bug e prossime mosse

Scritto il **15 agosto 2026, sera**, dopo il blackout e la riparazione della
coda. Questo file e' la lista operativa: cosa e' rotto, cosa e' stato corretto e
come, cosa aspetta una decisione del proprietario. Lo stato architetturale sta in
`AGENTS.md`, il piano dei documenti in `PIANO-DOCUMENTI.md`.

Convenzione: ✅ fatto e verificato · 🔧 in lavorazione · ⬜ da fare ·
👤 serve una decisione o una prova del proprietario.

---

## DOVE SIAMO — 20 agosto 2026: il progetto cambia bersaglio

Deciso dal proprietario il 19-20 agosto, discutendo a cosa serve davvero
Elechim. **A ottobre 2026 comincia una magistrale in Data Science.** Il primo
anno e' tutto obbligatorio, 54 CFU, e si divide cosi' per come si impara:

| natura | CFU | dove pesa |
|---|---:|---|
| coding e sistemi | 24 | dove gli strumenti che ha gia' bastano |
| **matematica** (apprendimento statistico, ottimizzazione) | 18 | **dove deve essere bravo lui** |
| discorsivo (diritto, gestione) | 12 | dove un modello locale regge quasi da solo |

Il piano di studi completo non entra in questo file: e' un documento
d'ateneo e i nomi esatti dei corsi identificano la persona.

**Sette settimane a ottobre.** Tutto quello che non serve allo studio slitta.

### Cosa vuole il proprietario, con le sue parole

> «Una fonte di conoscenza rapida. Non so qualcosa e mi aiuta a capirla meglio.
> Non come mezzo di studio. Una chat e piu' in la' un terminale sempre con me,
> pronto a rispondere alle mie domande e salvarle in degli appunti per poi unire
> i pezzi. Un sistema che quando prende una nota ci costruisce attorno il resto
> e i pezzi mancanti. Poi la notte o in idle lo trasforma e lo elabora, mette
> insieme i pezzi anche con quelli gia' presenti. Un RAG adattato allo studio ma
> attivo e non passivo.»

E: «uno studio facile e pratico che anche un bambino riesce a capire», «qualcosa
che non mi annoi e che mi aiuti a rimanere concentrato».

**Tira, non spinge.** Non un sistema che propone sessioni di studio: un sistema
che risponde quando lo interroghi e lavora da solo nel frattempo.

### Le decisioni prese, da non rimettere in discussione

1. **Tutto in locale, senza eccezioni.** Nessun LLM in cloud, neanche per le
   domande che non toccano documenti. Esce **solo** una query di ricerca verso i
   motori, via searxng. Le pagine scaricate entrano nel corpus, mai il contrario.
   La regola estesa sta in `AGENTS.md`.
2. **Il modello non risponde mai dalla sua testa.** Risponde solo su passaggi che
   ha davanti. Se il corpus non basta, si cerca sul web e la pagina scaricata
   diventa il passaggio. «Non ho una fonte» e' una risposta legittima. E' questa
   regola che rende utilizzabile un 8B su materiale che non conosce.
3. **Tre livelli, non due.** Il costo del Mac non e' la CPU, e' la cache.
   - `gemma-4` sul Mac: **solo** parlare col proprietario. Niente lavoro.
   - `qwen3:8b` sul fisso, GPU: tutta la generazione (risposte di studio,
     fusioni, orfani).
   - un **4B sulla CPU** del fisso: i lavori a risposta chiusa, in volume.
   Il piccolo va in CPU perche' la VRAM non basta: 8188 MiB totali, 1573 gia'
   occupati, `qwen3:8b` ne prende 5,2 GB. Un 4B accanto non ci sta. Sulla CPU
   (Ryzen 7 5700X, 55 GB liberi) i lavori a risposta chiusa emettono 1-5 token,
   quindi la lentezza non si manifesta — **e il piccolo esce dal mutex GPU**,
   cosi' puo' verificare mentre la GPU macina. Da misurare: il prefill in CPU.
   Modello consigliato `qwen3:4b`, stessa famiglia dell'8B, stessi prompt.
4. **Il piccolo fa i lavori a risposta chiusa, il grande quelli a risposta
   aperta.** Chiuso = c'e' una risposta giusta e si puo' controllare: riscrivere
   la domanda in termini di ricerca, scegliere i passaggi pertinenti, estrarre le
   affermazioni verificabili, etichettare la verifica web
   (`conferma`/`smentisce`/`non dice`), riassumere una pagina scaricata. Il
   vantaggio nascosto: **quegli output sono misurabili**, la prosa no.
5. **Due chat separate, due bot veri** (non una modalita' che si dimentica).
   - *cavolate*: Elechim di oggi, **invariato**. `DEFINIZIONI` non si tocca,
     nessuna cache invalidata.
   - *studio*: canale nuovo, cervello sul fisso.
   Costa zero perche' non condividono la cache. E soprattutto: **la separazione
   sostituisce il filtro intelligente** — chat studio = si salva tutto, chat
   cavolate = non si salva niente. Il giudizio «questa domanda merita?» sparisce,
   l'ha gia' dato il proprietario scegliendo quale chat aprire. E' il pezzo piu'
   fragile del disegno, eliminato da una scelta di prodotto.
6. **Niente Honcho per questo.** Sono due sistemi diversi: Honcho e' memoria
   episodica *sul proprietario* (attribuzione, timeline — il problema col 36,6%
   di attribuzione sbagliata). Il RAG di studio recupera *passaggi* da materiale
   in markdown: nessuna attribuzione, nessun fatto personale. Il secondo non ha
   bisogno del primo, e nemmeno di embedding per la v1 (2,4 MB si scorrono in
   millisecondi; `bge-m3` non e' neanche installato).

### Cosa si e' scoperto guardando il corpus, il 20 agosto

**Struttura e contenuto sono separati, e si uniscono gratis.**

```
markdown/dsml.md      1,4 MB    contenuto senza struttura (0 titoli `##`)
~/Obsidian/30-Note/   224 note  struttura senza contenuto (mediana 936 byte)
```

Le note sono segnalibri con un estratto troncato. Il markdown non ha titoli: le
176 righe che iniziano con `#` sono **commenti Python** finiti nel testo senza
recinto. Ma il frontmatter delle note porta `sezione`/`pagina`/`pagina_fine` e
il markdown porta i marcatori `<!-- pag N -->`. Misurato:

```
223 sezioni con pagina · coprono 1-533 · buchi fra sezioni consecutive: 0
```

Ogni pagina appartiene a esattamente una sezione. **Il recupero a due stadi si
costruisce da quello che c'e' gia': non manca il corpus, mancava la giunzione.**

Conseguenza pratica: **per collaudare il RAG non serve un PDF piu' piccolo.**
DSML era «troppo grande» per la *generazione* (4 ore di GPU), non per il
recupero, che non rimacina niente. Anzi: su dieci pagine qualunque ricerca
sembra funzionare. Un PDF piccolo serve solo per collaudare l'**ingestione** —
li' si usa il capitolo 1 ritagliato da DSML, perche' esiste gia' la versione
buona macinata dal libro intero come riferimento.
`Basic_Statistics_2007.pdf` resta il caso ostile: 10 pagine, **zero titoli**
(sono tipografici, non strutturali), su cui la rilevazione deve dire «non ci
sono» invece di inventarli.

### Il canale studio — i sei pezzi

Il pezzo 1 e' scritto: `INCARICO-studio-recupero.md`. Gli altri cinque sono
progettati qui e vanno scritti come incarichi quando il precedente e'
consegnato e misurato.

**1. Recupero (deterministico).** Giunzione sezioni<->pagine, ricerca a due
stadi, CLI. Niente modelli, niente GPU, niente rete. *Incarico scritto.*

**2. Il ciclo domanda -> risposta -> registro.** La domanda va al fisso;
recupero locale; se non trova, searxng + crawl4ai e la pagina diventa il
passaggio; `qwen3:8b` risponde **solo** sui passaggi, con riferimento. Tutto
finisce in `stato/registro.sqlite` (domanda, passaggi, risposta, fonti) —
**fuori dal vault**, altrimenti fra un mese la ricerca di Obsidian pesca 400
scarti. Tetto di latenza: **30 s** a fisso sveglio. Da misurare a parte: la
prima domanda dopo il sonno, che paga il magic packet.

**3. Il bot studio.** Secondo token BotFather, processo separato. La chat di
oggi non si tocca.

**4. `/elabora` e la notte.** Un solo codice, due inneschi (il timer e il
comando): due implementazioni della stessa cosa divergono, e quella che gira
meno marcisce in silenzio.
   - **preventivo prima di partire**, come intervallo e non come numero secco:
     mediana storica delle durate reali per categoria x quanti ce ne sono. Il
     punto di partenza e' la misura di `sbobina.py`: 6 sezioni in 323 s, ~54 s a
     pezzo su `qwen3:8b`. La verifica web va contata a parte: gira su CPU e
     rete, **non occupa la GPU e non blocca le domande**.
   - **il lock GPU si prende per singola nota, non per l'intera sessione.**
     Diverso da `sbobina.py`, che lo tiene per ore. Cosi' una domanda si infila
     fra una nota e l'altra: di pomeriggio il proprietario sta studiando proprio
     mentre l'elaborazione gira.
   - **`/elabora` aspetta Syncthing.** `~/Obsidian` e' una cartella Syncthing e
     il fisso di mattina dorme. Scenario reale: appunti presi in universita' sul
     portatile, il fisso dorme e non li riceve; alle 15 `/elabora` lo sveglia,
     parte subito, guarda un vault vecchio di un giorno e dice «niente da fare».
     Fallimento silenzioso, il guasto che qui si e' gia' ripetuto tre volte.
     Quindi: sveglia, **attende che Syncthing si dichiari allineato** (API locale
     su :8384, serve la chiave dal config) con un tetto di tempo, e **dichiara
     sempre il conteggio di cio' che ha visto** — «14 in sospeso» fa notare
     subito se ne mancano, «0» dice che qualcosa non ha sincronizzato.
   - **il filtro, due meccanismi per due casi.** `00-Inbox/` e' un nastro
     trasportatore: il proprietario ci butta le cose, il sistema elabora, scrive
     in `50-Studio/` e **sposta il suo file, intatto, in `30-Note/`**. L'Inbox si
     svuota e il progresso si vede — la stessa convenzione di `documenti/in/`.
     Per gli appunti gia' in `30-Note/` che lui rimette mano: **impronta del
     testo**, in sospeso = impronta cambiata. Non si sposta niente: spostare le
     note permanenti rompe link e preferiti, ed e' piu' invasivo che scriverci
     dentro. Il conteggio del preventivo esce gratis da questa stessa scansione.

**5. La consegna.** Sono tre, con tempi e destinatari diversi:

| cosa | dove | quando | chi inizia |
|---|---|---|---|
| la risposta | nello stesso canale della domanda | subito, <=30 s | il proprietario |
| la nota | vault, `50-Studio/` | **in silenzio** | nessuno |
| il lavoro notturno | una rassegna | **8:00** | il sistema |

   Il salvataggio e' **muto per progetto**: una notifica per ogni cosa salvata e
   in una settimana il bot e' silenziato. La rassegna e' un **indice di cosa e'
   cambiato**, quattro righe con una fine visibile, non il contenuto.
   **La smentita e' l'unica cosa che non aspetta**: se la verifica notturna
   trova sbagliata un'affermazione gia' salvata, arriva subito — quella nota
   potrebbe essere gia' stata studiata. Una nota nuova non letta e' un'occasione
   persa, una nota sbagliata gia' in testa e' un danno. E **non si corregge di
   nascosto**: resta, con la smentita accanto e la fonte.

**6. L'elaborazione notturna vera.** Il 4B passa il registro e decide cosa
merita, quali frammenti parlano della stessa cosa, quali affermazioni verificare.
Il grande scrive: sintesi dei frammenti, pezzo mancante di un orfano — **solo su
materiale gia' selezionato e verificato dal piccolo**.
   - **I pezzi mancanti hanno gia' un nome e il codice li conta gia'**:
     `_wikilink_risolti()` in `documenti.py:1204` confronta ogni `[[link]]`
     contro tutto il vault. **I link orfani sono i pezzi mancanti**, e sono la
     lista di lavoro della notte, calcolata gratis e senza modello. Oggi li
     conta per il rapporto: farglieli **elencare** e' poche righe.
   - **Mai cancellare, mai riscrivere l'esistente.** Una sintesi nuova che linka
     i frammenti, non al posto dei frammenti. Se il consolidamento sbaglia si
     perde una nota in piu', non il lavoro di un mese.
   - **Le cartelle del proprietario restano in sola lettura**, per costruzione.
     Vale doppio ora che il sistema scrive da solo mentre lui dorme.

**Dipendenza che diventa bloccante**: il ciclo notturno ha bisogno che il fisso
sia sveglio di notte, e oggi dorme dopo tre ore. Il Mac e' sempre acceso e
`mac/risveglio.py` manda gia' il magic packet: **il Mac sveglia il fisso alle 3,
il fisso lavora, poi torna a dormire**. Ma il lavoro deve prendere
`energia.blocco` per tutta la durata. La sezione 8-bis smette di essere «da
progettare con calma»: e' una dipendenza del pezzo 4.

### Ruoli, dal 20 agosto

- **opencode** costruisce (regola del 70/30, invariata).
- **agy** rivede, in `--mode plan`. Motivo: in headless i suoi tool sono
  auto-negati e le `permissions.allow` non sono ancora configurate (7-quinquies),
  ma in sola lettura non gli serve alcun permesso. Revisione indipendente a
  costo zero, senza toccare `settings.json`.
- **Claude** progetta, misura, verifica e supervisiona.

I lanci passano dal guardiano (`guardiano.esegui`, che ha gia' gli adattatori
per entrambi i motori): il 17 agosto tre sessioni su tre sono morte senza
consegnare e nessuno se n'e' accorto fino al giorno dopo.

### Cosa slitta, e va detto chiaro

Non sono cancellati, sono dopo ottobre o dopo che il canale studio funziona:

- **le 4 ore di sbobina su 214 sezioni** — producono un magazzino, e il
  magazzino non era il problema. Resta valida la correzione `CAR_PER_TOKEN`
  (1-ter) per quando si riprendera';
- le figure (`INCARICO-figure.md`), i pensieri (`INCARICO-pensieri.md`),
  Honcho / fase 3, Docling, `documenti/originali/`;
- `TOOL-DEFINITIVI.md`: i quattro tool restano fermi. Il canale studio non
  tocca `DEFINIZIONI` e non paga cache — e' proprio il motivo per cui e' un bot
  separato invece che un tool.

**Tronconi lasciati aperti il 17-18 agosto**, da chiudere o dichiarare morti:
`INCARICO-figure.md` (nessun rapporto), `INCARICO-lezioni.md` (`LESSONS.md` non
esiste), `INCARICO-salute.md` (rapporto scritto, `salute.py` mai nato).

---


## DOVE SIAMO — 17 agosto 2026, pomeriggio

Fatti oggi i passi 1 e 2 della sequenza qui sotto, piu' una riparazione che non
era in lista perche' nessuno l'aveva vista.

**La coda documenti era morta da 1 giorno e 19 ore, in silenzio.** ✅ RIPARATA —
vedi la sezione 1-bis. Un PDF messo in `documenti/in/` dal 15 agosto alle 17:20
non sarebbe stato macinato, e nessuno l'avrebbe detto.

**`dsml` rimacinato con le formule** (passo 2), 533/533 pagine:

```
formule marcate: 1815 · apici ricostruiti: 1718 · pedici ricostruiti: 1374
caratteri estratti: 936.277 (prima 911.417)
marcatori pagina: 533 su 533 pagine distinte, nessuna doppia
223 sezioni, 223 note + indice, wikilink 669/669 · corsia veloce
```

Le 224 note del vault sono state rigenerate. Il markdown e lo stato precedenti
sono in salvo nello scratchpad di sessione, non cancellati.

**Le tabelle passano da 1315 a 1168 (-147), e non e' una perdita.** Verificato
numericamente, senza guardare il testo: 142 dei 156 blocchi calati stanno su
pagine che **ora hanno recinti formula** — cioe' equazioni che il vecchio
rilevatore chiamava tabelle. I restanti 14 su 11 pagine sono spiegati dall'altra
correzione: il markdown vecchio e' del 15 agosto alle 12:15, mentre
`SOGLIA_DENSITA_TABELLA` e' entrata col commit `86dc6f4` alle **01:43 del 16**.
Quel markdown era prodotto dal rilevatore coi falsi positivi. Il calo somma due
correzioni volute.

**`prova_documenti.py`: TUTTO VERDE**, coi casi nuovi (coda esclusiva, scarto di
file sparito, ripresa, scansione rifiutata). Attenzione, e il difetto latente
della sezione 9 va corretto: il collaudo **cancella** le due fixture in
`documenti/elaborati/` (non le modifica come diceva questo file). Ripristinate con
`git checkout`; da rifare dopo ogni esecuzione, o da mettere in `.gitignore`.

**Progettato il "pensiero elaborato"**: `INCARICO-pensieri.md`, chiesto dal
proprietario oggi. Vedi la sezione 7-bis per cosa e' e in che ordine va fatto —
**non e' parallelizzabile** con il passo 3.

**Regola nuova dal proprietario, oggi: il lavoro si divide 70% opencode, 30%
Claude.** Scritta in `AGENTS.md`: il codice lo scrive opencode, a Claude restano
disegno, misure, verifica e memoria condivisa. E' un tetto, non un modo di dire.

**Il passo 3 e' in corso**: `INCARICO-sbobina-formule.md` scritto e lanciato su
`opencode-go/kimi-k2.7-code` alle 13:05 del 17 agosto — il modello che il 15
agosto ha consegnato completo **col rapporto**, mentre `glm-5.3` ha lasciato il
codice senza conclusioni. Lanciato attraverso un wrapper che tiene
`energia.blocco` per tutta la durata, cosi' il fisso non si addormenta sotto la
sessione (era il primo difetto latente della sezione 9), e con `timeout 3600`
esterno (era il terzo).

**Tre incarichi pronti, e l'ordine non e' negoziabile:**

| incarico | tocca | stato |
|---|---|---|
| `INCARICO-sbobina-formule.md` | `sbobina.py`, `prova_sbobina.py` | ✅ **consegnato e verificato** (13:39) |
| `INCARICO-ricerca.md` | solo `RICERCA-stato-arte.md` | ✅ **consegnato**, 3 citazioni verificate su 3 |
| `INCARICO-figure.md` | `documenti.py`, `prova_documenti.py` | 🔧 in corso, rivisto con la ricerca |
| `INCARICO-pensieri.md` | `sbobina.py` (estrae `modello.py`), `pensieri.py` nuovo | ⬜ **da correggere** prima di lanciarlo, vedi 7-quater |
| `INCARICO-salute.md` | `gateway.py`, `salute.py` nuovo, unit | 🔧 in corso (`glm-5.3`) |
| `INCARICO-lezioni.md` | solo `LESSONS.md` | 🔧 in corso (`kimi-k2.6`) |

**Non ancora scritto, e va fatto quando `sbobina.py` e' libero**: un incarico che
applica insieme la correzione di `CAR_PER_TOKEN` (1-ter) e il collaudo
dell'imbottitura reso capace di fallire (1-quater). Tocca `sbobina.py` e
`prova_sbobina.py`, e il suo collaudo **usa la GPU**, quindi non puo' partire
mentre gira la sessione figure — vedi il difetto della bandiera GPU nella sezione 9.

**Perche' figure non parte in parallelo, benche' i file non si sovrappongano**:
`INCARICO-sbobina-formule.md` chiede di verificare `prova_documenti.py` verde come
prova di non aver toccato i marcatori. Se la sessione figure sta modificando
`documenti.py` in quel momento, la sessione sbobina trova un collaudo rosso che
non ha causato lei e va a caccia di un difetto che non esiste. Costa piu' del
tempo che il parallelo fa risparmiare.

Il passo 4 (le 4 ore) resta bloccato dal giudizio del proprietario su **una**
nota — vedi la sezione 8. **E adesso c'e' anche un motivo tecnico per non
lanciarlo**: vedi 1-ter, `CAR_PER_TOKEN` va corretto prima.

---

## 1-quinquies. La sospensione ha mangiato 11 ore, e il guardiano non l'ha vista ⬜ DA CORREGGERE

Pagata la notte del **20 agosto 2026**. Due difetti distinti, uno dentro l'altro.

### `energia.blocco` non impedisce la sospensione. Mai l'ha impedita.

```
00:53:00  lanciata la sessione studio-recupero, tre blocchi energia attivi
01:22:52  systemd-logind: The system will suspend now!
12:29:28  resume — 11 ore e 7 minuti dopo
```

`energia.blocco()` scrive un file in `stato/blocca/` che viene letto **solo** da
`motivi_per_restare_svegli()` in `energia.py:282`, cioe' dalla decisione di
sospensione **di Elechim**. logind e KDE non lo vedono. Verificato con
`systemd-inhibit --list` mentre i tre blocchi erano attivi: **zero inibitori in
modalita' `block` sul sleep**. A sospendere e' stato PowerDevil.

E' la sezione 8-bis che si avvera: «il fisso puo' addormentarsi sotto un lavoro
vivo... finora e' andata bene solo perche' c'era qualcuno alla scrivania».
Quella notte non c'era nessuno. La ronda del codice l'aveva confermato alle
01:10, **dodici minuti prima del guasto**: «lavori lunghi lanciati a mano non
prendono `energia.blocco`... non ho trovato un wrapper generico».

**La correzione, gia' applicata per le sessioni a mano** (`tieni_sveglio.py`):

```
systemd-inhibit --what=sleep:idle --mode=block --who=Elechim \
    --why="..." <comando>
```

**Cosa resta da fare**: `energia.blocco()` deve prendere *anche* un inibitore
logind, non solo scrivere il suo file. Oggi ogni chiamante che voglia davvero
restare sveglio deve saperlo e aggiungerlo a mano — cioe' la trappola e' ancora
armata per il prossimo. Riguarda `documenti.py` e `sbobina.py`, che oggi
credono di essere protetti e non lo sono.

### Il guardiano non vede una sessione che muore attraverso una sospensione

Peggio del primo, perche' e' nello strumento costruito apposta per accorgersi
che una sessione muore in silenzio.

`guardiano.esegui` misura `silenzio_max` e `durata_max` con `time.monotonic()`.
**Su Linux l'orologio monotonico non avanza durante la sospensione.** Dopo 11
ore di sonno il guardiano credeva fossero passati 30 minuti: il tetto di 90
minuti non e' mai scattato, e la sessione ha continuato a emettere heartbeat
locali dal server opencode mentre il flusso verso il modello era morto da ore.

```
ultimo evento utile:  t=140s   00:55:20
poi:                  120 server.heartbeat, per 11 ore
esito del guardiano:  nessuno, la credeva viva
```

E' la stessa classe di guasto di `OnUnitActiveSec` che non avanza durante la
sospensione (gia' in `README.it.md` fra le lezioni), ricomparsa altrove.

**Correzione**: affiancare a `monotonic()` un controllo su `time.time()`, che la
sospensione la attraversa. Se i due orologi divergono di piu' di qualche
secondo, c'e' stata una sospensione e la sessione va dichiarata inaffidabile —
non ripresa, **abortita**: dopo undici ore la connessione al modello e' morta
comunque.

**Lezione generale, la terza di questa famiglia**: un timeout misurato con
`monotonic()` su una macchina che puo' dormire non e' un timeout. Vale per il
guardiano, per i timer systemd e per qualunque cosa scriveremo dopo.

---

## 1-sexies. `lavoro.py chiudi` non ha mai funzionato ⬜ CORREZIONE DI UNA RIGA

Trovato il 20 agosto provando a chiudere il worktree della ronda.

```
lavoro.py:227   conosciuto = any(wt.get("branch", "") == branch for wt in wts)
```

`_nome_branch()` produce `lavoro/<nome>`, ma `git worktree list --porcelain`
scrive `refs/heads/lavoro/<nome>`. Il confronto e' **sempre falso**, quindi
`chiudi` muore su «non e' un worktree git noto» per **qualunque** worktree, e la
fusione non avviene mai. Il worktree della ronda e' stato fuso a mano.

Non e' un caso limite: e' meta' del ciclo di vita dello strumento, e nessuno se
n'era accorto perche' finora nessun worktree era mai stato chiuso.

**Correzione**: confrontare togliendo il prefisso (`removeprefix("refs/heads/")`)
su entrambi i lati. Da fare insieme al resto dei rilievi della ronda.

**Attenzione quando si chiude a mano**: i symlink condivisi (`stato/`,
`markdown/`, `archivio/`, `.venv`) vanno rimossi **prima** di
`git worktree remove --force`, altrimenti si rischia di cancellare i bersagli
invece dei collegamenti. `lavoro.py` lo fa apposta (riga 241) e chi lo aggira
deve ricordarsene: `find <worktree> -maxdepth 2 -type l -delete`.

**Nota per la ronda**: `lavoro.py` era nel perimetro dichiarato e questo difetto
non e' stato trovato. Utile per calibrare quanto fidarsi del prossimo giro.

---

## 1-ter. Il margine di contesto e' stato speso tutto ⬜ DA CORREGGERE, prima delle 4 ore

Trovato il 17 agosto verificando la misura B di `RAPPORTO-sbobina-formule.md`. **Il
rapporto ha il numero giusto e ne trae la conclusione rovesciata**, quindi va letto
con questa nota accanto.

L'attesa era che togliendo le formule dal testo `CAR_PER_TOKEN` **salisse** (prosa
quasi pura, che tokenizza meglio della matematica). Misurato: **scende a 2,7444**
nel caso peggiore, contro il 3,06 assunto. Il rapporto conclude «tenere 3,06 resta
la scelta conservativa e sicura». **E' l'opposto**: nella formula

```
caratteri = (num_ctx - prompt - risposta) x (1 - margine) x CAR_PER_TOKEN
```

`CAR_PER_TOKEN` **moltiplica** il budget di caratteri, quindi un valore piu' alto
concede *piu* testo. 3,06 e' il valore **ottimista**, non quello prudente:

```
caratteri concessi            17.190
token reali a 2,7444           6.264   (preventivati: 5.618)
totale: 81 + 6.264 + 1.800   = 8.145   contro num_ctx 8.192
margine residuo                   47 token (0,6%)
margine progettato               624 token (10%)
```

Non trabocca **oggi**, e solo per una coincidenza: `TOKEN_PROMPT` e' sovrastimato
(150 assunti contro 81 misurati) e quei 69 token di scarto sono l'unica cosa che
tiene. Il margine del 10% — che esiste esattamente per impedire a ollama di
**tagliare la fonte in silenzio**, il guasto che il docstring di
`budget_caratteri` chiama il peggiore — e' consumato.

**Correzione**: `CAR_PER_TOKEN = 2.7444`, budget 15.417 caratteri (**-10,3%**).
Costa il 10% di pezzi in piu' e restituisce il margine. **Da fare prima di
macinare 214 sezioni**, altrimenti si lanciano 4 ore col margine azzerato.

---

## 1-quater. I nostri collaudi passano per ragioni strutturali ⬜ LEZIONE, terza occorrenza

E' il difetto che si ripete piu' spesso in questo progetto, e vale piu' di ognuno
dei bug che ha nascosto. **Tre volte** un'asserzione e' stata verde per costruzione,
cioe' non poteva fallire nemmeno col codice rotto:

| verifica | perche' era cieca | cosa nascondeva |
|---|---|---|
| «tre processi, tre exit 0» | la soglia di systemd e' **5** | la coda morta per 1g 19h (1-bis) |
| «marcatori distinti == pagine» | torna sempre `11 = 11` | le pagine duplicate (punto 2) |
| «imbottitura per tipo» | i due segnaposti sono **entrambi 77 caratteri** | niente, per fortuna |

Il terzo caso: `SEGNAPOSTO_TABELLA` e `SEGNAPOSTO_FORMULA` hanno la stessa
lunghezza perche' «tabella» e «formula» hanno le stesse lettere. L'imbottitura per
tipo e' **giusta** e regge se un giorno si cambia il testo, ma il collaudo che
dovrebbe proteggerla non esercita mai l'asimmetria. Va reso capace di fallire:
segnaposti di lunghezza diversa nel test (monkeypatch di `SEGNAPOSTI`).

**La regola generale che ne esce, da applicare a ogni collaudo nuovo**: quando si
prova un limite, la prova deve **superarlo**, non avvicinarsi; e quando si prova
una distinzione, i due casi devono **differire** nella dimensione che conta.
Chiedersi sempre: *se il codice fosse rotto, questa asserzione lo vedrebbe?*

---

## DOVE ERAVAMO — notte fra il 15 e il 16 agosto 2026, ore 01:20

**La sbobina di `dsml` NON e' ancora stata lanciata, ed e' voluto.** Lanciarla
adesso vorrebbe dire spendere 4 ore di GPU per riscrivere un testo in cui la
matematica e' gia' rovinata dall'estrazione, e rifare tutto dopo.

**La sequenza decisa, in quest'ordine:**

1. 🔧 `documenti.py` impara a ricostruire apici/pedici e a marcare le formule
   (`INCARICO-formule.md`, opencode in corso alle 01:20 — stava misurando le
   soglie di riconoscimento);
2. ⬜ **rimacinare `dsml`**: `documenti.py documenti/elaborati/DSML.pdf`, costa
   **70 secondi**, e rigenera markdown e note con la matematica a posto;
3. ⬜ `sbobina.py` protegge le formule dal modello **come gia' fa con le
   tabelle** — oggi le formule (16% delle righe) passerebbero tutte da un 8B.
   Va scritto un incarico: tocca `sbobina.py`, quindi non poteva partire mentre
   c'era l'altra sessione;
4. ⬜ **poi** partono le 4 ore: `sbobina.py dsml --tutte`.

**Prima di ripartire, una verifica unica** su tutto il codice messo insieme
stanotte da tre sessioni diverse: `prova_documenti.py` e `prova_sbobina.py`
entrambi verdi, e la **copertura su `dsml` vero** (l'invariante e' provata solo
sul sintetico, dove pero' `sezioni divise: 0` — cioe' il caso facile; su `dsml`
si divide davvero, 7 sezioni in 15 pezzi). Attenzione: `_chunk_fonte` **ha
cambiato firma**, ora torna `(chunks, statistiche)`.

**Fatto stanotte, tutto verificato:** chunking adattivo col budget derivato da
`num_ctx` (17.190 caratteri contro la costante 9.000), cascata dei confini
naturali, **0 sezioni saltate** dove prima se ne perdevano 46 pari a **meta' del
libro**, rapporto di copertura con l'invariante `caratteri_coperti ==
caratteri_fonte` come asserzione permanente, e `fusione.py` con RRF (nove casi
verdi) pronto per `ricorda` della fase 3.

---

## 0. Il blackout: nessun danno

Corrente staccata per un temporale, fisso e Mac riavviati. **Tutto e' risalito da
solo**: tunnel, gateway, searxng, crawl4ai, syncthing, il path unit della coda,
il bot sul Mac via launchd. Zero unit di sistema fallite.

Il rapporto automatico dopo il riavvio dice **0 errori kernel (EDAC/Xid)**,
contro i 6 della sessione precedente. Le due unit utente fallite sono gli
autostart di `nvidia-settings` e PowerMizer: rumore del desktop, non c'entrano
con Elechim.

---

## 1. Bug: la coda documenti si fermava ✅ CORRETTO

**Sintomo.** `elechim-documenti.service` usciva 1 e la coda restava ferma.

**Analisi.** Due difetti distinti che si sommavano.

*Il primo e' una corsa.* Il path unit sorveglia `documenti/in/*.pdf` e il
servizio svuota **proprio quella cartella** spostando i file finiti: la
condizione cambia mentre il lavoro e' in corso e systemd fa ripartire il
servizio sopra quello vivo. Il 15 agosto sono partiti due processi nello stesso
secondo; il secondo ha fatto `glob()` su una lista che il primo stava svuotando
e si e' ritrovato il PDF sparito a meta' elaborazione:

```
RuntimeError: comando fallito: pdfinfo .../documenti/in/prova-due-colonne.pdf
I/O Error: Couldn't open file ... No such file or directory
```

*Il secondo e' nel gestore d'errore.* Il blocco `except` che deve garantire «`in/`
si svuota sempre» faceva `shutil.move` di un file che `processa` aveva **gia'**
portato in `elaborati/`. Quel secondo `FileNotFoundError` partiva da dentro il
gestore, non lo prendeva nessuno, e il servizio moriva: **la coda si fermava
esattamente per il guasto che quel gestore esiste per evitare.**

**Correzione.**

- `_coda_esclusiva()` in `documenti.py`: `flock` non bloccante. Chi arriva
  secondo esce con **codice 0** — non e' un guasto, e uscire 1 farebbe segnare
  `failed` alla coda. Non e' stato riusato `energia.blocco`: quello scrive il
  proprio PID sopra quello di chi c'era, perche' il suo mestiere e' tenere
  sveglio il fisso, non escludere.
- `_scarta()`: controlla che il file esista prima di spostarlo, e scrive accanto
  un `<nome>.ragione.txt` col motivo. Senza, fra un mese in `falliti/` c'e' un
  PDF e nessun modo di sapere perche'.
- `_macina()` rilegge la cartella a ogni giro invece di fidarsi di una `glob()`
  sola: i PDF arrivati mentre macinava un documento da 533 pagine entrano in
  **questo** giro.

**Verifica.** Riprodotta la corsa vera — due istanze a mano piu' il path unit
che scatta: **tre processi, tre exit 0**, `Result=success`, `in/` svuotata,
11/11 pagine, 9/9 wikilink. Due casi permanenti aggiunti a `prova_documenti.py`
(`test_coda_esclusiva`, `test_scarto_file_sparito`).

---

## 1-bis. La correzione del punto 1 ha ucciso la coda ✅ CORRETTO il 17 agosto

**Il punto 1 qui sopra ha risolto la corsa e introdotto un guasto peggiore**,
perche' silenzioso. Scoperto il 17 agosto facendo il punto della situazione, non
da un allarme: nessuno se ne era accorto.

```
× elechim-documenti.service   failed (Result: start-limit-hit)        dal 15 ago 17:20
× elechim-documenti.path      failed (Result: unit-start-limit-hit)
```

**Il meccanismo.** Il `flock` fa uscire con codice 0 chi arriva secondo — ed e'
giusto. Ma il path unit riscatta finche' `in/*.pdf` e' vero, e quella condizione
resta vera per tutto il tempo in cui il primo macina. Il default di systemd e' **5
avvii in 10 secondi**. Il journal del 15 agosto mostra **dieci avvii fra 17:20:05
e 17:20:38, tutti riusciti**, tutti "coda gia' in lavorazione, esco". Al sesto
systemd ha dichiarato `start-limit-hit` sul servizio, il fallimento **si e'
propagato al path unit**, e la sorveglianza si e' spenta. Per 1 giorno e 19 ore.

**Perche' la verifica del punto 1 non poteva vederlo.** Diceva «tre processi, tre
exit 0, `Result=success`»: era vera, ed era cieca. **Tre sta sotto la soglia di
cinque.** E' la stessa forma della trappola del punto 2 — un'asserzione che per
costruzione non puo' fallire. Quando si prova un limite, la prova deve
**superarlo**, non avvicinarsi.

**Nota importante: `start-limit-hit` era gia' conosciuto**, e il commento in
`documenti.py:1074` lo descrive — ma per un innesco diverso: un PDF **gia' fatto**
che resta in coda. La guardia aggiunta la' sposta il file in `elaborati/` e rompe
il ciclo. Non copre questo caso, e non poteva: **chi esce per il lock non puo'
spostare niente**, il file e' in mano al primo. Stessa firma nel journal, due
cause distinte, una sola corretta. Vale al contrario la lezione del punto 2: un
sintomo solo puo' avere **due** cause.

**Correzione.** `StartLimitIntervalSec=0` nel `[Unit]` di
`elechim-documenti.service`, col commento che spiega il perche'. Alzare il burst
non basta: gli avvii sono **illimitati per costruzione**, non tanti.

**Verifica**, quella che il punto 1 non aveva fatto: lock tenuto da fuori con
`flock` su `stato/documenti/.coda.lock` e **dodici** avvii di fila in 2 secondi —
piu' del doppio della vecchia soglia.

```
avvii riusciti: 12   falliti: 0   in 2s
service: success   path: success   path attivo: active
```

**Da tenere**: un servizio `oneshot` innescato da un path unit che sorveglia la
cartella che il servizio stesso svuota **deve** avere il limite di frequenza
disattivato. Uscire con successo tante volte non e' un guasto, ma systemd non
sa distinguerlo da un crash loop.

**Difetto residuo, non corretto**: la coda risale da sola al riavvio, quindi il
sintomo e' intermittente e puo' tornare a nascondersi. Manca un allarme su
`elechim-documenti.path` non attivo — `verifica_avvio.py` guarda le unit dopo il
riavvio, ma nessuno guarda **durante**.

---

## 2. Bug: la ripresa duplicava le pagine ✅ RISOLTO — non era un bug a se'

**Sintomo.** `markdown/prova-due-colonne.md` contiene **18 marcatori di pagina
per 11 pagine**: le pagine 5-11 scritte due volte.

```
occorrenze per pagina: {1:1, 2:1, 3:1, 4:1, 5:2, 6:2, 7:2, 8:2, 9:2, 10:2, 11:2}
```

**Perche' e' grave.** Su un libro vero interrotto da una sospensione — che e' il
caso **normale**, il fisso dorme da solo dopo tre ore — significa integrale
doppio, sezioni doppie e conteggi gonfiati. Gli altri quattro documenti sono
puliti solo perche' non sono mai stati interrotti a meta'.

**Analisi — e qui la diagnosi iniziale era sbagliata.** Sembrava un difetto di
idempotenza in `genera_markdown`, che riprende da `ultima = max(pagine gia'
presenti)`. **Non lo era.** Era la stessa corsa del punto 1, vista dall'altro
capo: il collaudo scriveva i PDF in `documenti/in/` senza prendere il lock, il
path unit faceva partire il servizio in parallelo, e **due processi scrivevano
lo stesso markdown**. Le pagine 5-11 non erano riscritte da una ripresa
difettosa: erano scritte due volte da due processi diversi.

**Correzione.** Nessuna modifica a `genera_markdown`. Il lock del punto 1 toglie
la causa, e il collaudo ora prende `_coda_esclusiva()` **prima** di creare i PDF
e lo tiene finche' macina. Verificato: occorrenze == pagine su tutti i
documenti, e `test_interruzione` arriva in fondo con la sua asserzione.

**La lezione da tenere**, che vale piu' della correzione: due difetti che si
presentano in posti diversi — un servizio che esce 1 e un markdown con le pagine
doppie — possono avere **una causa sola**. Cercare la seconda causa dove non c'e'
costa piu' del bug.

**La trappola nella verifica, che resta valida.** Il difetto era stato
dichiarato risolto contando i marcatori **distinti** e confrontandoli con le
pagine totali: torna sempre `11 = 11` e **per costruzione non puo' vedere
nulla**. L'asserzione giusta conta le **occorrenze**:

```python
assert md.count("<!-- pag ") == pagine_totali
```

Quell'asserzione **esisteva gia'** in `test_interruzione`, e non proteggeva
perche' il collaudo si fermava prima, sul rosso del punto 3: *un test che non
viene raggiunto non protegge niente.* Adesso il collaudo arriva in fondo.

---

## 3. Bug: le tabelle erano falsi positivi ✅ CORRETTO (opencode)

**Sintomo.** `prova_documenti.py` e' **rosso**, e lo era gia' al commit pubblico:

```
percorso font-size (PDF senza indice)...
AssertionError: tabelle_conservate == 2, atteso 1
```

Su `Basic_Statistics_2007.pdf`: **42 tabelle su 10 pagine**, di cui **26 per piu'
del 50% lettere**, cioe' paragrafi di prosa. Densita' media di cifre 2,9% contro
il ~40% di una tabella vera.

**Analisi.** `_e_tabella` dichiara tabella una riga con due o piu' spazi ampi. Su
una pagina a due colonne quel vuoto e' **lo spazio fra le colonne**: il
rilevatore sta trovando l'impaginazione, non le tabelle.

**Correzione.** `_e_tabella` ora richiede anche una **densita' minima di cifre**
(`SOGLIA_DENSITA_TABELLA = 0.10`) quando trova due o piu' vuoti ampi: la prosa a
due colonne ha un solo vuoto ampio e densita' sotto l'1%, una tabella ne ha piu'
d'uno ed e' ricca di cifre.

**Misura**: su `Basic_Statistics_2007.pdf` i falsi positivi passano da **42 a
13**, e il sintetico continua a trovare la sua tabella vera (`1`, non `0`).

Nota: il rosso del collaudo **non era il rilevatore**. Il rilevamento sul
sintetico era gia' corretto; il `2` veniva dalla pagina duplicata del punto 2.
Il difetto sui documenti veri era invece reale, ed e' quello corretto qui.

---

## 4. Bug: le scansioni fallivano in silenzio ✅ CORRETTO (opencode)

**Il piu' pericoloso del sistema, ed e' pericoloso perche' non fa rumore.** Su
una scansione senza livello di testo la pipeline estrae **3 caratteri contro
3.610**, non dice niente e archivia il vuoto. Te ne accorgi mesi dopo, quando
cerchi quel documento e non c'e'.

**Correzione.** `classifica()` guarda il documento prima di lavorarlo:
`caratteri_pagina()` conta i caratteri non-spazio per pagina, piu' livello di
testo e outline. Sotto `SOGLIA_CARATTERI_PAGINA = 100` di **mediana** il
documento non produce note: va in `falliti/` con la ragione scritta. Il rapporto
di copertura dichiara ora la **corsia** usata e la mediana di caratteri/pagina.

**La soglia e' misurata, non inventata:**

| documento | pagine | mediana caratteri/pagina | esito |
|---|---|---|---|
| sintetico `prova-due-colonne` | 11 | 770 | corsia veloce |
| `DSML.pdf` | 533 | 1.606 | corsia veloce |
| scansione sintetica (`pdftoppm` + Pillow) | 11 | **0** | **rifiutata** |

100 sta molto sotto ai documenti veri e molto sopra a una scansione. Il collaudo
ha un caso permanente: la scansione viene rifiutata, finisce in `falliti/` con
la ragione, e **non lascia note nel vault**.

---

## 5. La trappola della depersonalizzazione ✅ CORRETTO

Pubblicare il repo ha sostituito il nome proprio con "il proprietario" e i path
con `NOME_UTENTE` **anche dentro file che girano**. Due danni veri:

- **`mac/core.py`**: il `SYSTEM_PROMPT` versionato diceva "assistente personale
  del proprietario". Sincronizzare avrebbe peggiorato il prompt **e** cambiato il
  prefisso della cache, cioe' prefill pieno (~340s a 8K token) su ogni
  conversazione viva.
- **`opencode.json`**: `/home/NOME_UTENTE/.config/containers/systemd/*` non
  agganciava piu' nessun permesso reale.

**Correzione.** Il nome si legge da `mac/.env` (`PROPRIETARIO`), il path usa
`{env:HOME}`. Verifica che conta: col valore a posto il prompt torna **byte per
byte** quello di prima — 2090 caratteri, `sha256 87ccb758c121ddf9` — quindi la
sincronizzazione **non ha azzerato la cache**. Bot sincronizzato e risalito,
`DEFINIZIONI` identica su tutte e tre le copie (fisso, `mac/`, Mac vivo).

**La regola che ne esce**: un file eseguibile non si depersonalizza in place. O
il dato si legge da `.env`, o la copia pubblica e' distinta da quella che gira.

---

## 6. La memoria condivisa era vecchia ✅ CORRETTO

`AGENTS.md` diceva «fase 4 ❌, il vault e' vuoto» con **233 note gia' dentro**, e
il README diceva «non legge PDF». E' il ponte da cui parte ogni sessione di
opencode: una fotografia vecchia moltiplica gli errori invece di risparmiare
tempo.

Riscritti la sezione "Stato" di `AGENTS.md` e il README (nuova sezione sui
documenti, con le lezioni e le misure). I cinque incarichi consegnati sono
marcati con data ed esito, cosi' non si confondono con quelli aperti.

---

## 7. Il da fare, in ordine di dipendenza

### Consegnato dal lavoro in parallelo del 15 agosto ✅

| filone | modello | esito |
|---|---|---|
| tabelle + scansioni (punti 3 e 4) | `kimi-k2.7-code` | **completo**, rapporto consegnato, collaudo verde |
| sbobina, stadio due della fase 4 | `glm-5.3` | **codice completo e funzionante**, rapporto mancante |

Entrambe le sessioni si sono poi **piantate su una connessione morta** verso
l'API (vedi la sezione 10): il lavoro sul disco e' buono, ma nessuna delle due
ha potuto scrivere le conclusioni. Il primo aveva gia' fatto in tempo.

### Sbobina — cosa manca per chiuderla ⬜

`sbobina.py` (19,5KB) e `prova_sbobina.py` ci sono e il **collaudo e' verde**,
provato di persona sul PDF sintetico:

```
6 sezioni riscritte su 6 · 0 numeri segnalati · 323s
qwen3:8b (500a1f067a9f) · 13,1-13,5 tok/s · 6.751 MiB di VRAM
```

Fa le cose giuste: due chiamate separate (spiegazione e punti, mai una che
chiede due cose), tabelle isolate e ricopiate **verbatim** con un segnaposto al
loro posto nel testo che va al modello, verifica di ogni numero generato contro
la sorgente, `<think>` ripulito, stato **per sezione**, e il lock GPU di
`gateway.py` — sfratta `qwen3-vl` e whisper, e **li rimette a posto alla fine**
(verificato: VRAM rientrata a 5.337 MiB, la visione risponde).

Restano tre cose, tutte corte:

1. **Il confronto fra modelli.** L'incarico ne chiedeva due o tre misurati; c'e'
   solo `qwen3:8b`. Un secondo candidato era scaricato al 43% quando la sessione
   si e' piantata.
2. **Una nota vera** riscritta su una sezione di `dsml`, **da non leggere**: il
   percorso va nel rapporto, la qualita' la giudica il proprietario. 👤
3. **`RAPPORTO-sbobina.md`**, che non e' stato scritto.

**Non lanciare le 214 sezioni** prima che il proprietario abbia visto una nota:
se il professore non e' all'altezza si cambia modello, e sarebbero un'ora di GPU
e 214 note buttate.

### Subito dopo ⬜

1. **Le figure** — misurate il 17 agosto, incarico pronto in `INCARICO-figure.md`.
   `90-Allegati/` e' vuota e `figure()` conta senza estrarre. Il `267` del
   rapporto e' sbagliato in tre modi: include `smask` e `stencil` (che sono
   canali alfa di altre immagini, 26), meta' sono **glifi** (mediana del lato
   minore: **46px**; su una pagina sola 50 immaginette da 29x29 tutte diverse), e
   6 hash coprono 99 file. La cascata misurata:
   `267 -> 168` (via gli hash ripetuti) `-> 25` (via il lato minore < 64px)
   `-> 24` (via le proporzioni oltre 8:1). **24 figure raster vere su 11 pagine.**

   **La lezione, che va contro l'intuizione: il filtro giusto e' l'hash del
   contenuto, non la dimensione.** La forma **piu' grande del libro**
   (2368x2800, 24 occorrenze) e' **un hash solo**, cioe' una decorazione ripetuta:
   un filtro "tieni le immagini grandi" la promuoverebbe a figura principale 24
   volte. E le 46 immagini da 600x500 sono **due** hash ripetuti 23 volte
   ciascuno — somigliavano tantissimo a 46 grafici esportati alla stessa
   dimensione, e non lo erano. Dimensioni identiche non sono contenuto identico:
   solo l'hash lo sa.

   **E il difetto piu' grosso: le figure del libro sono vettoriali.** 24 figure su
   11 pagine in un libro di statistica da 533 non e' credibile. Contando gli
   elementi di disegno con `pdftocairo -svg` su 43 pagine sparse: mediana 232 per
   pagina, p90 813, e il 6% del campione oltre 4x la mediana, cioe' **~37 pagine
   con figure vettoriali** che `pdfimages` non vede per costruzione. Oggi vediamo
   un quarto delle pagine con figure e ne conserviamo **zero**. Si rendono con
   `pdftocairo` a livello di **pagina** (non si ritaglia: e' un problema piu'
   difficile, dichiarato come limite). Totale ~61 chiamate a `qwen3-vl`, **~8
   minuti** di GPU.
3. **`documenti/originali/`**: la decisione delle tre cartelle (originale /
   arricchito nel vault / integrale fuori) non e' applicata, oggi c'e'
   `elaborati/`.

### Poi ⬜

4. **Le foto degli appunti a mano.** `qwen3-vl:4b` e' gia' installato e in
   servizio: probabilmente e' la cosa che il proprietario usera' di piu', e non
   serve niente di nuovo. Va solo verificato che una foto passata a `visione.py`
   produca testo utile. 👤 la prova la fa il proprietario, in locale.
5. **Docling** come seconda corsia (CPU, prende anche DOCX/PPTX/HTML), solo dopo
   che i punti 3 e 4 sono chiusi.
6. **Fase 3, Honcho**: Postgres+pgvector, Redis, `bge-m3`, LLM di ingestion su
   ollama. **Mai il modello del Mac**: sfratterebbe la conversazione dall'unica
   slot di cache. E' il prerequisito di `ricorda`/`salva`, dell'elaborazione
   appunti e del dreaming mode.
7. **`INCARICO-elaborazione-appunti.md`**: dipende dai titoli (fatti) e, per i
   collegamenti semantici veri, dalla fase 3.

### Ultimo atto, quando 3 e 4 sono entrambe pronte ⬜

**Applicare `TOOL-DEFINITIVI.md`**: i quattro tool (`cerca`, `leggi`, `ricorda`,
`salva`) si aggiungono **tutti insieme, una volta sola**, perche' toccare
`DEFINIZIONI` invalida la cache di ogni conversazione. La procedura e' scritta
li'. La prima conversazione dopo va fatta con `/nuova`.

---

## 7-bis. Il pensiero elaborato — `INCARICO-pensieri.md` ⬜ NUOVO, 17 agosto

Chiesto dal proprietario oggi: mandare un pensiero e ritrovarselo elaborato in
`50-Pensieri/` **come se fosse discusso fra colleghi**. Incarico scritto, da dare
a opencode. Le quattro decisioni di progetto che non vanno rimesse in discussione:

1. **Non e' un quinto tool.** E' `/pensa`, un **comando del bot**, instradato
   prima che il modello veda il messaggio. Un tool nuovo vorrebbe dire toccare
   `DEFINIZIONI` e pagare un prefill pieno su ogni conversazione viva, e i quattro
   di `TOOL-DEFINITIVI.md` entrano **in un colpo solo** quando fase 3 e 4 sono
   pronte. Quando quel giorno arriva, `pensa` diventa un tool e la pipeline e'
   gia' sotto.
2. **Gira sul fisso** (`qwen3:8b` + lock GPU), il Mac riceve ~200 token di
   conferma. Leggere l'elaborazione gli costerebbe minuti di prefill per niente.
3. **Non e' una chat**: cinque chiamate separate e corte, una per ruolo, ognuna
   che vede solo il suo input. Un dibattito a piu' giri ri-prefilla il transcript
   a ogni turno — 5 minuti a giro sul Mac, e sfratta la conversazione.
4. **Il pensiero resta verbatim in cima alla nota.** La discussione si rigenera
   rilanciando, il pensiero no: e' l'unico pezzo irripetibile. Stessa regola dei
   documenti, *l'integrale e' la verita'*.

**Il difetto da battere e' che il modello e' d'accordo con se stesso**: chi
obietta e chi propone sono gli stessi pesi, e l'obiezione esce come un complimento
riformulato. Contromisure nell'incarico, e una e' **misurabile** — se l'obiezione
sovrappone troppi n-grammi con la riformulazione e' un'eco, si rifa' la chiamata,
e al secondo fallimento la nota lo **dichiara** invece di spacciarla per critica.

**Sequenza, e qui sta il vincolo che si paga se lo si ignora:
`INCARICO-pensieri.md` e il passo 3 (formule nella sbobina) toccano
`ENTRAMBI` `sbobina.py`** — il primo per estrarne `modello.py`, il secondo per
proteggere le formule. **Non vanno lanciati in parallelo.** E' esattamente il
motivo per cui il 15 agosto il passo 3 non e' potuto partire («tocca `sbobina.py`,
quindi non poteva partire mentre c'era l'altra sessione»). Ordine consigliato:
**prima il passo 3**, che e' corto e sblocca le 4 ore; poi i pensieri.

---

## 7-ter. La ricerca sullo stato dell'arte ✅ FATTA — `RICERCA-stato-arte.md`

Chiesta dal proprietario il 17 agosto: *«Non ci sono metodi che possiamo copiare?
Se non dobbiamo re-inventare la ruota è meglio.»* Eseguita da
`opencode/deepseek-v4-flash-free` (modello gratuito) via searxng locale, con la
regola «ogni affermazione ha un URL aperto, e dove non c'e' niente si scrive *non
trovato*». **Tre affermazioni portanti verificate a mano su tre**, quote incluse:
il titolo di arXiv 2608.01463, il «universal antidote» di 2502.08788, e i flag di
PyMuPDF. Il file e' affidabile.

I sei verdetti: figure **PRENDERE L'IDEA** · apici/pedici **TENERE IL NOSTRO** ·
pipeline PDF→markdown **PRENDERE L'IDEA** · tabelle **TENERE IL NOSTRO** ·
ragionamento **TENERE IL NOSTRO + due aggiunte** · chunking **PRENDERE L'IDEA**
(solo il merge di docling).

**Le tre cose che valgono:**

1. **La sessione sui pedici non era la ruota.** Nessuna libreria espone un flag
   pedice: PyMuPDF ha `TEXT_FONT_SUPERSCRIPT = 1` e **nessun**
   `TEXT_FONT_SUBSCRIPT`, e il mantainer dichiara che «non c'e' modo di rilevare i
   pedici». Di piu': la doc dice che l'apice e' *«computed by MuPDF and not part of
   any font information»*, cioe' **anche li' e' un'euristica geometrica**. Non
   esiste una fonte di verita' che ci stavamo perdendo. E ci siamo risparmiati
   l'AGPL di PyMuPDF, che in un repo pubblico e' un vincolo vero.
2. **L'hash per le decorazioni era gia' la pratica raccomandata**, non una nostra
   invenzione: il mantainer di docling consiglia `PictureItem._image_to_hexhash`
   per le immagini ripetute. Avevamo ragione, e ora c'e' un vocabolario stabilito
   (`furniture`, `background`, `PAGE_HEADER`).
3. **Il ritaglio del riquadro vettoriale e' seconda corsia, non corsia veloce**:
   vuole torch, e DocLayout-YOLO e' **AGPL-3.0**. Il render a pagina intera resta
   il comportamento giusto e il fallback permanente.

## 7-quater. `INCARICO-pensieri.md` va corretto prima di lanciarlo ⬜

La ricerca colpisce una decisione del disegno, e va registrato perche' e' il genere
di cosa che si riapre fra un mese.

**Su Qwen3-8B — il nostro modello — forzare prospettive divergenti esplicite
peggiora i risultati**: StrategyQA scende a **68,4 contro 91,8** del semplice CoT
(LMAD, arXiv 2608.01463, che mette i modelli piccoli in tabella). La lezione
dichiarata li': *temperature diverse e input isolati si', persone opposte esplicite
no*. Il nostro «chi obietta» **e'** una persona opposta esplicita.

**Perche' non si butta comunque**: quel benchmark e' QA multi-hop con **una
risposta giusta**, dove l'avvocato del diavolo spinge lontano dalla risposta
corretta. Da noi non c'e' una risposta giusta e **l'obiezione e' il prodotto**, non
un mezzo. Il modo di fallimento misurato potrebbe non trasferirsi, e la ricerca lo
dice («per la nostra esatta combinazione: non trovato»).

**Le correzioni da fare, tutte supportate da misure:**

- **Chi obietta gira su un modello diverso** da chi riformula. L'eterogeneita' dei
  modelli e' l'«antidoto universale» misurato (arXiv 2502.08788), ed e' la
  mitigazione meglio supportata di tutte. Costa poco: un secondo modello piccolo.
- **Temperature diverse per ruolo** (misurato), invece di persone contrapposte.
- **`self-BLEU` e `distinct-n`** per l'invariante anti-eco, invece di inventare una
  soglia di n-grammi: sono metriche pronte e calcolabili senza modello. Il *gate di
  rifacimento* resta nostro — non esiste in letteratura («non trovato»).
- **Il valore reale non e' la discussione**: *Large Language Models Cannot
  Self-Correct Reasoning Yet* (2310.01798) mostra che l'autocritica senza feedback
  **esterno** non migliora niente. Quindi il pezzo che porta valore nel nostro
  disegno e' la **verifica deterministica dei numeri contro la fonte**, non i cinque
  ruoli. Da tenere presente quando si giudichera' la prima nota.

---

## 7-octies. Il lock GPU e' vero ✅, e `CAR_PER_TOKEN` e' corretto ✅

Consegnato il 17 agosto sera. `energia.riserva_gpu(chi, timeout)`: `flock`
non bloccante in un ciclo d'attesa — cosi' puo' avere un timeout — con default
**6 ore**, che e' la scelta giusta perche' una sbobina ne dura 4. Usato da
`gpu_della_sbobina` e da `gpu_delle_figure`. Il kernel rilascia il lock anche su
`SIGKILL`: e' la proprieta' per cui si usa `flock` invece di un file col PID.

**Provata la mutua esclusione**, misurando **l'ordine** e non solo che finissero
entrambi (era la trappola da evitare, quarta occorrenza della sezione 1-quater):
due processi, il primo tiene il lock 3s, **il secondo aspetta 3,0s**.

`CAR_PER_TOKEN = 2.7444`, budget **15.417** caratteri (-10,3%): il margine di
contesto e' tornato, e il blocco tecnico alle 4 ore e' rimosso.

Il collaudo dell'imbottitura ora sostituisce `SEGNAPOSTI` con lunghezze diverse,
quindi **puo' fallire**. `prova_sbobina.py` e `prova_documenti.py` entrambi
verdi, rieseguiti a mano.

**⬜ Due cose restano aperte su questo pezzo:**

1. **`RAPPORTO-lock-gpu.md` non e' stato scritto** — la sessione e' uscita a 4,9
   minuti col codice buono e senza conclusioni. Ancora una volta.
2. **Difetto trovato con una prova, non nel rapporto**: il messaggio d'attesa non
   dice mai **chi** tiene la GPU, stampa sempre «altro processo». Causa:
   `open(GPU_LOCK, "w")` **tronca il file**, quindi chi aspetta cancella
   l'identita' di chi lo tiene prima di poterla leggere. Correzione: aprire in
   append e troncare **dopo** aver preso il lock. E' proprio la parte chiesta
   perche' «un'attesa silenziosa di venti minuti e' indistinguibile da un blocco».

---

## 7-novies. Come si fanno le ricerche ✅ — `RICERCA-strumenti.md`

Chiesta dal proprietario: *«Le risorse sul web sono tante e spesso inesplorate»*,
con la segnalazione di `D4Vinci/Scrapling`.

**Scrapling: no.** Non toglie **nessuno** dei guasti che abbiamo misurato — e'
un framework anti-bot per pagine che non ci hanno mai bloccato. crawl4ai oggi ha
reso 38/40 e 37/40 pagine a 1,3s e 0,6s medi. Buon progetto (74.780 stelle),
soluzione a un problema che non abbiamo. Da rivalutare **solo** se un giorno una
pagina vera ci blocca con un anti-bot.

**Quello che toglie il guasto davvero:**

- **Un token GitHub a sola lettura**: da **60 a 5.000** richieste/ora. E' la
  risposta al guasto misurato (6 repo dichiarati inesistenti a torto per rate
  limit). Fine-grained **senza permessi espliciti**: i repo pubblici si leggono
  comunque. Va in `.env`, con `GITHUB_TOKEN=` aggiunto a `.env.example`. 👤
- **Due regole di disciplina**, che sono buchi veri del nostro metodo:
  - **registrare le query** in una sezione «come ho cercato»: oggi nessuna
    ricerca e' riproducibile, e non si distingue «non trovato» da «non cercato»;
  - **mai «non trovato» per rate limit**: su 403/429 si legge
    `x-ratelimit-remaining` e si **cambia fonte**. E' esattamente l'errore fatto
    stasera guardando i repo di `RICERCA-ridondanza.md`.

**Per il «quadro sempre chiaro» non serve un servizio**: GitHub pubblica feed
Atom (`releases.atom`, `tags.atom`, `commits.atom`) gratuiti e **senza token**, e
noi abbiamo gia' timer systemd e bot Telegram — lo stesso pattern della coda.
Scartati `newreleases.io` e `changedetection.io`: vogliono un account esterno o
un container in piu' per la stessa cosa. **Massimo otto repo sorvegliati**: una
lista lunga e' il modo in cui la sorveglianza muore.

**Nota di metodo**: questo rapporto ha **33 URL**, quello sulla ridondanza ne
aveva **zero**. La differenza non e' il modello, e' che qui l'URL accanto a ogni
affermazione era un **criterio di uscita dichiarato**. Va messo in tutti gli
incarichi di ricerca, insieme alla sezione «come ho cercato».

---

## 7-septies. La ricerca sulla ridondanza ✅ — `RICERCA-ridondanza.md`

Chiesta dal proprietario il 17 agosto sera: *«Secondo me sono problemi gia'
risolti da altre persone.»* Impostata al contrario delle precedenti: **parti
dall'ipotesi che il nostro sia ridondante e prova a dimostrarlo**, perche'
`RICERCA-stato-arte.md` aveva concluso «teniamo il nostro» su 4 punti su 6
giudicando il lavoro di casa.

**Esito: niente da adottare in blocco, tre cose da provare.**

- **`book-to-skill`** (★22.498, MIT, attivissimo) e' il piu' vicino alla fase 4,
  e la meta' deterministica somiglia alla nostra. Ma la strutturazione **non e'
  codice, e' un prompt**: la fa l'agente ospite, **in cloud di default**, e il
  README lo ammette. Per il nostro veto e' fuori. Non protegge tabelle e formule,
  non verifica i numeri, non produce note Obsidian.
  **Ma valida la nostra architettura**: «estrai in locale, poi l'agente vede solo
  il capitolo giusto» e' la nostra regola del Mac che non vede mai il documento,
  raggiunta da qualcun altro per conto suo. La differenza e' **dove si traccia la
  linea dell'LLM**: loro dopo l'estrazione, noi dopo la strutturazione.
- **`needle`** (Apache-2.0, team vero): **non c'entra**. E' un modello da 45M
  parametri per il tool calling in 28MB di RAM, non recupero e non memoria.
- **VaultForge** e' il concorrente diretto sul pezzo 1 (PDF -> note atomiche con
  wikilink su Obsidian) ma e' **★10, un solo manutentore, semiattivo, e tutta la
  strutturazione e' LLM in cloud**: non e' una dipendenza. Da rubare **l'idea**
  del suo imbuto di link-building deterministico (struttura -> TF-IDF ->
  euristiche -> LLM solo sui candidati) invece di lasciare i wikilink al modello.
- **`groundguard`** impacchetta la verifica «numeri contro la fonte» con un tier
  lessicale BM25 senza LLM e un verdetto `NOT_GROUNDED`. Da provare in un venv di
  scarto su sezioni con numeri alterati di proposito.
- **Graphiti** (Apache-2.0, progetto serio) implementa gia' il principio del
  dreaming mode — fatti datati, superati, mai cancellati — e gira **embedded con
  Kuzu**. E' un'alternativa molto piu' leggera a Postgres+pgvector+Redis per la
  fase 3, e va confrontata con Honcho **prima** di installare qualsiasi cosa.
- **Il guardiano non esiste**: nessuno sorveglia lo stream di eventi di un
  processo CLI esterno con escalation SIGTERM->SIGKILL e budget di retry. Si
  costruisce, rubando il disegno da CAO e agent-monitor.

**Dove siamo davvero rari, e la ragione e' tecnica**: nessun progetto rispetta i
tre vincoli **insieme** — tutto locale, i documenti non escono dalle due
macchine, tabelle e formule mai da un LLM. In particolare la **corsia veloce
deterministica** (533 pagine in 70 secondi, senza nessun modello) non l'ha fatta
nessuno: tutti strutturano con un LLM. Non e' «fatto meglio da altri», e' **fatto
da nessuno con questi vincoli**.

**Il difetto del rapporto, da correggere nei prossimi incarichi di ricerca**:
**zero URL** in 31 KB, benche' l'incarico li imponesse. I fatti reggono — quattro
affermazioni verificate a campione su quattro, con numeri identici — ma la
verifica e' costata una ricostruzione a mano con searxng. Nei prossimi incarichi:
**l'URL va accanto a ogni affermazione**, e prima di accettare un rapporto si
controlla che ce ne siano.

---

## 7-sexies. Gli MCP sono unificati ✅ 17 agosto sera

Prima ogni agente aveva la sua configurazione, in un file diverso e in una
sintassi diversa, mantenuta a mano:

| agente | prima | ora |
|---|---|---|
| Claude Code | `megamemory`, `web-forager`, `codegraph` | invariato |
| opencode | `megamemory` | **+ `codegraph`, + `web-forager`** |
| agy | **nessuno** | **`megamemory`, `codegraph`** |

Il guadagno non e' il numero di strumenti: e' che `codegraph`
(`recall_failures`, `recall_patterns`, `add_decision`) prima lo vedeva **un
agente solo**, quindi gli altri ripetevano errori gia' pagati. Oggi ne sono stati
ripetuti almeno tre.

**Dove va la configurazione, verificato:**

- opencode: `~/.config/opencode/opencode.json`, chiave `mcp`. **Non** quello del
  repo, che non viene letto (vedi sezione 9).
- agy: **`~/.gemini/config/mcp_config.json`**, chiave `mcpServers`, con
  `command` + `args` per lo stdio. **Non** `settings.json`, che e' solo
  preferenze. Confermato due volte: dalla documentazione ufficiale
  (`antigravity.google/docs/cli/mcp` e la pagina di migrazione) e **in locale**,
  perche' `agy` aveva gia' creato quel file vuoto accanto a un `.migrated`.
- Prova reale con `agy --print`: `status SUCCESS`, risposta piena, e nell'elenco
  ci sono i tool di **entrambi** i server.

**Una scelta**: ad `agy` non e' stato dato `web-forager`, perche' ha gia'
`search_web` e `read_url_content` suoi. Ogni tool in piu' e' contesto speso a
ogni turno.

**Il passo successivo, se un giorno stanca tenerne tre allineati**: un gateway
MCP che aggrega e presenta un endpoint solo. `RICERCA-mcp.md` ha verificato la
condizione che lo rende possibile — **tutti e tre i client accettano server
remoti/HTTP**, non solo stdio — e indica **1MCP** (Apache-2.0, vivo) perche' sa
anche **filtrare quali tool esporre a quale client**, che e' il guadagno vero.
Non serve adesso: con tre server e nessun segreto, tre file allineati a mano
costano meno di un processo in piu' che diventa un singolo punto di guasto.

---

## 7-quinquies. `agy` provato in locale — due misure che cambiano il guardiano

Provato il 17 agosto sera, due run veri (`--mode plan`, modello
`gemini-3.7-flash-low`, cartella di scarto). Colmano il buco che
`RICERCA-agy.md` dichiarava: la documentazione non dice cosa succede allo
scadere del timeout.

**Prova 1 — run normale.** Il contratto e' confermato: 7 righe NDJSON, chiave
`event`, tipi `init` (1) · `step_update` (5) · `result` (1). In `init` c'e' la
lista completa degli strumenti, e comprende **`call_mcp_tool`**,
`list_resources`, `read_resource`: gli MCP `agy` li sa usare.

**Ma il risultato mente due volte su tre.** Un tool e' stato auto-negato
(headless non puo' chiedere permessi) e il run non ha prodotto niente. Esito:

```
exit code:      0                      <- mente
result.status:  "SUCCESS"              <- mente
result.response: ""                    <- dice la verita'
stderr:         "no output produced — a tool required the "command" permission
                 that headless mode cannot prompt for, so it was auto-denied"
```

**Conseguenza per il guardiano**: la salute di un run non si legge da un
segnale solo. Servono **tre** condizioni insieme — `status == SUCCESS`, `response`
non vuota, e i file attesi esistono davvero. E' la stessa regola gia' nota per
opencode («guarda i file, non il codice di uscita»), qui confermata su un
secondo strumento: e' una proprieta' degli agenti da riga di comando, non un
difetto di uno solo.

**Prova 2 — `--print-timeout 5s` su una generazione lunga.** Qui `agy` si
comporta **bene**, ed e' la differenza vera con opencode:

```
exit code:       1                            (onesto, distinguibile da 0)
result.status:   "ERROR"
result.error:    "timeout waiting for response"
durata reale:    8s contro 5s dichiarati
processi rimasti: nessuno                     (muore da solo)
```

opencode nella stessa situazione resta su `epoll` per ore e vuole `SIGKILL`.

**Il limite della prova, da non dimenticare**: ho provato il caso «il modello e'
lento», non il caso patologico dell'endpoint morto — che e' quello che ci e'
costato 5h57m. La issue #594 dice che **proprio li'** `--print-timeout` viene
ignorato. Quindi il timeout esterno con `-k` resta obbligatorio anche per `agy`.

**Da fare prima di usarlo per un incarico vero**: in modalita' headless i tool
vengono **auto-negati**, quindi servono regole `permissions.allow` in
`settings.json` (`command(<target>)` e simili). E' lo stesso file dove andranno
gli MCP: si configura una volta sola, quando `RICERCA-mcp.md` avra' detto dove.

---

## 8. Cosa aspetta il proprietario 👤

1. **Guardare una nota sbobinata.** Nel vault ci sono 223 note da `DSML.pdf`, e
   oggi sono segnalibri con un estratto troncato a meta' parola. `sbobina.py`
   adesso sa riscriverle. La domanda vera non e' se la macchina gira — gira, 13
   tok/s, tabelle verbatim, numeri verificati — ma **se il professore e'
   all'altezza**, e quello lo dice solo lui leggendo. Serve prima il punto 2
   della sezione sbobina qui sopra.
2. **Provare una foto di appunti a mano** su `visione.py` (punto 4 sopra).
3. **Decidere se la 1050 va tolta** al prossimo spegnimento: non serve a niente
   e non fa danni, ma il giorno che si toglie **l'interfaccia di rete si
   rinumera di nuovo**. La connessione col Mac e' gia' legata al MAC e non al
   nome, quindi dovrebbe reggere — ma va guardato quel giorno, non dato per
   scontato.

---

## 8-bis. La sospensione deve essere intelligente 👤 DA PROGETTARE

Posto dal proprietario la notte del 16 agosto 2026, da discutere con calma:

> «Il sistema per poter funzionare deve essere intelligente: quando l'ecosistema
> lavora non va in sospensione. Quando il fisso e' in idle puo' andare in
> sospensione dopo tre ore.»

Oggi la sospensione guarda **l'inerzia della scrivania** (XScreenSaver) e
l'ultimo uso di Elechim. Non guarda il lavoro in corso: i lavori lunghi lanciati
a mano (una sessione opencode, uno script) **non prendono `energia.blocco`**, e
il fisso puo' addormentarsi sotto un lavoro vivo. Finora e' andata bene solo
perche' c'era qualcuno alla scrivania.

`documenti.py` e `sbobina.py` il blocco lo prendono. Manca il caso generale:
**qualunque cosa stia lavorando davvero tiene sveglia la macchina**, e l'idle
vero — nessun lavoro, nessuno alla scrivania — porta a dormire dopo tre ore.
Da definire: cosa conta come "l'ecosistema lavora" (GPU occupata? un blocco?
una sessione ssh? un container che macina?) e come accorgersene senza fare del
polling costoso.

---

## 8-ter. Le lezioni misurate sono l'asset, e sono solo in italiano ⬜

Notato la notte del 16 agosto, mentre si costruiva la vetrina. Adesso:

```
README.md    (inglese)  5.945 byte   <- la vetrina, cita 4 misure
README.it.md (italiano) 30.813 byte  <- TUTTE le lezioni, con i numeri
```

Il materiale che rende Elechim diverso da un altro "second brain" — il prefill a
23 tok/s che decide l'architettura, `BindsTo` che disattiva `Restart=always`,
`OnUnitActiveSec` che non avanza durante la sospensione, l'interfaccia di rete
che cambia nome quando monti una seconda GPU, le 26 tabelle false su 42, gli
apici persi in un libro di matematica — **sta tutto nei 30 KB in italiano**, che
il 99% di chi arriva non legge.

Da valutare: un `LESSONS.md` in inglese che raccolga solo quelle, ciascuna con
la misura che la dimostra. Non e' documentazione: e' **il pezzo che si condivide**
e che porta le persone al repo. Un post costruito su quel file vale piu' di
qualsiasi ottimizzazione dei topic.

## 9. Difetti latenti, da tenere d'occhio

- **I lavori lunghi lanciati a mano non prendono `energia.blocco`.** Oggi il
  fisso e' rimasto sveglio solo perche' rilevava qualcuno alla scrivania: un
  lavoro lungo mentre non c'e' nessuno si troverebbe la macchina addormentata
  sotto. Ripartirebbe al risveglio — e' ripartibile — ma resterebbe fermo in
  silenzio.
- **`opencode.json` del progetto non viene letto**, ed e' la causa comune di
  quasi tutti i guasti di permesso di oggi. Scoperto il 17 agosto sera: una
  sessione ha scaricato una pagina in `/tmp` e non e' riuscita a rileggerla —

  ```
  permission requested: external_directory (/tmp/*); auto-rejecting
  ```

  — benche' `/tmp/*` sia gia' su `allow` **nell'`opencode.json` del repo**. Il
  file non viene applicato perche' opencode non tratta `~/assistente` come radice
  di progetto: e' lo stesso motivo per cui una sessione cercava l'incarico nella
  home e per cui un percorso assoluto veniva respinto. `megamemory` funzionava
  perche' sta nella configurazione **globale**.

  **Correzione**: le regole `permission` sono state spostate in
  `~/.config/opencode/opencode.json`, dove vengono applicate davvero, con
  l'aggiunta di `{env:HOME}/assistente/*`. Da li' valgono per ogni sessione,
  qualunque cosa opencode decida sia la radice del progetto.

  Corollario: **qualunque cosa metti nell'`opencode.json` del repo, verifica che
  abbia effetto** prima di darla per buona. Una configurazione ignorata e' peggio
  di una assente, perche' sembra che ci sia.
- **Nei prompt a opencode si usano percorsi RELATIVI.** Un percorso assoluto
  dentro il repo viene classificato come *external directory* e, con
  `"external_directory": {"*": "ask"}` in `opencode.json`, in modalita' non
  interattiva diventa **auto-rifiuto**:

  ```
  permission requested: external_directory (/home/<utente>/assistente/*); auto-rejecting
  ✗ Read INCARICO-ricerca-simbiosi.md failed
  ```

  La sessione muore in **4 secondi** senza fare niente. Il 17 agosto ci sono
  cascato dopo aver scritto qui il consiglio opposto: una sessione aveva cercato
  l'incarico in `/home/<utente>/` invece che nel repo, e ne avevo concluso «usa
  percorsi assoluti». **Era sbagliato**: cinque sessioni su cinque col percorso
  relativo hanno letto l'incarico, quella con l'assoluto e' stata rifiutata dal
  sistema di permessi. Il `cwd` che il wrapper passa funziona; e' il percorso nel
  prompt che non deve uscire dal repo.

  Resta vero il corollario: **dopo il lancio si controlla che non ci siano file
  vaganti fuori dal repo**.
- **Gli endpoint dei modelli cadono senza preavviso.** Il 17 agosto
  `opencode-go/kimi-k2.6` ha risposto `Upstream request failed: Endpoint is
  unavailable` e la sessione e' uscita con **exit 1** in 1,3 minuti senza produrre
  niente. Non e' un guasto raro: e' il comportamento normale. Il wrapper di lancio
  deve avvisare quando il log e' minuscolo o la durata troppo breve, perche' un
  fallimento cosi' somiglia a un successo veloce.
- **`opencode run` esce 0 anche quando non ha fatto niente**, se l'endpoint del
  modello e' giu' (`deepseek-v4-flash-free`, il default, oggi era down). Il
  codice di uscita non basta: si guarda se i file attesi esistono davvero.
- **`opencode run` non ha timeout sulla risposta del modello.** Vedi sezione 10.
- **Le fixture sintetiche versionate** (`documenti/elaborati/prova-*.pdf`) vengono
  **cancellate** dal collaudo (non "modificate", come diceva prima questa riga:
  `git status` le mostra ` D`). Da ripristinare con `git checkout --` dopo ogni
  esecuzione di `prova_documenti.py`, o da togliere dal versionamento.
- **`pdftocairo -svg` aborta su circa il 15% delle pagine, e l'output e' buono.**
  Misurato il 17 agosto su `dsml`: 3 pagine su 20 escono con **exit 134**
  (SIGABRT, core dump) e l'assert `_cairo_hash_table_destroy` di cairo — ma il
  file SVG e' **completo e ben formato** (`</g></svg>`, `ET.parse` passa). Il
  crash sta solo nella pulizia delle statiche di cairo all'uscita.
  poppler 26.01.0, cairo 1.18.4, Fedora 44. `pdftocairo -png` **non aborta mai**.

  **Perche' e' una trappola**: `_comando()` in `documenti.py` solleva
  `RuntimeError` su qualunque codice diverso da 0. Un rilevatore di pagine
  vettoriali costruito su `-svg` — che e' il modo naturale di contare i tracciati,
  ed e' come sono state prese le nostre misure — **ammazzerebbe l'elaborazione del
  documento sul 15% delle pagine**, per un output perfetto. Chi usa `-svg` deve
  accettare l'exit 134 **dopo aver verificato che l'XML sia ben formato**, e non
  farlo passare da `_comando()` cosi' com'e'.
- **Il lock GPU non e' un mutex, e' una bandiera.** `gpu_della_sbobina` guarda
  `energia.in_gioco()`: chi arriva secondo trova la bandiera **gia' alzata**,
  quindi **non** libera la VRAM e **non** la abbassa uscendo. Lo stato non si
  corrompe in modo permanente (chi l'ha alzata la abbassa), ma la prima sessione
  che esce **ricarica i modelli di visione sotto i piedi della seconda**, e le
  sfratta il modello a metà lavoro. Conseguenza operativa: **non lanciare due
  sessioni che usano la GPU in parallelo** — vanno in fila. Se un giorno servisse
  davvero il parallelo, serve un `flock` come quello di `_coda_esclusiva`, non
  una bandiera.
- **Le 8 unit systemd non sono versionate.** Scoperto il 17 agosto preparando il
  primo commit della giornata: `elechim-bot`, `-documenti.path`,
  `-documenti.service`, `-gateway`, `-sospensione` (service e timer),
  `-verifica-avvio` (service e timer) vivono **solo** in
  `~/.config/systemd/user/`, non nel repo e non nel README.

  Conseguenze concrete: la correzione `StartLimitIntervalSec=0` di oggi — con
  dieci righe di commento che spiegano un guasto da 1 giorno e 19 ore — esiste in
  **una copia sola, senza storia e senza backup**; le lezioni piu' dure del
  progetto (`BindsTo` che disattiva `Restart`, `OnUnitActiveSec` che non avanza
  durante la sospensione, il glob su `*.pdf` che evita i PDF troncati) stanno
  scritte **dentro file che il repo non contiene**; e un repo pubblico che
  racconta come e' fatto Elechim non ha i file che lo fanno partire.

  Da fare: una cartella `unita/` con le otto unit e uno script che le installa,
  con i percorsi presi da `%h` come gia' fanno. E' anche la via piu' semplice per
  rendere visibili quelle lezioni a chi legge il repo.
- **957 MB di core dump** in `/var/lib/systemd/coredump` al 17 agosto. Non e'
  un'emergenza (769 GB liberi) ma cresce da sola, e ogni giro di `pdftocairo -svg`
  su un libro intero ne aggiungerebbe ~80. Il
  `drkonqi-coredump-cleanup.timer` settimanale evidentemente non basta.

---

## 10. Lo stallo di opencode — 15 agosto sera, da sapere prima di rilanciarlo

Le due sessioni lanciate in parallelo si sono **piantate**, e vanno riconosciute
perche' non somigliano a un guasto:

```
STAT  WCHAN     ELAPSED   %CPU
Sl    ep_poll   07:06:13  0.5     <- vivo, ma fermo da 6h43m
ESTAB 0 0  192.168.1.68:33348  172.65.90.20:443  users:(("opencode",pid=...))
```

Il processo e' **vivo**, la connessione TCP verso l'API e' **stabilita**, le code
di invio e ricezione sono a **zero**, e la CPU e' allo 0,5%. Cioe': opencode sta
aspettando su `epoll` una risposta che il server non manda piu', e **non ha un
timeout**. Restava li' indefinitamente.

Non c'entra la sospensione: il fisso non ha mai dormito (nessun `PM: suspend`
nel journal), e comunque le sessioni erano partite alle 17:19.

**Come accorgersene**: non guardare il processo, guarda **l'orologio del log**.
`ls -la` sul file di log contro l'ora attuale dice in un colpo se sta ancora
lavorando. Sei ore di silenzio non sono un lavoro lungo, sono uno stallo.

**Da fare la prossima volta**: dare a `opencode run` un `timeout` esterno
generoso ma finito (es. `timeout 3600`), cosi' un endpoint che smette di
rispondere costa un'ora e non una notte. E ricontrollare comunque i file
prodotti, mai il solo codice di uscita.

### AGGIORNAMENTO 17 agosto: `timeout 3600` **non basta**, e lo stallo si e' ripetuto

La contromisura scritta qui sopra e' stata applicata, e **ha fallito**. Tre
sessioni lanciate in parallelo il 17 agosto alle 14:00 si sono piantate alle
14:09 e sono rimaste li' **5h57m**, con il `timeout` ancora vivo accanto:

```
STAT  WCHAN     ELAPSED   %CPU
Sl    ep_poll   05:57:54  0.5
ESTAB 0 0  192.168.1.68:53506  172.65.90.20:443  users:(("opencode",pid=2532454))
```

Stessa firma del 15 agosto, **stesso indirizzo** `172.65.90.20`, code a zero.

**Perche' il timeout non ha ucciso.** `timeout` da solo manda **SIGTERM**.
opencode lo intercetta per chiudere con garbo, e quella chiusura si blocca sulla
stessa chiamata di rete morta: il processo non muore, e `timeout` **senza `-k`
non escala mai a SIGKILL**. Restano appesi tutti e due.

**La correzione vera**: `timeout -k 60 3600 opencode run ...`. Sessanta secondi
dopo il TERM parte SIGKILL, che nessuno puo' intercettare. Per liberarle a mano e'
servito `pkill -KILL`: il TERM non le smuoveva.

**Il bilancio del danno, ed e' la conferma della regola gia' nota.** Il lavoro sul
disco e' buono: `documenti.py` ha **350 righe nuove** e `prova_documenti.py` e'
**TUTTO VERDE** — la sessione figure aveva finito il codice. Si sono persi
`RAPPORTO-figure.md`, il codice di `salute.py` e tutto `LESSONS.md`. **Le
conclusioni sono l'ultima cosa che una sessione scrive, quindi la prima che si
perde.**

**Una cosa ha funzionato**, ed e' da tenere: l'istruzione «scrivi il rapporto
appena hai i numeri, non alla fine». `RAPPORTO-salute.md` esiste **con le misure
di partenza dentro** e i segnaposti `_(in corso)_` per il resto. E' l'unica
sessione delle tre che ha lasciato qualcosa di leggibile oltre al codice.

**Nota sul lavoro perso**: poco. Le modifiche al codice erano gia' sul disco e
sono buone — il collaudo di entrambi passa. Si e' perso il rapporto di sbobina e
il confronto fra modelli, cioe' le **conclusioni**, che sono l'ultima cosa che
una sessione scrive. Vale la regola gia' in `INCARICO-qualsiasi-documento.md`:
*le sessioni che hanno consegnato sono quelle che hanno scritto per prime.*
