"""Fondere piu' elenchi di risultati in uno solo: Reciprocal Rank Fusion.

Serve a `ricorda` (fase 3), che fa il fan-out su tre archivi diversi — i fatti
sulla persona in Honcho, le note del vault, i documenti ingeriti — e deve
restituire **un solo elenco ordinato**. Il modello non sceglie l'archivio:
chiedere a un 4B in quale dei tre sta la risposta significa chiedergli di
sbagliare, e ogni scelta sbagliata costa un giro di tool da 10-30s.

## Perche' non si sommano i punteggi

Perche' non sono confrontabili. Una distanza coseno di pgvector sta fra 0 e 2,
un punteggio BM25 non ha un massimo, e Honcho ha la sua scala ancora diversa.
Normalizzarli (min-max, z-score) sembra la cosa ovvia ed e' il punto in cui la
ricerca ibrida di solito si rompe: la normalizzazione dipende dai risultati che
sono tornati **quella volta**, quindi lo stesso documento cambia punteggio a
seconda di cosa gli sta intorno, e un archivio che restituisce pochi risultati
tutti mediocri se li ritrova promossi a eccellenti.

## Cosa fa invece RRF

Butta via i punteggi e guarda solo la **posizione**:

    punteggio(doc) = somma, su ogni elenco dove compare,  1 / (k + posizione)

Un documento primo in un elenco prende 1/61, secondo 1/62, e cosi' via. Chi
compare in piu' elenchi somma, ed e' esattamente il comportamento che vogliamo:
se una cosa esce sia dalla ricerca semantica sia da quella testuale, quasi
sempre e' quella giusta.

Tre proprieta' che contano qui:

1. **Non ha niente da tarare per archivio.** Aggiungere una quarta fonte domani
   non richiede di ribilanciare pesi.
2. **E' robusto a un archivio che sbaglia scala**, perche' la scala non la
   guarda.
3. **E' stabile**: il punteggio di un documento non dipende da quanto sono buoni
   i suoi vicini.

`k` smorza la differenza fra le prime posizioni: con k=60 il primo e il secondo
sono quasi pari (1/61 contro 1/62), mentre senza k il primo varrebbe il doppio
del secondo. Serve perche' fra il primo e il secondo risultato di un motore la
differenza e' spesso rumore. 60 e' il valore della pubblicazione originale
(Cormack, Clarke, Buettcher, 2009) ed e' quello che usano gli altri; si cambia
solo con una misura in mano.

Visto in esercizio in SurfSense (`github.com/MODSetter/SurfSense`, Apache 2.0),
che fonde cosi' pgvector e full-text. L'algoritmo e' pubblico e sono venti
righe: si implementa, non si importa una dipendenza per questo.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

# Il valore della pubblicazione originale. Smorza le prime posizioni, dove la
# differenza fra primo e secondo e' quasi sempre rumore del motore.
K_PREDEFINITO = 60


def rrf(
    elenchi: Sequence[Iterable[Any]],
    k: int = K_PREDEFINITO,
    identita: Callable[[Any], Any] | None = None,
    pesi: Sequence[float] | None = None,
) -> list[tuple[Any, float]]:
    """Fonde piu' elenchi ordinati in uno solo, dal piu' pertinente in giu'.

    `elenchi` sono gia' ordinati per pertinenza decrescente, uno per archivio.
    `identita` estrae la chiave con cui si riconosce lo stesso risultato in
    elenchi diversi (un id, un percorso): senza, si usa l'elemento stesso, che
    va bene solo se e' hashable e confrontabile.

    `pesi`, se dato, moltiplica il contributo di ciascun elenco. Serve solo se
    un archivio e' noto per essere piu' affidabile degli altri **con una misura
    a supporto**: il valore di RRF e' proprio non aver niente da tarare, quindi
    la scelta giusta e' lasciarlo stare.

    Torna `[(elemento, punteggio)]`. A parita' di punteggio vince chi e'
    comparso in piu' elenchi, e poi chi stava piu' in alto: senza questo
    spareggio l'ordine dipenderebbe da come sono arrivati i risultati, e due
    chiamate identiche potrebbero rispondere in ordine diverso.
    """
    if pesi is not None and len(pesi) != len(elenchi):
        raise ValueError(f"pesi: {len(pesi)} per {len(elenchi)} elenchi")

    chiave = identita or (lambda x: x)
    punteggi: dict[Any, float] = {}
    presenze: dict[Any, int] = {}
    migliore: dict[Any, int] = {}
    primo_visto: dict[Any, Any] = {}

    for n, elenco in enumerate(elenchi):
        peso = pesi[n] if pesi is not None else 1.0
        visti_qui: set[Any] = set()
        for posizione, elemento in enumerate(elenco):
            id_ = chiave(elemento)
            # Un duplicato dentro lo stesso elenco non deve contare due volte:
            # sommerebbe due contributi per una pertinenza sola.
            if id_ in visti_qui:
                continue
            visti_qui.add(id_)

            punteggi[id_] = punteggi.get(id_, 0.0) + peso / (k + posizione + 1)
            presenze[id_] = presenze.get(id_, 0) + 1
            migliore[id_] = min(migliore.get(id_, posizione), posizione)
            primo_visto.setdefault(id_, elemento)

    ordinati = sorted(
        punteggi,
        key=lambda id_: (-punteggi[id_], -presenze[id_], migliore[id_]),
    )
    return [(primo_visto[id_], punteggi[id_]) for id_ in ordinati]


def fondi(
    elenchi: Sequence[Iterable[Any]],
    quanti: int | None = None,
    k: int = K_PREDEFINITO,
    identita: Callable[[Any], Any] | None = None,
) -> list[Any]:
    """Come `rrf`, ma restituisce i soli elementi, gia' tagliati a `quanti`.

    E' la forma che serve a `ricorda`: il punteggio non esce mai verso il Mac,
    che maneggia handle e passaggi, non numeri da reinterpretare.
    """
    fusi = [elemento for elemento, _ in rrf(elenchi, k=k, identita=identita)]
    return fusi[:quanti] if quanti is not None else fusi
