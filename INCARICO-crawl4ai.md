# Incarico: crawl4ai al posto della corsia statica

Scritto il 15 agosto 2026. Deciso dal proprietario. **Non iniziare finche' la fase 4
non e' consegnata.** Leggi prima `AGENTS.md`.

## Cosa cambia, e cosa no

Oggi `strumenti._scarica` fa `requests.get` + `trafilatura.extract`. Si
sostituisce con una chiamata a **crawl4ai**, che gira in un container podman su
`127.0.0.1:11235` (quadlet gia' scritto in
`~/.config/containers/systemd/crawl4ai.container`, sullo schema di searxng).

**SearXNG resta.** crawl4ai non ha un indice e non trova le pagine: le prende e
le trasforma. La catena e' `SearXNG trova -> crawl4ai scarica ed estrae -> il
punteggio sceglie i passaggi`.

**Non cambia niente sopra `_scarica`.** `_punteggio`, `_passaggi`,
`CACHE_PAGINE`, un risultato per dominio, le vetrine in coda, la boilerplate
azzerata: sono le lezioni misurate del 12 agosto e restano **esattamente**
com'erano. Si sostituisce il tubo, non il rubinetto.

**`DEFINIZIONI` non si tocca.** Da fuori `cerca` e `leggi` fanno la stessa cosa
di prima, meglio: il Mac non deve accorgersi di niente, e se le descrizioni
cambiassero si azzererebbe la cache di ogni conversazione per un miglioramento
che al modello non serve sapere.

## La decisione da rispettare: crawl4ai davanti, statico dietro

**Non cancellare `requests` + `trafilatura`: diventano il ripiego.**

- primo tentativo: crawl4ai;
- se il container non risponde, va in timeout o torna vuoto: **si ricade sulla
  corsia statica**, che oggi funziona sull'80% delle pagine (misurato su 40
  pagine da 8 query reali, 15 agosto);
- se cade anche quella, resta lo snippet di SearXNG, com'e' gia' adesso.

La ragione e' che il fisso **si sospende da solo dopo tre ore** e i container
ripartono: un guasto momentaneo del servizio non deve togliere a Elechim la
lettura delle pagine. Ci costa nulla, il codice statico esiste gia'.

## Due usi diversi, un solo client

Scrivi un modulo `web.py` (o una sezione di `strumenti.py`, decidi tu e motiva)
che espone i due usi, perche' vogliono cose diverse:

1. **Per la ricerca**: testo pulito, da cui `_passaggi` ritaglia ~1400
   caratteri. E' l'uso di oggi. Il Mac maneggia handle, non contenuti.
2. **Per il vault**: il **markdown integrale** della pagina, con i link
   conservati, destinato a diventare una nota in Obsidian. E' il motivo per cui
   Il proprietario ha voluto crawl4ai: portare conoscenza dal web dentro Obsidian vuole
   una resa strutturata, non 1400 caratteri.

Il secondo uso non va collegato a nessun tool adesso (vedi
`TOOL-DEFINITIVI.md`): serve la funzione, pronta per quando si collegheranno
`ricorda` e `salva`.

## Cose da verificare, non da dare per buone

- **L'autenticazione JWT e' attiva di default dalla v0.9.0.** Su un servizio in
  ascolto solo su loopback si puo' disattivare, o si gestisce un token. Leggi la
  documentazione della versione che hai scaricato e **scegli motivando**: se
  disattivi, scrivi nel quadlet perche' e' sicuro (loopback, nessuna porta
  esposta, nessun forward nel tunnel).
- **`--shm-size=1g`**: gia' nel quadlet. Col default di 64MB Chromium muore a
  meta' caricamento sulle pagine pesanti, e sembra un timeout invece che una
  mancanza di memoria condivisa.
- **Niente chiavi LLM.** L'estrazione markdown di base non ne ha bisogno, e non
  deve averne: l'estrazione resta deterministica. Se una funzione di crawl4ai
  chiede un modello, **non e' quella che ci serve**.

## Le misure da fare, e da scrivere nel README

Il confronto **e' gia' stato fatto** il 15 agosto, su 40 pagine da 8 query
attraverso SearXNG (prime 5 per query, un dominio ciascuna). Non rifarlo al
buio: questi sono i numeri di partenza, e servono a sapere cosa aspettarsi.

```
statico   35/40  87.5%   0.59s medi
crawl4ai  36/40  90.0%   1.35s medi
```

**Sulla disponibilita' e' pareggio.** L'unica pagina in piu' e' facebook, 63
caratteri, cioe' niente. **I 403 restano 403**: crawl4ai li riconosce da solo e
risponde `Blocked by anti-bot protection`. Non aspettarti di sbloccarli, e **non
provare a aggirarli** con impronte finte o proxy: non e' il lavoro.

Il guadagno vero e' nella **resa**, e li' e' grosso:

```
sulle 35 pagine dove funzionano entrambi:
  caratteri medi   statico 9.957   |   crawl4ai 25.784      (2,6x)
```

Ma **va filtrato**, e questo e' il lavoro tecnico di questo incarico. Misurato
su tre pagine, contando le righe che sono solo link:

```
tgcom24    78.809 car → 69% righe di solo link,  1.536 car di prosa vera
macitynet  61.006 car → 39% righe di solo link, 25.200 car di prosa vera
ilmeteo    11.672 car → 36% righe di solo link,  4.776 car di prosa vera
```

Cioe': su una homepage quasi tutto il guadagno e' **menu di navigazione**, su un
articolo e' **prosa autentica che trafilatura buttava via**. Per la ricerca il
menu e' peggio di niente — di quei caratteri ne diamo 1400 a un modello da 4B, e
riempirli di navigazione e' esattamente il guasto del 12 agosto.

Nota: l'endpoint `/md` applica **gia'** il filtro `fit` per impostazione
predefinita (`f: "raw"` da' il dump grezzo, molto peggiore). Il filtro va quindi
**oltre** `fit`: le righe di soli link vanno tolte prima del punteggio.

Da misurare e scrivere:

1. **Quanta navigazione resta dopo il tuo filtro**, sulle stesse tre pagine
   qui sopra. Il numero da battere e' 69% / 39% / 36%.
2. **Quanto costa in tempo.** Oggi una ricerca completa e' ~2s, con le tre
   pagine aperte in parallelo e 6s di tetto ciascuna. Un browser e' piu' lento:
   misura il nuovo tempo e **rivedi `TIMEOUT_PAGINA` se serve**. Il metro di
   giudizio e' che un turno sul Mac costa 10-37s: qualche secondo qui e'
   invisibile, dieci no.
3. **Il primo colpo dopo un risveglio.** Il fisso dorme; misura quanto ci mette
   la prima pagina a container appena ripartito, e se supera il tetto di timeout
   sistemalo (scaldare il browser all'avvio, o un tetto piu' alto sul primo
   tentativo).
4. **La memoria del container a riposo e sotto carico.** Sul fisso ci sono 62GB
   di RAM, quindi non e' un problema di capienza, ma il numero va saputo.

Se crawl4ai **non batte** l'80%, dillo chiaramente nel rapporto con i numeri:
la decisione di adottarlo e' del proprietario ed e' presa anche per l'uso "vault",
ma il costo va documentato onestamente e non nascosto.

## Fuori scopo

- Non toccare `DEFINIZIONI`, ne' qui ne' in `mac/strumenti.py`.
- Non toccare SearXNG: le sue impostazioni sono state sistemate il 15 agosto
  (motori generali da 2 funzionanti a 4, `startpage` disabilitato) e sono in
  `~/assistente/searxng/settings.yml`.
- Non installare Playwright o Chromium nel `.venv`: stanno nel container, ed e'
  il motivo per cui si e' scelto il container invece del venv (lo stack ML di
  whisper non deve litigare con quello del browser).

## L'invariante da verificare prima di dire che hai finito

Il blocco `DEFINIZIONI` deve restare **identico** nelle due copie e identico a
com'era. Impronta di partenza, presa il 15 agosto 2026:

```
$ for f in strumenti.py mac/strumenti.py; do sed -n '/^DEFINIZIONI/,/^]/p' "$f" | sha256sum; done
1160ec454b8b9998270a8d16be6c3a262eb5d50787507ddac61d389768f2ebfa  -
1160ec454b8b9998270a8d16be6c3a262eb5d50787507ddac61d389768f2ebfa  -
```

Rifai questo controllo alla fine e **riporta le due impronte nel rapporto**. Se
non coincidono con quella di partenza hai rotto la cache di ogni conversazione
di Elechim, e non te ne accorgeresti in nessun altro modo.

## Criterio di uscita

Non consegnare finche' non hai **misurato** e scritto i numeri: quante delle 40
pagine passano, il tempo medio, il primo colpo dopo il riavvio del container, e
il confronto della resa con il ripiego statico. Un'integrazione che funziona su
una pagina sola non e' finita.
