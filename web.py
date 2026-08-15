"""Il client di crawl4ai: prendere la pagina, restituire la sostanza.

crawl4ai gira in un container podman su 127.0.0.1:11235 (quadlet
`crawl4ai.container`) e rende le pagine in markdown con un browser vero. Qui
stanno i suoi due clienti, che vogliono cose diverse:

1. `testo_pulito` — per la ricerca: testo senza navigazione e senza marcature,
   da cui `strumenti._passaggi` ritaglia i passaggi. E' la corsia che `cerca`
   e `leggi` usano attraverso `strumenti._scarica`.
2. `markdown_integrale` — per il vault: il markdown **con i link conservati**,
   destinato a diventare una nota su Obsidian quando `ricorda` e `salva`
   esisteranno (vedi `TOOL-DEFINITIVI.md`). Per adesso non e' collegato a
   nessun tool: la funzione c'e', il rubinetto no.

L'autenticazione e' il token Bearer della 0.9.0+: senza token il server si
legherebbe a 127.0.0.1 *dentro* il container, dove la porta pubblicata non
arriva (la ragione e' scritta nel quadlet).

Il filtro delle righe di solo link e' la parte che vale i soldi. Misurato il
15 agosto 2026 sul markdown `fit` di crawl4ai: tgcom24 69% di righe di solo
link, macitynet 39%, ilmeteo 36%. Il guadagno di resa del browser (2,6x
caratteri contro trafilatura) su una homepage e' quasi tutto menu di
navigazione, e dare 1400 caratteri di menu a un modello da 4B e' il guasto
del 12 agosto in forma nuova. Il filtro va **oltre** `fit`: pruning tiene la
struttura, non distingue la prosa dal parkeggio di link.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

import requests

BASE = os.environ.get("CRAWL4AI_URL", "http://127.0.0.1:11235")

# Il token sta nel env accanto a questo file. Una lettura sola, all'avvio:
# il gateway non si riavvia spesso e il token cambia quando lo si rigenera a
# mano, non da solo.
def _leggi_token() -> str:
    token = os.environ.get("CRAWL4AI_API_TOKEN")
    if token:
        return token
    riga = next(
        (
            r
            for r in (Path(__file__).resolve().parent / "crawl4ai.env")
            .read_text(encoding="utf-8")
            .splitlines()
            if r.startswith("CRAWL4AI_API_TOKEN=")
        ),
        "",
    )
    return riga.partition("=")[2].strip()


_TOKEN = _leggi_token()
SESSIONE = requests.Session()
SESSIONE.headers["Authorization"] = f"Bearer {_TOKEN}"

# La corsa in se': niente cache lato server (la pagina che cambia deve tornare
# cambiata quando la cache locale manca) e il filtro `fit` di pruning, lo
# stesso dell'endpoint /md. Il browser gira gia' senza immagini e senza
# javascript nella configurazione del server: e' la resa deterministica che
# vogliamo, e niente LLM da nessuna parte.
CRAWLER = {
    "cache_mode": "bypass",
    "markdown_generator": {
        "type": "DefaultMarkdownGenerator",
        "params": {"content_filter": {"type": "PruningContentFilter", "params": {}}},
    },
}

# Un'immagine o un link markdown: `[testo](url)`, `![alt](url)`. Il testo puo'
# contenere una coppia di quadre annidata — i titoli italiani lo fanno di
# continuo ("Meteo: svolta [Parla Gussoni] su tutta Italia") — e una regex
# ingenua la' si spezza e lascia passare la riga come prosa, url compreso.
LINK = re.compile(r"!?\[(?:[^\][]|\[[^\]]*\])*\]\([^)]*\)")
# Lo stesso scheletro, ma tiene il testo del link: serve ad aprire i link
# della prosa senza toccare le quadre che il testo porta con se'.
LINK_TESTO = re.compile(r"\[((?:[^\][]|\[[^\]]*\])*)\]\([^)]*\)")
# Solo immagini: l'alt di un menu non dice niente, l'alt di una figura si',
# ma quel testo non e' mai arrivato nemmeno a trafilatura.
IMMAGINE = re.compile(r"!\[(?:[^\][]|\[[^\]]*\])*\]\([^)]*\)")
# Gettoni riempiti dal javascript della pagina (`%cfw-date-day%` e simili):
# col browser senza js restano li', grezzi, e non sono contenuti.
GETTONE = re.compile(r"%[^\s%]+%")


def _riga_di_solo_link(riga: str) -> bool:
    """La riga, tolte le marcature, dice ancora qualcosa?

    Il menu di navigazione e' righe come `[Sport](/sport) [Calcio](/calcio)`,
    a volte separate da `|` o `•`. Tolto il markup non resta nemmeno una
    lettera. Una riga di prosa con un link dentro resta prosa: "leggi
    [questo](url) per approfondire" sopravvive al filtro, ed e' giusto. Gli
    stessi criteri valgono per le righe di soli gettoni `%cosi%`.
    """
    avanzo = GETTONE.sub(" ", LINK.sub(" ", riga))
    return not re.search(r"\w", avanzo)


def _senza_navigazione(markdown: str) -> list[str]:
    righe = markdown.splitlines()
    return [r for r in righe if r.strip() and not _riga_di_solo_link(r)]


def _richiesta(url: str, timeout: int) -> tuple[str, str] | None:
    """Una pagina: `(titolo, markdown fit)` oppure `None`. Non solleva mai.

    `None` vuol dire "per questa pagina crawl4ai non ha niente": container
    giu', timeout, 403 dell'anti-bot, markdown vuoto. Chi chiama decide il
    ripiego.
    """
    try:
        risposta = SESSIONE.post(
            f"{BASE}/crawl",
            json={"urls": [url], "crawler_config": CRAWLER},
            timeout=timeout,
        )
        risposta.raise_for_status()
        risultato = risposta.json()["results"][0]
        if not risultato.get("success"):
            return None
        markdown = (risultato.get("markdown") or {}).get("fit_markdown") or ""
        if not markdown.strip():
            return None
        titolo = (risultato.get("metadata") or {}).get("title") or url
        return titolo.strip(), markdown
    except Exception:  # noqa: BLE001 - una pagina in meno, non un errore
        return None


def testo_pulito(url: str, timeout: int = 8) -> tuple[str, str] | None:
    """La pagina come testo: niente link, niente marcature, niente menu.

    Esce un testo confrontabile con quello di trafilatura, perche' finisce
    nello stesso posto: il punteggio a parole chiave di `_passaggi`. Le
    marcature markdown in pasto al punteggio sarebbero rumore fisso, e il
    modello non deve vedere `[clicca qui](https://...)` dove basta "clicca
    qui".
    """
    letto = _richiesta(url, timeout)
    if letto is None:
        return None
    titolo, markdown = letto
    testo = "\n".join(_senza_navigazione(markdown))
    # Le marcature che sopravvivono alle righe di prosa: titoli, grassetto,
    # codice inline. Prima le immagini (che prendono il testo con loro), poi
    # i link aperti nel loro testo — l'ordine e' quello, altrimenti `![alt]`
    # diventerebbe `!alt` e `[testo](url)` sparirebbe col testo dentro.
    testo = IMMAGINE.sub("", testo)
    testo = LINK_TESTO.sub(r"\1", testo)
    testo = re.sub(r"^#{1,6}\s*", "", testo, flags=re.MULTILINE)  # titoli
    testo = re.sub(r"[*_`]{1,3}", "", testo)  # grassetto, corsivo, codice
    testo = html.unescape(testo)
    testo = re.sub(r"[ \t]+", " ", testo)
    testo = re.sub(r"\n{3,}", "\n\n", testo).strip()
    if not testo:
        return None
    return titolo, testo


def markdown_integrale(url: str, timeout: int = 15) -> tuple[str, str] | None:
    """La pagina come nota: markdown con i link, senza il menu.

    Per il vault si tiene la resa strutturata — titoli, liste, grassetto e
    link inline — perche' una nota su Obsidian e' un documento, non un
    passaggio. La navigazione la si toglie uguale: una nota che comincia con
    sessanta righe di menu e' il modo piu' sicuro di non rileggerla mai.

    Non e' collegata a nessun tool: servira' a `ricorda` e `salva`, quando la
    fase 3 e la fase 4 saranno pronte.
    """
    letto = _richiesta(url, timeout)
    if letto is None:
        return None
    titolo, markdown = letto
    corpo = "\n".join(_senza_navigazione(markdown))
    corpo = re.sub(r"\n{3,}", "\n\n", corpo).strip()
    if not corpo:
        return None
    return titolo, corpo
