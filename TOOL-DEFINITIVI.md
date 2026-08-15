# I tool definitivi

Deciso dal proprietario il **15 agosto 2026**. Questo file esiste perche' aggiungere
un tool invalida la cache dell'intera conversazione sul Mac
(`entry.tools == request.tools`): i tool mancanti si aggiungono **tutti insieme,
una volta sola**. Quindi l'elenco si decide prima, e si applica dopo.

**Stato: deciso, non ancora applicato.** `DEFINIZIONI` in `strumenti.py` e
`mac/strumenti.py` contiene ancora i due tool originali. Non toccarla finche'
non sono pronte **entrambe** le cose che i nuovi tool servono (fase 3 memoria e
fase 4 documenti): applicarla a meta' significherebbe pagare l'invalidazione due
volte, o peggio lasciare un tool che risponde "non ancora implementato" dentro
il contesto di ogni conversazione per settimane.

## L'elenco: quattro tool, per sempre

| nome | mestiere | stato |
|---|---|---|
| `cerca` | il web | esiste |
| `leggi` | una pagina web | esiste |
| `ricorda` | **tutto l'archivio locale** in lettura | da aggiungere |
| `salva` | l'archivio locale in scrittura | da aggiungere |

Quattro sta dentro il "4-6 tool grossolani" della regola 1. Il costo stimato dei
due nuovi e' **~180 token**, cioe' ~8 secondi di prefill **una volta per
conversazione**, mai piu'.

## Perche' `ricorda` e' uno solo

Dietro `ricorda` ci sono tre archivi diversi — i fatti sul proprietario in Honcho, le
note del vault, i documenti ingeriti nell'indice vettoriale — e **il fan-out lo
fa il fisso**, esattamente come `cerca` lo fa gia' sui motori di ricerca.

Il modello non deve sapere in quale dei tre sta la risposta. Chiedere a un 4B di
scegliere l'archivio giusto prima di cercare significa chiedergli di sbagliare,
e ogni scelta sbagliata costa un giro di tool completo (10-30s). Un solo
ingresso, ricerca ibrida dietro, passaggi compressi in uscita con il loro
riferimento.

## La distinzione che rende `ricorda` lecito

La regola 5 dice **memoria iniettata solo all'apertura della sessione, mai a
meta'**. Sembra vietare un tool di memoria. Non lo fa, e la ragione e' precisa:

- **Iniettare ricordi nel prompt di sistema cambia il *prefisso* del contesto**,
  quindi invalida la cache di tutto cio' che viene dopo. Vietato a meta'
  conversazione.
- **Il risultato di un tool si appende in *fondo* al contesto.** Non tocca il
  prefisso, non invalida niente: costa solo il prefill dei suoi token, come
  qualsiasi altro messaggio.

Sono due cose che sembrano la stessa e non lo sono. La regola 5 riguarda
l'iniezione automatica, non il recupero su richiesta.

## Le descrizioni — da congelare byte per byte

Scritte nello stile delle due esistenti: **dicono cosa fa il tool, non quando
usarlo.** Le regole su *quando* chiamarlo vanno nel prompt di sistema, che
viaggia una volta sola per conversazione; nelle `DEFINIZIONI` viaggerebbero a
ogni richiesta e sarebbero l'unica cosa che non si puo' piu' correggere senza
pagare.

```python
    {
        "type": "function",
        "function": {
            "name": "ricorda",
            "description": (
                "Cerca nell'archivio locale: fatti gia' noti sull'utente, note "
                "personali e documenti che ha mandato. Restituisce i passaggi "
                "pertinenti con il loro riferimento."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cosa cercare"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "salva",
            "description": (
                "Salva una nota o un fatto nell'archivio locale. Risponde dove "
                "l'ha messo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "testo": {"type": "string", "description": "Cosa salvare"},
                    "titolo": {"type": "string", "description": "Titolo breve"},
                },
                "required": ["testo"],
            },
        },
    },
```

**`salva` non ha un parametro per la destinazione**, ed e' voluto: dove va a
finire lo decide il fisso secondo le regole dell'autogestione (contano i tag nel
frontmatter, non le cartelle), e lo **dichiara nella risposta**. Un 4B che
sceglie la cartella e' un 4B che sbaglia cartella; e chiedere il permesso
costerebbe un turno intero, cioe' 4 secondi buttati per spostare un file
markdown, che e' gratis.

## Cosa va nel prompt di sistema, non qui

Il prompt di sistema e' l'unico posto dove si dice **quando** chiamare i tool.
Lezione gia' pagata l'11 agosto: zero chiamate a `cerca` in tutta la giornata,
con due richieste esplicite di ricerca web, perche' la descrizione diceva cosa
faceva e nessuno diceva quando usarlo.

Da aggiungere quando si applicano i tool, tenendo presente che il prompt si paga
una volta per conversazione (oggi ~565 token) e che **gli esempi valgono piu'
degli aggettivi**:

- quando il proprietario chiede qualcosa che riguarda lui, la sua storia o un documento
  che ha mandato, si chiama `ricorda` **prima** di rispondere a memoria;
- quando dice di ricordare qualcosa, o quando emerge un fatto che varra' anche
  domani, si chiama `salva` e si dice dove — **senza chiedere il permesso**;
- `ricorda` prima di `cerca`: quello che sta in casa e' gratis e vero, il web e'
  caro e generico.

## Come si applica, il giorno che si applica

1. Si modifica `DEFINIZIONI` in `strumenti.py` **e** in `mac/strumenti.py`.
2. Si verifica che le due copie siano **identiche byte per byte**, con
   `sha256sum` sul blocco serializzato — e' il controllo che ha gia' salvato il
   trasloco del bot sul Mac l'11 agosto.
3. Si propaga con `./sincronizza.sh`.
4. Si riavvia il bot sul Mac. **Un solo bot per token**: fermare prima, avviare
   dopo.
5. La prima conversazione dopo l'applicazione paga il prefill pieno. E' previsto
   e si paga una volta: farla con `/nuova`, non a meta' di una conversazione in
   corso.
6. Si annota in `README.md` la data e il costo misurato del primo turno, per
   avere il numero vero accanto alla stima di ~180 token.

## Cosa si e' deciso di NON fare

- **Niente tool `stato`.** Il bot sa per certo se il fisso e' sveglio e quanta
  VRAM c'e'; lo dichiara lui col comando `/stato`, e il prompt di sistema ci
  rimanda gia'. Un tool in piu' si paga a ogni conversazione, e darebbe al
  modello dei numeri da reinterpretare quando la risposta giusta e' gia' scritta.
- **Niente tool separati per documenti, note e memoria.** Vedi sopra: sarebbero
  tre ingressi per un mestiere solo, e la scelta fra i tre e' proprio la cosa
  che un modello piccolo sbaglia.
