# Incarico: la sbobina — riscrivere le sezioni come un professore

Scritto il 15 agosto 2026. Leggi prima `AGENTS.md`. Questo e' lo **stadio due**
della fase 4: i documenti sono gia' estratti e sezionati, qui si riscrive.

## L'obiettivo, con le parole del proprietario

Obsidian dev'essere il suo secondo cervello, ed Elechim il suo **sbobinatore**:
prendere un PDF complicato e restituire appunti gia' pronti da studiare, dove
una cosa difficile e' spiegata in modo semplice. Come un professore che ti
riscrive il capitolo, non come un indice che ti dice dove guardare.

Oggi le note atomiche sono segnalibri: frontmatter, link, e un estratto grezzo
**tagliato a meta' parola**. Quello va sostituito.

## Il vincolo non negoziabile, e vale anche per te

**Il contenuto dei documenti del proprietario non entra nel tuo contesto.** Il modello
che riscrive e' **locale, su ollama, sul fisso**. Tu costruisci la macchina.

In pratica:

- **Collauda sul PDF sintetico** (`prova_documenti.py` lo genera): il testo li'
  e' inventato da noi, puoi leggerlo quanto vuoi.
- Puoi **far girare** la pipeline su un documento vero e leggerne le
  **metriche**, ma **non stampare, non aprire e non incollare** il testo
  riscritto ne' l'originale.
- **Non usare mai un modello in cloud per riscrivere**, nemmeno per un
  confronto "solo per vedere". Sarebbe piu' bravo, ed e' esattamente il motivo
  per cui la regola esiste.

## Struttura: uno stadio separato, non dentro `documenti.py`

Un modulo nuovo, `sbobina.py`. **Non fondere la riscrittura nell'estrazione.**

La ragione e' architetturale e pesa: estrarre e' veloce (70s per 533 pagine) e
deterministico, riscrivere e' lento (~1 ora) e fallibile. Separati, fra sei mesi
puoi rifare tutte le sbobine con un modello migliore **senza riestrarre niente**.
Fusi, ogni miglioramento del modello costa tutto da capo.

Lo stato ha gia' gli stadi (`estratto` -> `fatto`): aggiungine uno, `sbobinato`,
con avanzamento **per sezione**, non per documento. Un lavoro da un'ora deve
riprendere dalla sezione 147, non da capo.

Usa `energia.blocco("sbobina")` come fa gia' `documenti.py`: il fisso si
sospende dopo tre ore di inerzia e questo e' proprio il lavoro lungo per cui
quel blocco esiste.

## L'unita' di lavoro e i numeri

214 sezioni su un libro da 533 pagine, ~1.700 token di sorgente ciascuna. Ci
stanno in qualsiasi modello locale: **non si passa mai il documento intero.**

Budget VRAM: 8.188 MiB totali, ~1.400 occupati da X11+plasma. Ci sta un **7-8B
quantizzato a 4 bit** (~5 GB). Un 12B no, non con X11 sopra. `qwen3-vl:4b`
(4.529 MiB) va **sfrattato** durante il lavoro: usa il lock GPU che c'e' gia' in
`gateway.py`, non farne un secondo, e rimetti `keep_alive` corto.

## Scegliere il modello: misura, non decidere a tavolino

Prova **due o tre candidati** su ollama (qwen3:8b e simili, buon italiano,
~5 GB a 4 bit). Per ciascuno misura e scrivi:

1. VRAM occupata davvero con `nvidia-smi`, non quella dichiarata;
2. token/s in generazione;
3. secondi per sezione, e quindi **il tempo stimato per un libro da 214 sezioni**.

La qualita' **non la giudichi tu** (vedi sopra). La giudica il proprietario.

## Le tre cose che fanno la differenza fra utile e inutile

**1. Riscrivere non e' riassumere.** Se al modello chiedi di riassumere ottieni
una versione piu' corta e piu' vaga: inutile come sbobina. Il professore
*espande* — prende il paragrafo denso e lo spiega. Nel prompt: "spiega questo
passaggio a uno studente", **mai** "riassumi". Su un modello piccolo la
differenza fra i due verbi e' la differenza fra utile e inutile.

Ricorda la lezione gia' pagata: **su un modello piccolo l'istruzione complessa
peggiora il risultato.** Prompt semplice, un compito solo. Se ti serve anche
l'elenco dei punti chiave, fai **due chiamate**, non una che chiede due cose.

**2. Cosa non passa mai dal modello.** Tabelle (regola non negoziabile),
codice, formule. Si copiano **verbatim** nella nota e il modello spiega attorno,
senza toccarli. I blocchi tabellari sono gia' marcati nel markdown integrale
(`<!-- tabella pag N blocco M -->`), quindi sai esattamente cosa isolare.

**3. Il controllo dei numeri — la parte che rende la promessa verificabile.**

Dopo ogni riscrittura: estrai ogni numero dal testo generato e verifica che
compaia nella sezione sorgente. Quelli che non ci sono si **segnalano nella nota
e si contano nel rapporto**.

Prende automaticamente la classe di errore per cui esiste la regola sulle
tabelle — il 180 che diventa 150 — e trasforma "fidati del modello" in una
garanzia misurabile. Attenzione ai falsi allarmi legittimi: un numero puo'
comparire riscritto ("due" per "2", "50%" per "0,5"). Misura quanti allarmi
produce sul PDF sintetico e regola di conseguenza; **meglio qualche allarme in
piu' che un numero sbagliato che passa liscio**.

## Come diventa la nota

```
---
frontmatter (come adesso, piu' i campi della sbobina)
---
# Titolo della sezione

## In breve
- due o tre punti, per il ripasso

## La spiegazione
[il professore. In cima, perche' e' quello che si legge]

## Materiale originale
[tabelle, codice, formule - verbatim, mai riscritti]

## Fonte
[[documento]] · [integrale](...) · pagina N
⚠ 2 numeri non verificati        <- solo se ce ne sono
```

L'estratto troncato di oggi **sparisce**: una frase tagliata a meta' parola e'
peggio di niente.

## Rapporto di copertura, esteso

Sezioni riscritte su totali, sezioni saltate e perche', numeri segnalati, tempo
impiegato, modello usato **con la sua versione**. Quest'ultimo campo serve piu'
di quanto sembri: fra sei mesi vorrai sapere quali note vengono da quale
modello, per decidere cosa rifare.

## Ordine di consegna — leggi bene, cambia cosa fai per primo

**Non costruire tutto e poi provare.** Prima:

1. modello scaricato, `sbobina.py` che riscrive **una sola sezione**;
2. fallo girare sul **PDF sintetico** e verifica li' quello che puoi verificare
   tu: che le tabelle escano verbatim, che il controllo dei numeri funzioni, che
   la nota abbia la forma giusta;
3. poi fallo girare su **una sola sezione** di `dsml` e **lascia il file dov'e'
   senza leggerlo**: dimmi solo il percorso della nota e le metriche. Quella la
   legge il proprietario, ed e' lui a dire se il professore e' all'altezza.

**Fermati li' e consegna.** Non lanciare le 214 sezioni: se la qualita' non
regge si cambia modello, e avresti buttato un'ora di GPU e 214 note.

## Criterio di uscita

- `sbobina.py` funziona su una sezione, da riga di comando;
- collaudo sul PDF sintetico verde, incluso il controllo dei numeri;
- i numeri dei modelli candidati misurati e scritti nel `README.md`;
- una nota vera di `dsml` prodotta e **non letta**, con il percorso nel rapporto;
- `DEFINIZIONI` non toccata: impronta attesa `1160ec454b8b9998`, verificala e
  riportala.
