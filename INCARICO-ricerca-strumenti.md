# Incarico: rendere la ricerca uno strumento affidabile, non un colpo di fortuna

Scritto il 17 agosto 2026 sera. Ricerca sul web: **non tocchi codice e non
installi niente**. Un solo file: `RICERCA-strumenti.md`.

Chiesto dal proprietario: *«Dovremmo fare ricerche approfondite su diverse cose,
cosi' da avere un quadro sempre chiaro. Le risorse sul web sono tante e molto
spesso inesplorate. Forse questa repo puo' aiutare: `d4vinci/Scrapling`.»*

## Prima di tutto: qual e' davvero il collo di bottiglia?

**Non dare per scontato che sia il recupero delle pagine.** Oggi abbiamo fatto
cinque ricerche e i guasti veri sono stati questi, misurati:

| guasto | quante volte | causa |
|---|---|---|
| muro dei permessi (`/tmp` auto-negato) | 1 sessione morta | configurazione ignorata, non il web |
| **rate limit dell'API GitHub** | 6 repo dichiarati inesistenti a torto | richieste non autenticate |
| repo che risponde 404 | 1 | il progetto non esiste |
| un rapporto senza **nessun URL** | 1 su 4 | disciplina, non strumenti |
| pagina che non si legge / bloccata | **nessuna** | — |

Quindi la domanda vera non e' «quale libreria di scraping», e' **«cosa ci ha
davvero fermato, e cosa lo toglie»**. Se la risposta e' «un token GitHub e una
regola di disciplina», dillo, anche se e' una risposta poco entusiasmante: e'
esattamente il genere di conclusione che ci fa risparmiare una dipendenza.

## Le domande

Per ognuna: **URL davvero aperto accanto a ogni affermazione**, licenza, ultimo
commit, quante persone. E «non trovato» dove non c'e' niente.

### 1. `d4vinci/Scrapling` — cosa fa, e risolve un problema che abbiamo?

- Cos'e' esattamente: libreria di scraping, parser, framework anti-bot? Cosa la
  distingue da `requests` + `beautifulsoup`?
- **Serve un browser** (Playwright/Chromium) o e' leggera? Il peso conta: il
  fisso ha gia' searxng e crawl4ai in container.
- **Confronto diretto con `crawl4ai`**, che abbiamo gia' in piedi su
  `127.0.0.1:11235`: fa cose che crawl4ai non fa? Su quali pagine? La
  documentazione tecnica e le pagine GitHub — che sono il 90% di cio' che
  leggiamo — le prende meglio?
- **La domanda che decide**: guardando la tabella dei guasti qui sopra,
  Scrapling ne toglie **almeno uno**? Se la risposta e' no, scrivilo chiaro.

### 2. Il rate limit di GitHub, che e' un guasto misurato

- Quali sono i limiti reali per richieste **non autenticate** contro
  **autenticate** sull'API? Numeri, dalla documentazione ufficiale.
- Basta un **token personale a sola lettura** per toglierlo? Come si passa
  all'API, e quali permessi minimi servono?
- Ci sono modi **senza token** che reggono meglio (endpoint alternativi, la
  pagina HTML invece dell'API, `codeload`)?
- **Attenzione**: un token e' un segreto. Come si tiene fuori da un repo
  pubblico? Noi abbiamo gia' `.env` e `.env.example`: e' il posto giusto?

### 3. Come si tiene «un quadro sempre chiaro» invece di ricerche a spot

E' la richiesta vera del proprietario, e vale piu' della libreria.

- Esistono strumenti o pratiche per **sorvegliare** un insieme di progetti e
  accorgersi quando cambiano qualcosa che ci riguarda (release, issue chiuse,
  deprecazioni)? Cerca: feed Atom di GitHub (`/releases.atom`, `/commits.atom`),
  `newreleases.io`, watcher self-hosted, e qualunque cosa faccia la stessa cosa.
- Quanto costa in pratica: un feed per progetto, o serve un servizio?
- C'e' un modo di far diventare questo un **rapporto periodico** invece di una
  ricerca a comando? Noi abbiamo gia' i timer systemd e un bot Telegram.
- E la domanda scomoda: **quali progetti varrebbe la pena sorvegliare**, viste le
  nostre dipendenze reali? (poppler, ollama, i modelli, opencode, agy, Graphiti,
  docling, marker). Proponi una lista corta e motivata: una lista lunga non la
  legge nessuno, ed e' il modo in cui la sorveglianza muore.

### 4. Cosa manca alle nostre ricerche, viste da fuori

Guarda `RICERCA-stato-arte.md`, `RICERCA-simbiosi.md`, `RICERCA-mcp.md` e
`RICERCA-ridondanza.md` (sono nel repo) e dimmi, **con esempi presi da li'**:

- dove si sono fermate troppo presto;
- quali fonti non abbiamo mai toccato e avremmo dovuto;
- se il formato «un capitolo per domanda + verdetto» funziona o produce
  ripetizione.

E' una critica al nostro metodo, non un complimento: se non trovi niente da
criticare, non stai guardando abbastanza.

## Cosa NON fare

- Non toccare codice, configurazioni, altri `INCARICO-*`, `RAPPORTO-*`,
  `AGENTS.md`, `DA-FARE.md`, git. **L'unico file che scrivi e'
  `RICERCA-strumenti.md`.**
- **Non installare niente** e non creare token.
- Non inventare progetti, limiti numerici o opzioni. Se non l'hai letto, dillo.

## Come cercare

```
searxng:  curl -s 'http://127.0.0.1:8888/search?q=<query>&format=json'
crawl4ai: http://127.0.0.1:11235
```

Evita di salvare le pagine in `/tmp` per poi rileggerle: usa `webfetch`, o
crawl4ai, o passa `curl` direttamente a una pipe.

## Come si scrive `RICERCA-strumenti.md`

In cima una **sintesi da dieci righe** che risponda a: **cosa cambiamo domani per
avere ricerche piu' affidabili, in ordine di rapporto fra guadagno e costo?**

Un capitolo per domanda, ciascuno con un verdetto secco. Chiudi con:

1. **Le tre cose da fare**, dalla piu' economica alla piu' cara, ognuna con il
   primo passo concreto.
2. **Cosa NON vale la pena**, che e' altrettanto utile.
3. **«Non trovato»**.

**Ogni affermazione deve avere il suo URL accanto**, non in fondo e non
sottinteso: l'ultima ricerca ne aveva zero in 31 KB, i fatti erano giusti ma
verificarli e' costato una ricostruzione a mano. Scrivi il file un capitolo alla
volta mentre lavori.
