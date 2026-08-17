"""La sbobina: riscrive le sezioni gia' estratte, come un professore.

Stadio due della fase 4, separato dall'estrazione per costruzione: estrarre e'
veloce e deterministico (70s per 533 pagine), riscrivere e' lento e fallibile.
Separati, fra sei mesi si rifanno tutte le sbobine con un modello migliore
senza riestrarre niente; fusi, ogni miglioramento del modello costa tutto da
capo.

Cosa consuma: il markdown integrale in `markdown/` (la verita') e le note
atomiche gia' in `30-Note/` (l'indice delle sezioni, con pagina e pagina_fine
nel frontmatter). Cosa produce: la stessa nota, con l'estratto-segnalibro
sostituito dalla spiegazione.

Le regole che questo modulo non puo' violare:

- le tabelle non passano mai dal modello: i recinti ``<!-- tabella -->`` del
  markdown integrale vengono tolti dal testo dato al modello e ricopiati
  verbatim nella nota, in "Materiale originale";
- il documento intero non passa mai: una sezione alla volta, con un tetto di
  caratteri sopra il quale la sezione si salta e si conta nel rapporto;
- il controllo dei numeri: ogni cifra del testo generato deve esserci nella
  fonte. Quelle che non ci sono si contano, si scrivono nel frontmatter e si
  segnalano in coda alla nota.

Lo stato e' un marcatore **mio**, `stato/sbobina/<slug>.json`, accanto a
`stato/documenti/`: l'avanzamento e' per sezione, un lavoro interrotto riprende
dalla sezione dove era arrivato. Lo stadio dei documenti (`estratto` ->
`fatto`) non si tocca; quando tutte le sezioni hanno la loro sbobina, qui
dentro lo stadio diventa `sbobinato`.

La GPU: la riserva con lo stesso meccanismo di `/gioco` -> `/amici`
(`energia.libera_vram` / `energia.carica_vram`). Il lock `threading.Lock` di
`gateway.py` vive nel processo del gateway e un processo separato non puo'
prenderlo: la bandiera `stato/gioco` e' l'unico lock GPU *fra processi* che
il progetto abbia, ed e' quella che il gateway rispetta prima di toccare la
scheda. Finche' la sbobina lavora, vocali e immagini rispondono che la GPU e'
riservata; alla fine qwen3-vl torna in caldo con keep_alive corto, come dopo
`/amici`. Se era il proprietario ad aver chiesto `/gioco`, la bandiera resta
su e nessuno gli ricarica i modelli sotto la partita.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

import documenti
import energia

OLLAMA = "http://127.0.0.1:11434"
MODELLO = os.environ.get("SBOBINA_MODELLO", "qwen3:8b")

# Il marcatore mio, accanto a quello dei documenti: deriva da
# documenti.STATO cosi' il collaudo, che ridirige i percorsi di documenti,
# ridirige anche questo.
STATO = documenti.STATO.parent / "sbobina"

# La finestra di contesto chiesta a ollama. Tutto il resto si deriva da qui:
# e' l'unico numero che si cambia quando si cambia modello.
NUM_CTX = int(os.environ.get("SBOBINA_NUM_CTX", "8192"))

# Quanto pesa il prompt fisso, in token. Sovrastimato di proposito: sbagliare
# per eccesso costa qualche carattere di fonte, sbagliare per difetto fa
# traboccare il contesto e ollama taglia in silenzio.
TOKEN_PROMPT = 150

# Il margine che si lascia libero nel contesto. Serve perche' il rapporto
# caratteri/token e' una media e una sezione puo' essere piu' densa delle altre.
MARGINE_CONTESTO = 0.10

# Caratteri per token, **misurato** il 16 agosto 2026 su cinque sezioni di
# `dsml` (leggendo `prompt_eval_count` di ollama, non stimando): media 3,72 e
# **caso peggiore 3,06**. Si usa il peggiore, non la media: il budget deve
# reggere la sezione piu' densa, non quella tipica. La matematica tokenizza
# male — formule e simboli costano piu' token della prosa — e questo e' il
# motivo per cui il numero si misura sul documento vero invece di prenderlo da
# una tabella generica (le stime "4 caratteri per token" qui sfonderebbero).
CAR_PER_TOKEN = float(os.environ.get("SBOBINA_CAR_PER_TOKEN", "3.06"))


def budget_caratteri(num_ctx: int = NUM_CTX) -> int:
    """Quanta fonte ci sta in un pezzo, derivata dal contesto del modello.

    Prima era una costante a 9.000 accanto a un `num_ctx` di 8.192: due numeri
    scelti a mano che dovevano restare coerenti senza che niente lo
    garantisse. Il giorno che si prova un modello con 32k di contesto la
    costante sarebbe rimasta a 9.000 sprecando tre quarti della finestra; il
    giorno che qualcuno l'alzasse senza toccare `num_ctx`, il contesto
    traboccherebbe e ollama taglierebbe la fonte **in silenzio** — che e' il
    guasto peggiore, perche' la nota sembra perfetta.

    Derivandola, cambiare modello ricalcola tutto da solo:

        (contesto - prompt - risposta) x (1 - margine) x caratteri/token

    Con i valori misurati: (8192 - 150 - 1800) x 0,9 x 3,06 = ~17.100
    caratteri, quasi il doppio della vecchia costante. Meno divisioni, quindi
    piu' coerenza: il modello spiega meglio un ragionamento intero.
    """
    token = (num_ctx - TOKEN_PROMPT - MAX_TOKEN_SPIEGAZIONE) * (1 - MARGINE_CONTESTO)
    return max(1000, int(token * CAR_PER_TOKEN))


# Sotto questa non c'e' niente da spiegare: titoli, intestazioni di capitolo.
MIN_FONTE = 200

# Quando la frazione di caratteri sostituiti da segnaposto supera questa
# soglia, la nota lo dichiara invece di fingere una spiegazione completa.
SOGLIA_SEGNAPOSTI = 0.50

# Il tetto di generazione. Il professore *espande*, quindi l'output puo'
# superare la fonte: 1.800 token sono ~60-70 righe di spiegazione. Il tetto
# alto non costa niente quando il modello e' breve, perche' si ferma da solo.
MAX_TOKEN_SPIEGAZIONE = 1800
MAX_TOKEN_PUNTI = 300

# Il tetto di un pezzo di fonte. **Non e' piu' una soglia di scarto**: niente
# si salta per lunghezza, si divide e basta (vedi `INCARICO-chunking-adattivo`).
# Resta sovrascrivibile a mano per le prove, ma il valore buono lo calcola
# `budget_caratteri` dal contesto del modello.
MAX_FONTE = int(os.environ.get("SBOBINA_MAX_FONTE", "0")) or budget_caratteri()

# Il modello resta in VRAM fra una sezione e l'altra (il lavoro dura ore) ma
# non per sempre: se il processo muore male, ollama se lo riprende entro
# mezz'ora invece di tenere 5 GB occupati fino al riavvio.
KEEP_ALIVE = "30m"

# Istruzione semplice, un compito solo: su un modello piccolo l'istruzione
# complessa peggiora il risultato. Mai "riassumi": la differenza fra i due
# verbi e' la differenza fra utile e inutile, come sbobina.
PROMPT_SPIEGAZIONE = (
    "Spiega questo passaggio a uno studente, in italiano, con parole semplici. "
    "Sviluppa i concetti invece di riassumere. "
    "Riporta i numeri esattamente come sono scritti nel testo, senza cambiarli. "
    "Massimo 50 righe.\n\n"
)

PROMPT_PUNTI = (
    "Elenca i punti chiave di questo passaggio, in italiano: "
    "una riga per punto, al massimo 4 punti, senza numerarli.\n\n"
)

PROMPT_MINIMO = "Spiega questo testo in italiano, con parole semplici.\n\n"

# Cosa scrivere al posto dei recinti nel testo dato al modello.
SEGNAPOSTO_TABELLA = "[qui c'e' una tabella, riportata uguale nella nota sotto Materiale originale]"
SEGNAPOSTO_FORMULA = "[qui c'e' una formula, riportata uguale nella nota sotto Materiale originale]"

SEGNAPOSTI = {"tabella": SEGNAPOSTO_TABELLA, "formula": SEGNAPOSTO_FORMULA}

# Recinti di tabella e formula prodotti da documenti.py.
RE_BLOCCO = re.compile(r"<!-- (tabella|formula) pag \d+ blocco \d+ -->\s*```.*?```", re.S)
RE_MARCA_BLOCCO = re.compile(r"__BLOCCO_(\d+)__+")
RE_NUMERI = re.compile(r"\d+(?:[.,]\d+)?")


# --- lo stato --------------------------------------------------------------


def _carica_stato(nome: str) -> dict:
    f = STATO / f"{nome}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"slug": nome, "modello": None, "sezioni": {}, "saltate": {}, "inizio": None}


def _salva_stato(nome: str, stato: dict) -> None:
    STATO.mkdir(parents=True, exist_ok=True)
    f = STATO / f"{nome}.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(stato, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


# --- le sezioni, lette dalle note che esistono gia' -------------------------


def _frontmatter(testo: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", testo, re.S)
    if not m:
        return {}
    campi = {}
    for riga in m.group(1).splitlines():
        if ":" not in riga or riga.startswith((" ", "-", "  ")):
            continue
        k, _, v = riga.partition(":")
        campi[k.strip()] = v.strip()
    return campi


def sezioni(nome: str) -> list[dict]:
    """Le sezioni di un documento, lette dalle note atomiche: il frontmatter
    ha pagina, pagina_fine e l'indice di sezione. Non serve il PDF ne'
    rilanciare le euristiche: la struttura e' gia' decisa."""
    fuori = []
    for f in documenti._note_del_documento(nome):
        campi = _frontmatter(f.read_text(encoding="utf-8"))
        if "sezione" not in campi or "pagina" not in campi:
            continue
        titolo = campi.get("titolo", '""')
        try:
            titolo = json.loads(titolo)
        except json.JSONDecodeError:
            titolo = titolo.strip('"')
        fuori.append(
            {
                "sezione": int(campi["sezione"]),
                "titolo": titolo,
                "pagina": int(campi["pagina"]),
                "pagina_fine": int(campi.get("pagina_fine", campi["pagina"])),
                "nota": f,
            }
        )
    fuori.sort(key=lambda s: s["sezione"])
    return fuori


def _fonte(nome: str, da_pag: int, a_pag: int) -> str:
    """Il testo dell'integrale, dalle pagine della sezione alla successiva."""
    md = documenti.MARKDOWN / f"{nome}.md"
    testo = md.read_text(encoding="utf-8")
    inizio = re.search(rf"<!-- pag {da_pag} -->", testo)
    if not inizio:
        return ""
    fine = re.search(rf"<!-- pag {a_pag + 1} -->", testo[inizio.end() :])
    pezzo = testo[inizio.end() : inizio.end() + fine.start()] if fine else testo[inizio.end() :]
    return pezzo.strip()


def _dividi(fonte: str) -> tuple[str, str]:
    """Separa la prosa (che va al modello) dai recinti (che non ci vanno')."""
    blocchi: list[tuple[str, str]] = []

    def sostituisci(m: re.Match) -> str:
        tipo = m.group(1)
        blocchi.append((tipo, m.group(0)))
        return SEGNAPOSTI[tipo]

    per_modello = RE_BLOCCO.sub(sostituisci, fonte)
    righe = []
    for tipo, recinto in blocchi:
        etichetta = "Tabella" if tipo == "tabella" else "Formula"
        righe.append(f"**{etichetta}**\n\n{recinto}")
    materiale = "\n\n".join(righe)
    return per_modello, materiale


def _chunk_fonte(fonte: str, max_car: int) -> tuple[list[str], dict[str, int]]:
    """Divide una sezione lunga in parti coerenti, senza spezzare i recinti
    di tabella e formula. I recinti sono blocchi indivisibili: se un recinto
    da solo supera il tetto, finisce in un chunk piu' lungo che comunque non
    passa al modello (il recinto e' sostituito dal segnaposto giusto).

    Torna anche le statistiche di taglio: quante volte si e' scesi a titoli,
    pagine, paragrafi, frasi, parole.
    """
    blocchi: list[tuple[str, str]] = []
    stats = {"titoli": 0, "pagine": 0, "paragrafi": 0, "frasi": 0, "parole": 0}

    def salva(m: re.Match) -> str:
        tipo = m.group(1)
        blocchi.append((tipo, m.group(0)))
        # Il segnaposto interno si imbottisce fino alla lunghezza di quello che
        # questo blocco ricevera' davvero (`SEGNAPOSTO_TABELLA` o
        # `SEGNAPOSTO_FORMULA`, ~80 caratteri contro i ~13 di `__BLOCCO_0__`).
        # Senza imbottitura la divisione misura una lunghezza e il modello ne
        # riceve un'altra: misurato su `dsml`, un pezzo dato per 17.190 caratteri
        # ne consegnava 22.076, cioe' ~7.200 token, che con prompt e risposta
        # sfondavano `num_ctx` e facevano tagliare la fonte a ollama in
        # silenzio. Il budget deve valere sul testo che parte, non su una sua
        # abbreviazione. Ogni tipo di blocco si imbottisce con la propria
        # lunghezza, perche' tabelle e formule hanno segnaposti diversi.
        marca = f"__BLOCCO_{len(blocchi) - 1}__"
        return "\n\n" + marca.ljust(len(SEGNAPOSTI[tipo]), "_") + "\n\n"

    testo_segnaposto = RE_BLOCCO.sub(salva, fonte)

    # La cascata dei confini naturali, dal piu' forte al piu' debole. Si scende
    # di livello **solo** se il pezzo non sta ancora nel budget, perche' ogni
    # gradino piu' in basso taglia piu' vicino al ragionamento: un titolo separa
    # due argomenti, una virgola separa due meta' della stessa frase.
    #
    # E' la terza volta che in questo progetto "spezza per struttura" batte
    # "spezza per lunghezza": era gia' successo con l'outline del PDF contro le
    # euristiche sui font, e col sezionamento per titoli contro i chunk fissi.
    #
    # Livello 1, i titoli interni: 14 delle 46 sezioni lunghe di `dsml` ne hanno
    # almeno due, e sono il confine migliore che esista perche' l'ha messo
    # l'autore. Il titolo resta attaccato al testo che introduce.
    def per_titoli(t: str) -> list[str]:
        parti = re.split(r"\n(?=#{1,6} )", t)
        return [p for p in (x.strip() for x in parti) if p]

    # Livello 2, le ancore di pagina: ci sono su ogni pagina dell'integrale e
    # nessuna sezione lunga sta su una pagina sola (min 3, mediana 5, max 18).
    # Non e' un confine semantico, ma e' un confine **vero** del documento, e
    # taglia molto piu' raramente a meta' di un discorso di quanto faccia un
    # conteggio di caratteri.
    def per_pagine(t: str) -> list[str]:
        parti = re.split(r"\n(?=<!-- pag \d+ -->)", t)
        return [p for p in (x.strip() for x in parti) if p]

    # Livello 3, i paragrafi.
    def per_paragrafi(t: str) -> list[str]:
        return [p for p in (x.strip() for x in re.split(r"\n\s*\n", t)) if p]

    def a_pezzi(t: str) -> list[str]:
        """Il pezzo piu' grande che sta nel budget, non il piu' piccolo comodo.

        Dividere piu' del necessario costa coerenza: il modello spiega meglio un
        ragionamento intero che tre terzi di ragionamento. Quindi si prova un
        livello per volta e ci si ferma **appena** uno basta.
        """
        if len(t) <= max_car:
            return [t]
        for nome, taglia in (
            ("titoli", per_titoli),
            ("pagine", per_pagine),
            ("paragrafi", per_paragrafi),
        ):
            parti = taglia(t)
            if len(parti) > 1:
                stats[nome] += 1
                fuori: list[str] = []
                for p in parti:
                    fuori.extend(a_pezzi(p) if len(p) > max_car else [p])
                return fuori
        # nessun confine naturale: si scende alle frasi, e in ultima istanza
        # alle parole - la rete che garantisce che il procedimento finisca
        # sempre, qualunque cosa gli arrivi.
        return spezza(t)

    def spezza(pezzo: str) -> list[str]:
        if len(pezzo) <= max_car:
            return [pezzo]
        frasi = [f.strip() for f in re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", pezzo) if f.strip()]
        if len(frasi) <= 1:
            stats["parole"] += 1
            parole = pezzo.split()
            out, cur = [], ""
            for parola in parole:
                if cur and len(cur) + 1 + len(parola) > max_car:
                    out.append(cur)
                    cur = parola
                else:
                    cur = f"{cur} {parola}".strip()
            if cur:
                out.append(cur)
            return out
        stats["frasi"] += 1
        out, cur = [], ""
        for f in frasi:
            if cur and len(cur) + 1 + len(f) > max_car:
                out.append(cur)
                cur = f
            else:
                cur = f"{cur} {f}".strip()
        if cur:
            out.append(cur)
        return out

    # `spezza` e' definita sopra perche' `a_pezzi` ci ricade quando non trova
    # nessun confine naturale.
    pezzi = a_pezzi(testo_segnaposto.strip())

    chunks, cur = [], ""
    for p in pezzi:
        if cur and len(cur) + 2 + len(p) > max_car:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}".strip() if cur else p
    if cur:
        chunks.append(cur)

    def ripristina(testo: str) -> str:
        # `_+` per riassorbire l'imbottitura messa da `salva`.
        def rimpiazza(m: re.Match) -> str:
            idx = int(m.group(1))
            return blocchi[idx][1]

        return RE_MARCA_BLOCCO.sub(rimpiazza, testo)

    chunks = [ripristina(c) for c in chunks]
    return chunks or [fonte], stats


# --- il controllo dei numeri ------------------------------------------------


def _normalizza_numero(t: str) -> str:
    t = t.replace(",", ".")
    t = re.sub(r"^0+(?=\d)", "", t)
    return t


def verifica_numeri(generato: str, fonte: str) -> list[str]:
    """I numeri del testo generato che non ci sono nella fonte.

    Riconosce i decimali con la virgola o col punto ("48,5" == "48.5"), e i
    falsi allarmi del tipo "due" per "2" non li produce perche' guarda solo
    alle cifre: la parola non e' una trascrizione che puo' essere sbagliata,
    la cifra si'. Gli allarmi trovati si segnalano, non si correggono.
    """
    buoni = {_normalizza_numero(m) for m in RE_NUMERI.findall(fonte)}
    fuori: list[str] = []
    for m in RE_NUMERI.findall(generato):
        n = _normalizza_numero(m)
        if n not in buoni and m not in fuori:
            fuori.append(m)
    return fuori


# --- il modello -------------------------------------------------------------


def _senza_pensiero(testo: str) -> str:
    """Togli il ragionamento che qwen3 lascia nel contenuto anche con
    think: false (l'apertura la taglia ollama, la chiusura no).

    Se il pensiero e' stato troncato dal tetto di token, la risposta non
    c'e': torna la stringa vuota e se ne occupa il secondo giro con
    l'istruzione minima. Lezione gia' pagata in visione.py.
    """
    if "</think>" in testo:
        return testo.split("</think>", 1)[1].strip()
    if testo.startswith("<think>"):
        return ""
    return testo.strip()


def _chiedi(modello: str, prompt: str, max_token: int, timeout: int = 600) -> tuple[str, dict]:
    """Un giro di chat. Torna (testo, metriche ollama).

    C'e' un timeout (10 minuti per chiamata) e un retry sui guasti di
    rete/ollama, perche' un modello impiantato non deve bloccare per sempre
    un lavoro da ore. Se la risposta e' vuota perche' ha sfondato il tetto
    di token (done_reason: length), torna stringa vuota e il chiamante
    decide se riprovare con un prompt piu' corto.
    """
    corpo = {
        "model": modello,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "temperature": 0.2,
            "num_predict": max_token,
            "num_ctx": 8192,
        },
    }
    ultimo_errore: Exception | None = None
    for tentativo in (1, 2):
        try:
            r = requests.post(f"{OLLAMA}/api/chat", json=corpo, timeout=timeout)
            if r.status_code != 200 and "think" in r.text.lower():
                # un modello senza ragionamento puo' rifiutare la flag: si ripete uguale
                corpo.pop("think")
                r = requests.post(f"{OLLAMA}/api/chat", json=corpo, timeout=timeout)
            r.raise_for_status()
            d = r.json()
            testo = _senza_pensiero(((d.get("message") or {}).get("content") or ""))
            if not testo:
                done = d.get("done_reason")
                print(f"  attenzione: risposta vuota (done_reason={done}), tentativo {tentativo}")
            return testo, d
        except requests.Timeout as e:
            ultimo_errore = e
            print(f"  timeout ollama, tentativo {tentativo}")
            time.sleep(2)
        except requests.ConnectionError as e:
            ultimo_errore = e
            print(f"  connessione ollama persa, tentativo {tentativo}")
            time.sleep(2)
    raise RuntimeError(f"ollama non risponde dopo 2 tentativi: {ultimo_errore}")


def riscrivi(modello: str, fonte_modello: str) -> tuple[str, str, dict]:
    """Due chiamate, un compito per volta: la spiegazione e i punti chiave."""
    t0 = time.time()
    spiegazione, m1 = _chiedi(modello, PROMPT_SPIEGAZIONE + fonte_modello, MAX_TOKEN_SPIEGAZIONE)
    if not spiegazione:
        # il ragionamento ha consumato il tetto e la risposta e' vuota:
        # secondo giro con l'istruzione minima, che costa pochi secondi e
        # salva la nota (lezione gia' pagata in visione.py).
        spiegazione, m1 = _chiedi(modello, PROMPT_MINIMO + fonte_modello, MAX_TOKEN_SPIEGAZIONE)
    if not spiegazione:
        raise RuntimeError("modello ha restituito spiegazione vuota per due volte")

    punti, m2 = _chiedi(modello, PROMPT_PUNTI + fonte_modello, MAX_TOKEN_PUNTI)
    if not punti:
        punti, m2 = _chiedi(
            modello, "Elenca i punti chiave, una riga per punto.\n\n" + fonte_modello, MAX_TOKEN_PUNTI
        )
    if not punti:
        punti = "(punti chiave non disponibili)"

    token = (m1.get("eval_count") or 0) + (m2.get("eval_count") or 0)
    durata_ns = (m1.get("eval_duration") or 0) + (m2.get("eval_duration") or 0)
    metriche = {
        "secondi": round(time.time() - t0, 1),
        "token_generati": token,
        "token_fonte": m1.get("prompt_eval_count") or 0,
        "tok_s": round(token * 1e9 / durata_ns, 1) if durata_ns else 0.0,
    }
    return spiegazione, punti, metriche


def versione_modello(nome: str) -> str:
    """Nome e digest: fra sei mesi e' l'unico modo di sapere quali note
    vengono da quale modello, per decidere cosa rifare."""
    try:
        r = requests.get(f"{OLLAMA}/api/tags", timeout=10)
        r.raise_for_status()
        for m in r.json().get("models", []):
            if m["name"] == nome or m["name"] == f"{nome}:latest":
                digest = m.get("digest", "").removeprefix("sha256:")[:12]
                return f"{m['name']} ({digest})"
    except Exception:  # noqa: BLE001 - diagnostica
        pass
    return nome


# --- la nota ----------------------------------------------------------------


def _escapa(testo: str) -> str:
    """Le doppie quadre della notazione matematica, in Obsidian, sarebbero
    wikilink verso note inesistenti: si escapano."""
    return testo.replace("[[", "\\[\\[").replace("]]", "\\]\\]")


def scrivi_nota(
    s: dict,
    nome: str,
    spiegazione: str,
    punti: str,
    materiale: str,
    allarmi: list[str],
    modello: str,
    caratteri_fonte: int,
    metriche: dict,
    frazione_segnaposti: float = 0.0,
) -> Path:
    originale = s["nota"].read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", originale, re.S)
    frontmatter = m.group(1) if m else ""
    aggiunti = [
        f"sbobinato: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"modello: {json.dumps(modello, ensure_ascii=False)}",
        f"caratteri_fonte: {caratteri_fonte}",
        f"numeri_non_verificati: {len(allarmi)}",
        f"frazione_segnaposti: {frazione_segnaposti:.4f}",
    ]
    if frazione_segnaposti > SOGLIA_SEGNAPOSTI:
        aggiunti.append("avviso_segnaposti: true")
    integrale = (documenti.MARKDOWN / f"{nome}.md").as_uri()
    pagine = f"{s['pagina']}" + (f"-{s['pagina_fine']}" if s["pagina_fine"] > s["pagina"] else "")

    corpo = [
        f"# {s['titolo']}",
        "",
        "## In breve",
    ]
    corpo += [f"- {riga.lstrip('- ').strip()}" for riga in punti.splitlines() if riga.strip()] or [
        "- (punti chiave non disponibili)"
    ]
    corpo += [
        "",
        "## La spiegazione",
        "",
    ]
    if frazione_segnaposti > SOGLIA_SEGNAPOSTI:
        corpo += [
            "⚠ Questa sezione e' in gran parte formule e tabelle: la spiegazione "
            "copre solo la prosa.",
            "",
        ]
    corpo += [
        _escapa(spiegazione).strip(),
        "",
    ]
    if materiale:
        corpo += ["## Materiale originale", "", materiale, ""]
    corpo += [
        "## Fonte",
        "",
        f"Documento: [[{nome}]] · [integrale]({integrale}) · pagina {pagine}",
    ]
    if allarmi:
        corpo += ["", f"⚠ {len(allarmi)} numeri non verificati"]

    nota = f"---\n{frontmatter}\n" + "\n".join(aggiunti) + "\n---\n\n" + "\n".join(corpo) + "\n"
    s["nota"].write_text(nota, encoding="utf-8")
    return s["nota"]


# --- la GPU, riservata col meccanismo che c'e' gia' --------------------------


@contextlib.contextmanager
def gpu_della_sbobina(modello: str):
    """Riserva la GPU con la bandiera che gia' rispetta il gateway.

    Se siamo noi ad alzare la bandiera (stato/gioco), la dobbiamo abbassare
    anche se ollama e' impiantato o il processo muore male: altrimenti il
    fisso resterebbe in modalita' gioco per sempre.
    """
    gia_in_gioco = energia.in_gioco()
    creato = False
    if not gia_in_gioco:
        print(energia.libera_vram(), flush=True)
        creato = True
    try:
        yield
    finally:
        try:
            requests.post(
                f"{OLLAMA}/api/generate",
                json={"model": modello, "keep_alive": 0},
                timeout=60,
            )
        except Exception:  # noqa: BLE001
            pass
        if creato:
            # Rimuoviamo la bandiera prima di chiedere a ollama di ricaricare i
            # modelli: se ollama e' impiantato, carica_vram() fallisce ma la
            # bandiera deve comunque tornare giu'.
            energia.GIOCO.unlink(missing_ok=True)
            try:
                print(energia.carica_vram(), flush=True)
            except Exception:  # noqa: BLE001
                pass


# --- il lavoro su una sezione ------------------------------------------------


def _riscrivi_chunked(
    modello: str, fonte: str
) -> tuple[str, str, str, dict, dict, int]:
    """Riscrive una sezione lunga spezzandola in chunk coerenti.

    Torna (spiegazione, punti, materiale_verbatim, metriche_aggregate,
    stats_taglio, n_chunk).
    """
    chunks, stats = _chunk_fonte(fonte, MAX_FONTE)
    spiegazioni, materiali, punti_list = [], [], []
    secondi, token_generati, token_fonte = 0.0, 0, 0

    for i, chunk in enumerate(chunks, 1):
        print(f"  chunk {i}/{len(chunks)} ({len(chunk)} caratteri)")
        per_modello, materiale = _dividi(chunk)
        sp, pu, met = riscrivi(modello, per_modello)
        spiegazioni.append(sp)
        if materiale.strip():
            materiali.append(materiale)
        punti_list.append(pu)
        secondi += met["secondi"]
        token_generati += met["token_generati"]
        token_fonte += met["token_fonte"]

    spiegazione = "\n\n".join(spiegazioni)
    materiale = "\n\n".join(materiali)

    visti: set[str] = set()
    punti_uniti: list[str] = []
    for riga in "\n".join(punti_list).splitlines():
        r = riga.lstrip("- ").strip()
        if r and r.lower() not in visti:
            punti_uniti.append(f"- {r}")
            visti.add(r.lower())
            if len(punti_uniti) >= 4:
                break
    punti = "\n".join(punti_uniti)

    metriche = {
        "secondi": round(secondi, 1),
        "token_generati": token_generati,
        "token_fonte": token_fonte,
        "tok_s": round(token_generati / secondi, 1) if secondi else 0.0,
    }
    return spiegazione, punti, materiale, metriche, stats, len(chunks)


def processa_sezione(
    nome: str, s: dict, modello: str, stato: dict, misura: bool, versione: str | None = None
) -> dict | None:
    fonte = _fonte(nome, s["pagina"], s["pagina_fine"])
    n_car = len(re.sub(r"\s+", " ", fonte).strip())
    sostituiti = sum(len(m.group(0)) for m in RE_BLOCCO.finditer(fonte))
    frazione_segnaposti = sostituiti / n_car if n_car else 0.0
    if n_car < MIN_FONTE:
        motivo = f"fonte troppo corta: {n_car} caratteri"
        print(f"sezione {s['sezione']} SALTATA: {motivo}")
        if not misura:
            stato["saltate"][str(s["sezione"])] = motivo
        return None

    try:
        if n_car <= MAX_FONTE:
            per_modello, materiale = _dividi(fonte)
            spiegazione, punti, metriche = riscrivi(modello, per_modello)
            stats_taglio = {}
            n_chunk = 1
        else:
            print(f"sezione {s['sezione']} troppo lunga ({n_car} caratteri), divisa in chunk")
            spiegazione, punti, materiale, metriche, stats_taglio, n_chunk = _riscrivi_chunked(modello, fonte)
    except Exception as e:
        motivo = f"errore nel modello: {type(e).__name__}: {e}"
        print(f"sezione {s['sezione']} SALTATA: {motivo}")
        if not misura:
            stato["saltate"][str(s["sezione"])] = motivo
        return None

    # Il controllo dei numeri confronta con la fonte completa, tabelle incluse:
    # se il modello cita una cifra della tabella non ha senso segnalarla come
    # inventata, perche' la tabella e' parte della sezione sorgente.
    allarmi = verifica_numeri(spiegazione + "\n" + punti, fonte)

    esito = {
        "titolo": s["titolo"],
        "caratteri_fonte": n_car,
        "numeri_non_verificati": len(allarmi),
        "chunk": n_chunk,
        "stats_taglio": stats_taglio,
        **metriche,
        "fatto": datetime.now().isoformat(timespec="seconds"),
    }
    if misura:
        print(
            f"sezione {s['sezione']}: {metriche['secondi']}s, "
            f"{metriche['tok_s']} tok/s, {esito['numeri_non_verificati']} allarmi"
        )
        return esito
    scrivi_nota(
        s, nome, spiegazione, punti, materiale, allarmi,
        versione or modello, n_car, metriche, frazione_segnaposti,
    )
    stato["sezioni"][str(s["sezione"])] = esito
    print(
        f"sezione {s['sezione']}: nota riscritta in {metriche['secondi']}s "
        f"({metriche['tok_s']} tok/s, {esito['numeri_non_verificati']} allarmi)"
    )
    return esito


def rapporto_dati(nome: str) -> dict:
    """Dict con tutti i numeri della copertura. Puo' essere usato dal collaudo
    per verificare l'invariante senza parsare il testo."""
    stato = _carica_stato(nome)
    sez = sezioni(nome)
    fatte = stato.get("sezioni", {})
    saltate = stato.get("saltate", {})
    totale = len(sez)
    if totale and len(fatte) + len(saltate) >= totale:
        stato["stadio"] = "sbobinato"

    caratteri_fonte = 0
    for s in sez:
        fonte = _fonte(nome, s["pagina"], s["pagina_fine"])
        caratteri_fonte += len(re.sub(r"\s+", " ", fonte).strip())

    caratteri_coperti = sum(v.get("caratteri_fonte", 0) for v in fatte.values())
    sezioni_divise = sum(1 for v in fatte.values() if v.get("chunk", 1) > 1)
    pezzi_totali = sum(v.get("chunk", 1) for v in fatte.values())

    livello_taglio = {"titoli": 0, "pagine": 0, "paragrafi": 0, "frasi": 0, "parole": 0}
    for v in fatte.values():
        s = v.get("stats_taglio") or {}
        for k in livello_taglio:
            livello_taglio[k] += s.get(k, 0)

    saltate_per_lunghezza = 0
    for motivo in saltate.values():
        if "troppo lunga" in motivo or "lunghezza" in motivo:
            saltate_per_lunghezza += 1

    return {
        "slug": nome,
        "stadio": stato.get("stadio", "sbobina"),
        "sezioni_totali": totale,
        "sezioni_riscritte": len(fatte),
        "sezioni_saltate": len(saltate),
        "saltate_dettaglio": saltate,
        "caratteri_fonte": caratteri_fonte,
        "caratteri_coperti": caratteri_coperti,
        "sezioni_divise": sezioni_divise,
        "pezzi_totali": pezzi_totali,
        "livello_taglio": livello_taglio,
        "saltate_per_lunghezza": saltate_per_lunghezza,
        "numeri_segnalati": sum(v.get("numeri_non_verificati", 0) for v in fatte.values()),
        "secondi": sum(v.get("secondi", 0) for v in fatte.values()),
        "modello": stato.get("modello") or MODELLO,
        "vram_mib": stato.get("vram_mib", "?"),
    }


def formatta_rapporto(dati: dict) -> str:
    """Versione leggibile del dict del rapporto."""
    righe = [
        "Rapporto di sbobina",
        "=" * 20,
        f"slug: {dati['slug']}",
        f"stadio: {dati['stadio']}",
        f"sezioni totali: {dati['sezioni_totali']}",
        f"sezioni riscritte: {dati['sezioni_riscritte']}",
        f"sezioni saltate: {dati['sezioni_saltate']}",
    ]
    for k, v in sorted(dati["saltate_dettaglio"].items(), key=lambda x: int(x[0])):
        righe.append(f"  - sezione {k}: {v}")
    righe += [
        f"caratteri fonte: {dati['caratteri_fonte']:,}",
        f"caratteri coperti: {dati['caratteri_coperti']:,}",
        f"sezioni divise: {dati['sezioni_divise']}",
        f"pezzi totali: {dati['pezzi_totali']}",
        "livello taglio:",
    ]
    for k, v in dati["livello_taglio"].items():
        righe.append(f"  - {k}: {v}")
    if dati["livello_taglio"].get("parole", 0) > 0:
        righe.append("  ⚠ attenzione: la divisione e' scesa fino alle parole")
    righe.append(f"saltate per lunghezza: {dati['saltate_per_lunghezza']}")
    if dati["saltate_per_lunghezza"] > 0:
        righe.append("  ⚠ ERRORE: ci sono sezioni saltate per lunghezza")
    righe += [
        f"numeri segnalati: {dati['numeri_segnalati']}",
        f"tempo impiegato: {dati['secondi']:.0f}s",
        f"modello: {dati['modello']}",
        f"vram durante il lavoro: {dati['vram_mib']} MiB",
    ]
    return "\n".join(righe)


def rapporto(nome: str) -> str:
    return formatta_rapporto(rapporto_dati(nome))


def lavora(
    slug: str,
    modello: str = MODELLO,
    sezione: int | None = None,
    tutte: bool = False,
    misura: bool = False,
) -> int:
    md = documenti.MARKDOWN / f"{slug}.md"
    if not md.exists():
        print(f"nessun markdown integrale per {slug}: serve prima la fase di estrazione")
        return 1
    sez = sezioni(slug)
    if not sez:
        print(f"nessuna nota di sezione per {slug} in {documenti.V30}")
        return 1

    stato = _carica_stato(slug)
    fatte = set(stato.get("sezioni", {}))
    saltate = set(stato.get("saltate", {}))
    if sezione is not None:
        da_fare = [s for s in sez if s["sezione"] == sezione]
        if not da_fare:
            print(f"sezione {sezione} inesistente (1-{len(sez)})")
            return 1
    elif tutte:
        da_fare = [s for s in sez if str(s["sezione"]) not in fatte | saltate]
    else:
        # una sola, la prima non ancora fatta: e' il modo sicuro di partire
        da_fare = [
            s for s in sez if str(s["sezione"]) not in fatte | saltate
        ][:1]
    if not da_fare:
        print(rapporto(slug))
        return 0

    versione = versione_modello(modello)
    print(f"modello: {versione}, {len(da_fare)} sezione/i da fare", flush=True)

    # il fisso dorme dopo tre ore di inerzia e questo e' il lavoro lungo per
    # cui il blocco esiste; la GPU si riserva col meccanismo di /gioco
    with energia.blocco("sbobina"), gpu_della_sbobina(modello):
        stato.setdefault("inizio", datetime.now().isoformat(timespec="seconds"))
        stato["modello"] = versione
        for s in da_fare:
            processa_sezione(slug, s, modello, stato, misura, versione)
            if not misura:
                # Salva dopo ogni sezione: se un lavoro di ore viene interrotto,
                # si riparte dall'ultima completata, non da capo.
                _salva_stato(slug, stato)
        if not misura:
            stato["vram_mib"] = energia.vram_usata()[0]
            _salva_stato(slug, stato)

    print()
    print(rapporto(slug))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="La sbobina: riscrive le sezioni come un professore")
    ap.add_argument("slug", help="documento gia' estratto (es. dsml)")
    ap.add_argument("--sezione", type=int, default=None, help="numero della sezione da riscrivere")
    ap.add_argument("--tutte", action="store_true", help="tutte le sezioni non ancora fatte")
    ap.add_argument("--modello", default=MODELLO, help=f"modello ollama (predefinito {MODELLO})")
    ap.add_argument("--misura", action="store_true", help="misura senza scrivere le note")
    args = ap.parse_args()
    return lavora(args.slug, args.modello, args.sezione, args.tutte, args.misura)


if __name__ == "__main__":
    sys.exit(main())
