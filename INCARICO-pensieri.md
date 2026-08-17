# Incarico: elaborare un pensiero come una discussione tra colleghi

Scritto il 17 agosto 2026. Chiesto dal proprietario: *«dare a Elechim la
possibilita', su richiesta, di elaborare un mio pensiero e scriverlo su Obsidian
in una sua cartella dedicata. Per elaborarlo al meglio serve un algoritmo di
ragionamento, in modo che venga formulato ed elaborato come se fosse una
discussione tra colleghi.»*

Leggi prima `AGENTS.md`, poi `sbobina.py` — da cui si riusa tutto il macchinario
del modello — e `TOOL-DEFINITIVI.md`, per capire perche' questo **non** e' un tool.

## Cos'e', in una frase

Il proprietario manda un pensiero in prosa (due righe o mezza pagina, anche
dettato a voce). Elechim lo fa passare attraverso una discussione fra ruoli
distinti e scrive in `50-Pensieri/` una nota che contiene il pensiero
**verbatim**, la sintesi e lo scambio intero. Poi risponde su Telegram con
~200 token: nota scritta, quante domande restano aperte.

## I quattro vincoli che decidono il progetto

Leggili prima di scrivere codice: ognuno esclude una soluzione che altrimenti
sembra la piu' ovvia.

**1. Non e' un tool, e `DEFINIZIONI` non si tocca.** La via ovvia sarebbe un
quinto tool `pensa` accanto a `cerca`/`leggi`/`ricorda`/`salva`. Non si fa:
`TOOL-DEFINITIVI.md` spiega che toccare `DEFINIZIONI` cambia il prefisso della
cache e costa un prefill pieno (~340s a 8K token) a **ogni** conversazione viva,
e che i quattro tool vanno aggiunti in un colpo solo quando fase 3 e fase 4 sono
pronte. Quindi: **comando del bot**, `/pensa <testo>`, instradato lato bot
**prima** che il messaggio arrivi al modello. Un comando non e' una definizione e
non invalida niente. Il giorno che i quattro tool entrano, `pensa` diventa un
tool vero e la pipeline sotto e' gia' costruita.

**2. L'elaborazione gira sul fisso, non sul Mac.** Cinque chiamate che generano
qualche centinaio di token ciascuna sono minuti di lavoro: sul Mac significa
occupare l'unica slot di cache e sfrattare la conversazione. Sul fisso c'e'
`qwen3:8b` a 13 tok/s e il lock GPU che sa sfrattare `qwen3-vl` e whisper e
**rimetterli a posto** (`gpu_della_sbobina`, verificato: VRAM rientrata a 5.337
MiB). Il Mac vede solo la conferma finale.

**3. Non e' una chat.** Una discussione a piu' giri in conversazione
ri-prefillerebbe a ogni turno un transcript che cresce: 5 minuti a giro, mezz'ora
per cinque. La discussione si fa a **chiamate separate e corte, una per ruolo,
ognuna che riceve solo cio' che le serve**. E' la stessa scelta che `sbobina.py`
ha gia' fatto: due chiamate separate, mai una che chiede due cose.

**4. Un pensiero e' contenuto personale, e vale piu' di un documento.** Un PDF il
proprietario l'ha scaricato da qualche parte; un pensiero e' suo e non esiste
altrove. Il contenuto di un pensiero vero **non entra mai nel contesto di un
modello in cloud**, quindi nemmeno nel tuo. Si prova su pensieri **sintetici che
scrivi tu** — che sono anche verita' di riferimento, quindi test migliori. Nel
rapporto vanno **solo conteggi e tempi**.

## L'algoritmo: cinque chiamate, cinque mestieri

Ogni ruolo e' una chiamata a `chiedi()` con un prompt suo, stretto, e un input
esplicito. Nessun ruolo vede la cronologia degli altri: vede solo quello che
elenco qui. E' la parte che va rispettata alla lettera, perche' e' cio' che
distingue una discussione da un monologo.

| # | ruolo | riceve | produce |
|---|---|---|---|
| 1 | **chi ascolta** | il pensiero | il pensiero nella sua forma piu' forte e chiara, e la **tesi implicita** in una riga |
| 2 | **chi chiede** | pensiero + riformulazione | 3-5 domande che farebbe un collega competente: cio' che e' indefinito, non critiche |
| 3 | **chi obietta** | pensiero + tesi (**non** la riformulazione) | l'obiezione piu' forte, e **cosa dovrebbe essere vero perche' il pensiero sia sbagliato** |
| 4 | **chi porta un precedente** | tesi | «questo somiglia a...», al massimo due spunti |
| 5 | **la sintesi** | tutto quanto sopra | cosa e' stabilito, cosa resta aperto, il prossimo passo concreto |

Tre cose non negoziabili sui ruoli:

- **La sintesi non deve risolvere.** Il suo lavoro e' separare cio' che regge da
  cio' che e' aperto. Deve poter concludere «non risolto», e va scritto nel
  prompt: un modello lasciato libero chiude sempre con una morale, che e' la cosa
  meno utile che possa produrre.
- **Il ruolo 4 e' quello che inventa.** Un 8B che cerca precedenti produce
  citazioni plausibili e false. Va marcato nella nota come **spunto da
  verificare**, mai come fatto. Se in fase di misura risulta inutile piu' spesso
  che utile, **proponi di toglierlo** e porta i numeri: e' una scelta che
  discutiamo, non un requisito.
- **Il ruolo 3 e' il cuore, ed e' quello che fallisce in silenzio.** Vedi sotto.

## Il difetto da battere: il modello e' d'accordo con se stesso

E' il modo in cui i "dibattiti fra agenti" diventano teatro. Chi obietta e chi
propone sono **gli stessi pesi con gli stessi pregiudizi**: l'obiezione esce come
un complimento riformulato, la discussione converge su un consenso che nessuno ha
messo in dubbio, e la nota sembra ragionata mentre non ha aggiunto niente.

Tre contromisure, e la terza e' misurabile:

1. **Chi obietta non vede la riformulazione approvata**, solo il pensiero e la
   tesi. Non gli si mostra l'approvazione di un collega.
2. Il prompt del ruolo 3 dice che la proposta e' **di un collega**, non sua, e che
   il suo mestiere e' trovare dove si rompe. Un'obiezione vuota e' una chiamata
   fallita.
3. **Invariante anti-eco.** Se l'obiezione ha troppa sovrapposizione di n-grammi
   con la riformulazione, non e' un'obiezione: e' un'eco, e la chiamata **si
   rifa'** una volta con un prompt piu' stretto. Se anche il secondo giro e' eco,
   la nota lo **dichiara** («nessuna obiezione indipendente prodotta») invece di
   spacciare l'eco per critica. La soglia la **misuri tu** su pensieri sintetici,
   e la dichiari nel rapporto: e' della stessa famiglia di
   `caratteri_coperti == caratteri_fonte`, un'asserzione esatta al posto di un
   giudizio a occhio.

Dichiara nel rapporto **quante volte su N** l'anti-eco e' scattato: e' il numero
che dice se la discussione e' vera.

## La nota

In `50-Pensieri/`, una nota per pensiero. La numerazione segue quella del vault
(`00-Inbox`, `10-Ricerche`, `20-Documenti`, `30-Note`, `40-Skills`, `90-Allegati`).

Ordine delle sezioni, e l'ordine e' una scelta:

1. **Il pensiero, verbatim.** Primo, intatto, mai riscritto. E' l'unico pezzo
   irripetibile: la discussione si rigenera lanciando di nuovo, il pensiero no.
   Vale la stessa regola dei documenti — *l'integrale e' la verita'*.
2. **La sintesi**: stabilito / aperto / prossimo passo.
3. **Le domande aperte**, come elenco. Sono il motivo per cui la nota si rilegge.
4. **Lo scambio intero**, ruolo per ruolo, col precedente marcato da verificare.
5. Frontmatter con data, modello e versione (`versione_modello`), durata, e i
   conteggi.

Il titolo del file: data e ora piu' uno slug breve dalla tesi del ruolo 1. E' un
titolo generato da un modello, quindi puo' essere goffo — ed e' accettabile,
perche' serve a navigare, non a informare. Il contenuto vero sta dentro.

**Se il pensiero contiene numeri**, valgono le regole di `sbobina.py`: ogni
numero che compare nella sintesi si verifica contro il pensiero con
`verifica_numeri`, e quelli non verificati si segnalano. Un modello che
arrotonda il tuo numero mentre "elabora" e' il difetto del 180 che diventa 150.

## Come si costruisce

Un file nuovo, `pensieri.py`, piu' un pezzo di rifattorizzazione che va fatto
prima perche' altrimenti si duplica mezza `sbobina.py`.

**Prima: estrai lo strato del modello in `modello.py`.** Oggi
`sbobina.py` contiene le primitive che servono identiche qui:

- `_chiedi()` -> `chiedi()` (la chiamata a ollama, con timeout)
- `_senza_pensiero()` -> `senza_pensiero()` (ripulisce `<think>`)
- `verifica_numeri()`, `_normalizza_numero()`
- `versione_modello()`
- `gpu_della_sbobina()` -> `gpu_del_lavoro(nome)`, che e' il nome giusto ora che
  non serve solo alla sbobina

`sbobina.py` le importa da li' e **mantiene i suoi nomi pubblici come alias**,
cosi' non si rompe niente fuori. `prova_sbobina.py` deve restare verde: e' il
guardiano di questa estrazione, e va eseguito **prima e dopo** per confronto.

**Poi `pensieri.py`**, che ricalca `documenti.py` nella forma:

- coda `pensieri/in/*.txt`, path unit, e la cartella si svuota sempre — chi
  finisce sposta in `pensieri/elaborati/`, chi fallisce in `pensieri/falliti/`
  con un `<nome>.ragione.txt` accanto;
- `_coda_esclusiva()` con `flock` non bloccante, chi arriva secondo esce **0**;
- stato per pensiero in `stato/pensieri/<slug>.json`, con il ruolo raggiunto: una
  pipeline di cinque chiamate va interrotta e ripresa, non ricominciata;
- `energia.blocco("pensieri")`, o il fisso si addormenta a meta' discussione;
- `gpu_del_lavoro("pensieri")` attorno alle cinque chiamate, **una volta sola**:
  prendere e rilasciare il lock cinque volte fa sfrattare e ricaricare
  `qwen3-vl` cinque volte.

**Il path unit nasce con la lezione gia' dentro.** Nel `[Unit]` del servizio va
`StartLimitIntervalSec=0`, con il commento che spiega perche'. Motivo, pagato in
esercizio il 15 agosto e scoperto il 17: il path unit riscatta finche' il glob e'
vero, e mentre un'istanza lavora tutte le altre escono 0 per il lock — sono
successi, ma col default di 5 avvii in 10 secondi al sesto systemd dichiara
`start-limit-hit`, il fallimento **si propaga al path unit** e la coda smette di
sorvegliare. La coda documenti e' rimasta morta **1 giorno e 19 ore** in silenzio
per questo. Non ripetere l'errore su una coda nuova.

**Il comando del bot** (`mac/`): `/pensa <testo>` scrive il testo in
`pensieri/in/` attraverso il gateway e risponde subito «ci penso»; a lavoro finito
arriva la conferma. Un vocale seguito da `/pensa` usa la trascrizione di whisper,
che c'e' gia'. **Non toccare `DEFINIZIONI`** — se ti sembra che serva, fermati e
scrivilo nel rapporto invece di farlo.

## Cosa NON fare

- **Non toccare `DEFINIZIONI`**, per nessun motivo. E' il confine piu' importante.
- Non toccare `documenti.py`, `fusione.py`, `strumenti.py`, `web.py`,
  `visione.py`, `README.md`, `README.it.md`, `AGENTS.md`, `DA-FARE.md`, git.
- Di `sbobina.py` tocca **solo** l'estrazione in `modello.py` descritta sopra:
  niente altre modifiche, niente riordini, niente miglioramenti non chiesti. Su
  quel file sta per partire una macinata da 4 ore e 214 sezioni.
- Non lanciare `sbobina.py` sul libro vero, per nessuna ragione.
- Niente dipendenze nuove: si usa quel che c'e' (ollama, poppler, whisper).
- Non inventare un secondo modello: `qwen3:8b`, come la sbobina. Se pensi che
  serva altro, misuralo e proponilo nel rapporto.

## Come si prova

Il contenuto di un pensiero vero non entra nel tuo contesto. Quindi:

1. Scrivi **tre pensieri sintetici** tu, di forme diverse — uno con una tesi
   chiara, uno vago e mal formulato, uno con dei numeri dentro. Sono verita' di
   riferimento: sai cosa ci hai messo, quindi le asserzioni sono esatte.
2. Casi permanenti in `prova_pensieri.py`:
   - il pensiero si ritrova nella nota **verbatino, byte per byte** (e' l'invariante
     principale: `il_pensiero_nella_nota == il_pensiero_sorgente`);
   - la nota ha tutte e cinque le sezioni, e le domande aperte non sono zero sul
     pensiero vago;
   - i numeri del pensiero numerico o sono verificati o sono segnalati, mai
     alterati in silenzio;
   - l'anti-eco: dai in pasto una finta obiezione identica alla riformulazione e
     verifica che **scatti il rifacimento**, e che al secondo fallimento la nota
     lo **dichiari**;
   - coda esclusiva: due istanze insieme, entrambe escono 0;
   - un pensiero vuoto o di tre parole finisce in `falliti/` con la ragione, e
     **non lascia una nota nel vault**;
   - interruzione a meta' pipeline: riprende dal ruolo dov'era, non da capo.
3. `prova_sbobina.py` verde prima e dopo l'estrazione di `modello.py`.

## Criterio di uscita

- `prova_pensieri.py` e `prova_sbobina.py` entrambi **TUTTO VERDE**;
- `RAPPORTO-pensieri.md` con: la soglia anti-eco scelta e **come l'hai misurata**,
  quante volte su N e' scattata, i tempi per ruolo e il totale per pensiero, il
  giudizio motivato su se il ruolo 4 vada tenuto, e i conteggi delle note
  prodotte sui sintetici. **Nessun testo di pensiero vero.**
- `DEFINIZIONI` intatta, e dichiaralo esplicitamente nel rapporto;
- il servizio nuovo con `StartLimitIntervalSec=0` e il commento che spiega perche'.

Una nota sul giudizio, che vale piu' del codice: la macchina si verifica coi test,
ma **se la discussione sia utile lo dice solo il proprietario leggendo una nota**.
Quindi il rapporto deve finire con il percorso di **una** nota generata da un
pensiero sintetico, pronta da guardare. Non lanciare niente sui pensieri veri:
quello lo fa lui.
