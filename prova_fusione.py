"""Collaudo di `fusione.py`. Asserzioni esatte su casi costruiti a mano:
niente archivi veri, niente Postgres, gira in un decimo di secondo.

I casi sono quelli che contano davvero per `ricorda`, non la copertura per la
copertura: cosa succede quando due archivi sono d'accordo, quando uno solo ha
la risposta, quando un archivio e' vuoto, e quando lo stesso documento arriva
due volte dalla stessa fonte.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fusione import K_PREDEFINITO, fondi, rrf


def test_accordo_batte_primo_posto() -> None:
    """Chi compare in due elenchi batte chi e' primo in uno solo.

    E' la ragione per cui esiste la ricerca ibrida: se una cosa esce sia dalla
    semantica sia dalla testuale, quasi sempre e' quella giusta.
    """
    semantica = ["b", "a", "c"]
    testuale = ["d", "a", "e"]
    fusi = fondi([semantica, testuale])
    assert fusi[0] == "a", fusi
    # 'a' e' secondo in entrambi: 2/62 = 0.0323 contro 1/61 = 0.0164 di 'b'.
    punteggi = dict(rrf([semantica, testuale]))
    assert punteggi["a"] > punteggi["b"] > 0, punteggi
    print("OK accordo: chi c'e' in due elenchi batte chi e' primo in uno.")


def test_un_solo_archivio_ha_la_risposta() -> None:
    """Se una cosa sta in un archivio solo, non deve sparire: l'ordine
    relativo dentro quell'elenco si conserva."""
    fusi = fondi([["x", "y", "z"], []])
    assert fusi == ["x", "y", "z"], fusi
    print("OK archivio solo: ordine conservato, un elenco vuoto non disturba.")


def test_nessun_risultato() -> None:
    assert fondi([[], [], []]) == []
    assert rrf([]) == []
    print("OK vuoto: nessun risultato, nessuna eccezione.")


def test_duplicato_nello_stesso_elenco() -> None:
    """Lo stesso documento due volte nello stesso elenco conta una volta sola:
    altrimenti una fonte che restituisce doppioni si auto-promuove."""
    doppio = ["a", "a", "b"]
    punteggi = dict(rrf([doppio]))
    assert punteggi["a"] == 1 / (K_PREDEFINITO + 1), punteggi
    assert punteggi["a"] > punteggi["b"], punteggi
    print("OK duplicati: contati una volta sola.")


def test_identita_su_oggetti() -> None:
    """Il caso vero: i risultati sono dict con un id, e lo stesso documento
    arriva da due archivi con testo e punteggio diversi."""
    honcho = [{"id": "n7", "fonte": "honcho", "testo": "corre il martedi'"}]
    vault = [
        {"id": "n3", "fonte": "vault", "testo": "altro"},
        {"id": "n7", "fonte": "vault", "testo": "corsa del martedi'"},
    ]
    fusi = fondi([honcho, vault], identita=lambda r: r["id"])
    assert [r["id"] for r in fusi] == ["n7", "n3"], fusi
    # si tiene la prima occorrenza incontrata, quindi la versione di Honcho
    assert fusi[0]["fonte"] == "honcho", fusi[0]
    assert len(fusi) == 2, "lo stesso id deve comparire una volta sola"
    print("OK identita': stesso documento da due archivi, fuso in uno.")


def test_ordine_deterministico() -> None:
    """Due chiamate identiche danno lo stesso ordine, anche a parita' di
    punteggio: senza spareggio l'ordine dipenderebbe dall'iterazione."""
    a = [["p", "q"], ["q", "p"]]
    assert fondi(a) == fondi(a)
    # p e q hanno lo stesso punteggio (1/61 + 1/62): vince chi e' arrivato
    # primo in assoluto, cioe' 'p', che e' in posizione 0 nel primo elenco.
    assert fondi(a)[0] == "p", fondi(a)
    print("OK determinismo: parita' risolta, ordine stabile.")


def test_taglio() -> None:
    fusi = fondi([["a", "b", "c", "d"], ["e", "f"]], quanti=3)
    assert len(fusi) == 3, fusi
    print("OK taglio: `quanti` limita l'uscita.")


def test_k_smorza_le_prime_posizioni() -> None:
    """Con k grande le prime posizioni si equivalgono, con k=0 il primo vale
    il doppio del secondo. E' il comportamento che giustifica k=60."""
    p60 = dict(rrf([["a", "b"]], k=60))
    assert p60["a"] / p60["b"] < 1.05, p60
    p0 = dict(rrf([["a", "b"]], k=0))
    assert abs(p0["a"] / p0["b"] - 2.0) < 1e-9, p0
    print("OK k: smorza le prime posizioni come previsto.")


def test_pesi() -> None:
    """I pesi esistono ma non si usano senza una misura. Qui si verifica solo
    che facciano quello che dicono, e che un numero sbagliato di pesi non
    passi in silenzio."""
    normale = fondi([["a"], ["b"]])
    assert normale[0] == "a", normale  # parita', vince il primo elenco
    pesato = fondi([["a"], ["b"]], k=60)
    assert pesato[0] == "a"
    punteggi = dict(rrf([["a"], ["b"]], pesi=[1.0, 5.0]))
    assert punteggi["b"] > punteggi["a"], punteggi
    try:
        rrf([["a"], ["b"]], pesi=[1.0])
    except ValueError:
        pass
    else:
        raise AssertionError("pesi di lunghezza sbagliata accettati in silenzio")
    print("OK pesi: applicati, e la lunghezza sbagliata da' errore.")


def main() -> None:
    test_accordo_batte_primo_posto()
    test_un_solo_archivio_ha_la_risposta()
    test_nessun_risultato()
    test_duplicato_nello_stesso_elenco()
    test_identita_su_oggetti()
    test_ordine_deterministico()
    test_taglio()
    test_k_smorza_le_prime_posizioni()
    test_pesi()
    print("TUTTO VERDE")


if __name__ == "__main__":
    main()
