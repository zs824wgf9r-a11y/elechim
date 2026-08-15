# Incarico: la sbobina non ha un limite di dimensione

Scritto il 16 agosto 2026. Deciso dal proprietario. Leggi prima `AGENTS.md`,
`INCARICO-sbobina.md` e `PIANO-DOCUMENTI.md`.

## Il requisito, in una riga

**Qualunque sia la grandezza del documento, la sbobina si fa.** Non esiste un
PDF troppo grande, una sezione troppo lunga, un capitolo che si salta. La
dimensione non e' piu' un motivo di rifiuto: e' solo un parametro della
divisione.

## Perche' e' un requisito e non un miglioramento

E' la regola che regge tutta la fase 4 — *senza tralasciare nulla* — applicata
allo stadio due. Su `DSML.pdf`, misurato il 16 agosto:

```
223 sezioni · 1.365.854 caratteri
sopra MAX_FONTE=9000: 46 sezioni  =  20% delle sezioni
                                  =  686.018 caratteri
                                  =  50% del libro
```

**Saltarle voleva dire perdere meta' del libro**, e il rapporto avrebbe detto
"176 riscritte, 47 saltate" con l'aria di un risultato accettabile. E' la classe
di guasto peggiore del sistema: quello che non fa rumore.

E le sezioni lunghe sono lunghe perche' sono i **capitoli veri**. Saltare per
lunghezza significa saltare esattamente cio' che si voleva studiare.

## Le due strade sbagliate, che vanno escluse per iscritto

**Alzare la soglia** non e' una soluzione, e' lo stesso difetto piu' in la'.
Peggio: `num_ctx` in `sbobina.py` e' **8192 token**, quindi alzare `MAX_FONTE`
senza toccarlo fa **troncare il testo a ollama in silenzio**. Il modello
riscriverebbe un capitolo tagliato e la nota sembrerebbe perfetta. Un limite
superato di nascosto e' peggio di un limite dichiarato.

**Tagliare a lunghezza fissa** produce pezzi che cominciano a meta' di un
ragionamento e finiscono a meta' di un altro. Il modello spiega male cio' che
gli arriva mutilato, e il difetto non si vede leggendo la nota: si vede solo
confrontandola con la fonte, che e' proprio quello che nessuno fara' mai.

## Il principio: si spezza per struttura, non per lunghezza

E' la lezione che in questo progetto ha gia' vinto **due volte**: l'outline
incorporato ha battuto le euristiche sui font, e il sezionamento per titoli ha
battuto i chunk a lunghezza fissa. Vale la terza volta.

**La cascata dei confini naturali**, dal piu' forte al piu' debole. Si scende di
livello **solo** quando il pezzo non sta ancora nel budget:

1. **titoli interni** al testo estratto (14 delle 46 sezioni lunghe ne hanno 2+);
2. **ancore di pagina** `<!-- pag N -->` — ci sono su ogni pagina, e nessuna
   sezione lunga sta su una pagina sola (min 3, mediana 5, max 18);
3. **paragrafi** (riga vuota);
4. **frasi**;
5. **parole** — l'ultima rete, quella che garantisce che il procedimento
   termini sempre, qualunque cosa gli arrivi.

Il livello 5 non deve praticamente mai servire. Se serve spesso, il documento ha
qualcosa di strano e **il rapporto lo deve dire**.

**Regola del pezzo piu' grande**: si prende sempre il pezzo piu' grande che sta
nel budget, non il piu' piccolo comodo. Dividere piu' del necessario costa
coerenza: il modello spiega meglio un ragionamento intero che tre terzi di
ragionamento.

**I blocchi indivisibili restano interi**: tabelle, codice, formule. Non si
spezzano mai, a nessun livello. Se un blocco da solo sfora il budget, sfora — e
tanto al modello non ci va comunque, ci va il segnaposto (regola non
negoziabile: le tabelle non passano mai per un LLM).

## Adattivo vuol dire derivato, non scritto a mano

Oggi `MAX_FONTE = 9000` e' una **costante**, e `num_ctx = 8192` un'altra: due
numeri scelti a mano che devono restare coerenti fra loro senza che niente lo
garantisca. Il giorno che si prova un modello con 32k di contesto, la costante
resta 9000 e si spreca tre quarti della finestra; il giorno che si alza la
costante, il contesto trabocca in silenzio.

Il budget di un pezzo va **calcolato**:

    budget_caratteri ≈ (num_ctx − token_del_prompt − num_predict − margine) × caratteri_per_token

`caratteri_per_token` non si indovina: si **misura** sul documento vero, e su
DSML sara' piu' basso della media perche' la matematica tokenizza male. Ollama
restituisce `prompt_eval_count` a ogni chiamata: dopo la prima sezione il
rapporto fra caratteri mandati e token contati e' un dato reale, non una stima.
Usalo, e scrivi nel README il valore misurato.

Da qui discende la proprieta' che serve: **cambiare modello cambia il budget da
solo**, e la soglia non e' piu' un numero da ricordare di aggiornare.

## La promessa dev'essere un numero, o non e' una promessa

"Senza tralasciare nulla" o e' verificabile o e' marketing. Quindi:

**Invariante di copertura.** Per ogni sezione, i pezzi prodotti ricomposti
devono contenere **tutto** il testo della fonte: nessun carattere perso, nessuno
duplicato. Va verificato con codice, come asserzione permanente del collaudo,
non a occhio:

```python
# a meno degli spazi di giunzione, il contenuto e' identico
assert normalizza("".join(pezzi)) == normalizza(fonte)
```

Attenzione: gli `.strip()` e le ricomposizioni con spazio **mangiano gli a-capo**,
e dentro un blocco di codice o una formula l'a-capo *e'* contenuto. Se
l'invariante ignora gli spazi, allora i blocchi indivisibili vanno verificati a
parte, byte per byte.

**Nel rapporto di copertura** devono comparire, per documento:

- caratteri della fonte e **caratteri effettivamente finiti in una nota**;
- sezioni divise, e in quanti pezzi;
- **a quale livello della cascata** si e' scesi (e quante volte si e' arrivati
  alle parole);
- sezioni saltate, che d'ora in poi devono essere **zero per lunghezza** — se
  ne resta anche una, e' un difetto, non una statistica.

## Come si ricuce

Un pezzo diventa una spiegazione; i pezzi di una sezione diventano **una nota
sola**, non tre note. La nota e' l'unita' di lettura e corrisponde alla sezione:
tre note per una sezione romperebbero la corrispondenza con l'indice e i
wikilink.

Dentro la nota, i pezzi si susseguono senza cuciture visibili — niente "parte 1
di 3", che e' rumore di implementazione che trapela nel prodotto.

**Cosa non fare**: chiedere al modello di riassumere le spiegazioni dei pezzi
per unirle. Sarebbe un secondo passaggio generativo su testo gia' generato, cioe'
il modo piu' rapido di perdere i dettagli che la divisione voleva salvare.

## Il collaudo

Sul PDF sintetico, dove il testo e' noto e si puo' leggere:

1. una sezione **appena** sopra il budget si divide in 2, non in 5;
2. una sezione **enormemente** sopra il budget (costruiscine una da 100.000
   caratteri) si divide e **finisce**: e' la prova che non esiste "troppo
   grande";
3. l'invariante di copertura vale su tutte;
4. una tabella a cavallo di due pezzi **resta intera** in uno solo;
5. una sezione con titoli interni si divide **sui titoli**, non sui paragrafi —
   verificalo guardando dove cadono i tagli;
6. il budget cambia se cambia `num_ctx`: raddoppialo e i pezzi devono
   raddoppiare di dimensione, senza toccare altre costanti.

## Confini

- Puoi modificare `sbobina.py` e `prova_sbobina.py`.
- **Non toccare** `documenti.py`, `prova_documenti.py`, `fusione.py`,
  `README.md`, `AGENTS.md`, `mac/`, `strumenti.py`, `gateway.py`, git.
- **Il contenuto di `DSML.pdf` non entra nel tuo contesto**: si lavora sul
  sintetico e sulle metriche. Titoli, conteggi e posizioni dei tagli sono
  metadati e li puoi guardare.
- Non installare niente: la cascata dei confini e' `re` e la libreria standard.
