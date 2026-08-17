# Incarico: `LESSONS.md` — le lezioni misurate, in inglese

Scritto il 17 agosto 2026. Motivazione nella sezione 8-ter di `DA-FARE.md`, notata
dal proprietario mentre costruiva la vetrina.

## Il problema, in due righe

```
README.md    (inglese)  ~6 KB   <- la vetrina, cita 4 misure
README.it.md (italiano) ~34 KB  <- TUTTE le lezioni, con i numeri
```

Il materiale che rende questo progetto diverso da un altro "second brain" sono le
**lezioni misurate**: non opinioni sull'architettura, ma cose che si sono rotte in
esercizio, con il numero che lo dimostra. Stanno **tutte** nei 34 KB in italiano,
che il 99% di chi arriva non legge.

`LESSONS.md` in inglese e' il pezzo **che si condivide**. Non e' documentazione: e'
la ragione per cui qualcuno arriva al repo.

## La regola che decide se una lezione entra

**Ogni lezione deve avere un numero misurato accanto.** Se non c'e' una misura, non
e' una lezione: e' un'opinione, e va fuori. Il formato di ciascuna:

1. **il sintomo** — cosa si e' visto, in una riga;
2. **la causa** — perche' succedeva;
3. **la misura** — il numero, il tempo, la percentuale. E' il pezzo non
   negoziabile;
4. **la regola generale** — cosa se ne porta via chi non ha il nostro progetto.

Il punto 4 e' quello che rende il file condivisibile: chi legge non ha una pipeline
di PDF, ma ha dei collaudi e dei servizi systemd.

## Le lezioni candidate, con dove trovarle

Le conosco e te le elenco, cosi' non le cerchi a tentoni. **Verifica ogni numero
alla fonte** — `README.it.md`, `DA-FARE.md`, i `RAPPORTO-*.md` — e **non riportare
un numero che non hai trovato scritto**.

**Sui collaudi che ingannano** (il filone piu' forte, sezione 1-quater di `DA-FARE.md`):
- tre asserzioni verdi per costruzione: «tre processi, tre exit 0» con soglia 5;
  «marcatori distinti == pagine» che torna sempre 11 = 11; due segnaposti «diversi»
  entrambi da 77 caratteri. Regola: *quando provi un limite, superalo; quando provi
  una distinzione, i due casi devono differire nella dimensione che conta.*
- «un test che non viene raggiunto non protegge niente» (punto 2).

**Su systemd:**
- `start-limit-hit`: un `oneshot` innescato da un path unit sulla cartella che il
  servizio stesso svuota — 10 avvii **riusciti** in 33 secondi, default 5 in 10s, e
  il fallimento **si propaga al path unit**. Coda morta **1 giorno e 19 ore**, in
  silenzio (sezione 1-bis).
- `BindsTo` disattiva `Restart=always`.
- `OnUnitActiveSec` non avanza durante la sospensione.

**Sui modelli e il contesto:**
- il prefill decide l'architettura: 23 tok/s a 8K token, ~5 min per turno; per
  questo il modello piccolo non vede mai un documento.
- il budget derivato da `num_ctx` invece di una costante, e perche' due numeri che
  devono restare coerenti senza che niente lo garantisca divergono sempre.
- l'imbottitura del segnaposto: un pezzo dato per 17.190 caratteri ne consegnava
  **22.076**, e ollama tagliava la fonte **in silenzio**.
- `CAR_PER_TOKEN` misurato leggendo `prompt_eval_count`, caso peggiore e non media,
  e la scoperta del 17 agosto che il margine era stato speso tutto (sezione 1-ter).
  **Nota bene**: qui la lezione e' che *il segno di una correzione va verificato*, non
  solo il numero — un rapporto puo' avere il dato giusto e la conclusione rovesciata.

**Sull'estrazione dai PDF:**
- 26 tabelle false su 42: su una pagina a due colonne il "vuoto ampio" e' lo spazio
  fra le colonne, quindi il rilevatore trovava l'impaginazione.
- la scansione senza livello di testo: 3 caratteri contro 3.610, archiviati in
  silenzio. La soglia misurata (mediana caratteri/pagina) e la regola *dichiarare
  invece di fingere*.
- gli apici persi in un libro di matematica, e che **nessuna libreria da' il
  pedice** — PyMuPDF ha solo `TEXT_FONT_SUPERSCRIPT`, e la sua doc dice che pure
  l'apice e' *computed*, non letto (vedi `RICERCA-stato-arte.md` capitolo 2).
- le figure: **l'hash del contenuto, non la dimensione** — la forma piu' grande del
  libro (2368x2800, 24 occorrenze) e' **un hash solo**, cioe' decorazione. E che
  `pdfimages` non vede le figure vettoriali per costruzione: 11 pagine viste contro
  ~37 reali.
- `pdftocairo -svg` aborta sul ~15% delle pagine **con l'output perfetto** (exit
  134, SVG ben formato). Regola: *un codice di uscita non e' una prova, guarda cio'
  che e' stato prodotto.*

**Sul lavorare con agenti:**
- `opencode run` esce **0** anche quando non ha fatto niente: si guardano i file
  prodotti, mai il codice di uscita.
- non ha timeout suo: due sessioni ferme **6h43m** su `epoll` con la connessione
  stabilita e le code a zero. Come accorgersene: **l'orologio del log**, non il
  processo.
- «le sessioni che hanno consegnato sono quelle che hanno scritto per prime»: le
  conclusioni sono l'ultima cosa che una sessione scrive, quindi la prima che si
  perde.

**Sull'hardware, se ci sta:** l'interfaccia di rete che si rinomina quando monti una
seconda GPU.

Scegline **quelle con la misura piu' forte** — meglio dodici lezioni solide che
venticinque annacquate. Se una candidata non ha un numero verificabile, lasciala
fuori e dillo nel rapporto.

## Cosa NON fare

- **L'unico file che scrivi e' `LESSONS.md`.** Non toccare `README.md` ne'
  `README.it.md`: nessun riordino, nessun "allineamento", nessun link aggiunto. Se
  pensi che il README dovrebbe linkare `LESSONS.md`, **scrivilo nel rapporto** e
  lascia decidere.
- Non toccare **nessun** file di codice, e in particolare `documenti.py`,
  `prova_documenti.py`, `sbobina.py`, `prova_sbobina.py`: ci sono altre sessioni al
  lavoro adesso.
- Non toccare `AGENTS.md`, `DA-FARE.md`, gli altri `INCARICO-*`, i `RAPPORTO-*`, git.
- **Niente dati personali.** Nessun nome proprio, nessun percorso assoluto tipo
  `/home/<utente>/...`, nessun nome di file di un documento privato, nessun
  contenuto di documenti o conversazioni. Si parla del **proprietario**, come fa
  tutto il repo. E' un file destinato a stare pubblico: trattalo come tale.
- **Non fare commit e non fare push.** Lo decide il proprietario.
- Non inventare numeri, e non arrotondare per rendere una lezione piu' bella. Se una
  fonte dice 26 su 42, si scrive 26 su 42.

## Come si scrive

Inglese, prosa asciutta, prima persona plurale o impersonale — **non** tono da post
motivazionale, **non** «10 things I learned». Ogni lezione un titolo che dice la
cosa (`A oneshot service triggered by a path unit needs its rate limit disabled`,
non `Lesson 4: systemd`). Un indice in cima. Sotto ogni lezione, il numero in
evidenza.

In apertura, tre righe che dicono cos'e' questo file e cos'e' il progetto, e un
rimando al README per il resto. Chi arriva qui da un link deve capire in dieci
secondi dove e' finito.

## Criterio di uscita

- `LESSONS.md` esiste, in inglese, ogni lezione con la sua misura verificata alla
  fonte;
- `RAPPORTO-lezioni.md` con: quali lezioni hai incluso e quali **scartate per
  mancanza di misura** (e' la parte interessante), e la tua raccomandazione se e
  dove il README dovrebbe linkarlo;
- `git status` mostra **solo** i due file nuovi: nessun altro file modificato.
