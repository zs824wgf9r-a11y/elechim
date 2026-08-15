from __future__ import annotations

import argparse
import contextlib
import fcntl
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

import energia
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
DOCUMENTI = BASE / "documenti"
IN = DOCUMENTI / "in"
ELABORATI = DOCUMENTI / "elaborati"
MARKDOWN = BASE / "markdown"
STATO = BASE / "stato" / "documenti"
VAULT = Path.home() / "Obsidian"
V20 = VAULT / "20-Documenti"
V30 = VAULT / "30-Note"

WORD_RE = re.compile(r"<word ([^>]+)>([^<]*)</word>")

# Meno prosa di cosi' sotto un "titolo" in grande e non e' una sezione: e' una
# dedica, un frontespizio, un'etichetta. Il valore e' basso di proposito:
# scartare una sezione vera e' peggio che tenere una dedica.
SOGLIA_TESTO_SEZIONE = 80

# Densita' minima di cifre per considerare una riga a piu' colonne una tabella:
# la prosa a due colonne ha un solo vuoto ampio e densita' < 1%, una tabella ha
# piu' gap ed e' ricca di cifre.
SOGLIA_DENSITA_TABELLA = 0.10

# Sotto questa mediana di caratteri non-spazio per pagina il documento e'
# considerato una scansione o un PDF senza livello di testo.
SOGLIA_CARATTERI_PAGINA = 100

# --- formule: apici, pedici e recinti ------------------------------------
#
# Le soglie che seguono sono misurate sulle cinque pagine piu' dense di
# DSML.pdf (443, 145, 142, 67, 467) e su otto pagine di sola prosa, il
# 16 agosto 2026: gli istogrammi sono in RAPPORTO-formule.md.

# Un apice/pedice e' circa il 65-80% del corpo della sua base: sotto
# l'80% e' chiaramente piu' piccolo, sopra e' la stessa corsa tipografica
# (il maiuscoletto 'D'+'OCUMENTO' sta a ~0.80 e in baseline comune, quindi
# resta fuori per lo spostamento del centro, non per l'altezza).
SOGLIA_CORPO_SCRIPT = 0.80

# Spostamento del centro verticale dello script rispetto al centro della
# base, in frazioni dell'altezza della base. Ispettivamente sopra e sotto
# la linea di base i due cluster partono a ~0.15; i run ridotti sulla
# stessa baseline (unita', citazioni) stanno dentro +/-0.12.
SOGLIA_CENTRO = 0.16

# Distanza orizzontale base->script, in frazioni della maggiore delle due
# altezze. Il mino negativo ammette la sovrapposizione dei limiti di
# sommatoria, che stanno sopra/sotto il simbolo e rientrano nel suo ingombro.
GAP_SCRIPT_MIN = -0.9
GAP_SCRIPT_MAX = 0.7

# Due parole che differiscono di piu' di cosi' nella base (yMax, in
# frazioni dell'altezza dello script) non sono della stessa riga visiva:
# un apice si sposta di 0.3-0.6 altezze, la riga sotto sta a un interlinea
# (circa 1.1-1.5 altezze del corpo). Con 1.3 la riga successiva passava
# il filtro e produceva pedici fantasma.
SOGLIA_BASELINE_SCRIPT = 1.0

# Un riga visiva si spezza in frammenti (le colonne) quando il vuoto
# orizzontale supera questa frazione dell'altezza mediana della pagina.
SOGLIA_COLONNA = 2.2

# Le parole normali di una riga condividono la baseline entro questa
# frazione dell'altezza mediana.
TOL_RIGA_BASELINE = 0.45

SIMBOLI_MATH = frozenset(
    "=≠≤≥≈≅<>+±×·⋅÷−–∞∑∏∫√∂∇∈∉∀∃∪∩∅⊂⊃⊆⊇∝∼→←↔⇒⇐⊕⊗∧∨¬"
)
# L'apice dritto e il trattino ASCII NON entrano nell'insieme: nella prosa
# di DSML '-' compare 22 volte in otto pagine (parole composte) e '/'
# 3 volte (date), mentre '+' e' 24 volte nelle dense e 0 in prosa.
RE_NUMEQUAZIONE = re.compile(r"^[\[(][A-Za-z]?\d+(?:\.\d+)+[\])]$")

RE_NUMERO = re.compile(r"^\d+(\.\d+)*\.?\s+")


class DocumentoRifiutato(RuntimeError):
    """Il documento non ha livello di testo sufficiente per la corsia veloce."""


def _attr(attrs: str, nome: str) -> float:
    m = re.search(rf'{nome}="([\d.\-]+)"', attrs)
    return float(m.group(1)) if m else 0.0


def _comando(args: list[str], cwd: Path | None = None) -> str:
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"comando fallito: {' '.join(args)}\n{r.stderr}")
    return r.stdout


def slug(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "documento"


def pagine_totali(pdf: Path) -> int:
    out = _comando(["pdfinfo", str(pdf)])
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if not m:
        raise RuntimeError("pdfinfo non ha restituito il numero di pagine")
    return int(m.group(1))


def figure(pdf: Path) -> int:
    out = _comando(["pdfimages", "-list", str(pdf)])
    righe = [r for r in out.splitlines()[2:] if re.match(r"^\s*\d+", r)]
    return len(righe)


def metadati(pdf: Path) -> dict:
    out = _comando(["pdfinfo", str(pdf)])
    meta = {}
    for chiave in ("Title", "Author", "CreationDate"):
        m = re.search(rf"^{chiave}:\s*(.*)$", out, re.M)
        if m and m.group(1).strip():
            meta[chiave] = m.group(1).strip()
    return meta


def caratteri_pagina(pdf: Path) -> list[int]:
    """Caratteri non-spazio per pagina, usando un'unica chiamata pdftotext."""
    out = _comando(["pdftotext", "-layout", str(pdf), "-"])
    # `pdftotext` separa le pagine con \f; l'ultimo split puo' essere vuoto.
    pagine = out.rstrip("\f").split("\f") if out else [""]
    return [len(re.sub(r"\s", "", p)) for p in pagine]


def classifica(pdf: Path, pagine: int) -> dict:
    """Metriche semplici per scegliere la corsia e decidere se rifiutare."""
    cpp = caratteri_pagina(pdf)
    if len(cpp) < pagine:
        cpp.extend([0] * (pagine - len(cpp)))
    cpp = cpp[:pagine]
    totale = sum(cpp)
    mediana = sorted(cpp)[len(cpp) // 2] if cpp else 0
    media = totale / pagine if pagine else 0.0
    return {
        "pagine": pagine,
        "caratteri_totali": totale,
        "caratteri_per_pagina_media": media,
        "caratteri_per_pagina_mediana": mediana,
        "livello_testo": mediana >= SOGLIA_CARATTERI_PAGINA,
        "outline": len(voci_outline(pdf)) >= 3,
    }


def prosa_pagina(pdf: Path, n: int) -> str:
    out = _comando(["pdftotext", "-f", str(n), "-l", str(n), str(pdf), "-"])
    return out.replace("\f", "").strip()


def parole_bbox(pdf: Path, n: int) -> list[tuple[float, float, float, float, str]]:
    out = _comando(
        ["pdftotext", "-f", str(n), "-l", str(n), "-bbox", str(pdf), "-"]
    )
    parole = []
    for attrs, testo in WORD_RE.findall(out):
        parole.append(
            (
                _attr(attrs, "xMin"),
                _attr(attrs, "yMin"),
                _attr(attrs, "xMax"),
                _attr(attrs, "yMax"),
                html.unescape(testo),
            )
        )
    return parole


def righe_geometriche(parole: list[tuple]) -> list[list[tuple]]:
    if not parole:
        return []
    altezze = [w[3] - w[1] for w in parole]
    media = sum(altezze) / len(altezze)
    tol = max(0.5, media * 0.4)
    righe: list[list[tuple]] = []
    for w in sorted(parole, key=lambda p: (p[1], p[0])):
        if righe and abs(w[1] - righe[-1][-1][1]) <= tol:
            righe[-1].append(w)
        else:
            righe.append([w])
    for r in righe:
        r.sort(key=lambda p: p[0])
    return righe


def _stats_riga(parole: list[tuple]) -> tuple[list[float], float, int]:
    gap = [b[0] - a[2] for a, b in zip(parole, parole[1:])]
    testo = "".join(p[4] for p in parole)
    nongap = re.sub(r"\s", "", testo)
    cifre = sum(c.isdigit() or c in ".," for c in nongap)
    dens = cifre / len(nongap) if nongap else 0.0
    return gap, dens, len(nongap)


def _soglia_gap(righe: list[list[tuple]]) -> float:
    gap = [g for r in righe for a, b in zip(r, r[1:]) if (g := b[0] - a[2]) >= 0]
    if not gap:
        return 8.0
    gap.sort()
    return max(8.0, gap[len(gap) // 2] * 3)


def _e_tabella(parole: list[tuple], soglia: float) -> bool:
    gap, dens, _ = _stats_riga(parole)
    ampi = sum(1 for g in gap if g > soglia)
    # Una colonna di prosa ha un solo vuoto ampio e pochissime cifre;
    # una tabella ne ha piu' d'uno e le cifre sono dense.
    if ampi >= 2 and dens >= SOGLIA_DENSITA_TABELLA:
        return True
    if ampi >= 1 and dens >= 0.25 and len(parole) >= 2:
        return True
    return False


def _coda_numerica(riga: list[tuple], blocco: list[list[tuple]]) -> bool:
    """Riga spaiata di soli numeri, appena sotto una tabella e allineata con lei.

    Nei documenti veri e' il totale, oppure l'ultima riga rimasta incompleta.
    `_e_tabella` pretende due colonne e la lascerebbe fuori dal blocco: nel
    markdown integrale non si perde comunque, ma finirebbe in mezzo alla prosa
    invece che dentro il recinto verbatim, che e' l'unico posto dove i numeri
    di una tabella devono stare.
    """
    testi = [str(w[4]).strip() for w in riga if str(w[4]).strip()]
    if not testi or len(testi) > 2:
        return False
    if not all(re.fullmatch(r"[-+]?[\d.,]+%?", t) for t in testi):
        return False
    sinistra = min(w[0] for r in blocco for w in r)
    return abs(riga[0][0] - sinistra) <= 20.0


def blocchi_tabella(
    pdf: Path, n: int, parole: list[tuple] | None = None
) -> list[tuple[float, float, float, float]]:
    if parole is None:
        parole = parole_bbox(pdf, n)
    if not parole:
        return []
    righe = righe_geometriche(parole)
    soglia = _soglia_gap(righe)
    blocchi: list[list[list[tuple]]] = []
    corrente = None
    for r in righe:
        if _e_tabella(r, soglia):
            if corrente is None:
                corrente = [r]
            else:
                corrente.append(r)
        elif corrente is not None and _coda_numerica(r, corrente):
            corrente.append(r)
        else:
            if corrente is not None:
                blocchi.append(corrente)
                corrente = None
    if corrente is not None:
        blocchi.append(corrente)
    risultato = []
    for blocco in blocchi:
        xs = [w[0] for r in blocco for w in r]
        ys = [w[1] for r in blocco for w in r]
        xe = [w[2] for r in blocco for w in r]
        ye = [w[3] for r in blocco for w in r]
        risultato.append((min(xs), min(ys), max(xe), max(ye)))
    return risultato


def tabella_verbatim(pdf: Path, n: int, X: float, Y: float, W: float, H: float) -> str:
    out = _comando(
        [
            "pdftotext",
            "-f", str(n),
            "-l", str(n),
            "-x", str(int(X)),
            "-y", str(int(Y)),
            "-W", str(int(W - X)),
            "-H", str(int(H - Y)),
            "-layout",
            str(pdf),
            "-",
        ]
    )
    return out.replace("\f", "").strip()


def _mediana(xs: list[float]) -> float:
    s = sorted(xs)
    return s[len(s) // 2] if s else 0.0


def _marca_apici_pedici(parole: list[tuple]) -> dict[int, tuple[str, int]]:
    """Per ogni parola che e' un apice o un pedice: ('apice'|'pedice', indice base).

    Accoppiamento a coppie, non per righe: poppler spezza gli apici in blocchi
    propri (misurato: l'apice di un PDF sintetico finisce in un <block>
    separato dalla sua base), quindi nessun raggruppamento per righe di
    poppler e' affidabile. Qui una parola e' uno script della parola che la
    precede se: e' chiaramente piu' piccola, le e' adiacente in orizzontale
    (sovvrapposizione ammessa: limiti di sommatoria), sta sulla sua stessa
    riga visiva, e il suo centro e' spostato in alto (apice) o in basso
    (pedice) oltre SOGLIA_CENTRO. Un portatore sano di maiuscoletto ha
    baseline comune e centro quasi allineato: resta fuori.

    La base di uno script puo' essere a sua volta uno script (x_i^2):
    in quel caso basta l'altezza quasi uguale, il resto lo decide il centro.
    Se il rilevamento e' incerto la parola non si tocca: un apice mancato e'
    il comportamento di oggi, uno inventato e' un peggioramento.
    """
    if not parole:
        return {}
    marcature: dict[int, tuple[str, int]] = {}
    ordine = sorted(range(len(parole)), key=lambda i: parole[i][0])
    for pos, i in enumerate(ordine):
        b = parole[i]
        # virgole, punti e parentesi sono sempre piu' basse del loro vicino:
        # senza questo filtro ogni virgola diverrebbe un pedice.
        if not any(c.isalnum() for c in b[4]):
            continue
        hb = b[3] - b[1]
        if hb <= 0:
            continue
        cb = (b[1] + b[3]) / 2
        migliore: tuple[tuple[float, float], float, int] | None = None
        for j in ordine[:pos]:
            a = parole[j]
            ha = a[3] - a[1]
            if ha <= 0:
                continue
            if j in marcature:
                if hb > 1.05 * ha:
                    continue
            elif hb > SOGLIA_CORPO_SCRIPT * ha:
                continue
            gap = b[0] - a[2]
            m = max(ha, hb)
            if not (GAP_SCRIPT_MIN * m <= gap <= GAP_SCRIPT_MAX * m):
                continue
            if abs(a[3] - b[3]) > SOGLIA_BASELINE_SCRIPT * hb:
                continue
            ca = (a[1] + a[3]) / 2
            dc = (ca - cb) / ha
            chiave = (abs(a[3] - b[3]), gap)
            if migliore is None or chiave < migliore[0]:
                migliore = (chiave, dc, j)
        if migliore is None:
            continue
        dc = migliore[1]
        if dc >= SOGLIA_CENTRO:
            marcature[i] = ("apice", migliore[2])
        elif dc <= -SOGLIA_CENTRO:
            marcature[i] = ("pedice", migliore[2])
    return marcature


def _righe_frammenti(
    parole: list[tuple], marcature: dict[int, tuple[str, int]]
) -> tuple[list[list[int]], float]:
    """Righe visive (per baseline delle parole normali, script attaccati alla
    base) spezzate nei frammenti di colonna. Ritorna (frammenti, altezza mediana)."""
    hs = [w[3] - w[1] for w in parole if w[3] - w[1] > 0]
    med = max(_mediana(hs), 1.0)
    normali = sorted(
        (i for i in range(len(parole)) if i not in marcature),
        key=lambda i: parole[i][3],
    )
    righe: list[list[int]] = []
    for i in normali:
        if righe and abs(parole[i][3] - parole[righe[-1][0]][3]) <= TOL_RIGA_BASELINE * med:
            righe[-1].append(i)
        else:
            righe.append([i])
    for i, (_, base) in marcature.items():
        for r in righe:
            if base in r:
                r.append(i)
                break
    frammenti: list[list[int]] = []
    for r in righe:
        r.sort(key=lambda i: parole[i][0])
        corrente: list[int] = []
        for i in r:
            if corrente and parole[i][0] - parole[corrente[-1]][2] > SOGLIA_COLONNA * med:
                frammenti.append(corrente)
                corrente = [i]
            else:
                corrente.append(i)
        if corrente:
            frammenti.append(corrente)
    frammenti.sort(key=lambda f: (parole[f[0]][3], parole[f[0]][0]))
    return frammenti, med


def _segnali_frammento(
    idxs: list[int], parole: list[tuple], marcature: dict[int, tuple[str, int]]
) -> dict:
    testo = "".join(parole[i][4] for i in idxs)
    compatti = re.sub(r"\s", "", testo)
    return {
        "len": len(compatti),
        "math": sum(c in SIMBOLI_MATH for c in compatti),
        "nonalfa": sum(1 for c in compatti if not c.isalpha()) / len(compatti) if compatti else 0.0,
        # le parole normali, non gli script: 'x' + apice '2' e' un pezzo solo
        "parole": sum(1 for i in idxs if i not in marcature),
        "num_fine": bool(idxs) and RE_NUMEQUAZIONE.match(parole[idxs[-1]][4].strip()) is not None,
    }


def _e_formula(s: dict) -> bool:
    """Il riconoscimento sbaglia per difetto: una formula non marcata e' il
    comportamento di oggi, un paragrafo di prosa recintato e' il difetto dei
    falsi positivi che le tabelle hanno appena finito di pagare."""
    if s["len"] < 3:
        return False
    if s["math"] >= 2 and s["parole"] <= 6:
        return True
    if s["math"] >= 1 and s["parole"] <= 3 and s["len"] <= 42 and s["nonalfa"] >= 0.4:
        return True
    if s["math"] >= 2 and s["parole"] <= 9 and s["nonalfa"] >= 0.50:
        return True
    if s["num_fine"] and s["math"] >= 1:
        return True
    return False


def _testo_frammento(
    idxs: list[int], parole: list[tuple], marcature: dict[int, tuple[str, int]], med: float
) -> str:
    """Il testo del frammento con gli apici e i pedici nella forma base^apice
    e base_pedice. Script consecutivi dello stesso tipo si fondono in un
    unico marcatore."""
    pezzi: list[str] = []
    tipo_prec: str | None = None
    for k, i in enumerate(idxs):
        testo = parole[i][4]
        if i in marcature:
            tipo = marcature[i][0]
            simbolo = "^" if tipo == "apice" else "_"
            if tipo == tipo_prec:
                pezzi.append(testo)
            else:
                if pezzi and pezzi[-1].endswith(" "):
                    pezzi[-1] = pezzi[-1].rstrip(" ")
                pezzi.append(simbolo + testo)
            tipo_prec = tipo
        else:
            if k > 0 and parole[i][0] - parole[idxs[k - 1]][2] > 0.2 * med and pezzi and not pezzi[-1].endswith(" "):
                pezzi.append(" ")
            pezzi.append(testo)
            tipo_prec = None
    return "".join(pezzi)


def recinti_formula(
    pdf: Path, n: int, tabelle: list[tuple], parole: list[tuple] | None = None
) -> tuple[list[str], int, int]:
    """Recinti formula della pagina: testo pronto per il markdown, apici e
    pedici ricostruiti (solo quelli caduti dentro un recinto: nel testo
    semplice non si tocca nulla, perche' la segmentazione di pdftotext e di
    -bbox divergono proprio sulle pagine matematiche - misurato, 10-46% di
    allineamento)."""
    if parole is None:
        parole = parole_bbox(pdf, n)
    if len(parole) < 2:
        return [], 0, 0
    if not any(c in SIMBOLI_MATH for w in parole for c in w[4]):
        # pagina senza simboli: nessuna regola puo' scattare, e saltare
        # l'accoppiamento (quadratico nelle parole piccole) mantiene il
        # collaudo e il libro veloci.
        return [], 0, 0
    marcature = _marca_apici_pedici(parole)
    frammenti, med = _righe_frammenti(parole, marcature)

    def interseca(f: list[int]) -> bool:
        fx0 = min(parole[i][0] for i in f)
        fy0 = min(parole[i][1] for i in f)
        fx1 = max(parole[i][2] for i in f)
        fy1 = max(parole[i][3] for i in f)
        return any(fx0 < t[2] and fx1 > t[0] and fy0 < t[3] and fy1 > t[1] for t in tabelle)

    recinti: list[str] = []
    corrente: list[str] = []
    apici = pedici = 0
    for f in frammenti:
        if _e_formula(_segnali_frammento(f, parole, marcature)) and not interseca(f):
            corrente.append(_testo_frammento(f, parole, marcature, med))
        elif corrente:
            recinti.append("\n".join(corrente))
            corrente = []
    if corrente:
        recinti.append("\n".join(corrente))
    for r in recinti:
        apici += r.count("^")
        pedici += r.count("_")
    return recinti, apici, pedici


def testo_pagina(pdf: Path, n: int, blocchi: list[tuple], parole: list[tuple] | None = None) -> str:
    parti = []
    prosa = prosa_pagina(pdf, n)
    if prosa:
        parti.append(prosa)
    for i, (X, Y, W, H) in enumerate(blocchi, 1):
        t = tabella_verbatim(pdf, n, X, Y, W, H)
        if t:
            parti.append(f"<!-- tabella pag {n} blocco {i} -->")
            parti.append("```")
            parti.append(t)
            parti.append("```")
    recinti, _, _ = recinti_formula(pdf, n, blocchi, parole)
    for i, testo in enumerate(recinti, 1):
        parti.append(f"<!-- formula pag {n} blocco {i} -->")
        parti.append("```")
        parti.append(testo)
        parti.append("```")
    return "\n\n".join(parti)


def genera_markdown(pdf: Path, nome: str, pagine: int, fino_a: int | None = None) -> int:
    md = MARKDOWN / f"{nome}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    esistenti = set()
    if md.exists():
        esistenti = {int(x) for x in re.findall(r"<!-- pag (\d+) -->", md.read_text(encoding="utf-8"))}
    ultima = max(esistenti) if esistenti else 0
    if not md.exists():
        md.write_text(
            f"<!-- documento: {nome} -->\n<!-- sorgente: {pdf} -->\n",
            encoding="utf-8",
        )
    with open(md, "a", encoding="utf-8") as f:
        for n in range(ultima + 1, pagine + 1):
            if fino_a is not None and n > fino_a:
                break
            parole = parole_bbox(pdf, n)
            blocco = f"\n\n<!-- pag {n} -->\n\n{testo_pagina(pdf, n, blocchi_tabella(pdf, n, parole), parole)}"
            os.write(f.fileno(), blocco.encode("utf-8"))
            f.flush()
    letto = {int(x) for x in re.findall(r"<!-- pag (\d+) -->", md.read_text(encoding="utf-8"))}
    return max(letto) if letto else 0


def sezioni_xml(pdf: Path, pagine: int) -> tuple[list[tuple], list[int], float]:
    """Righe del PDF con la dimensione del font, gli indici dei titoli e il corpo.

    Le righe si raggruppano per **baseline** (top + height) con la stessa
    tolleranza di `righe_geometriche`: il maiuscoletto tipografico e' un
    elemento grande e uno piu' piccolo con `top` diverso di pochi pixel ma
    baseline comune, e raggruppare per `top` esatto lo spezza ('P' + 'REFACE').
    """
    # pdftohtml tratta l'ultimo argomento come *base* del nome e ci appende
    # ".xml": passandogli "x.html" scrive "x.html.xml". Rileggere il nome che
    # gli si e' passato da' FileNotFoundError **dopo** che il comando e' uscito
    # con 0, quindi il guasto sembra un problema di lettura e non di nome.
    with tempfile.TemporaryDirectory() as cartella:
        base = Path(cartella) / "pagine"
        _comando(["pdftohtml", "-xml", "-i", "-f", "1", "-l", str(pagine), str(pdf), str(base)])
        root = ET.fromstring(
            base.with_suffix(".xml").read_text(encoding="utf-8", errors="replace")
        )
    fontsize = {fs.get("id"): float(fs.get("size", "0")) for fs in root.iter("fontspec")}
    righe: list[tuple[int, int, float, str]] = []
    for page in root.iter("page"):
        num = int(page.get("number"))
        elementi = []
        for t in page.iter("text"):
            # `t.text` NON basta: pdftohtml avvolge il grassetto in un <b>
            # figlio, quindi per un titolo in grassetto `t.text` e' None e la
            # riga sparisce come se fosse vuota. Il risultato e' zero sezioni
            # trovate su un documento che ne ha, senza un solo errore nei log.
            testo = "".join(t.itertext()).strip()
            if not testo:
                continue
            top = float(t.get("top", "0"))
            height = float(t.get("height", "0") or "0")
            elementi.append(
                (
                    top + height,  # baseline
                    top,
                    float(t.get("left", "0")),
                    float(t.get("width", "0") or "0"),
                    fontsize.get(t.get("font"), 0.0),
                    testo,
                )
            )
        if not elementi:
            continue
        altezze = [e[0] - e[1] for e in elementi]
        media = sum(altezze) / len(altezze)
        tol = max(0.5, media * 0.4)
        elementi.sort(key=lambda e: (e[0], e[2]))
        gruppi: list[list[tuple]] = [[elementi[0]]]
        for e in elementi[1:]:
            if abs(e[0] - gruppi[-1][-1][0]) <= tol:
                gruppi[-1].append(e)
            else:
                gruppi.append([e])
        for g in gruppi:
            g.sort(key=lambda e: e[2])
            size = max(e[4] for e in g)
            testo = g[0][5]
            for prec, e in zip(g, g[1:]):
                # I pezzi di uno stesso run tipografico sono adiacenti: il
                # maiuscoletto e' 'P'+'REFACE' con gap ~0, non 'P REFACE'.
                gap = e[2] - (prec[2] + prec[3])
                testo += ("" if gap <= 1.5 else " ") + e[5]
            righe.append((num, min(e[1] for e in g), size, testo))
    pesi: dict[float, int] = {}
    for _, _, size, testo in righe:
        if testo:
            pesi[size] = pesi.get(size, 0) + len(testo)
    body = max(pesi, key=pesi.get) if pesi else 0.0
    soglia = body * 1.25
    titoli = [i for i, r in enumerate(righe) if r[2] >= soglia and len(r[3]) > 1]
    righe.sort(key=lambda r: (r[0], r[1]))
    titoli.sort(key=lambda i: (righe[i][0], righe[i][1]))
    return righe, titoli, body


def voci_outline(pdf: Path) -> list[dict]:
    """L'indice incorporato dal PDF: titolo, livello e pagina di ogni voce.

    E' la struttura che l'editore ha dichiarato: titoli esatti, gerarchia
    gia' annidata, nessuna dedica. Un indice con meno di 3 voci non e' una
    struttura, e' un caso: si torna alle euristiche.
    """
    lettore = PdfReader(str(pdf))
    voci: list[dict] = []

    def cammina(items: list, livello: int) -> None:
        for it in items:
            if isinstance(it, list):
                cammina(it, livello + 1)
                continue
            try:
                pagina = lettore.get_destination_page_number(it) + 1
            except Exception:
                continue  # destinazione irrisolvibile: la voce non esiste per noi
            titolo = " ".join((it.title or "").split())
            if titolo:
                voci.append({"titolo": titolo, "livello": livello, "pagina": pagina})

    cammina(lettore.outline, 1)
    return voci


def _conchiudi_pagine(sez: list[dict], pagine: int) -> None:
    """Il confine di una sezione: dalla sua pagina alla pagina della successiva."""
    for i, s in enumerate(sez):
        successiva = sez[i + 1]["pagina"] - 1 if i + 1 < len(sez) else pagine
        s["pagina_fine"] = max(s["pagina"], successiva)


def sezioni_font_size(pdf: Path, pagine: int) -> dict:
    """Ripiego per i PDF senza indice incorporato: euristiche sul corpo dei font.

    Dediche e frontespizi sono scritti in grande come i titoli veri: si
    riconoscono per quanta prosa ci sta sotto, e si contano nel rapporto
    invece di sparire in silenzio. L'integrale non si tocca mai.
    """
    righe, indici, body = sezioni_xml(pdf, pagine)
    if not indici:
        return {"tipo": "nessuna-struttura", "titolo_documento": None, "sezioni": [], "body": body, "scartate": 0}
    sizes = sorted({righe[i][2] for i in indici}, reverse=True)
    primo = righe[indici[0]]
    titolo_doc = primo[3] if primo[2] == sizes[0] and primo[0] == 1 else None
    if titolo_doc:
        indici = indici[1:]
    soglia = body * 1.25
    tenute = []
    scartate = 0
    for k, i in enumerate(indici):
        fine = indici[k + 1] if k + 1 < len(indici) else len(righe)
        sotto = sum(len(r[3]) for r in righe[i + 1 : fine] if r[2] < soglia)
        if sotto < SOGLIA_TESTO_SEZIONE:
            scartate += 1
            continue
        tenute.append(i)
    sizes = sorted({righe[i][2] for i in tenute}, reverse=True)
    livello = {s: i + 1 for i, s in enumerate(sizes)}
    sez = [
        {"titolo": righe[i][3], "livello": livello[righe[i][2]], "pagina": righe[i][0]}
        for i in tenute
    ]
    _conchiudi_pagine(sez, pagine)
    return {"tipo": "font-size", "titolo_documento": titolo_doc, "sezioni": sez, "body": body, "scartate": scartate}


def struttura(pdf: Path, pagine: int) -> dict:
    voci = voci_outline(pdf)
    if len(voci) >= 3:
        _conchiudi_pagine(voci, pagine)
        return {"tipo": "outline", "titolo_documento": None, "sezioni": voci, "body": None, "scartate": 0}
    return sezioni_font_size(pdf, pagine)


def _estratto(md: str, pagina: int, maxc: int = 600) -> str:
    m = re.search(rf"<!-- pag {pagina} -->\n+(.*)", md, re.S)
    if not m:
        return ""
    testo = re.sub(r"```.*?```", "", m.group(1), flags=re.S)
    testo = re.sub(r"<!--.*?-->", "", testo, flags=re.S)
    testo = re.sub(r"\s+", " ", testo).strip()
    if len(testo) <= maxc:
        return testo
    pezzo = testo[:maxc]
    cut = pezzo.rfind(" ")
    if cut > 0:
        pezzo = pezzo[:cut]
    return pezzo.rstrip(" ,;:-") + "…"


def _etichetta(stem: str) -> str:
    """Il nome breve del documento, dal file com'e' stato chiamato: DSML.pdf
    e' l'acronimo che usa il proprietario, e il nome visibile della nota e' il titolo
    che in Obsidian si vede."""
    s = re.sub(r"[-_]+", " ", stem).strip()
    return s if s.isupper() else s.title()


def _titolo_pulito(titolo: str) -> str:
    t = re.sub(r"[/#^\[\]|]", " ", titolo)
    return re.sub(r"\s+", " ", t).strip()


def _numerazione(sez: list[dict]) -> list[str | None]:
    """Il numero di sezione per il nome della nota.

    Percorso outline: l'indice incorporato non porta numeri (l'editore li
    lascia in stampa), quindi si derivano dalla gerarchia: i capitoli con
    figli contano 1..N, le sottosezioni cap.sub, le sottosottosezioni
    cap.sub.sub.     E l'unico modo per tenere disambiguati i sette "Exercises"
    e i sette "Introduction" del libro. Se la voce e' gia' numerata non si
    raddoppia.
    """
    numeri: list[str | None] = [None] * len(sez)
    cap = sub = subsub = 0
    for i, s in enumerate(sez):
        if RE_NUMERO.match(s["titolo"]):
            continue
        if s["livello"] == 1:
            ha_figli = i + 1 < len(sez) and sez[i + 1]["livello"] > 1
            cap = cap + 1 if ha_figli else 0
            sub = subsub = 0
            numeri[i] = str(cap) if cap else None
        elif s["livello"] == 2:
            sub += 1
            subsub = 0
            numeri[i] = f"{cap}.{sub}" if cap else None
        else:
            subsub += 1
            numeri[i] = f"{cap}.{sub}.{subsub}" if cap and sub else None
    return numeri


def nomi_note(etichetta: str, sez: list[dict]) -> list[str]:
    """Nomi delle note atomiche: 'DSML 5.2 Linear regression'.

    Il progressivo di pipeline non si vede: in Obsidian il nome del file e'
    il titolo. I doppioni restano impossibili: se il nome esiste gia', si
    numerano in coda.
    """
    nomi: list[str] = []
    usati: set[str] = set()
    for s, n in zip(sez, _numerazione(sez)):
        base = _titolo_pulito(" ".join(x for x in (etichetta, n, s["titolo"]) if x))
        nome = base
        k = 2
        while nome in usati:
            nome = f"{base} ({k})"
            k += 1
        usati.add(nome)
        nomi.append(nome)
    return nomi


def genera_note(
    pdf: Path,
    nome: str,
    pagina: dict,
    struttura_doc: dict,
    meta: dict,
    tabelle: int,
    fig: int,
    estrazione_completa: bool,
) -> tuple[int, int]:
    dir_doc = V20 / nome
    dir_doc.mkdir(parents=True, exist_ok=True)
    V30.mkdir(parents=True, exist_ok=True)
    # Le note di una lavorazione precedente hanno nomi che questa non
    # riscrivera': resterebbero orfane con il loro link di ritorno. Le note
    # della pipeline sono di proprieta' della pipeline, si rifanno da zero.
    for f in _note_del_documento(nome):
        f.unlink()
    md = MARKDOWN / f"{nome}.md"
    md_testo = md.read_text(encoding="utf-8") if md.exists() else ""
    integrale = md.as_uri()
    oggi = datetime.now().strftime("%Y-%m-%d %H:%M")
    titolo_doc = struttura_doc.get("titolo_documento") or meta.get("Title") or nome
    sez = struttura_doc.get("sezioni", [])
    struttura_ok = bool(sez)
    etichetta = _etichetta(pdf.stem)
    nomi = nomi_note(etichetta, sez) if sez else []

    indice = dir_doc / f"{nome}.md"
    parti = [
        "---",
        "tipo: documento",
        f"slug: {nome}",
        f"titolo: {json.dumps(titolo_doc, ensure_ascii=False)}",
        f"autore: {json.dumps(meta.get('Author', ''), ensure_ascii=False)}",
        f"data: {json.dumps(meta.get('CreationDate', ''), ensure_ascii=False)}",
        f"pagine: {pagina}",
        f"sezioni: {len(sez)}",
        f"tabelle: {tabelle}",
        f"figure: {fig}",
        f"elaborato: {oggi}",
        f"struttura: {struttura_doc.get('tipo')}",
        "tags:",
        "  - documento",
        f"  - {nome}",
        "---",
        "",
        f"# {titolo_doc}",
        "",
        "Documento elaborato in locale dalla corsia veloce (pdftotext).",
        "",
        "## Metadati",
        "",
        f"- pagine: {pagina}",
        f"- sezioni riconosciute: {len(sez)}",
        f"- tabelle conservate verbatim: {tabelle}",
        f"- figure trovate: {fig}",
        f"- [markdown integrale]({integrale})",
        "",
    ]
    if struttura_ok:
        parti.append("## Sommario")
        parti.append("")
        # I capitoli come intestazioni, le sottosezioni come elenco annidato:
        # la gerarchia c'e' gia' nell'indice, non serve ricostruirla.
        for s, nome_sez in zip(sez, nomi):
            link = f"[[{nome_sez}]]"
            if s["livello"] == 1:
                parti.append(f"## {link}")
            else:
                rientro = "  " * (min(s["livello"], 4) - 2)
                parti.append(f"{rientro}- {link} (pag {s['pagina']})")
        parti.append("")
    else:
        parti.append("Nessuna struttura di sezioni riconosciuta con affidabilita' dal font del PDF.")
        parti.append("")
    indice.write_text("\n".join(parti), encoding="utf-8")

    for i, (s, nome_sez) in enumerate(zip(sez, nomi), 1):
        nota = V30 / f"{nome_sez}.md"
        estr = _estratto(md_testo, s["pagina"]) if estrazione_completa else ""
        titolo = s["titolo"]
        # alias per la ricerca: il titolo nudo e quello senza numerazione
        aliases = [titolo]
        m = RE_NUMERO.match(titolo)
        if m:
            senza = titolo[m.end() :].strip()
            if senza:
                aliases.append(senza)
        p = [
            "---",
            "tipo: nota-sezione",
            f'documento: "[[{nome}]]"',
            f"sezione: {i}",
            f"titolo: {json.dumps(titolo, ensure_ascii=False)}",
            f"pagina: {s['pagina']}",
            f"pagina_fine: {s['pagina_fine']}",
            "tags:",
            "  - sezione",
            f"  - {nome}",
            "aliases:",
            *[f"  - {json.dumps(a, ensure_ascii=False)}" for a in aliases],
            "---",
            "",
            f"# {titolo}",
            "",
            f"Documento: [[{nome}]]",
            f"[integrale]({integrale})",
            f"Pagina: {s['pagina']}" + (
                f"-{s['pagina_fine']}" if s["pagina_fine"] > s["pagina"] else ""
            ),
            "",
        ]
        if estr:
            # Le doppie quadre della notazione matematica, in Obsidian,
            # sarebbero wikilink verso note inesistenti: si escapano.
            estr = estr.replace("[[", "\\[\\[").replace("]]", "\\]\\]")
            p.append(f"> {estr}")
            p.append("")
        nota.write_text("\n".join(p), encoding="utf-8")

    return 1 + len(sez), len(sez)


def _note_del_documento(nome: str) -> list[Path]:
    """Le note atomiche di un documento, riconosciute dal frontmatter:
    con i nomi leggibili non si puo' piu' cercarle per prefisso."""
    if not V30.exists():
        return []
    return [
        f
        for f in V30.glob("*.md")
        if f'documento: "[[{nome}]]"' in f.read_text(encoding="utf-8")[:400]
    ]


def _wikilink_risolti(nome: str) -> tuple[int, int]:
    """I link delle note di <nome> risolti contro il vault INTERO.

    Contarli contro 20-Documenti/<nome> + 30-Note e' il difetto che ha
    prodotto i famosi sei rotti: le atomiche di un altro documento
    linkano il loro indice, che sta fuori da quell'insieme, e venivano
    contati rotti nel rapporto di chi non c'entrava.
    """
    # il lookbehind salta le quadre escapatate: notazione matematica, non link
    pattern = re.compile(r"(?<!\\)\[\[([^\]|#]+?)(?<!\\)\]\]")
    noti = {f.stem for f in VAULT.rglob("*.md")}
    file = list((V20 / nome).glob("*.md")) if (V20 / nome).exists() else []
    file += _note_del_documento(nome)
    totali = 0
    risolti = 0
    for f in file:
        for m in pattern.finditer(f.read_text(encoding="utf-8")):
            totali += 1
            if m.group(1).strip() in noti:
                risolti += 1
    return totali, risolti


def _caratteri(md: str) -> int:
    testo = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    testo = re.sub(r"\s+", "", testo)
    return len(testo)


def _conteggi_formule(md: str) -> tuple[int, int, int]:
    """Recinti formula, apici e pedici ricostruiti, contati dal markdown.

    Come le tabelle (contate dal file, non dal processo): cosi' il rapporto
    e' vero anche dopo un'interruzione e una ripresa. I marcatore ^ e _
    esistono solo dentro i recinti: nel testo estratto di DSML sono zero
    (misurato sull'intero libro), quindi il conteggio e' esatto salvo un
    accento circonflesso letterale dentro una formula, caso dichiarato.
    """
    formule = len(re.findall(r"<!-- formula pag", md))
    apici = pedici = 0
    for corpo in re.findall(r"<!-- formula pag [^>]* -->\s*```\s*(.*?)```", md, re.S):
        apici += corpo.count("^")
        pedici += corpo.count("_")
    return formule, apici, pedici


def rapporto(
    nome: str,
    pdf: Path,
    pagine: int,
    pagine_fatte: int,
    caratteri: int,
    struttura_doc: dict,
    tabelle: int,
    fig: int,
    note: tuple[int, int],
    stadio: str,
    classif: dict | None = None,
    formule: tuple[int, int, int] = (0, 0, 0),
) -> dict:
    tot_links, risolti = _wikilink_risolti(nome)
    sez = struttura_doc.get("sezioni", [])
    d = {
        "slug": nome,
        "sorgente": str(pdf),
        "pagine_totali": pagine,
        "pagine_processate": pagine_fatte,
        "caratteri_estratti": caratteri,
        "sezioni_trovate": len(sez),
        "sezioni_con_nota": len(sez) if stadio == "fatto" else 0,
        "tabelle_conservate": tabelle,
        "formule_marcate": formule[0],
        "apici_ricostruiti": formule[1],
        "pedici_ricostruiti": formule[2],
        "figure_trovate": fig,
        "note_indice": note[0] - note[1],
        "note_atomiche": note[1],
        "wikilink_totali": tot_links,
        "wikilink_risolti": risolti,
        "sezioni_scartate": struttura_doc.get("scartate", 0),
        "struttura": struttura_doc.get("tipo"),
        "stadio": stadio,
    }
    if classif:
        d["corsia"] = "veloce" if classif["livello_testo"] else "scansione"
        d["caratteri_per_pagina_mediana"] = classif["caratteri_per_pagina_mediana"]
    return d


def formatta_rapporto(r: dict) -> str:
    righe = [
        "Rapporto di copertura",
        "=" * 20,
        f"slug: {r['slug']}",
        f"sorgente: {r['sorgente']}",
        f"stadio: {r['stadio']}",
        f"pagine: {r['pagine_processate']}/{r['pagine_totali']}",
        f"caratteri estratti: {r['caratteri_estratti']}",
        f"sezioni trovate: {r['sezioni_trovate']}",
        f"sezioni scartate: {r.get('sezioni_scartate', 0)}",
        f"sezioni con nota: {r['sezioni_con_nota']}",
        f"tabelle conservate: {r['tabelle_conservate']}",
        f"formule marcate: {r.get('formule_marcate', 0)}",
        f"apici ricostruiti: {r.get('apici_ricostruiti', 0)}",
        f"pedici ricostruiti: {r.get('pedici_ricostruiti', 0)}",
        f"figure trovate: {r['figure_trovate']}",
        f"note: indice {r['note_indice']}, atomiche {r['note_atomiche']}",
        f"wikilink: {r['wikilink_risolti']}/{r['wikilink_totali']} risolti",
        f"struttura: {r['struttura']}",
        f"corsia: {r.get('corsia', 'n/d')}",
        f"caratteri per pagina (mediana): {r.get('caratteri_per_pagina_mediana', 'n/d')}",
    ]
    return "\n".join(righe)


def _carica_stato(nome: str) -> dict:
    f = STATO / f"{nome}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {}


def _salva_stato(nome: str, stato: dict) -> None:
    STATO.mkdir(parents=True, exist_ok=True)
    f = STATO / f"{nome}.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(stato, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def processa(pdf: Path | str, fino_a_pagina: int | None = None) -> dict:
    pdf = Path(pdf)
    if not pdf.exists():
        raise FileNotFoundError(pdf)
    # `.stem` e non `.name`: con il nome intero il punto dell'estensione
    # diventa un trattino e ogni documento si chiama "...-pdf".
    nome = slug(pdf.stem)
    stato = _carica_stato(nome)
    if stato.get("stadio") == "fatto":
        # Gia' elaborato: il lavoro non si rifa', ma il file deve comunque
        # uscire dalla coda. Lasciarlo qui manda in ciclo il path unit di
        # systemd: il servizio parte, non trova niente da fare, esce, e la
        # condizione `*.pdf` e' ancora vera. Cinque avvii in un secondo e
        # l'unita' finisce in `start-limit-hit`, con la coda bloccata.
        # Successo davvero il 15 agosto 2026, alla prima prova in esercizio.
        if pdf.resolve().parent == IN.resolve():
            ELABORATI.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf), str(ELABORATI / pdf.name))
        return stato.get("rapporto", {"slug": nome})

    in_coda = pdf.resolve().parent == IN.resolve()
    if "sorgente" not in stato:
        stato = {"slug": nome, "sorgente": str(pdf), "inizio": datetime.now().isoformat()}
    pagine = stato.get("pagine_totali") or pagine_totali(pdf)
    stato["pagine_totali"] = pagine

    classif = classifica(pdf, pagine)
    if classif["caratteri_per_pagina_mediana"] < SOGLIA_CARATTERI_PAGINA:
        ragione = (
            f"PDF senza livello di testo o testo insufficiente per la corsia veloce: "
            f"{classif['caratteri_totali']} caratteri su {pagine} pagine "
            f"(mediana {classif['caratteri_per_pagina_mediana']}/pagina)"
        )
        # Stessa cartella `documenti/falliti/` usata da `_macina` per i file
        # che arrivano da `documenti/in/`.
        _scarta(pdf, pdf.parent.parent / "falliti", ragione)
        raise DocumentoRifiutato(ragione)

    pagine_fatte = genera_markdown(pdf, nome, pagine, fino_a_pagina)
    md = (MARKDOWN / f"{nome}.md").read_text(encoding="utf-8")
    caratteri = _caratteri(md)
    tabelle = len(re.findall(r"<!-- tabella pag", md))
    formule = _conteggi_formule(md)

    stato.update({"pagine_fatte": pagine_fatte, "stadio": "estratto"})
    _salva_stato(nome, stato)

    if fino_a_pagina is not None and pagine_fatte < pagine:
        return rapporto(
            nome, pdf, pagine, pagine_fatte, caratteri,
            {"tipo": "parziale", "titolo_documento": None, "sezioni": []},
            tabelle, figure(pdf), (0, 0), "estratto-parziale", classif, formule,
        )

    strutt = struttura(pdf, pagine)
    fig = figure(pdf)
    note = genera_note(
        pdf, nome, pagine, strutt, metadati(pdf), tabelle, fig,
        estrazione_completa=True,
    )
    stato["stadio"] = "fatto"
    stato["fine"] = datetime.now().isoformat()
    r = rapporto(nome, pdf, pagine, pagine_fatte, caratteri, strutt, tabelle, fig, note, "fatto", classif, formule)
    stato["rapporto"] = r
    _salva_stato(nome, stato)
    if in_coda:
        ELABORATI.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pdf), str(ELABORATI / pdf.name))
    return r


@contextlib.contextmanager
def _coda_esclusiva():
    """Una sola istanza per volta sulla coda.

    Il path unit sorveglia `documenti/in/*.pdf` e il servizio stesso svuota
    quella cartella spostando i file che finisce: la condizione cambia proprio
    mentre il lavoro e' in corso, e systemd fa ripartire il servizio addosso a
    quello vivo. Successo il 15 agosto 2026: due processi nello stesso secondo,
    il secondo ha fatto `glob()` su una lista che il primo stava svuotando e si
    e' ritrovato il PDF sparito a meta' elaborazione, dentro `metadati()`:

        RuntimeError: comando fallito: pdfinfo .../documenti/in/prova-due-colonne.pdf
        I/O Error: Couldn't open file ... No such file or directory

    `energia.blocco` non serve a questo: scrive il proprio PID sopra quello di
    chi c'era, perche' il suo mestiere e' tenere sveglio il fisso, non escludere.
    Qui serve mutua esclusione vera, ed e' `flock` non bloccante: chi arriva
    secondo esce **senza errore**, perche' non e' un guasto. Il lavoro non va
    perso: chi sta gia' lavorando rilegge la cartella prima di chiudere, e se
    dopo restano PDF il path unit riscatta da solo.
    """
    STATO.mkdir(parents=True, exist_ok=True)
    f = open(STATO / ".coda.lock", "w")  # noqa: SIM115 - deve restare aperto quanto il lock
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        f.close()  # chiudere rilascia il flock, anche se il processo muore male


def main() -> int:
    ap = argparse.ArgumentParser(description="Corsia veloce fase 4: PDF -> markdown + note Obsidian")
    ap.add_argument("destinazione", help="file PDF o cartella della coda")
    ap.add_argument("--fino-a", type=int, default=None, help="fermati dopo questa pagina (per test)")
    args = ap.parse_args()
    dest = Path(args.destinazione)
    with _coda_esclusiva() as mio:
        if not mio:
            print("coda gia' in lavorazione da un'altra istanza, esco")
            return 0
        # Il fisso si sospende da solo dopo tre ore di inerzia, e macinare la
        # coda non e' attivita' che lui veda: senza questo blocco un documento
        # lungo si ritrova la macchina addormentata a meta'. Il lavoro
        # riprenderebbe al risveglio - e' ripartibile - ma resterebbe fermo in
        # silenzio finche' qualcuno non tocca la tastiera. Il marcatore contiene
        # il PID e sparisce da solo: un processo morto male non lascia il fisso
        # sveglio per sempre.
        with energia.blocco("documenti"):
            _macina(dest, args.fino_a)
    return 0


def _scarta(f: Path, falliti: Path, ragione: str) -> None:
    """Toglie dalla coda un documento che non si e' potuto macinare.

    Il file puo' non essere piu' li': `processa` lo sposta in `elaborati/`
    appena finito, quindi un'eccezione sollevata *dopo* quello spostamento
    trovava un `shutil.move` su un percorso inesistente. Quel secondo
    FileNotFoundError partiva da dentro il gestore, non lo prendeva nessuno, e
    il servizio usciva 1: cioe' la coda si fermava esattamente per il guasto che
    questo gestore esiste per evitare.
    """
    if not f.exists():
        return
    falliti.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(f), str(falliti / f.name))
    except OSError as e:
        print(f"  impossibile spostare {f.name} in falliti: {e}")
        return
    # La ragione scritta accanto al file: senza, fra un mese in `falliti/` c'e'
    # un PDF e nessun modo di sapere perche' ci sia finito.
    (falliti / f"{f.name}.ragione.txt").write_text(
        f"{datetime.now().isoformat()}\n{ragione}\n", encoding="utf-8"
    )
    print(f"  spostato in {falliti}")


def _macina(dest: Path, fino_a: int | None) -> None:
    if not dest.is_dir():
        print(formatta_rapporto(processa(dest, fino_a)))
        return

    falliti = dest.parent / "falliti"
    # Si rilegge la cartella a ogni giro invece di fidarsi di una `glob()`
    # sola: un documento da 533 pagine dura minuti, e i PDF arrivati nel
    # frattempo - da Syncthing o da Telegram - vanno macinati in questo giro,
    # non al prossimo scatto del path unit. `visti` impedisce il ciclo infinito
    # su un file che resta in `in/` perche' non si e' potuto spostare.
    visti: set[Path] = set()
    while True:
        restano = [f for f in sorted(dest.glob("*.pdf")) if f not in visti]
        if not restano:
            break
        for f in restano:
            visti.add(f)
            # Un documento che esplode non deve restare in coda: il path unit
            # lo rivedrebbe, ripartirebbe, esploderebbe di nuovo, e la coda
            # sarebbe ferma per sempre su un file solo. Si mette da parte e si
            # va avanti con gli altri - la regola e' che `in/` si svuota
            # sempre, qualunque cosa succeda.
            try:
                print(formatta_rapporto(processa(f, fino_a)))
            except Exception as e:  # noqa: BLE001 - un documento in meno, non una coda ferma
                ragione = f"{type(e).__name__}: {e}"
                print(f"FALLITO {f.name}: {ragione}")
                _scarta(f, falliti, ragione)
            print()


if __name__ == "__main__":
    raise SystemExit(main())
