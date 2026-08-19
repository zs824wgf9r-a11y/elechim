# Incarico: il recupero per il canale studio (fase 1, deterministica)

Scritto il **20 agosto 2026**. Leggi prima `AGENTS.md`, in particolare la
sezione sulla localita'. Questo e' il primo di sei pezzi del canale studio: il
disegno completo sta in `DA-FARE.md`, sezione "Il canale studio".

**Questa fase non usa modelli, non usa la GPU, non usa la rete.** Se ti trovi a
chiamare ollama o a scaricare qualcosa, hai sbagliato incarico.

## L'idea in una riga

Il corpus per studiare esiste gia' sul disco, ma e' spezzato in due meta' che
non si parlano: rendilo interrogabile senza aggiungere niente.

## Il problema, misurato

```
markdown/dsml.md       1,4 MB    il contenuto, SENZA struttura
~/Obsidian/30-Note/    224 note  la struttura, SENZA contenuto
```

Le 224 note sono segnalibri: mediana **936 byte**, massimo 1083. Contengono
frontmatter, titolo, e un estratto troncato a meta' parola. Non contengono il
testo della sezione.

`markdown/dsml.md` non ha titoli: **zero righe `##`**. Ha 176 righe che
iniziano con `#` e sono **tutte commenti Python** finiti nel testo senza
recinto (`# round to two decimal places`, `# generate test data`, ...).

Ma le due meta' si uniscono su un campo che c'e' gia' in entrambe. Misurato il
20 agosto sul vault vero:

```
note con pagina:     223 su 224
copertura:           pagine 1-533
buchi fra sezioni consecutive:  0
pagina == pagina_fine:          103 (46%), le altre sono intervalli
```

**Ogni pagina del libro appartiene a esattamente una sezione, senza buchi.**
La giunzione e' totale e deterministica.

## La trappola, ed e' la ragione principale per cui questo incarico e' scritto

Chiunque scriva il pezzo che spezza il testo pensera' di spezzare su `^#`.
Su `dsml.md` **spezzerebbe su 176 commenti Python** e produrrebbe pezzi senza
capo ne' coda, e il collaudo passerebbe lo stesso perche' i pezzi ci sono.

> **Il testo si spezza sui marcatori `<!-- pag N -->`. Mai su `^#`.**

Il titolo del pezzo non si legge dal testo: si prende dalla mappa
sezione->pagine costruita dal frontmatter delle note.

## Cosa costruire

Un modulo nuovo, **`studio.py`**. Non toccare `documenti.py`.

### 1. La mappa sezione <-> pagine

Legge il frontmatter delle note in `~/Obsidian/30-Note/` (`documento`,
`sezione`, `titolo`, `pagina`, `pagina_fine`) e costruisce la mappa.

Regole:

- una nota senza `pagina` si **salta e si conta**, non si indovina (oggi ce
  n'e' una su 224: dev'essere nel rapporto);
- se due sezioni si sovrappongono su una pagina, **e' un errore da dichiarare**,
  non da risolvere in silenzio scegliendo la prima;
- la mappa e' per documento: `dsml` oggi, altri domani. Non cablare `dsml`
  da nessuna parte.

### 2. I pezzi

Dal markdown integrale (`markdown/<documento>.md`), spezzato sui marcatori di
pagina, ogni pezzo porta con se':

```
documento · sezione · titolo della sezione · pagina · testo
```

Un pezzo non e' mai piu' grande di una pagina. Se una pagina supera i ~4000
caratteri si spezza ulteriormente sui paragrafi (riga vuota), **mai a meta'
frase**, e i sotto-pezzi ereditano la stessa pagina.

### 3. La ricerca, a due stadi

Primo stadio: quali sezioni sono pertinenti. Secondo stadio: quali pezzi dentro
quelle sezioni.

L'algoritmo lo scegli tu (BM25, TF-IDF, quello che ti convince), **con due
vincoli**: solo libreria standard, e nessun modello. Su 2,4 MB deve rispondere
in **meno di 200 ms** a freddo, indice ricostruito compreso se lo ricostruisci
ogni volta; altrimenti l'indice si salva in `stato/` e si rigenera quando il
markdown cambia (impronta del file, deterministico).

Ogni risultato deve poter dire **da dove viene**: documento, sezione, titolo,
pagina. Un passaggio senza riferimento e' inutile per chi studia, perche' il
punto e' andare a guardare sul libro.

### 4. Il caso vuoto — la regola piu' importante di tutto l'incarico

> **Se nessun pezzo supera la soglia di pertinenza, la ricerca restituisce
> zero risultati.** Non il meno peggio.

Questa fase non genera testo, quindi qui il danno sembra piccolo. Non lo e':
sopra questa funzione ci andra' un modello che risponde **solo** sui passaggi
che riceve. Se la ricerca gli passa il paragrafo meno peggio invece di niente,
il modello scrivera' una risposta sicura di se' su una fonte che non c'entra —
ed e' il guasto peggiore che questo sistema possa avere, perche' chi legge sta
imparando la materia e non ha modo di accorgersene.

La soglia va **dichiarata nel rapporto con il numero scelto e il perche'**.

### 5. La riga di comando

```
python3 studio.py cerca "<domanda>" [--quanti N]   passaggi con riferimento
python3 studio.py indice                            ricostruisce e riporta
python3 studio.py stato                             cosa c'e' indicizzato
```

`cerca` stampa i passaggi in chiaro sul terminale. Niente JSON come formato
principale: questa CLI la usa una persona. Un `--json` in piu' va bene.

## I collaudi, e devono poter fallire

In questo progetto **tre collaudi su tre** sono passati per ragioni strutturali
(vedi `DA-FARE.md` 1-quater): un'asserzione che non puo' fallire nemmeno col
codice rotto e' peggio di nessuna asserzione. Scrivi `prova_studio.py` con
questi casi, e verifica **di persona che ognuno fallisca** se rompi apposta il
codice che dovrebbe proteggere.

| collaudo | deve fallire se |
|---|---|
| **unicita' della copertura** — per ogni pagina 1..533 esiste **esattamente una** sezione | due sezioni si sovrappongono, o una pagina resta scoperta |
| **il chunker non spezza su `#`** — documento sintetico con dentro `# commento python` fra due marcatori di pagina: deve dare **un** pezzo | qualcuno spezza su `^#` |
| **il caso vuoto** — domanda su un argomento assente dal corpus (es. "ricetta della carbonara"): **zero** risultati | la soglia e' assente o troppo bassa |
| **il riferimento c'e' sempre** — ogni risultato ha documento, sezione, pagina non vuoti | un percorso di codice perde i metadati |
| **la nota senza pagina** — viene contata, non fa cadere la costruzione | si assume che il frontmatter sia sempre completo |

Non contare mai una cosa contro se stessa. «223 sezioni == 223 sezioni» torna
sempre vero: e' il difetto esatto che ha nascosto le pagine duplicate.

## La misura di qualita', da riportare qualunque sia il numero

Scrivi a mano **10 domande** su argomenti che stanno in `dsml`, con accanto la
sezione che secondo te dovrebbe rispondere. Misura **quante volte la sezione
attesa e' fra le prime 3**.

Il numero va nel rapporto **cosi' com'e'**. Se e' 4 su 10 lo scrivi: e' quello
che decide se il prossimo pezzo si costruisce o se prima si cambia recupero.
Un rapporto che gonfia questo numero fa perdere settimane a valle.

## Vincoli

- **Solo libreria standard.** Niente nuove dipendenze in `requirements.txt`.
- **Sola lettura assoluta su `~/Obsidian/`.** Questa fase non scrive nel vault,
  in nessuna cartella, per nessun motivo. Lo stato va in `~/assistente/stato/`.
- **Non toccare**: `documenti.py`, `sbobina.py`, `energia.py`, `guardiano.py`,
  `lavoro.py`, `gateway.py`, `fusione.py`, `strumenti.py`, `mac/`, `unita/`,
  i loro collaudi, gli altri `INCARICO-*` e `RAPPORTO-*`.
- **Niente GPU, niente ollama, niente rete.**
- Il markdown in `markdown/` e' sorgente in sola lettura.

## Cosa consegnare

1. `studio.py`
2. `prova_studio.py` — tutto verde, e ogni caso della tabella provato a
   rompersi apposta
3. `RAPPORTO-studio-recupero.md` con:
   - le misure della mappa (sezioni, copertura, buchi, note saltate)
   - la soglia scelta per il caso vuoto e il perche'
   - il tempo di risposta misurato, a freddo e a caldo
   - **le 10 domande con l'esito**, numero grezzo
   - i limiti che hai trovato e non hai risolto

Il rapporto senza il numero delle 10 domande e' una consegna incompleta.
