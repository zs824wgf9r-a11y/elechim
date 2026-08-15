# Incarico: macinare qualsiasi documento

Scritto il 15 agosto 2026. Leggi prima `AGENTS.md` e `PIANO-DOCUMENTI.md`.
Il proprietario ha posto il criterio: **deve macinare qualsiasi PDF, nota e quant'altro.**
Oggi non e' vero, e questo incarico chiude il divario in tre passi, in
quest'ordine.

## Dove siamo, misurato il 15 agosto

| classe | stato |
|---|---|
| digitale con indice incorporato | ✅ 533 pagine in 70s, titoli esatti |
| digitale senza indice | ✅ ripiego font-size, 9/9 wikilink, dediche scartate e contate |
| digitale a due colonne | ⚠️ testo giusto, tabelle da rifinire |
| **scansione senza livello di testo** | ❌ **3 caratteri contro 3.610** |
| foto di appunti a mano | ❌ non contemplato |
| docx, epub, html, slide | ❌ non contemplato |

## 1. La duplicazione — prima di tutto, corrompe i dati adesso

Dopo il collaudo di interruzione/ripresa, `markdown/prova-due-colonne.md`
contiene **18 marcatori di pagina per 11 pagine**: le pagine 5-11 sono scritte
**due volte**.

Su un libro vero interrotto da una sospensione — che e' il caso normale, il
fisso dorme da solo — significa **contenuto doppio nell'integrale**, sezioni
doppie e conteggi gonfiati. E la ripartibilita' e' proprio la proprieta' per cui
la coda e' costruita cosi'.

`genera_markdown` riprende da `ultima = max(pagine gia' presenti)`. Trova
perche' quel calcolo puo' ripartire da un valore vecchio e **rendi la scrittura
di una pagina idempotente**: scrivere la pagina N due volte deve lasciare il
file identico. Non fidarti del solo `ultima`: e' gia' dimostrato che non basta.

Aggiungi al collaudo un'asserzione permanente: **marcatori di pagina distinti ==
pagine totali**. E' il controllo che avrebbe preso questo difetto al primo giro.

## 2. Il rilevatore di classe e il rifiuto onesto — poco lavoro, toglie il rischio peggiore

Oggi la pipeline prova sempre la stessa strada. Su una scansione produce il
vuoto **senza dire che e' il vuoto**: crede di aver archiviato una cosa che non
c'e'. E' il rischio peggiore di tutto il sistema, perche' te ne accorgi mesi
dopo quando cerchi quel documento.

Prima di lavorare, classifica: caratteri per pagina, presenza di un livello di
testo, indice incorporato, numero di colonne. Da li' si sceglie la corsia, e
**il rapporto dichiara quale ha usato** — serve a sapere quanto fidarsi.

**Sotto una soglia di caratteri per pagina il documento non produce note**: va
in `documenti/falliti/` con la ragione scritta (`"sembra una scansione, serve
OCR"`) e la notifica lo dice. **Meglio un rifiuto esplicito che venti note
vuote.** Misura la soglia sui documenti che hai (il sintetico, DSML, e una
scansione che ti costruisci con `pdftocairo -png` piu' ricomposizione), non
inventarla.

## 3. Docling come seconda corsia

**La corsia veloce resta.** 533 pagine in 70 secondi, deterministica, senza
modelli: docling sara' molto piu' lento. Prende in carico **cio' che la corsia
veloce rifiuta**, non la sostituisce. E' la struttura a due corsie gia' decisa
l'11 agosto; cambia solo il motore della seconda.

**Perche' docling e non Marker**, e va rispettato:

- **gira su CPU.** La VRAM e' la risorsa scarsa: 8.188 MiB, di cui ~1.400 per
  X11 e ~5.000 per il modello delle sbobine. Un estrattore su CPU fa si' che
  estrazione e riscrittura **non si contendano la scheda**. Marker vuole `torch`
  e la GPU: litigherebbe proprio col pezzo piu' importante.
- **ingerisce anche DOCX, PPTX, XLSX, HTML e immagini**, quindi chiude tre
  classi mancanti invece di una.
- **licenza MIT**, senza le soglie di Marker.

Da misurare e scrivere nel README, sul PDF-scansione di prova e su DSML:

1. caratteri estratti contro la corsia veloce (dove entrambe funzionano);
2. **secondi per pagina** — e quindi il tempo per un libro da 533 pagine;
3. RAM occupata, e se davvero non tocca la GPU (`nvidia-smi` durante);
4. se la sua struttura (titoli, gerarchia) e' migliore o peggiore del nostro
   percorso outline. **Sul documento con indice incorporato il nostro resta
   autorevole**: docling non deve mai sovrascrivere una struttura che il PDF
   dichiara.

Se docling risulta troppo lento o troppo pesante, **dillo con i numeri e
fermati**: meglio una corsia sola che funziona di due che si ostacolano.

## 4. Le foto degli appunti a mano — il pezzo che c'e' gia'

`qwen3-vl:4b` e' **gia' installato e in servizio** sul fisso, e legge pagine
scansionate e scrittura a mano. Non serve niente di nuovo.

Non implementarlo in questo incarico: **verifica soltanto** che una foto di
appunti passata a `visione.py` produca testo utile, e scrivi l'esito nel README.
Se funziona diventa il prossimo incarico, ed e' probabilmente la cosa che
il proprietario usera' di piu'.

Ricorda le trappole gia' pagate: immagini ridotte a 1536px (a piena risoluzione
legge `AROSAKA` per `ARASAKA`), `exif_transpose`, istruzione **semplice**, e
margine su `num_predict` perche' il ragionamento lo consuma e `content` torna
vuoto con `done_reason: length`.

## Fuori scopo

- Non toccare `DEFINIZIONI` (impronta `1160ec454b8b9998`, verificala e riportala).
- Non installare Marker, MinerU, `pymupdf4llm`: valutati e **rimandati**.
  `pymupdf4llm` sostituirebbe codice appena scritto e collaudato — churn, finche'
  non compra qualcosa di misurato.
- Non toccare la sbobina ne' l'elaborazione degli appunti: sono altri incarichi.

## Ordine di lavoro

**Prima il codice che gira, poi le misure.** Le sessioni che hanno consegnato
sono quelle che hanno scritto per prime. Il punto 1 e il punto 2 sono corti e
vanno consegnati **prima** di cominciare a valutare docling: se la sessione
finisce li', il sistema e' comunque migliore di adesso.
