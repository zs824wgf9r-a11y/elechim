# Rapporto: l'estrazione di Honcho regge l'italiano?

## Obiettivo

Verificare, senza installare Honcho/Postgres/pgvector, se il prompt del deriver
Honcho estrae osservazioni in italiano da conversazioni italiane vere. Il
modello e' configurabile; la prova usa il prompt ufficiale con qwen3:8b su
ollama del fisso.

## Vincoli

- `archivio/` non e' stato letto dall'umano: lo script legge i messaggi e scrive
  le osservazioni in `stato/prova-estrazione/`, che e' ignorata da git.
- Nel rapporto ci sono solo numeri, zero testo di conversazioni, zero
  osservazioni riportate.
- Non toccati `energia.py`, `sbobina.py`, `documenti.py`, `gateway.py`, `mac/`,
  `unita/`, `lavoro.py`, `guardiano.py`, `DEFINIZIONI`.

## Prompt Honcho

- URL: https://github.com/plastic-labs/honcho/blob/f88892b0715adbd852c6b846532cc39a335d2de4/src/deriver/prompts.py
- Revisione: `f88892b0715adbd852c6b846532cc39a335d2de4`
- Commit: `fix(deriver): update prompt to prevent example leakage (#1028)`,
  2026-08-17T18:49:15Z.
- Prompt usato: `minimal_deriver_prompt` (funzione `minimal_deriver_prompt` in
  `src/deriver/prompts.py`). E' stato aggiunta solo l'ultima riga con
  l'istruzione di formato output (elenco puntato, una conclusione per riga)
  per poter contare in modo meccanico; il compito semantico e' identico.

## Criterio di campionamento

Tutti i file `*.db` in `archivio/`, in ordine lessicografico crescente. Ogni
file .db e' trattato come una conversazione. I messaggi vengono letti dalla
tabella `messaggi` in sola lettura (`sqlite3.connect(..., uri=True)` con
`mode=ro`), ordinati per `ts` e `id`.

## Criterio di rilevamento lingua

Per ogni osservazione:
- si contano le parole funzione italiane e inglesi presenti nel testo
  (liste dichiarate in `prova_estrazione.py`);
- **italiano**: almeno 2 parole italiane e rapporto italiano/inglese > 1.5;
- **inglese**: almeno 2 parole inglesi e rapporto inglese/italiano > 1.5;
- altrimenti **misto/indeterminato**.

## Misure

Campione: 3 conversazioni, 90 messaggi totali (6, 54, 30 messaggi).
Non e' un campione per giudicare la qualita' su larga scala; basta per la
domanda binaria.

| misura | valore |
|---|---|
| conversazioni | 3 |
| messaggi totali | 90 |
| osservazioni per conversazione (min / mediana / max) | 8 / 10 / 17 |
| conversazioni con zero osservazioni | 0 |
| tempo per conversazione (s) | 94.76 / 108.75 / 140.46 |
| tempo medio per conversazione | 114.66 s |
| tempo totale | 343.97 s |
| prompt tokens per conversazione | 665 / 2050 / 2667 |
| prompt tokens totali | 5382 |
| output tokens totali | 2919 |
| osservazioni in italiano | 23 (65.7%) |
| osservazioni in inglese | 4 (11.4%) |
| osservazioni miste/indeterminate | 8 (22.9%) |
| osservazioni con numeri | 7 |
| osservazioni con date | 0 |

Distribuzione per conversazione:

| file | messaggi | osservazioni | italiano | inglese | misto |
|---|---|---:|---:|---:|---:|
| stato-mac-20260811-0021 | 6 | 10 | 0 | 4 | 6 |
| stato-prima-dei-fix-20260811-1205 | 54 | 8 | 8 | 0 | 0 |
| stato-prima-del-trasloco-20260810-2357 | 30 | 17 | 15 | 0 | 2 |

## File prodotto

- Osservazioni estratte: `stato/prova-estrazione/`
- Misure grezze: `stato/prova-estrazione/misure.json`
- `stato/` e `archivio/` sono ignorati da git (`git check-ignore` confermato).

## Verdetto

**Sì — ma non garantito.** Con il prompt ufficiale di Honcho (revisione
`f88892b0715adbd852c6b846532cc39a335d2de4`) e qwen3:8b, il **65,7% delle
osservazioni è in italiano (23/35)** e **2 conversazioni su 3 escono in italiano**.
La terza conversazione esce in inglese: il rischio di deriva verso l'inglese su
messaggi brevi o misti esiste ed è reale. Postgres+pgvector non sono lavoro
buttato, ma va previsto un meccanismo di guardia (custom instructions esplicite
o post-filter lingua) prima di fidarsi in produzione.
