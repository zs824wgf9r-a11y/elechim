# Incarico: dimostra che stiamo reinventando la ruota

Scritto il 17 agosto 2026, su richiesta del proprietario: *«Secondo me sono
problemi gia' risolti da altre persone, bisogna fare ricerche piu' accurate.»*

Ricerca sul web: **non tocchi codice, non installi niente**. Produci un solo
file, `RICERCA-ridondanza.md`.

## L'inquadramento, ed e' diverso dalle ricerche precedenti

`RICERCA-stato-arte.md` ha concluso «TENERE IL NOSTRO» su quattro punti su sei.
E' un verdetto sospetto, perche' chi lo ha dato stava giudicando il lavoro della
casa. **Qui il compito e' l'opposto**: parti dall'ipotesi che quello che abbiamo
costruito esista gia', fatto meglio, e **prova a dimostrarlo**. Se non ci
riesci, quel fallimento vale piu' di dieci «teniamo il nostro» — ma devi averci
provato davvero.

Regola di onesta': se un progetto copre **una parte** del nostro lavoro, dillo
con la parte, non con un si'/no. La domanda utile non e' «esiste qualcosa di
simile» (esiste sempre) ma **«cosa possiamo cancellare dal nostro codice se lo
adottiamo, e cosa ci perdiamo»**.

## Le due segnalazioni del proprietario — guardale per prime

### 1. https://github.com/virgiliojr94/book-to-skill

- Cosa fa **davvero**? Leggi README e codice, non solo la descrizione.
- Trasforma un libro/PDF in che cosa esattamente — una «skill» in senso Claude
  Code (cartella con istruzioni), un indice, delle note?
- **Confronto diretto col nostro**: noi abbiamo `documenti.py` (PDF -> markdown
  con tabelle e formule recintate, note Obsidian, ~1000 righe) e `sbobina.py`
  (riscrittura sezione per sezione con un modello locale, numeri verificati).
  Cosa di questo copre? Cosa no?
- Manda il contenuto del libro a un modello **in cloud**? Per noi e' un veto
  assoluto (vedi `AGENTS.md`): i documenti del proprietario non escono dalle
  due macchine.
- Licenza, se e' vivo, dipendenze, e quanto codice e' davvero.

### 2. https://github.com/cactus-compute/needle

- Cosa fa, e a quale dei nostri problemi risponde — se risponde. Non forzarlo:
  se non c'entra niente col nostro, **dillo e basta**, e' una risposta valida.
- Cactus Compute lavora su inferenza on-device: `needle` e' una libreria di
  recupero, un motore di ricerca locale, un indice vettoriale, altro?
- **Se e' recupero/memoria**, e' molto rilevante: e' il pezzo della **fase 3**
  che dobbiamo ancora costruire (oggi il piano e' Honcho con Postgres+pgvector,
  Redis, `bge-m3`). Gira in locale? Su CPU? Che risorse vuole?
- Licenza, se e' vivo, maturita'.

## Poi, in ordine: i nostri pezzi, uno per uno

Per **ognuno**: esiste un progetto che lo fa? Cosa cancelleremmo? Cosa ci
perderemmo? Verdetto **ADOTTARE / PRENDERE UN PEZZO / TENERE IL NOSTRO**, e per
l'ultimo pretendo una ragione tecnica, non «il nostro e' piu' su misura».

1. **Da libro a note collegate.** PDF di centinaia di pagine -> note atomiche in
   un vault Obsidian, con wikilink risolti e un indice. Esistono progetti fatti
   per **Obsidian** che fanno questo? (cerca fra i plugin della community, non
   solo su GitHub)
2. **La riscrittura con un modello locale** che spiega una sezione senza
   toccare tabelle e formule e verificando i numeri contro la fonte. E' un
   pattern che qualcuno ha impacchettato?
3. **La coda su cartella**: file che arriva -> elaborazione -> archiviato, con
   ripresa dopo interruzione e stato per documento. Sicuramente esiste gia' come
   libreria: quale, e vale la pena?
4. **Il ragionamento a piu' ruoli su un pensiero** (`INCARICO-pensieri.md`).
   Esiste un progetto che prende un appunto e ne produce obiezioni e domande?
   Cerca anche fuori dal mondo Obsidian.
5. **L'orchestrazione di agenti da riga di comando** con sorveglianza e
   confini — quello che stiamo per costruire come guardiano. Esiste gia'?
6. **La memoria condivisa fra piu' agenti**: noi abbiamo quattro posti
   (`MEMORY.md`, `megamemory`, `codegraph`, `AGENTS.md`+`DA-FARE.md`). Esiste un
   progetto che la unifica?

## Come cercare, e qui devi essere piu' accurato delle volte scorse

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235
```

- **Non fermarti alla prima pagina di risultati** e non fermarti al README: se
  un progetto sembra rilevante, **apri il codice** e guarda cosa fa davvero. I
  README promettono piu' di quanto mantengano.
- Cerca anche dove non abbiamo cercato: **plugin della community di Obsidian**,
  **Awesome list** di settore, **Show HN**, subreddit di PKM e di agenti,
  e i concorrenti citati dentro i README dei progetti che trovi (la sezione
  «alternatives»/«similar projects» e' spesso la miniera migliore).
- Per ogni progetto: **licenza**, **ultimo commit**, **numero di persone** che
  ci lavorano. Un progetto morto o di una persona sola non e' una dipendenza,
  e' codice da mantenere noi.

## Cosa NON fare

- Non toccare codice, configurazioni, altri `INCARICO-*`, `RAPPORTO-*`,
  `AGENTS.md`, `DA-FARE.md`, git. **L'unico file che scrivi e'
  `RICERCA-ridondanza.md`.**
- **Non installare niente**, nessun clone, nessun `pip`/`npm install`.
- **Non inventare** progetti, funzioni o numeri di stelle. Se un repo che ti
  aspetti di trovare non esiste, scrivi «non trovato» — e' successo gia' una
  volta oggi con un repo che dava 404, ed e' stata una risposta utile.
- Niente dati personali nel rapporto.

## Come si scrive `RICERCA-ridondanza.md`

In cima, **una sintesi da dieci righe** che risponda a una domanda sola:
**cosa dovremmo smettere di scrivere noi, e adottare?**

Poi un capitolo per i due repo segnalati, poi uno per ognuno dei sei pezzi, ogni
capitolo col verdetto e col **costo del cambio** (cosa si installa, cosa si
butta, cosa si perde).

Chiudi con:

1. **Le tre cose piu' promettenti**, in ordine, con il primo passo concreto per
   valutarle sul serio (una prova, non un'altra ricerca).
2. **Dove abbiamo davvero qualcosa di raro**, se c'e': i vincoli che ci
   distinguono sono che tutto e' locale, che i documenti non escono dalle due
   macchine, e che le tabelle e le formule non passano mai da un LLM. Se nessun
   progetto rispetta quei vincoli, **quello** e' il motivo per tenere il nostro
   — ed e' una ragione tecnica, non affettiva.
3. Una sezione **«non trovato»**.

Scrivi il file **un capitolo alla volta mentre lavori**, non alla fine.
