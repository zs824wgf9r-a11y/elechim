# Estrazione deterministica dei fatti

## Obiettivo e principio

Dopo tre esperimenti con il deriver di Honcho su `qwen3:8b` (prompt originale,
+istruzione di lingua, filtro user-only) il problema e' risultato essere il
modello, non il prompt: attribuzione sbagliata, allucinazioni, non-terminazione.

L'estrazione deterministica rovescia la premessa: invece di chiedere a un LLM
"cosa e' un fatto", prende **solo i messaggi [user]**, li taglia in frasi e
tiene quelle che affermano qualcosa sul proprietario. Il fatto e' quindi **una
frase del proprietario, con il suo timestamp e l'id del messaggio d'origine**.
Zero parafrasi, zero normalizzazione, zero attribuzioni sbagliate per
costruzione.

Vincoli rispettati:

- **Nessun modello**, nessuna chiamata a ollama.
- **Solo libreria standard** (`sqlite3`, `re`, `pathlib`, `json`, `statistics`,
  `time`, `sys`).
- `archivio/` e' stato letto solo dalla macchina; il rapporto contiene solo
  numeri e percorsi.
- Non toccati `energia.py`, `sbobina.py`, `documenti.py`, `guardiano.py`,
  `lavoro.py`, i loro collaudi, `gateway.py`, `mac/`, `unita/`, gli altri
  `INCARICO-*` e `RAPPORTO-*`. `DEFINIZIONI` non e' stata toccata.

## Regole scelte

### 1. Solo messaggi [user]

L'attribuzione e' risolta a monte. Se una frase viene da un messaggio `user`,
il soggetto e' il proprietario.

### 2. Taglio in frasi

Le frasi si spezzano su `.`, `!`, `?`, `;`, `:`. Il taglio protegge:

- **abbreviazioni**: `ecc.`, `etc.`, `cioè.`, `es.`, `ad es.`, `p.es.`, `n.b.`,
  `dott.`, `sig.`, `prof.`, `avv.`, `ca.`, `circa`, `vol.`, `pag.`, `cap.`,
  `art.`, `cfr.`, `ibid.`, `op cit.`, e altre comuni;
- **numeri decimali**: `3.5` e `3,5` non vengono spezzati dal punto o dalla
  virgola.

### 3. Frasi tenute

Una frase viene tenuta se **afferma qualcosa sul parlante**. Criteri:

- contiene un indicatore di prima persona (`io`, `mi`, `mio`, `ho`, `sono`,
  `sto`, `voglio`, `preferisco`, `posso`, `devo`, `uso`, `mi serve`, `mi piace`,
  `mi sembra`, `ho deciso`, `facciamo`, `useremo`, `faremo`, `restiamo`, ...);
- oppure e' nel **contesto** di un messaggio che gia' contiene un indicatore di
  prima persona (es. gli elementi di un elenco dopo "il mio allenamento lo sto
  facendo così:"), a patto che non sia domanda, imperativo o rivolta
  all'assistente.

### 4. Frasi scartate

| regola | perche' |
|---|---|
| **domanda** | finisce con `?`; una domanda non e' un fatto sul proprietario |
| **imperativo** | inizia con verbi come `fammi`, `dimmi`, `dammi`, `scrivimi`, `mostrami`, `cerca`, `sentiti`, `cercalo`, ... o con `puoi`/`potresti`/`mi fai` |
| **sull'assistente** | soggetto e' l'interlocutore (`tu`, `ti`, `hai`, `sei`, `stai`, `puoi`, `potresti`, `useresti`...) senza indicatori di prima persona |
| **troppo breve** | meno di 2 parole |
| **non sul parlante** | nessun indicatore di prima persona e nessun contesto utile |

### 5. Nessuna normalizzazione

Il testo del fatto e' **verbatim**. Se la frase e' sgrammaticata, resta
sgrammaticata. Ogni fatto porta `ts` e `msg_id` del messaggio d'origine.

## Implementazione

- `estrazione_deterministica.py`: estrattore puro, solo stdlib.
- `misura_attribuzioni.py`: adattato per riconoscere la sezione `## Fatti` e
  usare `msg_id` quando presente; cosi' il tasso di attribuzione sbagliata si
  misura sul messaggio d'origine.

## Misura sul campione

Campione: 3 conversazioni in `archivio/`, 90 messaggi totali, di cui 43
messaggi `[user]`.

### Confronto con gli esperimenti a modello

| misura | prompt originale | +lingua B | user-only | deterministica |
|---|---:|---:|---:|---:|
| fatti per conversazione | 8 / 10 / 17 | 1 / 8 / 21 | non termina | **0 / 26 / 3** |
| attribuzione sbagliata | 36,6% | 55,6% | - | **0%** |
| conv. lunga errata | 73,7% | 82,6% | - | **0%** |
| fatti con data | 0 / 35 | 0 / 30 | - | **29 / 29** |
| tempo totale | ~344 s | ~368 s | ~600 s | **3,6 ms** |

### Risultati dell'estrazione deterministica

| conversazione | messaggi | messaggi [user] | fatti | fatti / messaggi user |
|---|---:|---:|---:|---:|
| stato-mac-20260811-0021 | 6 | 3 | 0 | 0,0 |
| stato-prima-dei-fix-20260811-1205 | 54 | 27 | 26 | 0,96 |
| stato-prima-del-trasloco-20260810-2357 | 30 | 13 | 3 | 0,23 |
| **totale** | **90** | **43** | **29** | **0,67** |

Tempo: 3,57 ms totali, 1,19 ms per conversazione in media.

### Frasi scartate per regola

| regola | numero |
|---|---:|
| domanda | 19 |
| non sul parlante | 10 |
| imperativo | 5 |
| troppo breve | 5 |
| sull'assistente | 3 |
| **totale scartate** | **42** |

### Verifica attribuzione

`misura_attribuzioni.py` e' stato adattato per usare `msg_id` quando presente.
Sui 29 fatti prodotti:

- attribuiti a `[user]`: 29
- attribuiti a `[assistant]`: 0
- non attribuiti: 0
- **tasso di attribuzione sbagliata: 0%**

## Analisi del silenzio

Il rischio annunciato e' reale: **un estrattore troppo stretto produce zero
fatti e sembra funzionare**.

- La conversazione `stato-mac-20260811-0021` (6 messaggi totali, 3 user) ha
  dato **0 fatti**: e' fatta di descrizioni di immagini e domande, quindi
  nessuna frase afferma qualcosa sul proprietario. Lo scarto e' corretto, ma
  va detto forte.
- La conversazione `stato-prima-del-trasloco-20260810-2357` (30 messaggi
  totali, 13 user) ha dato **3 fatti**: la maggior parte dei messaggi user sono
  domande, imperativi o proposte rivolte all'assistente. E' una conversazione
  dove il proprietario esplora piu' che dichiarare.
- La conversazione `stato-prima-dei-fix-20260811-1205` (54 messaggi totali, 27
  user) ha dato **26 fatti**, quasi un fatto per messaggio user: e' una
  conversazione in cui il proprietario parla del suo allenamento, del suo
  corpo, delle sue decisioni.

La produzione e' quindi **altamente dipendente dal tipo di conversazione**:
domande e comandi producono pochi fatti, i racconti di esperienza ne producono
molti. La media (0,67 fatti per messaggio user) nasconde una varianza enorme.

## Verdetto

**L'attribuzione sbagliata si elimina per costruzione: 0% su tutto il
campione.** Il timestamp e l'id del messaggio sono presenti in ogni fatto,
mentre l'LLM ne aveva prodotti zero su 35/30.

Il problema che resta e' il **recall**: 29 fatti su 43 messaggi user significa
che quasi un terzo dei messaggi user non lascia fatti. Non perche' il filtro
sia troppo stretto in generale, ma perche' molte interazioni con un assistente
sono domande, comandi e scambi di servizio che non contengono informazioni sul
proprietario.

Per una memoria episodica questo e' **accettabile come primo stadio**: cio'
che cattura e' vero, datato e attribuito correttamente. Per aumentare il
volume servira' probabilmente arricchire le regole (es. riconoscere frasi con
soggetto sottinteso "io" in contesti noti, o tenere intenzioni espresse come
"vorrei provare X") senza perdere il vantaggio principale: nessuna
attribuzione sbagliata.

## File da leggere

I fatti estratti, con accanto il messaggio d'origine e il motivo di scarto,
sono in:

```
stato/prova-estrazione-deterministica/
```

La cartella e' ignorata da git. Il giudizio su cosa e' un fatto utile e' del
proprietario.
