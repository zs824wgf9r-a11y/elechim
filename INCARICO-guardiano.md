# Incarico: il guardiano — sorvegliare un agente invece di sperare

Scritto il 17 agosto 2026 sera. Leggi prima `AGENTS.md`, poi `RICERCA-simbiosi.md`
(la ricetta e gli eventi) e la sezione **7-quinquies** di `DA-FARE.md` (le due
prove fatte su `agy`).

## Il problema, misurato oggi

| guasto | misura |
|---|---|
| stallo su `epoll` con l'endpoint morto | 3 sessioni ferme **5h57m** |
| `timeout` esterno che non uccide | manda SIGTERM, opencode **non ha handler** (#24658) |
| l'exit code mente | exit **0** su un run che non ha fatto niente |
| anche `result.status` mente | `SUCCESS` con `response` vuota, provato su `agy` |
| le conclusioni si perdono | 4 rapporti su 8 non scritti oggi |
| nessuno se ne accorge | l'unico controllo e' un umano che guarda l'orologio di un log |

La causa di fondo **non verra' corretta**: la issue #40330 di opencode e' chiusa
come *not planned* (retry senza budget, `session.error` mai pubblicato, `run`
esce solo su `idle`). Quindi il guardiano non e' un lusso: e' l'unica difesa.

## Il cuore, che e' lo stesso per tutti e due i motori

Non «pilotare opencode». Il mestiere e': **leggere un flusso di eventi,
accorgersi del silenzio, ed escalare**. Entrambi i motori danno un flusso a
righe:

- **agy**: NDJSON su stdout con `--output-format stream-json`. Eventi
  `init` / `step_update` / `result` (chiave **`event`**, non `type` — verificato
  in locale, ci sono cascato).
- **opencode**: SSE da `GET /event` di `opencode serve`, eventi `session.status`,
  `session.idle`, `session.error`, `message.part.updated`.

Scrivi **il cuore una volta** e due adattatori sottili che normalizzano in tre
fatti: *e' vivo* (un evento e' arrivato), *ha finito* (bene o male), *ha fallito*.

## Le tre regole non negoziabili

### 1. La salute vuole **tre** segnali, non uno

Provato su `agy`: un run che non ha prodotto niente ha dato **exit 0** *e*
**`status: SUCCESS`** — con `response` vuota, e la verita' solo su stderr. Un run
e' andato bene se e solo se: **stato finale non d'errore**, **output non vuoto**,
**i file attesi esistono**. Tre condizioni insieme; ognuna, da sola, mente.

### 2. `session.idle` non e' un fine turno affidabile

Per le issue #26635 e #38661 il primo `idle` puo' precedere gli eventi finali.
Prima di dichiarare finita una sessione opencode, aspetta anche gli eventi di
chiusura o interroga `GET /session/:id/message`.

### 3. L'escalation e' a gradini, e ognuno ha un tempo

1. **silenzio** oltre N minuti senza eventi → si prova `POST /session/:id/abort`
   (opencode) o si chiude lo stdin (agy);
2. se non muore entro un tempo breve → **SIGTERM**;
3. se non muore → **SIGKILL**. Non e' pignoleria: oggi SIGTERM non ha smosso tre
   processi e ci e' voluto `pkill -KILL`.

N va **misurato e dichiarato**, non inventato: guarda quanto tempo passa
davvero fra due eventi in un lavoro normale, e prendi un multiplo generoso. Un
guardiano che uccide una sessione viva e' peggio di nessun guardiano.

## Cosa fa, in concreto

Un modulo `guardiano.py` con una funzione sola che conta:

```
esegui(incarico, motore, file_attesi, silenzio_max) -> Esito
```

- lancia il motore, apre il flusso **prima** di mandare il prompt (con opencode,
  aprire `/event` dopo perde i primi eventi);
- registra un **diario** (`stato/guardiano/<nome>.jsonl`) con un rigo per evento
  normalizzato: e' quello che oggi manca quando una sessione muore;
- applica le tre regole sopra;
- torna un `Esito` che dice: finito bene / fallito / ucciso per silenzio, con
  **il motivo**, i tempi e quali file attesi mancano.

Con opencode servono anche le **risposte ai permessi**
(`POST /session/:id/permissions/:permissionID`): oggi una sessione e' morta in 4
secondi per un permesso auto-negato. Il guardiano deve poter rispondere secondo
una politica dichiarata, non lasciare che il default neghi in silenzio.

## Come si prova, e qui non serve bruciare quota

I casi che contano si provano con un **finto motore** che emette righe da un
copione: e' anche progetto migliore, perche' separa il leggere dal decidere.

1. flusso normale fino a `result` → **finito bene**;
2. `status` di successo ma **output vuoto** → **fallito** (regola 1);
3. `status` di successo ma **file attesi mancanti** → **fallito** (regola 1);
4. flusso che si **interrompe a meta'** e non arriva piu' niente → ucciso per
   silenzio dopo `silenzio_max`, e il diario contiene tutti gli eventi arrivati
   fino a li';
5. un processo che **ignora SIGTERM** → il guardiano arriva a SIGKILL e lo dice;
6. eventi che arrivano **lenti ma regolari** → **non** viene ucciso (e' il falso
   positivo che rende inutile un guardiano);
7. `idle` che arriva **prima** degli eventi finali → non si dichiara finito
   troppo presto (regola 2).

Poi **una prova vera sola**, corta, con `agy` (ha il piano gratuito e un timeout
suo): un prompt banale in `--mode plan`, per verificare che il parsing del flusso
vero coincida col finto. **Non** lanciare prove vere con opencode: costa e oggi
gli endpoint sono stati instabili.

## Cosa NON fare

- Non usare il pacchetto **`opencode-ai`**: e' fermo alla 0.1.0a36 del 2025-08-27.
  L'API e' una REST normale, si parla con `requests` e la SSE si legge a righe.
- **Niente Node**: Elechim e' tutto Python.
- Non toccare `energia.py`, `sbobina.py`, `documenti.py`, i loro collaudi,
  `gateway.py`, `mac/`, `AGENTS.md`, `DA-FARE.md`, `unita/`, gli altri
  `INCARICO-*` e `RAPPORTO-*`.
- **`DEFINIZIONI` non si tocca.**
- Non avviare `opencode serve` come servizio di sistema e non aggiungere unit:
  qui si scrive la libreria, l'integrazione viene dopo.
- Niente dipendenze nuove oltre a quelle gia' in `requirements.txt`.

## Criterio di uscita

- `prova_guardiano.py` **TUTTO VERDE**, coi sette casi sopra;
- la prova vera con `agy` documentata, con gli eventi osservati;
- `RAPPORTO-guardiano.md` con: il `silenzio_max` scelto e **come l'hai misurato**,
  i tempi dell'escalation, il formato del diario, e cosa il guardiano **non** puo'
  fare (l'onesta' sui limiti vale piu' dell'elenco delle funzioni);
- `DEFINIZIONI` intatta, e dichiaralo.

Scrivi il rapporto **appena hai i numeri**. Oggi quattro sessioni su otto sono
morte perdendo proprio le conclusioni: stai costruendo la cosa che deve impedirlo,
non ripetere l'errore mentre la costruisci.
