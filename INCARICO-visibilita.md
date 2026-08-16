# Incarico: rendere Elechim trovabile (e degno di essere trovato)

Scritto il 16 agosto 2026. **Le tre decisioni in fondo sono state prese dal
proprietario la notte del 16 agosto: licenza MIT, dati personali da togliere,
README in inglese con l'italiano a fianco.** Si esegue.

Obiettivo del proprietario: dare visibilita' al progetto **restando anonimo**.
Non e' vanita' — un progetto che nessuno usa non riceve segnalazioni, e le
segnalazioni sono l'unico modo per scoprire i difetti che il collaudo non vede.

## Prima di tutto: cosa blocca oggi

Misurato il 16 agosto sul repo `zs824wgf9r-a11y/elechim`:

```
licenseInfo: null      topics: null      stars: 0      homepage: ""
README: in italiano
```

**Senza licenza un repo pubblico e' "tutti i diritti riservati"**: nessuno puo'
legalmente usarlo, forkarlo o contribuire. E' il primo filtro che uno
sviluppatore applica, e rende falsa la frase di `INCARICO-repo-pubblico.md`
(«perche' chiunque possa usarlo»). Nessuna ottimizzazione compensa questo.

## Il punto che cambia la strategia

La guida generica dice: tag, SEO, GitHub Pages, condividi sui social. Vero, ma
non e' li' che sta il valore di questo progetto.

**La cosa piu' preziosa di Elechim non e' il codice: sono le misure.** Un
"assistente AI locale" e' uno dei cinquanta su GitHub. Un progetto che spiega,
col numero accanto, perche' ha fatto scelte controintuitive, e' raro:

- **il modello non vede mai il documento** — l'opposto di ogni RAG, e c'e' la
  ragione: prefill a 23 tok/s, una slot di cache sola;
- **26 tabelle false su 42**, perche' il vuoto fra due colonne sembra una
  tabella;
- in un libro di matematica **`x²` diventa `x2`** e nessuno se ne accorge: il
  41% delle parole di una pagina densa e' in corpo ridotto e `pdftotext` butta
  via l'informazione;
- **«senza tralasciare nulla» come invariante**: `caratteri_coperti ==
  caratteri_fonte`, asserito nel collaudo;
- 46 sezioni saltate su 223 che erano **meta' del libro** in caratteri;
- le trappole gia' pagate: `BindsTo` che disattiva `Restart=always`,
  `OnUnitActiveSec` che non avanza durante la sospensione, l'interfaccia di rete
  che cambia nome quando monti una seconda GPU.

**La distribuzione viene dal racconto, il repo e' dove si atterra.** Un post
tecnico onesto con questi numeri porta piu' visite di qualsiasi lista di topic.
Quindi il lavoro qui sotto serve a fare in modo che chi atterra **resti**.

## 1. La licenza (decisione 1 in fondo)

Un file `LICENSE` con l'anno e l'intestatario **`Elechim`** — mai il nome vero.
Aggiungere la riga corrispondente nel README e nei metadati del repo.

## 2. Il README come vetrina (decisione 3 in fondo)

Il README attuale e' **documentazione operativa**, ottima per chi lavora qui e
sbagliata come vetrina: comincia da "Chi fa cosa" e dal tunnel ssh. Chi arriva
da fuori ha bisogno, nei primi venti secondi, di sapere **cos'e'** e **perche'
dovrebbe importargli**.

Struttura da usare:

1. **Una riga** che dice cos'e', senza aggettivi. Non "un potente assistente":
   "un assistente personale che gira interamente su due macchine di casa, dove
   il modello non vede mai i tuoi documenti".
2. **Perche' e' diverso** — tre o quattro punti, ciascuno **con il numero
   accanto**. E' la parte che convince, ed e' gia' tutta scritta nel README
   attuale: va solo estratta e messa in cima.
3. **Un diagramma** della topologia a due macchine. Ascii o mermaid, non
   un'immagine: si legge anche da terminale e non si rompe.
4. **Cosa funziona e cosa no**, onestamente. Il README attuale lo fa gia' ed e'
   una delle sue qualita': va tenuto in evidenza, non nascosto in fondo. Un
   README che promette piu' del vero fa perdere tempo, e chi ci perde tempo non
   torna.
5. **Installazione**: c'e' gia', va solo spostata dopo la vetrina.
6. **Il requisito hardware dichiarato subito**: due macchine, un Mac con
   TurboFieldfare e un PC con una GPU. E' un progetto difficile da riprodurre e
   **dirlo in cima** e' onesto: chi non ha quel setup non apre una issue
   frustrata, e chi ce l'ha si sente parlare addosso.

## 3. Metadati del repo

- **Descrizione**: una riga, con le parole che uno cercherebbe davvero.
  Oggi dice "in italiano", che restringe il pubblico prima ancora di cominciare.
- **Topics** (massimo ~10, quelli veri, non a caso): `local-llm`,
  `personal-assistant`, `ollama`, `obsidian`, `rag`, `telegram-bot`,
  `self-hosted`, `privacy`, `pdf-extraction`, `whisper`.
- Nessuna GitHub Pages per ora: una pagina vuota fa peggio di nessuna pagina.

## 4. `CONTRIBUTING.md`, corto e onesto

Il progetto e' cucito su due macchine specifiche: va detto che le pull request
sono benvenute ma **non c'e' modo di collaudarle** su hardware diverso, e che le
segnalazioni piu' utili sono quelle con **numeri** (log, misure, `nvidia-smi`),
perche' e' cosi' che lavora tutto il resto del progetto.

Aggiungere che la documentazione interna resta in italiano, e perche': e' la
memoria di lavoro, non la vetrina.

## 5. Riconoscimenti — chi ci ha fatto risparmiare mesi

Voluto dal proprietario, e non e' cortesia: e' il modo piu' efficace di farsi
notare, perche' i progetti citati spesso ricambiano, e perche' un progetto che
dichiara su cosa poggia e' un progetto di cui ci si fida di piu'.

**L'elenco e' verificato dal codice il 16 agosto 2026** (import veri, porte in
ascolto, binari invocati): non aggiungerne di fantasia, non toglierne.

*Su cui gira, oggi:*

| cosa | a cosa serve qui |
|---|---|
| **TurboFieldfare** (`127.0.0.1:8080`) | il server del modello sul Mac mini. La sua `ServerPromptCache` a slot singola e' il vincolo da cui discende meta' dell'architettura |
| **ollama** (`127.0.0.1:11434`) | i modelli sul fisso: `qwen3-vl:4b` per le immagini, `qwen3:8b` per la sbobina |
| **SearXNG** (`127.0.0.1:8888`) | metamotore di ricerca locale — trova le pagine |
| **crawl4ai** (`127.0.0.1:11235`) | le scarica e le estrae |
| **trafilatura** + **requests** | la corsia statica, rimasta come ripiego |
| **faster-whisper** (`large-v3`) | i vocali di Telegram |
| **poppler** | `pdftotext`, `pdfinfo`, `pdftohtml`, `pdfimages`, `pdftoppm`: tutta la corsia veloce dei documenti |
| **pypdf** | l'outline incorporato dei PDF, che ha battuto ogni euristica sui font |
| **Obsidian** | il vault dove atterrano le note |
| **Syncthing** | la coda dei documenti fra le macchine |
| **podman** (quadlet) + **systemd** | i servizi, e la loro sopravvivenza al riavvio |
| **ffmpeg** | l'audio |

*Modelli*: `gemma-4-26b-a4b-it` (Mac), `qwen3-vl:4b` e `qwen3:8b` (fisso),
`whisper large-v3`.

*Idee prese in prestito, con onesta':*

- **[SurfSense](https://github.com/MODSetter/SurfSense)** (Apache 2.0) — non e'
  stato adottato, ma la sua ricerca ibrida ci ha convinti che **Reciprocal Rank
  Fusion** fosse la risposta giusta per unire tre archivi. `fusione.py` e'
  un'implementazione nostra dell'algoritmo pubblico, non codice loro.
- **RRF**, Cormack, Clarke, Buettcher (2009) — venti righe che risolvono il
  problema di fondere punteggi che non sono confrontabili.
- **Honcho** — il modello della persona per la fase 3, non ancora integrato.
- **docling** — candidato per la seconda corsia dei documenti, non ancora usato.
- **Khoj** e i vari "second brain" — utili per capire cosa **non** volevamo
  fare: il modello che legge i documenti.

*Costruito con*: **opencode** e **Claude Code**, che qui hanno un ruolo preciso
e limitato — architetti e muratori, mai operai. Vedono il codice, i log e le
metriche; **mai** il contenuto di un documento o di una conversazione. Vale la
pena scriverlo nel README: e' una scelta di progetto, non un dettaglio.

## 6. Obiettivi futuri — la roadmap

Voluta dal proprietario. Deve essere **onesta**: cio' che non c'e' si dichiara,
e non si promette una data. La fonte e' `DA-FARE.md`, che va tenuto allineato.

Da scrivere nel README (inglese) in forma breve, con lo stato vero:

- **fase 4, il resto**: estrazione delle figure (`90-Allegati/` e' vuota, le
  figure vettoriali vanno rese con `pdftocairo`); **docling** come seconda
  corsia per le scansioni, che oggi vengono rifiutate onestamente ma non lette;
  le **foto di appunti a mano**, per cui `qwen3-vl` e' gia' in casa.
- **la sbobina su documenti veri**: il codice c'e' e il collaudo e' verde sul
  sintetico, ma non e' ancora passata su un libro intero.
- **fase 3, la memoria**: Postgres+pgvector, `bge-m3`, Honcho per i fatti sulla
  persona — datati, superati e mai cancellati. `fusione.py` (RRF) e' gia'
  pronto ad aspettarla. **Da valutare se partire da una ricerca full-text e
  aggiungere il vettoriale solo dove fallisce**, invece del contrario.
- **i quattro tool definitivi** (`cerca`, `leggi`, `ricorda`, `salva`), da
  applicare **tutti insieme una volta sola**, perche' toccare le definizioni
  invalida la cache di ogni conversazione.
- **dreaming mode**: consolidamento notturno guidato dagli eventi, non
  dall'orologio — connessioni fra fonti, contraddizioni, e oblio inteso come
  *datare e superare*, mai cancellare.
- **sospensione intelligente**: oggi il fisso guarda l'inerzia della scrivania,
  non il lavoro in corso.

## Il confine che non si sposta, qualunque visibilita' arrivi

**Le conversazioni Telegram e i PDF del proprietario non entrano nel repo. Mai.**
Non sono materiale interessante per nessuno e sono privati: la visibilita' non
cambia questa riga di una virgola, semmai la rende piu' importante.

Verificato il 16 agosto, dopo il primo push: `archivio/`, `stato/`, `stato.db`,
`markdown/`, `documenti/in/`, `documenti/falliti/`, `DSML.pdf` e `.megamemory/`
sono **tutti fuori**; nel repo ci sono 50 file e sotto `documenti/` esistono
solo le due fixture sintetiche. Il database delle conversazioni non e' mai stato
tracciato in nessun commit della storia.

Regola operativa che ne discende, e che vale per ogni sessione futura: **nei
rapporti e nella documentazione vanno i numeri, non i contenuti.** Percentuali,
soglie, conteggi, tempi, istogrammi: si'. Passaggi di un documento o di una
conversazione: mai, nemmeno come esempio, nemmeno "solo una riga per far
capire". Se serve un esempio, si inventa — come si e' gia' fatto per i PDF di
collaudo.

## Fuori scopo — non fare

- **Non toccare git**: niente `commit`, niente `push`. Prepari i file, il
  proprietario decide quando pubblicare.
- **Non cambiare `mac/core.py`** senza che la decisione 2 sia stata presa: il
  `SYSTEM_PROMPT` e' il prefisso della cache, e cambiarlo azzera il prefill di
  ogni conversazione viva.
- Non toccare `DEFINIZIONI`, `documenti.py`, `sbobina.py`, `fusione.py`.
- Non inventare numeri per il README: **tutti** quelli citati sopra sono nei
  file del progetto, si prendono da li'.
- Niente badge decorativi (build che non esiste, coverage che non misuri):
  un badge falso e' peggio di nessun badge.

## Le tre decisioni del proprietario

**1. Licenza.** Raccomandata **MIT**: la piu' permissiva e riconoscibile,
massimizza adozione e contributi. Alternative: Apache 2.0 (uguale piu' clausola
sui brevetti, preferita dalle aziende), AGPL-3.0 (copyleft forte, protegge
dall'appropriazione ma riduce molto l'adozione; e' quella di Khoj).

**2. I dati personali residui.** Nei file gia' pubblici c'e':

```
PIANO-DOCUMENTI.md:103     "dal 1 marzo: corso di tedesco, due sere a settimana"
INCARICO-fase3-memoria.md  lo stesso dato
mac/core.py:99             l'esempio nel prompt: "la pianta la annaffio la sera o la mattina?"
mac/bot.py:279             "un PDF non gestito e' sparito"
```

Il **nome** e' anonimo, la **persona** no: con abbastanza visitatori quei
dettagli sono un identikit (abitudini, impegni fissi, hardware specifico,
fuso orario italiano). Sono
tutti sostituibili con esempi inventati equivalenti — il prompt di sistema ha
bisogno di **un** esempio, non di **quell'** esempio.

Da sapere: toccare `mac/core.py` **cambia il `SYSTEM_PROMPT`**, quindi azzera la
cache del Mac. Si paga una volta, e conviene farlo insieme all'applicazione dei
tool definitivi (`TOOL-DEFINITIVI.md`), che la azzera comunque.

E va deciso **ora**: su GitHub la cronologia non si ritira, e resta nei fork
anche se il file viene cambiato dopo.

**3. Lingua del README.** Raccomandato: `README.md` **in inglese** come vetrina
e `README.it.md` in italiano linkato in cima. La documentazione interna
(`AGENTS.md`, `INCARICO-*`, `PIANO-DOCUMENTI.md`) **resta in italiano**: e'
memoria di lavoro e la sua lingua non ostacola nessuno.
