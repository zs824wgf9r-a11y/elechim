from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import documenti
from documenti import (
    ELABORATI,
    IN,
    MARKDOWN,
    STATO,
    V20,
    V30,
    formatta_rapporto,
    processa,
    struttura,
)

# Due PDF, stesso contenuto: uno senza indice (collaudo del ripiego font-size,
# con titolo a maiuscoletto e pagina di dedica) e uno con l'indice incorporato
# (collaudo del percorso primario). Un difetto trovato una volta e non messo
# nel collaudo torna.
SLUG = "prova-due-colonne"
PDF = IN / f"{SLUG}.pdf"
SLUG_OUT = "prova-outline"
PDF_OUT = IN / f"{SLUG_OUT}.pdf"
PS = Path("/tmp/prova-due-colonne.ps")

COLONNA_SX = 60
COLONNA_DX = 340
LINEE_SX = 30
LINEE_DX = 26

TITOLO_DOC = "DOCUMENTO SINTETICO"
DEDICA = "A CHI LEGGE"
DEDICA_PICCOLA = "pagina di dedica, non una sezione"


def avvolgi(testo: str, maxcar: int) -> list[str]:
    parole = testo.split()
    righe: list[str] = []
    corrente = ""
    for p in parole:
        if corrente and len(corrente) + 1 + len(p) > maxcar:
            righe.append(corrente)
            corrente = p
        else:
            corrente = f"{corrente} {p}".strip()
    if corrente:
        righe.append(corrente)
    return righe


def frasi_sezione(prefix: str, n: int) -> list[str]:
    return [
        f"{prefix} frase di collaudo numero {i}: il testo e' noto a priori e la verita' "
        f"di riferimento e' questa stessa stringa scritta in fase di generazione."
        for i in range(1, n + 1)
    ]


FRASI_S1 = frasi_sezione("PRIMA SEZIONE", 18)
FRASI_S2 = frasi_sezione("SECONDA SEZIONE", 24)
FRASI_S3 = frasi_sezione("TERZA SEZIONE", 18)

CIFRE = [
    "1250", "48.5", "3.14", "7.25", "901",
    "62.75", "13.6", "8.42", "550", "27.3",
    "99.1", "4.08", "610", "31.9", "17.45",
    "76.2", "5.9", "240", "88.4", "12.7",
    "56.1", "6.3", "330", "21.8", "44.9",
]


def pagina_ps(fonti: list[tuple[str, str, float, int, int, str]]) -> list[str]:
    righe: list[str] = ["%%Page", "save"]
    corrente = None
    for nome_font, font, size, x, y, testo in fonti:
        if corrente != (nome_font, size):
            righe.append(f"/{nome_font} findfont {size} scalefont setfont")
            corrente = (nome_font, size)
        testo_ps = testo.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        righe.append(f"{x} {y} moveto ({testo_ps}) show")
    righe.append("restore")
    righe.append("showpage")
    return righe


def blocca_frasi(frasi: list[str], per_pagina: int) -> list[list[list[str]]]:
    pagine = []
    for i in range(0, len(frasi), per_pagina):
        gruppo = frasi[i : i + per_pagina]
        meta = len(gruppo) // 2
        pagine.append([gruppo[:meta], gruppo[meta:]])
    return pagine


def righe_prosa(meta: list[list[str]], y_top: int) -> list[tuple]:
    righe = []
    for k, colonna in enumerate((COLONNA_SX, COLONNA_DX)):
        yy = y_top
        for frasi in meta[k]:
            for l in avvolgi(frasi, LINEE_SX if k == 0 else LINEE_DX):
                righe.append(("Helvetica", "Helvetica", 10, colonna, yy, l))
                yy -= 14
    return righe


def genera_ps() -> None:
    righe = ["%!PS"]
    pagine = []

    s1 = blocca_frasi(FRASI_S1, 6)
    s2 = blocca_frasi(FRASI_S2, 6)
    s3 = blocca_frasi(FRASI_S3, 6)

    # Titolo a maiuscoletto tipografico: iniziale grande e resto piu'
    # piccolo, BASELINE comune e top diversi di pochi pixel. Sono due
    # elementi <text> distinti per pdftohtml: raggruppare per top esatto
    # li spezza ('D' + 'OCUMENTO SINTETICO'), per baseline li unisce.
    p1 = [
        ("Helvetica-Bold", "Helvetica", 30, COLONNA_SX, 800, "D"),
        ("Helvetica-Bold", "Helvetica", 24, COLONNA_SX + 21.7, 800, "OCUMENTO SINTETICO"),
        ("Helvetica-Bold", "Helvetica", 16, COLONNA_SX, 760, "1. Prima sezione"),
    ]
    p1.extend(righe_prosa(s1[0], 730))
    pagine.append(p1)
    pagine.extend(righe_prosa(meta, 760) for meta in s1[1:])

    # Pagina di dedica: testo in grande come un titolo, quasi niente sotto.
    # Il ripiego font-size deve scartarla e contarla, non farla sparire.
    pagine.append(
        [
            ("Helvetica-Bold", "Helvetica", 20, 200, 700, DEDICA),
            ("Helvetica", "Helvetica", 10, COLONNA_SX, 650, DEDICA_PICCOLA),
        ]
    )

    p5 = [("Helvetica-Bold", "Helvetica", 16, COLONNA_SX, 800, "2. Seconda sezione")]
    y = 770
    # Tutte le cifre di CIFRE, non un numero fisso di righe: con `range(6)` la
    # venticinquesima non veniva mai disegnata e il collaudo la cercava
    # comunque, accusando l'estrattore di aver perso un numero che nel PDF non
    # c'era. L'ultima riga resta spaiata di proposito: una riga incompleta e'
    # il caso che rompe i rilevatori di colonne.
    for cifre_riga in range((len(CIFRE) + 3) // 4):
        for k, x in enumerate([60, 150, 240, 330]):
            i = cifre_riga * 4 + k
            if i >= len(CIFRE):
                break
            p5.append(("Helvetica", "Helvetica", 10, x, y, CIFRE[i]))
        y -= 14
    p5.extend(righe_prosa(s2[0], y - 10))
    pagine.append(p5)
    pagine.extend(righe_prosa(meta, 760) for meta in s2[1:])

    p9 = [("Helvetica-Bold", "Helvetica", 16, COLONNA_SX, 800, "3. Terza sezione")]
    p9.extend(righe_prosa(s3[0], 760))
    pagine.append(p9)
    pagine.extend(righe_prosa(meta, 760) for meta in s3[1:])

    n_pag = 0
    for p in pagine:
        n_pag += 1
        righe.extend(pagina_ps(p))
    assert n_pag == 11, f"attese 11 pagine, generata {n_pag}"
    PS.write_text("\n".join(righe) + "\n", encoding="utf-8")
    r = subprocess.run(["ps2pdf", str(PS), str(PDF)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ps2pdf fallito:\n{r.stderr}")


# L'indice incorporato del PDF di collaudo: tre livelli, capitoli con e senza
# figli, come quello di DSML. Le pagine sono in base 0.
OUTLINE = [
    (0, "Prima sezione", None),
    (1, "Sottosezione alpha", "Prima sezione"),
    (4, "Seconda sezione", None),
    (4, "Tabella dei dati", "Seconda sezione"),
    (5, "Nota sulla tabella", "Tabella dei dati"),
    (8, "Terza sezione", None),
]


def genera_pdf_outline(src: Path, dst: Path, voci: list[tuple[int, str, str | None]] | None = None) -> None:
    from pypdf import PdfWriter

    w = PdfWriter(clone_from=src)
    genitori: dict[str, object] = {}
    for pagina, titolo, padre in voci or OUTLINE:
        genitori[titolo] = w.add_outline_item(titolo, pagina, parent=genitori.get(padre))
    with open(dst, "wb") as f:
        w.write(f)


def normalizza(testo: str) -> str:
    testo = re.sub(r"<!--.*?-->", " ", testo, flags=re.S)
    # ps2pdf converte l'apostrofo dritto in quello tipografico, e il testo va a
    # capo a meta' frase perche' il PDF e' a due colonne. Nessuna delle due
    # cose riguarda cio' che questa prova deve dimostrare - che le parole
    # escano contigue e nell'ordine giusto, cioe' che le colonne non si siano
    # mescolate - quindi si normalizzano su entrambi i lati del confronto.
    testo = testo.replace("’", "'").replace("‘", "'")
    testo = testo.replace("“", '"').replace("”", '"')
    testo = re.sub(r"\s+", " ", testo)
    return testo


def assert_sentenze(md: str) -> None:
    norm = normalizza(md)
    pos = -1
    tutte = []
    for s in (FRASI_S1, FRASI_S2, FRASI_S3):
        tutte.extend(s)
    for frase in tutte:
        idx = norm.find(normalizza(frase))
        assert idx >= 0, f"frase non trovata: {frase[:50]}"
        assert idx > pos, f"frase fuori ordine: {frase[:50]}"
        pos = idx


def assert_cifre(md: str) -> None:
    # Righe vuote tollerate attorno al recinto: metterle e' markdown corretto,
    # e il collaudo non deve imporre una formattazione che non sta provando.
    blocchi = re.findall(
        r"<!-- tabella pag (\d+) blocco (\d+) -->\s*```\s*(.*?)```", md, re.S
    )
    assert blocchi, "nessun blocco tabella verbatim trovato"
    testo_tabella = "\n".join(b[2] for b in blocchi)
    for c in CIFRE:
        assert re.search(rf"\b{re.escape(c)}\b", testo_tabella), f"cifra mancante: {c}"


def assert_ancore(md: str, attese: set[int]) -> None:
    presenti = {int(x) for x in re.findall(r"<!-- pag (\d+) -->", md)}
    assert presenti == attese, f"ancore: attese {sorted(attese)}, presenti {sorted(presenti)}"


def assert_note(slug: str) -> None:
    indice = V20 / slug / f"{slug}.md"
    assert indice.exists(), f"manca nota indice: {indice}"
    pattern = re.compile(r"(?<!\\)\[\[([^\]|#]+?)(?<!\\)\]\]")
    link = pattern.findall(indice.read_text(encoding="utf-8"))
    assert link, "nessun wikilink nell'indice"
    for l in link:
        stem = l.strip()
        found = (V20 / slug / f"{stem}.md").exists() or (V30 / f"{stem}.md").exists()
        assert found, f"wikilink non risolto: [[{stem}]]"
    atomiche = documenti._note_del_documento(slug)
    assert len(atomiche) == len(link), f"note atomiche {len(atomiche)} != wikilink {len(link)}"
    for a in atomiche:
        contenuto = a.read_text(encoding="utf-8")
        assert f"[[{slug}]]" in contenuto, f"nota senza ritorno all'indice: {a.name}"
        assert "aliases:" in contenuto, f"nota senza aliases: {a.name}"


def pulisci_vault() -> None:
    for slug in (SLUG, SLUG_OUT):
        d = V20 / slug
        if d.exists():
            shutil.rmtree(d)
        for f in documenti._note_del_documento(slug):
            f.unlink()
        for f in (MARKDOWN / f"{slug}.md", STATO / f"{slug}.json"):
            if f.exists():
                f.unlink()
        for f in (IN / f"{slug}.pdf", ELABORATI / f"{slug}.pdf", Path(f"{slug}.pdf")):
            if f.exists():
                f.unlink()
    if PS.exists():
        PS.unlink()


def test_percorso_fontsize() -> dict:
    print("percorso font-size (PDF senza indice)...")
    r = processa(PDF)
    assert r["struttura"] == "font-size", r
    assert r["sezioni_trovate"] == 3, r
    # la dedica e' scartata e CONTATA, non sparita
    assert r["sezioni_scartate"] == 1, r
    assert r["tabelle_conservate"] == 1, r
    assert r["wikilink_totali"] == r["wikilink_risolti"], r
    md = (MARKDOWN / f"{SLUG}.md").read_text(encoding="utf-8")
    assert_ancore(md, set(range(1, 12)))
    assert_sentenze(md)
    assert_cifre(md)
    assert_note(SLUG)
    # il maiuscoletto e' una riga sola, con la sua iniziale
    indice = (V20 / SLUG / f"{SLUG}.md").read_text(encoding="utf-8")
    assert f"titolo: \"{TITOLO_DOC}\"" in indice, "titolo documento mangiato dal maiuscoletto"
    nomi = [f.stem for f in documenti._note_del_documento(SLUG)]
    assert "Prova Due Colonne 1. Prima sezione" in nomi, nomi
    assert not any(DEDICA in n for n in nomi), nomi
    print(formatta_rapporto(r))
    print("OK ripiego: maiuscoletto unito, dedica scartata e contata, 3 sezioni.")
    return r


def test_percorso_outline() -> dict:
    print("percorso outline (PDF con indice incorporato)...")
    r = processa(PDF_OUT)
    assert r["struttura"] == "outline", r
    assert r["sezioni_trovate"] == 6, r
    assert r["sezioni_scartate"] == 0, r
    assert r["wikilink_totali"] == r["wikilink_risolti"], r
    assert r["note_atomiche"] == 6, r
    nomi = {f.stem for f in documenti._note_del_documento(SLUG_OUT)}
    attesi = {
        "Prova Outline 1 Prima sezione",
        "Prova Outline 1.1 Sottosezione alpha",
        "Prova Outline 2 Seconda sezione",
        "Prova Outline 2.1 Tabella dei dati",
        "Prova Outline 2.1.1 Nota sulla tabella",
        "Prova Outline Terza sezione",
    }
    assert nomi == attesi, sorted(nomi ^ attesi)
    indice = (V20 / SLUG_OUT / f"{SLUG_OUT}.md").read_text(encoding="utf-8")
    # sommario annidato: capitoli come intestazioni, sottosezioni a elenco
    assert "## [[Prova Outline 1 Prima sezione]]" in indice
    assert "- [[Prova Outline 1.1 Sottosezione alpha]] (pag 2)" in indice
    assert "  - [[Prova Outline 2.1.1 Nota sulla tabella]] (pag 6)" in indice
    assert_note(SLUG_OUT)
    print(formatta_rapporto(r))
    print("OK outline: 6 voci, numerazione derivata, sommario annidato.")
    return r


def test_poche_voci() -> None:
    print("indice troppo povero: si torna al ripiego...")
    pdf_povero = Path("/tmp/prova-poche-voci.pdf")
    genera_pdf_outline(PDF, pdf_povero, [(0, "Solo una voce", None), (4, "E un'altra", None)])
    s = struttura(pdf_povero, documenti.pagine_totali(pdf_povero))
    assert s["tipo"] == "font-size", s
    assert s["sezioni"], s
    pdf_povero.unlink()
    print("OK: due voci non sono una struttura, ripiego attivo.")


def test_idempotenza() -> None:
    print("rilancio sullo stesso file...")
    dest = ELABORATI / PDF.name
    assert dest.exists(), "il PDF non e' stato spostato in elaborati"
    n_atomiche = len(documenti._note_del_documento(SLUG))
    r_rip = processa(dest)
    assert r_rip["stadio"] == "fatto", r_rip
    assert len(documenti._note_del_documento(SLUG)) == n_atomiche
    print("OK rilancio: note non duplicate.")


def test_interruzione() -> None:
    print("interruzione a meta'...")
    r1 = processa(PDF, fino_a_pagina=4)
    assert r1["stadio"] == "estratto-parziale"
    assert r1["pagine_processate"] == 4
    md1 = (MARKDOWN / f"{SLUG}.md").read_text(encoding="utf-8")
    assert_ancore(md1, {1, 2, 3, 4})
    assert not (V20 / SLUG).exists(), "note non ancora attese dopo il taglio"
    r2 = processa(PDF)
    assert r2["stadio"] == "fatto", r2
    md2 = (MARKDOWN / f"{SLUG}.md").read_text(encoding="utf-8")
    assert_ancore(md2, set(range(1, 12)))
    assert md2.count("<!-- pag ") == 11


def main() -> None:
    pulisci_vault()
    print("generazione PDF sintetici...")
    genera_ps()
    genera_pdf_outline(PDF, PDF_OUT)
    assert PDF.exists() and PDF_OUT.exists()

    test_percorso_fontsize()
    test_idempotenza()
    test_percorso_outline()
    test_poche_voci()

    pulisci_vault()
    print("collaudo interruzione/ripresa...")
    genera_ps()
    test_interruzione()
    assert len(documenti._note_del_documento(SLUG)) == 3
    print("OK ripresa: ha completato da dove era, senza ricominciare.")

    # Il vault si lascia PULITO: le note di collaudo dimenticate in giro sono
    # gli orfani che un giorno sono finiti nel rapporto di un altro documento
    # come "sei wikilink rotti" che rotti non erano.
    pulisci_vault()
    assert not documenti._note_del_documento(SLUG) and not documenti._note_del_documento(SLUG_OUT)
    print("TUTTO VERDE")


if __name__ == "__main__":
    main()
