"""Il collegamento col PC fisso: qui non si esegue niente, si delega.

Sul Mac girano solo il bot e il modello. Ricerca web, trascrizione dei vocali e
lettura delle immagini stanno sul fisso, che ha la GPU e la RAM, e si
raggiungono col forward inverso del tunnel ssh su `127.0.0.1:8090`.

**Le DEFINIZIONI non vanno mai tolte, nemmeno col fisso spento.** La cache del
prompt del Mac pretende `entry.tools == request.tools` byte per byte: cambiare
la lista degli strumenti azzera il prefill dell'intera conversazione, che a 8K
token sono quasi sei minuti. Quindi restano sempre tutte e due, e quando il
fisso non c'e' e' l'esecutore a rispondere che e' spento — quindici token, e il
modello se la cava con quello che sa.

Sono anche le stesse identiche definizioni di quando il bot girava sul fisso:
riscriverle diversamente avrebbe buttato la cache della conversazione in corso.
"""

from __future__ import annotations

import os

import requests

import risveglio

GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8090")

# Generoso di proposito: `leggi` deve scaricare una pagina, un vocale lungo puo'
# richiedere il caricamento di whisper, la prima immagine dopo cinque minuti di
# inerzia paga il caricamento del modello di visione. Non e' un timeout che
# protegge da un fisso spento — quello da' rifiuto immediato — ma da una pagina
# web che non risponde.
TIMEOUT = 300


class FissoSpento(RuntimeError):
    """Il gateway non risponde: il PC fisso e' spento o il tunnel e' giu'."""


# Quanto aspettare il `/ping` prima di dichiarare morto il fisso. Sul loopback
# attraverso il tunnel sono millisecondi: tre secondi sono gia' generosi.
ATTESA_PING = 3


def _vivo() -> bool:
    """Il fisso c'e' davvero, o e' solo il tunnel a fingere?

    **Il rifiuto immediato vale per il fisso spento, non per quello sospeso.**
    Quando il fisso si sospende la connessione ssh si congela senza chiudersi:
    nessun FIN, nessun RST, e `sshd` sul Mac tiene aperto il listener del
    forward inverso. La `connect()` allora riesce, il canale viene aperto verso
    una macchina che dorme e la richiesta resta appesa fino a `TIMEOUT`, che e'
    volutamente lungo perche' `cerca` ci mette mezzo minuto. Cinque minuti di
    attesa invece di un magic packet.

    Un `/ping` con tre secondi di pazienza distingue i due casi e costa qualche
    millisecondo quando il fisso c'e'. Copre anche il gateway bloccato, che dal
    di fuori e' indistinguibile da una macchina addormentata.
    """
    try:
        requests.get(f"{GATEWAY}/ping", timeout=ATTESA_PING).raise_for_status()
        return True
    except Exception:  # noqa: BLE001 - qualunque cosa vada storta, il fisso non c'e'
        return False


def _chiama(percorso: str, corpo: dict) -> str:
    if not _vivo():
        acceso = risveglio.sveglia()
        raise FissoSpento(
            "il PC fisso dormiva e l'ho appena svegliato: fra una ventina di "
            "secondi gli strumenti tornano"
            if acceso
            else "il PC fisso non risponde"
        )

    try:
        risposta = requests.post(f"{GATEWAY}{percorso}", json=corpo, timeout=TIMEOUT)
    except requests.ConnectionError as errore:
        # Il tunnel lo apre il fisso: se il fisso e' spento la porta 8090 non
        # esiste proprio e questo scatta subito, senza attese. E' anche il
        # momento giusto per svegliarlo: il rifiuto immediato e' la prova che
        # non c'e', e chi voleva uno strumento voleva il fisso.
        acceso = risveglio.sveglia()
        raise FissoSpento(
            "il PC fisso dormiva e l'ho appena svegliato: fra una ventina di "
            "secondi gli strumenti tornano"
            if acceso
            else "il PC fisso non risponde"
        ) from errore

    if risposta.status_code >= 400:
        try:
            dettaglio = risposta.json().get("errore", risposta.text[:200])
        except ValueError:
            dettaglio = risposta.text[:200]
        raise RuntimeError(dettaglio)

    return risposta.json()["testo"]


def trascrivi(file_id: str) -> str:
    """Vocale -> testo. Il fisso se lo scarica da solo da Telegram."""
    return _chiama("/trascrivi", {"file_id": file_id})


def immagine(file_id: str, didascalia: str = "") -> str:
    """Immagine -> testo. I pixel non arrivano mai qui."""
    return _chiama("/immagine", {"file_id": file_id, "didascalia": didascalia or ""})


def energia(percorso: str) -> str:
    """`/gioco`, `/amici` e `/energia`: la GPU del fisso, comandata dal bot.

    Passano di qui e non dalle DEFINIZIONI perche' non sono decisioni del
    modello ma del proprietario, e perche' un tool in piu' costerebbe il prefill di
    ogni conversazione futura per una cosa che si usa due volte al giorno.
    """
    return _chiama(percorso, {})


def gateway_raggiungibile() -> tuple[bool, str]:
    try:
        risposta = requests.get(f"{GATEWAY}/salute", timeout=8)
        risposta.raise_for_status()
        dati = risposta.json()
        return bool(dati.get("ok")), f"ricerca {dati.get('ricerca')}, visione {dati.get('visione')}"
    except Exception as errore:  # noqa: BLE001 - diagnostica, va mostrato tutto
        return False, str(errore)[:150]


# Le definizioni che il Mac vede. Tenerle poche e stabili e' il punto di tutto:
# ogni tool in piu' si paga sul primo turno di OGNI conversazione.
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


def esegui(nome: str, argomenti: dict) -> str:
    """Esegue uno strumento sul fisso. Non solleva mai: quello che torna di qui
    finisce nel contesto del modello, quindi anche i guasti vanno raccontati in
    una riga corta invece che con un'eccezione."""
    try:
        return _chiama("/esegui", {"nome": nome, "argomenti": argomenti})
    except FissoSpento as errore:
        return (
            f"Strumento non disponibile: {errore}. Rispondi con quello che sai "
            "e di' che non hai potuto controllare."
        )
    except Exception as errore:  # noqa: BLE001
        return f"{nome} non ha risposto: {errore}"[:300]
