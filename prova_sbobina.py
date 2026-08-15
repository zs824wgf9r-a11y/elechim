"""Collaudo della sbobina sul PDF sintetico.

Tutto gira in /tmp/opencode: i percorsi di documenti (vault, markdown, stato)
vengono ridiretti prima di usare sbobina, che li legge dal modulo. Il vault
vero non viene toccato, e il PDF sintetico e' generato dalle stesse funzioni
di prova_documenti (testo inventato, quindi leggibile quanto serve).

Cosa dimostra: la nota esce nella forma giusta, le tabelle restano verbatim
fuori dal modello, il controllo dei numeri conta quello che deve, lo stato
avanza per sezione e un secondo giro riprende da dove era rimasto.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = Path("/tmp/opencode/sbobina/collaudo")
if BASE.exists():
    shutil.rmtree(BASE)
BASE.mkdir(parents=True)

import documenti

documenti.VAULT = BASE / "vault"
documenti.V20 = documenti.VAULT / "20-Documenti"
documenti.V30 = documenti.VAULT / "30-Note"
documenti.MARKDOWN = BASE / "markdown"
documenti.STATO = BASE / "stato" / "documenti"

import prova_documenti

SLUG = "prova-sbobina"
PDF_SRC = BASE / "prova-sbobina-src.pdf"
PDF = BASE / f"{SLUG}.pdf"
prova_documenti.PS = BASE / "generato.ps"
prova_documenti.PDF = PDF_SRC

import energia
import sbobina

MODELLO = sys.argv[1] if len(sys.argv) > 1 else sbobina.MODELLO
IDX_TABELLA = 4  # "2.1 Tabella dei dati": pagina col blocco delle CIFRE


def assert_nota_della_tabella() -> None:
    note = {s["sezione"]: s for s in sbobina.sezioni(SLUG)}
    s = note[IDX_TABELLA]
    testo = s["nota"].read_text(encoding="utf-8")
    fm = sbobina._frontmatter(testo)

    # il frontmatter originario non si perde
    for campo in ("tipo", "documento", "sezione", "titolo", "pagina", "pagina_fine", "aliases"):
        assert campo in fm, f"frontmatter senza {campo}"
    assert fm["documento"] == f'"[[{SLUG}]]"', fm["documento"]
    # ... e i campi della sbobina ci sono
    for campo in ("sbobinato", "modello", "caratteri_fonte", "numeri_non_verificati"):
        assert campo in fm, f"frontmatter senza {campo}"

    # la forma della nota
    for sezione in ("# ", "## In breve", "## La spiegazione", "## Materiale originale", "## Fonte"):
        assert sezione in testo, f"manca {sezione}"
    assert "[integrale](" in testo and f"[[{SLUG}]]" in testo, "fonte senza rimandi"
    # l'estratto-segnalibro di prima e' sparito
    assert not re.search(r"^> ", testo, re.M), "restato il blockquote dell'estratto"
    # il ragionamento del modello non deve finire nella nota
    assert "<think>" not in testo and "</think>" not in testo, "il pensiero e' finito nella nota"

    # le CIFRE stanno nel recinto verbatim: la copia autoritativa c'e' sempre
    fonte = sbobina._fonte(SLUG, s["pagina"], s["pagina_fine"])
    per_modello, _ = sbobina._dividi(fonte)
    # il recinto e' isolato davvero: al modello va il segnaposto, non il blocco
    assert sbobina.SEGNAPOSTO_TABELLA in per_modello, "il recinto non e' stato sostituito"
    assert "<!-- tabella" not in per_modello, "il marcatore di tabella e' andato al modello"
    materiale = testo.split("## Materiale originale", 1)[1].split("## Fonte", 1)[0]
    for c in prova_documenti.CIFRE:
        assert re.search(rf"\b{re.escape(c)}\b", materiale), f"cifra mancante dal verbatim: {c}"

    # Quanto il modello cita i numeri della tabella nella spiegazione: la
    # prosa di pagina di documenti.py contiene gia' i numeri (il pdftotext
    # nudo legge tutta la pagina, recinti a parte), quindi una parte puo'
    # tornare. Si MISURA, non si asserisce.
    spiegazione = testo.split("## La spiegazione", 1)[1].split("## Materiale originale", 1)[0]
    citate = [c for c in prova_documenti.CIFRE if re.search(rf"\b{re.escape(c)}\b", spiegazione)]
    print(f"    (misura: {len(citate)}/{len(prova_documenti.CIFRE)} cifre di tabella citate"
          f" nella spiegazione, via gemello di prosa)")

    # il controllo dei numeri torna, ricalcolato per conto suo; la fonte
    # completa (tabelle incluse) e' il riferimento, per non segnalare falsi
    # allarmi su cifre che il modello cita dalla tabella.
    breve = testo.split("## In breve", 1)[1].split("## La spiegazione", 1)[0]
    ricalcolo = sbobina.verifica_numeri(spiegazione + breve, fonte)
    assert len(ricalcolo) == int(fm["numeri_non_verificati"]), (
        f"contatore sballato: frontmatter {fm['numeri_non_verificati']}, ricalcolo {len(ricalcolo)}"
    )
    if ricalcolo:
        assert re.search(rf"⚠ {len(ricalcolo)} numeri non verificati", testo), "allarme mancante in Fonte"
    print(f"OK nota della sezione {IDX_TABELLA}: verbatim, numeri, forma.")


def assert_copertura_rapporto() -> None:
    """L'invariante di copertura deve essere un numero, non una promessa."""
    dati = sbobina.rapporto_dati(SLUG)
    assert dati["saltate_per_lunghezza"] == 0, (
        f"sezioni saltate per lunghezza: {dati['saltate_per_lunghezza']}"
    )
    assert dati["caratteri_coperti"] == dati["caratteri_fonte"], (
        f"copertura non totale: coperti {dati['caratteri_coperti']} "
        f"su {dati['caratteri_fonte']} caratteri fonte"
    )
    print("OK rapporto di copertura: copertura totale, nessuna saltata per lunghezza.")


def assert_verifica_numeri() -> None:
    """Il controllore deve prendere il 180 diventato 150 e lasciare passare
    le riscritture legittime di separatore e zeri."""
    v = sbobina.verifica_numeri
    assert v("il valore e' 150", "il valore e' 180") == ["150"], "non prende il numero cambiato"
    assert v("48,5 per cento", "48.5") == [], "falso allarme sul separatore decimale"
    assert v("0.5 di quota", "0,5") == [], "falso allarme sulla virgola"
    assert v("05 unita'", "5") == [], "falso allarme sullo zero iniziale"
    assert v("il 3.14 e il 2", "pi greco 3.14") == ["2"], "il numero inventato deve suonare"
    assert v("due volte", "2") == [], "le parole non sono numeri, non suonano"
    # le cifre contenute nelle tabelle verbatim sono parte della fonte
    assert v("la quota e' 12345", "```\n| 12345 |\n```") == [], "numero di tabella segnalato per errore"
    print("OK controllo dei numeri: prende i cambiati, tace sui legittimi.")


def assert_suddivisione() -> None:
    """Una sezione lunga viene divisa in chunk coerenti senza spezzare i
    recinti di tabella."""
    paragrafi = []
    for i in range(12):
        frase = f"Questo e' il paragrafo numero {i} della sezione lunga. " * 20
        paragrafi.append(frase.strip())
    tabella = "<!-- tabella pag 1 blocco 1 -->\n```\n| valore |\n| 12345 |\n| 67890 |\n```"
    testo = "\n\n".join(paragrafi[:6]) + "\n\n" + tabella + "\n\n" + "\n\n".join(paragrafi[6:])

    # Il budget si passa esplicito e piccolo: legarlo a `MAX_FONTE` rendeva il
    # collaudo dipendente da una costante, e infatti si e' rotto appena il
    # budget e' diventato derivato (17.190 invece di 9.000: lo stesso testo non
    # si divideva piu' e il test falliva senza che niente fosse peggiorato).
    budget = 4000
    chunks, _ = sbobina._chunk_fonte(testo, budget)
    assert len(chunks) > 1, "la sezione lunga non e' stata divisa"
    for c in chunks:
        # un recinto ripristinato puo' superare il tetto, ma non di molto
        assert len(c) <= int(budget * 1.5), f"chunk troppo lungo: {len(c)}"
        # se un chunk apre un recinto, deve anche chiuderlo
        if "<!-- tabella" in c:
            assert "```" in c, "recinto di tabella spezzato"
    unito = re.sub(r"\s+", " ", "\n\n".join(chunks))
    originale = re.sub(r"\s+", " ", testo)
    assert unito == originale, "la suddivisione ha perso pezzi"
    print("OK suddivisione: chunk coerenti, recinti intatti.")


def assert_budget_derivato() -> None:
    """Il budget si ricava dal contesto del modello, non da una costante.

    Erano due numeri scelti a mano (`MAX_FONTE` e `num_ctx`) che dovevano
    restare coerenti senza che niente lo garantisse: col primo piu' grande del
    secondo, ollama taglia la fonte **in silenzio** e la nota sembra perfetta.
    """
    piccolo = sbobina.budget_caratteri(8192)
    grande = sbobina.budget_caratteri(32768)
    assert grande > piccolo * 3, f"il budget non segue il contesto: {piccolo} -> {grande}"
    # quello che parte deve stare nel contesto, con il margine
    token = piccolo / sbobina.CAR_PER_TOKEN + sbobina.TOKEN_PROMPT + sbobina.MAX_TOKEN_SPIEGAZIONE
    assert token < 8192, f"il budget non sta in num_ctx: {token:.0f} token"
    print(f"OK budget: derivato dal contesto ({piccolo:,} caratteri a 8k, {grande:,} a 32k).")


def assert_nessuna_dimensione_impossibile() -> None:
    """Non esiste "troppo grande": qualunque sezione si divide e finisce.

    E' il requisito posto dal proprietario — *senza tralasciare nulla* — e la
    ragione per cui `MAX_FONTE` non e' piu' una soglia di scarto ma un innesco
    di divisione. Prima 46 sezioni su 223 di `dsml`, cioe' meta' del libro in
    caratteri, venivano saltate perche' troppo lunghe.
    """
    # una sezione mostruosa e senza nessun confine naturale: niente titoli,
    # niente ancore, niente righe vuote. Deve cadere fino alle parole e finire.
    mostro = ("parola " * 30_000).strip()
    pezzi, _ = sbobina._chunk_fonte(mostro, sbobina.MAX_FONTE)
    assert len(pezzi) > 1, "la sezione mostruosa non e' stata divisa"
    for p in pezzi:
        per_modello, _ = sbobina._dividi(p)
        assert len(per_modello) <= sbobina.MAX_FONTE, (
            f"un pezzo sfora il budget: {len(per_modello)} > {sbobina.MAX_FONTE}"
        )
    # copertura: nessuna parola persa per strada
    assert " ".join(pezzi).split() == mostro.split(), "la divisione ha perso testo"

    # e con i confini naturali si taglia li', non a caso
    con_titoli = "\n\n".join(f"# Titolo {i}\n\n" + ("testo lungo. " * 900) for i in range(6))
    pezzi, _ = sbobina._chunk_fonte(con_titoli, sbobina.MAX_FONTE)
    assert len(pezzi) > 1
    assert all(p.lstrip().startswith("#") for p in pezzi), (
        "con i titoli disponibili la divisione ha tagliato altrove"
    )
    print(f"OK nessuna dimensione impossibile: {len(mostro):,} caratteri divisi e coperti.")


def main() -> int:
    assert_verifica_numeri()
    assert_suddivisione()
    assert_budget_derivato()
    assert_nessuna_dimensione_impossibile()
    print("generazione del PDF sintetico...")
    prova_documenti.genera_ps()
    prova_documenti.genera_pdf_outline(PDF_SRC, PDF, prova_documenti.OUTLINE)
    r = documenti.processa(PDF)
    assert r["struttura"] == "outline" and r["note_atomiche"] == 6, r

    sez = sbobina.sezioni(SLUG)
    assert len(sez) == 6, f"sezioni trovate: {len(sez)}"
    assert [s["sezione"] for s in sez] == [1, 2, 3, 4, 5, 6]

    # 1. il giro completo, da "riga di comando": una sezione sola, quella con
    #    la tabella, che e' il caso che interessa
    assert sbobina.lavora(SLUG, MODELLO, sezione=IDX_TABELLA) == 0
    assert_nota_della_tabella()

    stato = sbobina._carica_stato(SLUG)
    assert set(stato["sezioni"]) == {str(IDX_TABELLA)}, stato["sezioni"]
    assert stato["modello"] and stato["vram_mib"], "metriche mancanti nello stato"

    # 2. ripresa: la prossima da fare e' la 1, non di nuovo la 4; le altre
    #    finiscono nello stesso giro di GPU
    with energia.blocco("sbobina"), sbobina.gpu_della_sbobina(MODELLO):
        versione = sbobina.versione_modello(MODELLO)
        stato = sbobina._carica_stato(SLUG)
        fatte = set(stato["sezioni"]) | set(stato["saltate"])
        restanti = [s for s in sez if str(s["sezione"]) not in fatte]
        assert restanti and restanti[0]["sezione"] == 1, "la ripresa non parte dalla sezione 1"
        for s in restanti:
            sbobina.processa_sezione(SLUG, s, MODELLO, stato, False, versione)
        sbobina._salva_stato(SLUG, stato)

    stato = sbobina._carica_stato(SLUG)
    fatte = set(stato["sezioni"])
    saltate = set(stato["saltate"])
    assert len(fatte) + len(saltate) == 6, f"fatte {sorted(fatte)}, saltate {sorted(saltate)}"
    assert IDX_TABELLA in {int(x) for x in fatte}, "la sezione della tabella non risulta fatta"

    assert_copertura_rapporto()

    righe = sbobina.rapporto(SLUG)
    print(righe)
    assert "sezioni riscritte:" in righe and "modello:" in righe

    # 3. le due note non riscritte di proposito non esistono: ogni sezione
    #    processata ha la sua nota sostituita, ogni saltata e' contata
    for i in fatte:
        nota = next(s for s in sez if s["sezione"] == int(i))["nota"]
        testo = nota.read_text(encoding="utf-8")
        assert "## La spiegazione" in testo, f"la sezione {i} non e' stata riscritta"
        assert not re.search(r"^> ", testo, re.M), f"la sezione {i} ha ancora l'estratto"

    usati, totali = energia.vram_usata()
    print(f"VRAM a fine collaudo: {usati} MiB su {totali}")
    print("COLLAUDO VERDE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
