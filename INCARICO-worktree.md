# Incarico: un worktree per sessione, senza rompere i lock

Scritto il 17 agosto 2026 sera. Leggi prima `AGENTS.md`.

## Il problema

Oggi due sessioni di opencode non possono lavorare insieme sugli stessi file, e
i conflitti sono **vietati a parole** — «non toccare `sbobina.py`» scritto negli
incarichi — non **impossibili**. Ha retto solo perche' c'era qualcuno a
programmare l'ordine a mano.

La soluzione e' un **worktree git per sessione**: ogni sessione lavora su una
copia isolata del codice, e il conflitto sparisce per costruzione.

## La trappola, che va capita prima di scrivere codice

I moduli calcolano i percorsi cosi':

```python
BASE = Path(__file__).resolve().parent
STATO = BASE / "stato"
GPU_LOCK = STATO / ".gpu.lock"     # energia.py
```

In un worktree `__file__` sta altrove, quindi **`GPU_LOCK` diventa un file
diverso** — e un `flock` su due inode diversi non esclude proprio niente. Lo
stesso vale per `.coda.lock` di `documenti.py` e per la bandiera `stato/gioco`
che il **gateway** legge: una sessione in un worktree la alzerebbe dove nessuno
guarda.

Cioe': i worktree fatti ingenuamente **annullano il mutex GPU appena costruito**,
in silenzio.

## Il principio: il codice si isola, lo stato si condivide

E' la divisione giusta, non un compromesso. I conflitti che abbiamo avuto sono
di **codice** (due sessioni che scrivono `sbobina.py`); i lock esistono apposta
per serializzare le risorse **condivise** (GPU, coda). Quindi:

| cosa | dove |
|---|---|
| il codice (`*.py`, gli `INCARICO-*`, i `RAPPORTO-*`) | **per worktree** |
| `stato/`, `markdown/`, `documenti/in`, `documenti/falliti`, `archivio/` | **condivisi col repo principale** |
| `.venv` | **condivisa** col principale |
| le fixture versionate (`documenti/elaborati/prova-*.pdf`) | **per worktree** |

L'ultima riga e' un guadagno gratuito: il collaudo **cancella** quelle fixture
(sezione 9 di `DA-FARE.md`), e con un worktree per sessione la cancellazione
resta isolata. Oggi le ho ripristinate cinque volte a mano.

## Il lavoro

Uno script `lavoro.sh` (o `lavoro.py`, decidi tu e motiva) con tre verbi:

- **`apri <nome>`** — crea il worktree da un ramo nuovo `lavoro/<nome>`, mette i
  collegamenti verso lo stato condiviso e la `.venv`, e stampa il percorso.
- **`stato`** — elenca i worktree aperti, con il ramo, se ha modifiche non
  committate e da quanto e' fermo.
- **`chiudi <nome>`** — dopo che il lavoro e' stato verificato: riporta il ramo
  nel principale (`merge --no-ff`) e rimuove il worktree. **Non** deve poter
  cancellare un worktree con modifiche non committate senza dirlo.

I collegamenti verso lo stato condiviso: **symlink** verso il repo principale.
Sono l'opzione senza modifiche al codice — `flock` finisce sullo stesso inode e
tutto continua a funzionare. Se pensi che una variabile d'ambiente sia meglio,
**proponilo nel rapporto** ma non farlo qui: toccherebbe `energia.py`,
`documenti.py` e `sbobina.py`, e su quei file c'e' appena passata un'altra
sessione.

## Come si prova, e i casi che contano

`prova_worktree.py` nuovo. **Il caso 1 e' il motivo di tutto l'incarico:**

1. **Il lock GPU regge fra worktree diversi**: un processo che prende
   `energia.riserva_gpu` nel repo principale e un altro che la prende **dentro
   un worktree** si devono escludere davvero. Misura l'**ordine**, come si e'
   fatto per il lock stesso: il secondo non deve cominciare prima che il primo
   abbia finito. Se questo test non passa, il resto non serve.
2. Lo stesso per `.coda.lock` di `documenti.py`.
3. La bandiera `stato/gioco` alzata dentro un worktree e' vista **dal repo
   principale** (e' quella che il gateway legge).
4. `apri` due volte con lo stesso nome non rompe niente e lo dice.
5. `chiudi` su un worktree con modifiche non committate **rifiuta** e spiega.
6. Le fixture cancellate dentro un worktree **non spariscono** dal principale.
7. `.venv` e' raggiungibile dal worktree: `.venv/bin/python -c "import energia"`
   funziona da li'.

## Cosa NON fare

- **Non toccare** `energia.py`, `sbobina.py`, `documenti.py`, i loro collaudi,
  `gateway.py`, `mac/`, `AGENTS.md`, `DA-FARE.md`, `unita/`, gli `INCARICO-*` e
  `RAPPORTO-*` esistenti.
- **`DEFINIZIONI` non si tocca.**
- Non fare `push`, non toccare `main` se non con il `merge` esplicito di
  `chiudi`, e **non cancellare rami** che non hai creato tu.
- Niente dipendenze nuove.
- Non spostare `stato/`, `markdown/` o `documenti/` dal repo principale: qui si
  aggiungono collegamenti, non si riorganizza il progetto.

## Criterio di uscita

- `prova_worktree.py` **TUTTO VERDE**, col caso 1 dentro e provato;
- `prova_sbobina.py` e `prova_documenti.py` **ancora verdi** dal repo principale:
  la prova che non hai rotto niente;
- `RAPPORTO-worktree.md` con: la scelta symlink contro variabile d'ambiente e il
  perche', la prova che il lock GPU regge fra worktree (coi tempi), e cosa
  succede a un worktree lasciato aperto per giorni;
- `git worktree list` pulito alla fine, nessun worktree di prova lasciato in giro.

Scrivi il rapporto **appena hai i numeri**, non alla fine.
