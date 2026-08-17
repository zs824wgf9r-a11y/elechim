#!/usr/bin/env python3
"""Misura il tasso di attribuzione sbagliata nelle osservazioni gia' prodotte.

Per ogni osservazione estrae la citazione (testo tra virgolette), la cerca nei
messaggi della conversazione di origine e stabilisce meccanicamente se viene da
[user] o [assistant]. Le osservazioni senza citazione chiara vengono cercate
per intero. Il criterio e' dichiarato nel rapporto.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVIO = BASE / "archivio"
OUT = BASE / "stato" / "prova-estrazione-lingua"

# Espressioni regolari per estrarre le citazioni dalle osservazioni.
RE_CITAZIONI = re.compile(r'"([^"]+)"')
RE_PAROLA = re.compile(r"\b\w+\b", re.UNICODE)


def normalizza(testo: str) -> str:
    """Lowercase, collassa spazi, rimuove punteggiatura non alfabetica."""
    testo = testo.lower().strip()
    testo = re.sub(r"\s+", " ", testo)
    testo = re.sub(r"[^\w\s]", "", testo)
    return testo


def carica_messaggi(percorso: Path) -> list[dict]:
    conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT ruolo, contenuto, ts FROM messaggi ORDER BY ts, id"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"ruolo": r["ruolo"], "contenuto": (r["contenuto"] or "").strip(), "ts": r["ts"]}
        for r in rows
        if (r["contenuto"] or "").strip()
    ]


def estrai_citazioni(osservazione: str) -> list[str]:
    """Restituisce tutti i testi tra virgolette; se non ce ne sono, l'osservazione stessa."""
    citazioni = RE_CITAZIONI.findall(osservazione)
    if citazioni:
        return citazioni
    # Se non ci sono virgolette, usa il testo pulito dell'osservazione.
    pulito = osservazione
    if pulito.startswith("- "):
        pulito = pulito[2:]
    if pulito.startswith("EXPLICIT:"):
        pulito = pulito[len("EXPLICIT:"):]
    pulito = pulito.strip()
    return [pulito] if pulito else []


def finestre_parole(testo: str, min_parole: int, max_parole: int) -> list[str]:
    """Genera finestre di parole da max a min, dalla piu' lunga alla piu' corta."""
    parole = RE_PAROLA.findall(testo)
    out = []
    for n in range(max_parole, min_parole - 1, -1):
        for i in range(len(parole) - n + 1):
            out.append(" ".join(parole[i : i + n]))
    return out


SOGLIA_CARATTERI = 20
SOGLIA_PAROLE = 4


def trova_corrispondenza(query: str, testo: str) -> int:
    """Restituisce la lunghezza della piu' lunga sottostringa comune
    continua tra query normalizzata e testo normalizzato.
    """
    q = normalizza(query)
    t = normalizza(testo)
    if not q or not t:
        return 0
    # Cerca la query per intero.
    if q in t:
        return len(q)
    # Cerca finestre decrescenti.
    parole = RE_PAROLA.findall(q)
    for n in range(min(15, len(parole)), min(SOGLIA_PAROLE, len(parole)) - 1, -1):
        for i in range(len(parole) - n + 1):
            finestra = " ".join(parole[i : i + n])
            if finestra in t:
                return len(finestra)
    return 0


def attribuisci(citazione: str, messaggi: list[dict]) -> tuple[str | None, int]:
    """Restituisce (ruolo, lunghezza_corrispondenza).

    Criterio:
    1. per ogni messaggio calcola la lunghezza della piu' lunga sottostringa
       comune continua tra la citazione normalizzata e il messaggio normalizzato;
    2. scegli il ruolo con la corrispondenza piu' lunga;
    3. se la lunghezza massima e' inferiore alla soglia (20 caratteri o 4 parole),
       l'osservazione e' non attribuita.
    """
    if len(normalizza(citazione)) < SOGLIA_CARATTERI:
        return None, 0

    best_ruolo = None
    best_len = 0
    for m in messaggi:
        lung = trova_corrispondenza(citazione, m["contenuto"])
        if lung > best_len:
            best_len = lung
            best_ruolo = m["ruolo"]

    # Verifica anche la soglia in parole.
    parole_cit = RE_PAROLA.findall(normalizza(citazione))
    if best_len >= SOGLIA_CARATTERI or best_len >= SOGLIA_PAROLE * 4:
        return best_ruolo, best_len
    return None, best_len


def leggi_osservazioni(percorso: Path) -> list[str]:
    out = []
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if riga.startswith("- "):
            out.append(riga[2:].strip())
    return out


def analizza_file(nome: str, suffisso: str) -> dict:
    md_path = OUT / f"{nome}{suffisso}.md"
    if not md_path.exists():
        # Prova nella cartella originale per il prompt base.
        md_path = BASE / "stato" / "prova-estrazione" / f"{nome}.md"
    osservazioni = leggi_osservazioni(md_path)
    messaggi = carica_messaggi(ARCHIVIO / f"{nome}.db")

    conteggi = {"user": 0, "assistant": 0, "non_attribuito": 0, "dettagli": []}
    for o in osservazioni:
        citazioni = estrai_citazioni(o)
        ruolo = None
        for c in citazioni:
            ruolo, _ = attribuisci(c, messaggi)
            if ruolo:
                break
        if ruolo == "user":
            conteggi["user"] += 1
        elif ruolo == "assistant":
            conteggi["assistant"] += 1
        else:
            conteggi["non_attribuito"] += 1
        conteggi["dettagli"].append({
            "osservazione": o,
            "ruolo": ruolo,
            "citazione_usata": citazioni[0] if citazioni else None,
        })
    return conteggi


def main() -> int:
    files = sorted(p.stem for p in ARCHIVIO.glob("*.db"))
    varianti = {
        "originale": ("", BASE / "stato" / "prova-estrazione"),
        "variante_a": ("-a", OUT),
        "variante_b": ("-b", OUT),
    }

    riassunto = {}
    for nome_var, (suffisso, cartella) in varianti.items():
        print(f"\n=== {nome_var} ===")
        tot_user = tot_assistant = tot_non = 0
        per_conv = {}
        for nome in files:
            md_path = cartella / f"{nome}{suffisso}.md"
            if not md_path.exists():
                print(f"  {nome}: file mancante {md_path}")
                continue
            osservazioni = leggi_osservazioni(md_path)
            messaggi = carica_messaggi(ARCHIVIO / f"{nome}.db")
            conteggi = {"user": 0, "assistant": 0, "non_attribuito": 0}
            for o in osservazioni:
                citazioni = estrai_citazioni(o)
                ruolo = None
                for c in citazioni:
                    ruolo, _ = attribuisci(c, messaggi)
                    if ruolo:
                        break
                if ruolo == "user":
                    conteggi["user"] += 1
                elif ruolo == "assistant":
                    conteggi["assistant"] += 1
                else:
                    conteggi["non_attribuito"] += 1
            tot = sum(conteggi.values())
            tasso_sbagliato = round(100 * conteggi["assistant"] / tot, 1) if tot else 0
            print(
                f"  {nome}: tot={tot} user={conteggi['user']} "
                f"assistant={conteggi['assistant']} non={conteggi['non_attribuito']} "
                f"err={tasso_sbagliato}%"
            )
            per_conv[nome] = {
                "totale": tot,
                "user": conteggi["user"],
                "assistant": conteggi["assistant"],
                "non_attribuito": conteggi["non_attribuito"],
                "tasso_sbagliato_pct": tasso_sbagliato,
            }
            tot_user += conteggi["user"]
            tot_assistant += conteggi["assistant"]
            tot_non += conteggi["non_attribuito"]

        tot = tot_user + tot_assistant + tot_non
        riassunto[nome_var] = {
            "totale_osservazioni": tot,
            "user": tot_user,
            "assistant": tot_assistant,
            "non_attribuito": tot_non,
            "tasso_sbagliato_pct": round(100 * tot_assistant / tot, 1) if tot else 0,
            "per_conversazione": per_conv,
        }
        print(
            f"  TOTALE: {tot} osservazioni — user={tot_user} "
            f"assistant={tot_assistant} non={tot_non} "
            f"err={riassunto[nome_var]['tasso_sbagliato_pct']}%"
        )

    (BASE / "stato" / "misura_attribuzioni.json").write_text(
        json.dumps(riassunto, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
