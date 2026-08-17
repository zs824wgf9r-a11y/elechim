# Incarico: Graphiti contro Honcho, per la fase 3

Scritto il 17 agosto 2026. Ricerca sul web: **non tocchi codice, non installi
niente**. Un solo file: `RICERCA-memoria.md`.

Il proprietario vuole provare Graphiti. Prima di installare qualcosa serve
sapere quale dei due regge i **nostri** vincoli, che non sono quelli di un
confronto generico.

## Cosa siamo noi, e perche' cambia il confronto

- **Tutto in locale.** Nessun servizio in cloud, per nessun motivo: le
  conversazioni e i documenti del proprietario non escono da due macchine.
- **Il fisso** ha 62 GB di RAM e **8 GB di VRAM condivisi** fra `qwen3:8b` (la
  sbobina), `qwen3-vl:4b` (la visione) e whisper, che si sfrattano a vicenda con
  un lock. Una memoria che vuole la GPU si mette in coda con gli altri.
- **Il Mac** (M4, 16 GB) tiene il modello di conversazione con **65.536 token di
  contesto** e un prefill a **23 tok/s**: cinque minuti per turno a 8K token.
- Il piano attuale, mai realizzato, e' **Honcho** con Postgres+pgvector, Redis e
  `bge-m3`.

## Il criterio che decide, e va misurato prima degli altri

**Quanti token restituisce la memoria a ogni turno.**

A 23 tok/s, ogni 1.000 token di contesto in piu' costano **43 secondi** di
prefill. Il Mac deve ricevere un riassunto da **~300 token**, non un elenco di
fatti. Quindi la domanda non e' «quale ricostruisce meglio la conoscenza» ma:

- cosa restituisce **davvero** una query, nei due casi? Un elenco di fatti? Un
  sottografo? Del testo?
- si puo' **limitare** la dimensione della risposta, e come? C'e' un parametro,
  o tocca troncare noi?
- esiste un modo di farsi dare una **sintesi corta** invece dei fatti grezzi?

Se un progetto non permette di tenere la risposta corta, **e' fuori**, per quanto
bello sia il resto. Dillo chiaro.

## Le altre domande

Per ognuna: **URL davvero aperto accanto all'affermazione**, licenza, ultimo
commit, quante persone. «Non trovato» dove non c'e' niente. E su 403/429
**cambia fonte**, non scrivere «non trovato» per un rate limit.

### 1. Cosa serve per farli girare, davvero

- **Honcho**: conferma o smentisci che vuole Postgres+pgvector e Redis. Si puo'
  far girare piu' leggero? Esiste una modalita' incorporata?
- **Graphiti**: la voce che gira e' che funzioni **embedded con Kuzu** senza
  Neo4j. Verificalo: quali backend supporta, quale e' consigliato, e cosa si
  perde con quello incorporato.
- Per entrambi: RAM, disco, e se vogliono la GPU.

### 2. Il modello di ingestione — attenzione, e' un veto

Entrambi usano un LLM per estrarre i fatti dal testo. Per noi:

- **puo' essere un modello locale via ollama?** Nomi e configurazione esatti.
- **non puo' essere il modello del Mac**: sfratterebbe la conversazione
  dall'unica slot di cache. Deve girare sul fisso.
- quanto costa in tempo per conversazione ingerita? Se ingerire un giorno di
  chat costa un'ora di GPU, e' un problema.
- funziona in **italiano**? Molti estrattori di entita' sono tarati sull'inglese,
  e le nostre conversazioni sono in italiano. **Cerca prove, non promesse.**

### 3. Il tempo e le contraddizioni

E' il principio del nostro dreaming mode: **fatti datati, superati, mai
cancellati**.

- Graphiti si presenta come grafo **temporale**: come rappresenta «X era vero
  fino a marzo, poi e' diventato Y»? Invalida, versiona, o sovrascrive?
- Honcho come gestisce la stessa cosa con la sua memoria episodica?
- Chi dei due sa dire **da quando** sa una cosa, e **cosa sapeva** a una certa
  data?

### 4. Maturita' e rischio

- Chi c'e' dietro, da quanto, con che cadenza di rilascio.
- **Il costo di sbagliare**: se scegliamo uno e dopo sei mesi cambiamo idea, i
  dati si portano via? C'e' un export? O si ricomincia da capo?
- Ci sono confronti **indipendenti** fra i due, non i README dei rispettivi
  progetti?

### 5. Esiste una terza via che non abbiamo considerato?

`RICERCA-ridondanza.md` citava anche **mem0** e **cognee**. Meritano una riga
ciascuno con lo stesso metro, e se uno regge i nostri vincoli meglio dei due
candidati, **dillo**: non siamo sposati con nessuno dei due.

E la domanda scomoda: per quello che ci serve davvero — ricordare fatti sul
proprietario e ritrovarli — **serve un grafo, o basterebbe molto meno**? Se
la risposta onesta e' «basterebbe un database di fatti datati con una ricerca
lessicale», scrivilo: sarebbe il risultato piu' utile di tutti.

## Cosa NON fare

- **Non installare niente**, nessun clone, nessun `pip install`, nessun container.
- Non toccare codice, configurazioni, altri `INCARICO-*`, `RAPPORTO-*`,
  `AGENTS.md`, `DA-FARE.md`, git. **L'unico file che scrivi e'
  `RICERCA-memoria.md`.**
- **Non guardare `archivio/`**: contiene le conversazioni vere del proprietario.
  La prova sui dati veri la facciamo noi in locale.
- Non inventare parametri, backend o numeri.

## Come cercare

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235
```

C'e' ora un `GITHUB_TOKEN` in `.env`: **usalo** negli header
(`Authorization: Bearer $GITHUB_TOKEN`) quando interroghi l'API di GitHub, cosi'
non sbatti nei 60 richieste/ora. **Non stampare mai il token** nel rapporto ne'
nei log.

## Come si scrive `RICERCA-memoria.md`

In testa una sezione **«come ho cercato»** con le query usate — cosi' la ricerca
e' ripetibile, e si distingue «non trovato» da «non cercato».

Poi una **sintesi da dieci righe** che risponda a: **quale dei due installiamo, e
cosa rischiamo se abbiamo scelto male?**

Un capitolo per domanda. Chiudi con:

1. **La raccomandazione**, e il **primo passo concreto** per provarla in locale
   (comandi esatti, senza eseguirli).
2. **Cosa NON vale la pena.**
3. **«Non trovato»**.

Scrivi il file un capitolo alla volta mentre lavori, non alla fine.
