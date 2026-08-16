# Fase 4 — Ingestione documenti

Stato: **progettata l'11 agosto 2026, non ancora implementata.** Questo file e'
il punto di ripresa: il fisso e' stato spento per montare la GTX 1050.

Obiettivo dichiarato dal proprietario: mandare a Elechim un PDF anche da 80+ pagine,
con schemi, immagini e tabelle, e ritrovarselo elaborato **da tutto
l'ecosistema** come appunti su Obsidian, **senza tralasciare nulla**. Honcho
incluso nel disegno.

## Il vincolo che decide tutto

Ottanta pagine sono 40-70K token. Il contesto del Mac e' 65.536: non ci stanno,
e anche se ci stessero sarebbero 35-50 minuti di solo prefill a 23 tok/s.

**Il Mac non vede mai il documento.** Nemmeno a pezzi, nemmeno una volta. Vede
una sintesi da ~300 token e un handle.

Non e' una rinuncia: e' la ragione per cui "senza tralasciare nulla" e'
ottenibile. La completezza non puo' venire da un modello che legge tutto e
riassume — e' esattamente cio' che nessun modello fa in modo affidabile, meno
che mai un 4B. Viene da una **pipeline deterministica che passa su ogni
pagina**, in cui il modello non e' mai l'unica copia dell'informazione.

## Il principio: l'integrale e' la verita', le note sono l'indice

- Il markdown integrale estratto resta in `~/assistente/markdown/<slug>.md`,
  **fuori dal vault**.
- Le note su Obsidian sono lo strato di navigazione sopra quel testo, con
  ancore che ci puntano.
- Se una nota e' imprecisa o salta un passaggio, l'informazione non e' persa:
  e' a un link di distanza, testuale e ricercabile.

Corollario non negoziabile: **le tabelle non passano mai per un LLM.** I macro
di un piano alimentare, i numeri di uno schema: estratti come markdown e
lasciati verbatim. E' il punto in cui un 4B ti cambia un 180 in un 150 e non te
ne accorgi mai piu'.

## La catena

### 1. Ingestione — due porte

- **Telegram**, per i file piccoli. Attenzione: la Bot API scarica al massimo
  **20MB**, e un PDF da 80 pagine con immagini li supera spesso.
- **Cartella sorvegliata** `~/assistente/documenti/in/` per tutto il resto:
  ci si butta dentro il file da Dolphin o via `scp`. Stessa coda, stesso
  trattamento.

### 2. Estrazione — due velocita'

- **Corsia veloce**: se il PDF ha il livello di testo (nato digitale, come un
  manuale o un rapporto professionale), `pdftotext -layout` lo prende in millisecondi. Niente
  GPU, niente modello, niente possibilita' di allucinare. Poppler 26.01 e' gia'
  installato.
- **Corsia piena**: per scansioni, schemi e tabelle su piu' colonne, **Marker**
  sul 4060 Ti — layout-aware PDF->markdown, tiene le tabelle, fa OCR solo dove
  il livello di testo manca. Da installare: serve `torch` (~3GB), il venv e'
  Python 3.12, ci sono 783GB liberi. Alternative da valutare: docling, MinerU,
  pymupdf4llm per la corsia leggera.

**Ordine di costruzione deciso**: prima la corsia veloce con la catena
*completa* fino alla nota su Obsidian, poi Marker innestato come secondo motore.
L'ordine inverso rischia di far passare una giornata su `torch` senza avere
ancora una nota nel vault.

### 3. Figure — il pezzo che di solito si perde

Ogni immagine e ogni schema si estrae come PNG in `90-Allegati/`, e
**qwen3-vl la descrive**: la descrizione finisce nel markdown accanto al link
dell'immagine. Cosi' un diagramma smette di essere un buco nel testo e diventa
qualcosa che si puo' cercare, incorporare e ricordare.

Serve un filtro a monte su dimensione e proporzioni, o si finisce a descrivere
quaranta loghi di intestazione.

Vedi le trappole gia' note del VLM in `visione.py`: il ragionamento consuma
`num_predict` e puo' restituire contenuto **vuoto**; istruzione semplice e
margine di token.

### 4. Note su Obsidian — le scrive il fisso (regola 4)

Una cartella per documento in `20-Documenti/<slug>/`: la nota indice con
frontmatter e tag, e da li' i wikilink alle note atomiche in `30-Note/`, una per
sezione. **Mai una nota unica da 80 pagine**, che in Obsidian e' inutilizzabile.

### 5. Rapporto di copertura — cio' che rende vera la promessa

A fine lavoro, su Telegram: pagine processate su totali, sezioni con e senza
nota, figure descritte, tabelle conservate. Se qualcosa e' stato saltato lo
vedi, invece di fidarti.

### 6. Indice vettoriale

Chunk per struttura (titoli), non a lunghezza fissa, con ancore di pagina.
Embedding con `bge-m3` -> pgvector, lo stesso Postgres di Honcho.

## Dove sta Honcho, e dove non sta

Honcho e' il modello **della persona**, non un archivio di documenti. Versargli
dentro 80 pagine da' un motore di ricerca mediocre e un modello dialettico
annegato.

- In **Honcho** va il fatto sul proprietario: "dal 1 marzo: corso di tedesco,
  due sere a settimana" — con una data, che fra tre mesi verra'
  **superato e non cancellato** (vedi `dreaming-mode-consolidamento`).
- Nel **vault + indice vettoriale** va il corpo del documento.

Due archivi, due mestieri, un solo database.

## Cosa vede il Mac

> Documento ingerito: 80 pagine, 34 figure, 12 tabelle. [~300 token di sintesi]
> handle: `doc:manuale-2026-03`

Poi il proprietario chiede e un tool restituisce i passaggi pertinenti, compressi, come
fa gia' `leggi`.

**Trappola di tempismo**: aggiungere un tool invalida la cache
(`entry.tools == request.tools`). I tool che mancano — documenti e memoria —
vanno aggiunti **tutti insieme, una volta sola**, non uno per fase. Va deciso
l'elenco definitivo prima di toccare `DEFINIZIONI`.

## Tempi e VRAM

Per 80 pagine: Marker 3-6 min, figure 3-5, note ed embedding 4-8. **Sotto i
venti minuti** => lavoro asincrono con notifica su Telegram (regola 7) e **coda
ripartibile**, perche' il fisso e' spegnibile e un lavoro interrotto deve
riprendere da dove era, non da capo.

Sugli 8GB non convivono Marker (~2-3GB), qwen3-vl (3,3GB) e whisper (1,6GB): la
pipeline va **a stadi** — tutta l'estrazione, scarico, tutte le figure — col
lock GPU gia' presente in `gateway.py`.

## La GTX 1050 — montata l'11 agosto 2026, e scartata lo stesso giorno

Doveva tenere **`bge-m3` residente**, sempre acceso, per non togliere mai VRAM
alla 4060 Ti. **Non se ne fa niente.** Due motivi indipendenti, entrambi
verificati a scheda montata.

**1. Pascal non ha piu' driver.** Il branch 610 esiste solo come modulo *open*,
che richiede il GSP (Turing in su); il 580 e' l'ultimo che supporta Pascal.

```
NVRM: The NVIDIA GPU 0000:04:00.0 (PCI ID: 10de:1c81) ... is not supported by
NVRM: open nvidia.ko because it does not include the required GPU System
NVRM: Processor (GSP).
nvidia 0000:04:00.0: probe with driver nvidia failed with error -1
```

`nvidia-smi` elenca solo la 4060 Ti. Nouveau e' in blacklist sulla riga di
comando del kernel e comunque non da' CUDA.

**2. Tornare al 580 non servirebbe comunque.** `bge-m3` e' XLM-RoBERTa-large,
568M parametri: **2,27GB in fp32 su una scheda da 2GB**. E l'fp16 consumer su
GP107 gira a **1/64** del rate fp32, quindi caricarlo in mezza precisione per
farcelo entrare lo renderebbe piu' lento della CPU. Il lavoro assegnato non ci
stava fin dall'inizio.

**Decisione**: gli embedding restano sul fisso senza scheda dedicata —
`bge-m3` via **ollama**, che e' gia' un servizio attivo, sotto lo stesso lock
GPU di `gateway.py`, con `keep_alive` corto; oppure forzato su CPU
(`num_gpu: 0`) quando la 4060 Ti serve per Marker, la visione o per giocare.
La 1050 puo' essere rimossa al prossimo spegnimento: non fa danni, ma non
serve.

**L'effetto collaterale che ha rotto qualcosa di vero.** Montare la scheda ha
**rinumerato i bus PCI**: 4060 Ti da `0a:00.0` a `07:00.0`, NIC I225-V da
`09:00.0` a `06:00.0`, quindi l'interfaccia **da `enp9s0` a `enp6s0`**. La
connessione `MacMini-Direct` era legata a `connection.interface-name = enp9s0`:
non e' piu' salita, niente `10.0.0.1`, `macmini-tunnel.service` in restart loop
e Elechim senza ricerca web, vocali e immagini — col Mac perfettamente acceso e
il cavo collegato. Risolto legandola al **MAC** e svuotando `interface-name`:

```
nmcli con mod MacMini-Direct connection.interface-name "" \
      802-3-ethernet.mac-address c8:7f:54:6e:0d:54
```

Stessa lezione degli indici GPU: **mai legarsi a un nome che dipende dalla
topologia PCI.** Vale anche al contrario, quando la 1050 verra' tolta.

**Controlli post-montaggio, esito**: 4060 Ti ancora **Gen4 x8** (hostmax 4, la
Gen4 del BIOS e' sopravvissuta), `compute_mode Default`, indice 0, UUID
`GPU-ae0d3d2a-9b5c-c404-64cd-3ab42ec60cd8`, X11 sul 4K dalla 4060 Ti, nessun
unit systemd con `nvidia-smi -i <indice>`. Il pinning di ollama e
`faster-whisper` per UUID **non serve piu'**: c'e' una sola GPU visibile al
driver. Da rifare solo se un giorno si torna al 580 con due schede vive.

---

## Dove vivono i documenti — deciso il 15 agosto 2026

Tre cartelle, tre mestieri:

```
documenti/originali/      come l'ha mandato il proprietario, mai toccato, solo sul fisso
~/Obsidian/90-Allegati/   arricchito con l'indice iniettato, DENTRO il vault
markdown/                 l'integrale, fuori dal vault
```

**Perche' l'arricchito sta dentro il vault**: le note oggi linkano
`file:///home/NOME_UTENTE/...`, e sul portatile la home e' `/home/NOME_UTENTE`.
**Tutti quei link sono rotti fuori dal fisso.** Dentro il vault il collegamento
e' relativo e funziona su qualsiasi macchina, adesso e in futuro.

Costo accettato: ~21MB per documento sincronizzati ovunque. Per un secondo
cervello, avere la fonte a un clic dalla nota vale piu' dello spazio.

**Regola che tiene il sistema riparabile**: l'arricchito si rigenera **sempre
dall'originale**, mai da se' stesso. Cosi' non accumula indici sovrapposti, e
quando il rilevamento migliora basta rilanciare per avere un PDF migliore.
L'arricchito e' una funzione pura di (originale + codice); se smette di esserlo,
ogni miglioramento diventa un rischio.

**Corollario**: nessuna nota deve contenere un percorso assoluto. Se un
artefatto serve cliccabile, sta nel vault; se sta fuori, nella nota e' un
riferimento testuale e non un link che mente.

## Gli appunti del proprietario non sono documenti — deciso il 15 agosto 2026

Un PDF si puo' riestrarre mille volte: l'originale non cambia. **Un appunto
scritto dal proprietario e' l'unica copia di un suo pensiero**, e la formulazione *e'*
il contenuto.

Quindi, sui file scritti da lui: **mai riscrivere sul posto.** Il modello puo'
aggiungere accanto — collegamenti ad altre note, un titolo, dei tag, una
spiegazione, una sintesi in un blocco separato — ma il testo che ha scritto lui
non si tocca, non si "migliora" e non si accorcia. Un 8B che ripulisce la frase
buttata giu' alle due di notte porta via l'intuizione insieme alla sciatteria.
