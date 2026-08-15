"""Tool gateway: pochi strumenti grossolani, risultati corti.

Due regole, entrambe misurate il 2026-08-10:

1. **Pochi tool, sempre identici.** Ogni definizione entra nel contesto del Mac
   a ogni conversazione: 40 tool sono 2.600 token, cioe' +58s sul primo turno.
   E se il set cambia fra un turno e l'altro la cache non aggancia piu'
   (`entry.tools == request.tools`).

2. **I risultati li comprime il fisso.** Una pagina web grezza sono ~2.000
   token, cioe' un minuto di prefill sul Mac. Qui si estrae, si taglia e si
   restituisce l'essenziale. Il gateway non e' un esecutore di tool: e' un
   compressore di contesto.

La compressione e' volutamente **estrattiva**, senza LLM: per le pagine si
scelgono i paragrafi piu' pertinenti alla domanda con un punteggio a parole
chiave. Un modello di riassunto sul 4060 Ti arrivera' con Honcho, se e quando
servira' davvero.

Il 12 agosto e' caduta la terza regola scritta qui, che diceva che gli snippet
di SearXNG bastano quasi sempre. Non bastano: vedi `cerca`.
"""

from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
import trafilatura

import web

SEARXNG = "http://127.0.0.1:8888/search"

# Tetti in caratteri: ~4 caratteri per token, quindi 1200 caratteri ≈ 300 token.
# Sul Mac 300 token di prefill sono ~4s; 2000 token sarebbero un minuto.
TETTO_RICERCA = 1400
TETTO_PAGINA = 1600

# Quante pagine `cerca` apre davvero, e quanto testo tiene di ognuna. Tre da
# ~340 caratteri stanno nei 1400 di prima insieme a titoli e url: il tetto non
# si alza, cambia solo cosa c'e' dentro. Aprirne di piu' non servirebbe a
# niente, perche' il posto per scriverle non c'e'.
PAGINE_APERTE = 3
TETTO_PASSAGGIO = 340

# Sei secondi a pagina, e si aprono tutte insieme. Una ricerca costava 0,7s e
# ora ne costa 2-3: sul Mac lo stesso turno ne dura 37, quindi il tempo qui non
# si vede. Chi non risponde entro la scadenza lascia il posto al suo snippet.
TIMEOUT_PAGINA = 6

# Senza User-Agent parecchi siti rispondono 403 a trafilatura.
INTESTAZIONI = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    )
}

PAROLE_VUOTE = {
    "il","lo","la","i","gli","le","un","uno","una","di","a","da","in","con","su",
    "per","tra","fra","e","o","ma","che","chi","cosa","come","quando","dove",
    "the","of","and","to","a","in","is","for","on","with","how","what",
}


@dataclass
class Documento:
    """Una pagina scaricata. Il testo integrale resta qui sul fisso."""

    url: str
    titolo: str
    testo: str


# Il testo integrale non entra mai nel contesto del Mac: lui maneggia gli url,
# noi teniamo il contenuto. La cache la riempie anche `cerca`, quindi una
# `leggi` sullo stesso url e' gratis e istantanea.
#
# Il tetto serve da quando la riempie `cerca`: tre pagine per ricerca dentro un
# processo che non si riavvia mai sono una perdita lenta. Duecento pagine sono
# pochi MB e coprono comunque la `leggi` che segue la ricerca, che e' l'unico
# caso in cui la cache serva davvero.
CACHE_PAGINE: dict[str, Documento] = {}
MAX_PAGINE_IN_CACHE = 200


def _parole(testo: str) -> set[str]:
    return {
        p for p in re.findall(r"\w+", testo.lower())
        if len(p) > 2 and p not in PAROLE_VUOTE
    }


def _scarica(url: str, timeout: int = TIMEOUT_PAGINA) -> Documento | None:
    """Scarica ed estrae una pagina. `None` se non si puo': non solleva mai.

    Chi chiama deve poter tirare avanti con gli altri risultati — un sito che
    risponde 403 non e' una ricerca fallita.

    Due corsie, crawl4ai davanti e statico dietro (misurato il 15 agosto: il
    browser rende 2,6x caratteri in piu', ma un container che riparte dopo il
    risveglio del fisso non deve costare a Elechim la lettura delle pagine).
    Se la prima non risponde entro il timeout, si prova l'altra: il costo e'
    qualche secondo sulla pagina sfortunata, il beneficio e' che il tubo non
    ha un punto unico di rottura.
    """
    documento = CACHE_PAGINE.get(url)
    if documento is not None:
        return documento

    estratto = web.testo_pulito(url, timeout=timeout)
    if estratto is None:
        try:
            risposta = requests.get(url, headers=INTESTAZIONI, timeout=timeout)
            risposta.raise_for_status()
            estratto = trafilatura.extract(
                risposta.text, include_comments=False, include_tables=False
            )
            if not estratto:
                return None
            metadati = trafilatura.extract_metadata(risposta.text)
            titolo = getattr(metadati, "title", None) or url
        except Exception:  # noqa: BLE001 - una pagina in meno, non un errore
            return None
    else:
        titolo, estratto = estratto

    documento = Documento(url=url, titolo=titolo, testo=estratto)

    if len(CACHE_PAGINE) >= MAX_PAGINE_IN_CACHE:
        # I dict di Python conservano l'ordine di inserimento: il primo e' il
        # piu' vecchio, ed e' quello che serve meno.
        del CACHE_PAGINE[next(iter(CACHE_PAGINE))]
    CACHE_PAGINE[url] = documento
    return documento


def _punteggio(paragrafo: str, chiavi: set[str], posizione: int, quanti: int) -> float:
    """Quanto vale un paragrafo per la domanda.

    Le parole chiave da sole non bastano: su una pagina che parla proprio di
    quello che hai cercato le contengono quasi tutti i paragrafi, disclaimer
    compresi, e il primo risultato del 12 agosto era "questo articolo ha uno
    scopo puramente informativo". Quindi due correzioni: la boilerplate va a
    zero, e a parita' di parole vince chi sta piu' in alto, perche' negli
    articoli la sostanza sta prima e i cookie stanno dopo.
    """
    if BOILERPLATE.search(paragrafo):
        return 0.0
    # Normalizzato sulla lunghezza per non premiare i muri di testo.
    pertinenza = len(chiavi & _parole(paragrafo)) / (1 + len(paragrafo) / 800)
    anzianita = 1 - (posizione / max(quanti, 1))  # 1 il primo, ~0 l'ultimo
    return pertinenza + 0.35 * anzianita


# Frasi che compaiono in ogni pagina e non rispondono a nessuna domanda.
BOILERPLATE = re.compile(
    r"scopo (puramente )?informativ|non sostituisce|consulta(re)? (il|un) medico"
    r"|cookie|newsletter|tutti i diritti riservat|p\.? ?iva|privacy policy"
    r"|termini e condizioni|iscriviti|registrati|accedi al tuo account"
    r"|spedizione gratuita|aggiungi al carrello|disclaimer",
    re.IGNORECASE,
)


def _passaggi(documento: Documento, domanda: str, tetto: int) -> str:
    """I paragrafi del documento piu' pertinenti alla domanda, entro il tetto."""
    paragrafi = [p.strip() for p in documento.testo.split("\n") if len(p.strip()) > 80]
    if not paragrafi:
        return re.sub(r"\s+", " ", documento.testo).strip()[:tetto]

    chiavi = _parole(domanda)
    if chiavi:
        classifica = sorted(
            range(len(paragrafi)),
            key=lambda i: _punteggio(paragrafi[i], chiavi, i, len(paragrafi)),
            reverse=True,
        )
        classifica = [paragrafi[i] for i in classifica]
    else:
        classifica = paragrafi

    scelti: list[str] = []
    totale = 0
    for paragrafo in classifica:
        if totale + len(paragrafo) > tetto:
            continue
        scelti.append(paragrafo)
        totale += len(paragrafo)
        if totale > tetto * 0.8:
            break

    if not scelti:
        # Tutti i paragrafi sono piu' lunghi del tetto: si taglia il migliore.
        return re.sub(r"\s+", " ", classifica[0]).strip()[:tetto]

    # Rimetto i paragrafi nell'ordine originale: la classifica serviva a
    # sceglierli, non a leggerli.
    scelti.sort(key=paragrafi.index)
    return "\n\n".join(scelti)


def _e_vetrina(url: str) -> bool:
    """Url senza percorso: quasi sempre la homepage di un negozio.

    Su "migliori integratori naturali" i primi due risultati erano vetrine di
    e-commerce, e il loro snippet era "approfitta delle offerte e acquista
    online". Non si buttano via — si mandano in fondo, e se restano fuori dai
    tre che apriamo e' perche' qualcosa di meglio ha preso il loro posto.
    """
    return not urlsplit(url).path.strip("/")


def cerca(query: str, quanti: int = 5) -> str:
    """Cerca sul web e restituisce i passaggi utili delle prime pagine.

    **Gli snippet di SearXNG da soli non bastano.** Il 12 agosto, alla richiesta
    esplicita "mi fai una ricerca web sui migliori integratori naturali", il
    modello ha chiamato lo strumento e poi ha risposto ignorando quello che era
    tornato: cinque righe di marketing da e-commerce ("al miglior prezzo
    garantito"), zero fatti da citare. Lo strumento funzionava e non serviva a
    niente, che e' il modo peggiore in cui una cosa puo' rompersi.

    Quindi la ricerca apre da sola le prime pagine e ne estrae i passaggi
    pertinenti, invece di aspettare che il modello incateni una `leggi`: un
    secondo giro di tool costa un altro turno sul Mac (10-30s) e comunque il
    modello non lo faceva. Stesso tetto di prima, contenuto diverso.
    """
    try:
        risposta = requests.get(
            SEARXNG,
            params={"q": query, "format": "json", "language": "it"},
            timeout=30,
        )
        risposta.raise_for_status()
        risultati = risposta.json().get("results", [])
    except Exception as errore:  # noqa: BLE001
        return f"Ricerca fallita: {errore}"

    if not risultati:
        return "Nessun risultato."

    # Le vetrine in fondo, il resto nell'ordine di SearXNG (`sorted` e' stabile).
    # Guardo oltre `quanti` perche' la deduplica per dominio scarta risultati:
    # con tre soli slot, due pagine dello stesso sito sono uno slot buttato
    # (visto: ilprodottomigliore.it due volte di fila sulla stessa ricerca).
    ordinati = sorted(risultati[:12], key=lambda r: _e_vetrina(r.get("url", "")))

    candidati: list[dict] = []
    domini: set[str] = set()
    for risultato in ordinati:
        dominio = urlsplit(risultato.get("url", "")).netloc.removeprefix("www.")
        if not dominio or dominio in domini:
            continue
        domini.add(dominio)
        candidati.append(risultato)
        if len(candidati) == PAGINE_APERTE:
            break

    with concurrent.futures.ThreadPoolExecutor(max_workers=PAGINE_APERTE) as pool:
        documenti = list(pool.map(lambda r: _scarica(r.get("url", "")), candidati))

    righe: list[str] = []
    totale = 0
    for risultato, documento in zip(candidati, documenti):
        url = risultato.get("url", "")
        titolo = (documento.titolo if documento else risultato.get("title") or "").strip()
        if documento is not None:
            corpo = _passaggi(documento, query, TETTO_PASSAGGIO)
        else:
            # La pagina non si apre: meglio lo snippet che una riga vuota.
            corpo = re.sub(r"\s+", " ", (risultato.get("content") or "")).strip()[:220]

        blocco = f"- {titolo}\n  {corpo}\n  {url}"
        if totale + len(blocco) > TETTO_RICERCA and righe:
            break
        righe.append(blocco)
        totale += len(blocco)

    return "\n".join(righe)[:TETTO_RICERCA]


def leggi(url: str, domanda: str = "") -> str:
    """Scarica una pagina e restituisce solo i passaggi utili alla domanda."""
    documento = _scarica(url)
    if documento is None:
        return f"Non sono riuscito a leggere {url}"
    # Il tetto vale su quello che entra nel contesto del Mac, titolo compreso:
    # sforarlo di poco non si nota, ma il tetto e' un budget di prefill e i
    # budget si contano interi.
    intestazione = f"{documento.titolo}\n\n"
    return intestazione + _passaggi(
        documento, domanda, TETTO_PAGINA - len(intestazione)
    )


# Le definizioni che il Mac vede. Tenerle poche e stabili e' il punto di tutto:
# ogni tool in piu' si paga sul primo turno di OGNI conversazione. Non si
# toccano nemmeno quando cambia quello che c'e' sotto: il 12 agosto `cerca` ha
# cominciato ad aprire le pagine, e la sua descrizione e' rimasta identica
# byte per byte perche' riscriverla avrebbe buttato la cache di ogni
# conversazione in corso.
DEFINIZIONI = [
    {
        "type": "function",
        "function": {
            "name": "cerca",
            "description": "Cerca sul web. Restituisce titoli, riassunti brevi e url.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cosa cercare"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leggi",
            "description": (
                "Legge una pagina web da un url trovato con cerca e ne "
                "restituisce solo i passaggi utili alla domanda."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "domanda": {
                        "type": "string",
                        "description": "Cosa cercare nella pagina",
                    },
                },
                "required": ["url"],
            },
        },
    },
]

ESECUTORI = {"cerca": cerca, "leggi": leggi}


def esegui(nome: str, argomenti: dict) -> str:
    funzione = ESECUTORI.get(nome)
    if funzione is None:
        return f"Strumento sconosciuto: {nome}"
    try:
        return funzione(**argomenti)
    except TypeError as errore:
        return f"Argomenti sbagliati per {nome}: {errore}"
    except Exception as errore:  # noqa: BLE001
        return f"{nome} e' fallito: {errore}"
