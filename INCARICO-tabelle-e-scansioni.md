# Incarico: le tabelle false e le scansioni mute

Scritto il 15 agosto 2026, sera. Leggi prima `AGENTS.md` (la sezione "Stato" e'
stata riscritta stasera ed e' vera) e `PIANO-DOCUMENTI.md`.

Questo incarico prende i punti 1 e 2 di `INCARICO-qualsiasi-documento.md` e li
consegna. Sono due difetti indipendenti, corti, e **il secondo toglie il rischio
peggiore di tutto il sistema**. Il resto di quel file — docling, gli appunti a
mano — resta fuori: e' un altro giro.

**Un'altra sessione sta lavorando in parallelo su `sbobina.py`.** Vedi "Confini"
in fondo: ci sono file che non devi toccare, e non e' una preferenza di stile.

## Il collaudo e' rosso adesso, e lo era gia' al commit pubblico

```
$ .venv/bin/python prova_documenti.py
percorso font-size (PDF senza indice)...
AssertionError: tabelle_conservate == 2, atteso 1
```

Riproducibile in un minuto, sul PDF sintetico. **Comincia da qui**: e' lo stesso
difetto del PDF vero, in miniatura e senza bisogno di guardare il contenuto di
niente.

## 1. Le tabelle sono falsi positivi

Misure gia' fatte, non rifarle: su `Basic_Statistics_2007.pdf` la pipeline
dichiara **42 tabelle su 10 pagine**, e di quelle **26 sono per piu' del 50%
lettere**, cioe' paragrafi di prosa. Densita' media di cifre 2,9% contro il ~40%
di una tabella vera.

La causa e' in `_e_tabella`: dichiara tabella una riga con due o piu' spazi
ampi. **Su una pagina a due colonne il vuoto fra le colonne e' esattamente
quello.** Il rilevatore sta trovando l'impaginazione.

L'idea da provare **e misurare**, non da adottare al buio: una colonna di testo
ha **un solo** vuoto ampio, sempre alla stessa x su tutta la pagina; una tabella
ne ha piu' d'uno, con colonne corte e ricche di cifre. La densita' di cifre e'
gia' un segnale forte.

Numeri da battere, entrambi:

- sul sintetico: `tabelle_conservate == 1` (oggi 2);
- su `Basic_Statistics_2007.pdf`: **meno di 26 falsi positivi**, e riporta il
  numero nuovo accanto a quello vecchio.

Non ribaltare l'errore. La regola dice di sbagliare per eccesso, ma 26 paragrafi
di prosa chiusi in un recinto verbatim non sono prudenza: sono il testo reso
illeggibile. **Se elimini anche la tabella vera hai peggiorato**, e il collaudo
sul sintetico deve continuare a trovarne una.

## 2. Il rifiuto onesto sulle scansioni

Oggi la pipeline prova sempre la stessa strada. Su una scansione senza livello
di testo estrae **3 caratteri contro 3.610** e archivia il vuoto **senza dire
che e' il vuoto**. E' il rischio peggiore del sistema perche' e' silenzioso: te
ne accorgi mesi dopo, quando cerchi quel documento e non c'e'.

Prima di lavorare, **classifica**: caratteri per pagina, livello di testo
presente, indice incorporato, numero di colonne. Da li' si sceglie la corsia, e
**il rapporto dichiara quale ha usato** — serve a sapere quanto fidarsi.

Sotto la soglia il documento **non produce note**: va in `documenti/falliti/`
con la ragione scritta (`_scarta` in `documenti.py` scrive gia' un
`<nome>.ragione.txt` accanto al file, riusalo) e il rapporto lo dice a chiare
lettere. **Meglio un rifiuto esplicito che venti note vuote.**

**La soglia si misura, non si inventa.** Ti servono i casi: il PDF sintetico,
`DSML.pdf`, e una scansione che ti costruisci tu con `pdftocairo -png` piu'
ricomposizione — cosi' il caso di prova e' sintetico e la verifica e'
un'asserzione esatta invece di un giudizio. Scrivi nel README la soglia scelta e
i caratteri per pagina delle tre classi che l'hanno decisa.

Aggiungi al collaudo un caso permanente: **una scansione finisce in `falliti/`
con la ragione, e non lascia note nel vault.**

## Ordine di lavoro — vincolante

1. Il sintetico verde sulle tabelle. Piccolo, misurabile, chiude il collaudo.
2. La classificazione e il rifiuto. Corto, e toglie il rischio peggiore.
3. Le misure sul PDF vero, e il README.

**Prima il codice che gira, poi le misure.** Le sessioni che si sono consumate
in analisi sono finite senza scrivere il file. Scrivi il primo file entro il
primo minuto.

## Come si prova — questo vincola il metodo

Vale la regola di `AGENTS.md`: **il contenuto dei documenti non entra nel tuo
contesto.** Tu sei l'architetto e il muratore, non l'operaio che legge i PDF.

- Sul sintetico puoi leggere tutto: il testo l'abbiamo scritto noi.
- Sul PDF vero **stampa e leggi solo le metriche**: pagine, caratteri, tabelle,
  densita', wikilink. Non aprire `markdown/`, non incollare passaggi.
- Titoli, conteggi e nomi di file sono metadati e li puoi guardare. Il corpo no.
- Se ti serve un'occhiata al testo per capire un guasto, **fermati e scrivilo
  nel rapporto**: quella verifica la fa il proprietario, in locale.

## Confini — un'altra sessione sta lavorando adesso

- **Non toccare `sbobina.py`** (non esiste ancora: lo sta scrivendo l'altra
  sessione) ne' `mac/`, ne' `strumenti.py`, ne' `gateway.py`.
- **Non toccare `DEFINIZIONI`.** Verificala e riporta l'impronta: il confronto
  che vale e' fra `strumenti.py` e `mac/strumenti.py`, e devono restare identici.
- **Non modificare `README.md` e `AGENTS.md`.** Scrivi invece
  **`RAPPORTO-tabelle-e-scansioni.md`** con quello che andrebbe nel README: la
  lezione e il numero che la dimostra, in italiano, nello stile del resto. Le
  integra Claude, per non ritrovarci due sessioni che si sovrascrivono la
  memoria condivisa a vicenda.
- **Non toccare git**: niente `add`, `commit`, `push`.
- **Non riavviare ne' fermare i servizi** (`elechim-gateway`, `macmini-tunnel`,
  `searxng`, `crawl4ai`). Il bot e' in uso vero.
- **Non installare pacchetti da gigabyte**: niente torch, marker, docling. Qui
  si lavora con poppler, che c'e' gia'.
- La coda ha un lock da stasera: se lanci `documenti.py` mentre il servizio
  systemd sta macinando, esci con "coda gia' in lavorazione" ed e' corretto,
  non e' un guasto.

## Criterio di uscita

- `prova_documenti.py` **tutto verde**, coi due casi nuovi dentro (tabelle sul
  sintetico, scansione rifiutata);
- falsi positivi su `Basic_Statistics_2007.pdf` **sotto 26**, col numero scritto;
- la soglia di rifiuto misurata e motivata in `RAPPORTO-tabelle-e-scansioni.md`;
- il rapporto di copertura dichiara la **corsia usata**;
- `DEFINIZIONI` intatta e identica nelle due copie, impronta riportata;
- nel rapporto finale: cosa hai lasciato indietro e perche', e le decisioni da
  far confermare al proprietario.
