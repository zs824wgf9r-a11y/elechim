# Incarico: elaborazione degli appunti del proprietario

Scritto il 15 agosto 2026. Leggi prima `AGENTS.md` e la sezione "Gli appunti del
proprietario non sono documenti" in `PIANO-DOCUMENTI.md`.

**Non iniziare finche' `INCARICO-titoli-indice.md` non e' consegnato**: tocca
`documenti.py` e le convenzioni delle note.

## L'idea in una riga

Il proprietario scrive un appunto. Con un comando da Telegram, il fisso lo elabora e
scrive il risultato in una **cartella separata del vault**. Lui legge, e se gli
piace travasa a mano.

## La regola che governa tutto

**Gli appunti del proprietario non si toccano. Mai. Nemmeno per appendere in fondo.**

Un PDF si riestrae mille volte, l'originale non cambia. Un appunto scritto da
lui e' **l'unica copia di un suo pensiero**, e la formulazione *e'* il
contenuto. Un modello che "sistema" la frase buttata giu' alle due di notte
porta via l'intuizione insieme alla sciatteria.

Conseguenza pratica: la pipeline **legge** da `~/Obsidian/30-Note` (e dalle
altre cartelle del proprietario) e **scrive solo** in `~/Obsidian/50-Elaborazioni/`.
Zero scritture nelle cartelle sue. Nemmeno il frontmatter, nemmeno i tag.

Effetto collaterale utile: siccome non si scrive nella cartella sorvegliata,
**il ciclo a vuoto non e' possibile**. E' lo stesso guasto del path unit del 15
agosto (cinque avvii in un secondo, `start-limit-hit`), qui evitato per
costruzione invece che per rimedio.

## Il collegamento fra le due note

L'elaborazione contiene un wikilink alla nota originale. **Obsidian mostra il
backlink dalla parte del proprietario senza che il suo file sia stato modificato**:
legame bidirezionale, scrittura unidirezionale. Non aggiungere link dalla sua
nota verso l'elaborazione: sarebbe una scrittura, ed e' vietata.

Nome del file: lo stesso della nota originale, dentro `50-Elaborazioni/`. Se
Se il proprietario rinomina la sua nota, l'elaborazione resta orfana: **rilevalo e dillo
nel rapporto**, non provare a indovinare l'accoppiamento.

## Il comando: `/elabora`

**E' un comando del bot, non un tool.** Come `/stato`, `/gioco`, `/nuova`:
vive in `mac/bot.py`, **non tocca `DEFINIZIONI`** e non costa cache. Non
dipende dalla decisione sui tool in `TOOL-DEFINITIVI.md`.

- `/elabora` — tutte le note in sospeso;
- `/elabora <nome>` — una sola.

"In sospeso" = modificata dopo la sua ultima elaborazione. Deterministico:
impronta del testo della nota, salvata nello stato accanto all'elaborazione.
Nessuna euristica.

Il fisso puo' dormire: vale il preflight `GET /ping` gia' in uso, e il risveglio
col magic packet. Il lavoro gira sotto `energia.blocco("elaborazione")`.

**Niente scatto automatico, per adesso.** Il valore dell'automatismo non e'
dimostrato e il costo del rumore e' alto: un vault pieno di commenti generati su
appunti che non li meritavano e' un vault che si smette di leggere. Se fra un
mese il proprietario si accorge di lanciarlo sempre, si aggiunge un innesco a periodo di
quiete (dieci minuti senza modifiche) - **mai al salvataggio**, che elaborerebbe
pensieri a meta'.

## Cosa contiene un'elaborazione

Il modello e' quello **locale sul fisso** (vedi `INCARICO-sbobina.md` per la
scelta e le misure). Mai il modello del Mac: sfratterebbe la conversazione
dall'unica slot di cache.

```markdown
---
tipo: elaborazione
di: "[[nome della nota]]"
modello: qwen3:8b
impronta: a3f9c1
data: 2026-08-15
---

## In breve
[due o tre punti]

## Approfondimento
[la spiegazione: espande, non riassume]

## Da riformattare
[la sua nota riscritta pulita - una PROPOSTA che travasa lui]

## Collegamenti
[altre note pertinenti]
```

**"Espande, non riassume"** vale qui come nella sbobina: chiedere a un modello
piccolo di riassumere da' una versione piu' corta e piu' vaga, inutile.

**Un pavimento**: sotto una certa lunghezza (misurala sul vault vero, non
inventarla) niente approfondimento — solo collegamenti. La lista della spesa non
merita un saggio, e il rumore fa smettere di leggere anche le elaborazioni buone.

**Una via d'uscita**: `elechim: no` nel frontmatter della nota e quella non viene
elaborata mai. Va letto, non scritto.

## I collegamenti: dipendenza dalla fase 3

La parte piu' preziosa - accorgersi che l'appunto di oggi parla della stessa cosa
di uno di marzo - richiede la **ricerca semantica**, cioe' `bge-m3` e l'indice
vettoriale della fase 3, che **non esistono ancora**.

Adesso: collegamento a parole chiave. Funziona, ma trova solo le note che usano
le stesse parole — quelle che il proprietario troverebbe gia' con la ricerca di Obsidian.
**Scrivilo onestamente nel README**: e' un ripiego, non la funzione finale.
Costruisci l'aggancio in modo che sostituire il motore di somiglianza sia una
funzione da cambiare, non una riscrittura.

## La notifica

A fine lavoro, su Telegram, **dal fisso** (ha gia' il token): quante note
elaborate, quante saltate e perche', quanto tempo, il modello usato.

**Solo il conto, mai il contenuto.** Vale la lezione gia' scritta in
`dreaming-mode-consolidamento`: un assistente che ti recapita le sue riflessioni
diventa insopportabile in una settimana. Le elaborazioni si leggono su Obsidian
quando si vuole; la notifica dice solo che sono pronte.

## Criterio di uscita

- `/elabora` funziona da Telegram, anche col fisso addormentato;
- **nessun file nelle cartelle del proprietario e' stato modificato** — verificalo con
  gli hash prima e dopo, e riportali;
- le elaborazioni stanno in `50-Elaborazioni/` e i backlink compaiono in Obsidian;
- rilanciare senza aver cambiato la nota **non rifa' il lavoro**;
- il pavimento e `elechim: no` funzionano, misurati sul vault vero;
- `DEFINIZIONI` intatta: `1160ec454b8b9998`.
