#!/usr/bin/env python3
"""Prova: un'istruzione di lingua esplicita chiude la deriva verso l'inglese?

Variante di prova_estrazione.py. Stesso modello, campione, criterio e temperatura;
cambia solo il prompt, con l'aggiunta di una riga che impone la lingua.
Non installa Honcho, Postgres ne' pgvector.

I dati in archivio/ vengono toccati solo dalla macchina: questo script legge
i messaggi, chiama il modello e scrive le osservazioni in
stato/prova-estrazione-lingua/. Il rapporto contiene solo numeri.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import requests

import energia

BASE = Path(__file__).resolve().parent
ARCHIVIO = BASE / "archivio"
STATO = BASE / "stato"
OUT = STATO / "prova-estrazione-lingua"
OUT.mkdir(parents=True, exist_ok=True)

OLLAMA = "http://127.0.0.1:11434"
MODELLO = "qwen3:8b"
PEER_ID = "proprietario"
SEED = 42
TEMPERATURE = 0.0

PROMPT_URL = (
    "https://github.com/plastic-labs/honcho/blob/"
    "f88892b0715adbd852c6b846532cc39a335d2de4/src/deriver/prompts.py"
)
PROMPT_REVISION = "f88892b0715adbd852c6b846532cc39a335d2de4"

# Prompt esatto minimal_deriver_prompt dal sorgente Honcho, piu' l'istruzione di
# formato gia' usata in prova_estrazione.py. Alla fine viene aggiunta, su una
# riga sola, l'istruzione di lingua per la variante A o B.
PROMPT_TEMPLATE_COMUNE = """Analyze messages to extract **explicit atomic facts** about the target peer.

[EXPLICIT] DEFINITION: Facts about the target peer that can be derived directly from their messages.
   - Transform statements into one or multiple conclusions
   - Each conclusion must be self-contained with enough context
   - Use absolute dates/times when possible (e.g. "June 26, 2025" not "yesterday")

RULES:
- The target peer is the peer identified below under `Target peer:`.
- A peer can be a human user, AI agent, bot, service, or other actor.
- Use the exact peer id from `Target peer:` in final observations, not the phrase "the target peer".
- Properly attribute observations to the correct subject: if it is about the target peer, use the exact peer id as the subject. If the target peer is referencing someone or something else, make that clear.
- Observations should make sense on their own. Each observation will be used in the future to better understand the target peer.
- Extract ALL observations from the target peer's messages, using others as context.
- Contextualize each observation sufficiently (e.g. "Ann is nervous about the job interview at the pharmacy" not just "Ann is nervous")

<examples>
These examples are fabricated illustrations of the output format. Never emit a conclusion for which content comes from these examples. Every conclusion must be supported by the <messages> block only.

EXAMPLES (using `alice` as the target peer id):
- EXPLICIT: "I just turned 25" → "alice is 25 years old"
- EXPLICIT: "I took my dog for a walk in NYC" → "alice has a dog", "alice walked her dog in NYC"
- EXPLICIT: "I've lived in NYC for six years" → "alice lives in NYC", "alice has lived in NYC for six years"
</examples>

Target peer:
{peer_id}

Messages to analyze:
<messages>
{messages}
</messages>

Return the conclusions as a bullet list, one observation per line, prefixed with "- ".

{lingua_istruzione}"""

VARIANTI = {
    "a": "Write every conclusion in the same language as the messages.",
    "b": "Scrivi tutte le conclusioni in italiano, la stessa lingua dei messaggi.",
}

# Criterio di lingua: stesso di prova_estrazione.py.
PAROLE_ITALIANE = {
    "il", "la", "lo", "i", "le", "gli",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "e", "o", "ma", "se", "perche", "che", "chi", "cui", "quale",
    "un", "uno", "una",
    "e", "e'", "è", "sono", "e", "ho", "ha", "hai", "hanno", "abbiamo",
    "mi", "ti", "si", "ci", "vi",
    "questo", "questa", "questi", "queste", "quello", "quella",
    "come", "dove", "quando", "perche", "perché", "anche", "solo",
    "mio", "tuo", "suo", "nostro", "vostro", "loro",
}

PAROLE_INGlesi = {
    "the", "a", "an",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can",
    "and", "or", "but", "if", "then", "because", "that", "which",
    "this", "these", "those", "with", "from", "for", "about", "into",
    "to", "of", "in", "on", "at", "by", "as",
    "i", "you", "he", "she", "it", "we", "they",
    "my", "your", "his", "her", "its", "our", "their",
}

RE_PAROLA = re.compile(r"\b\w+\b", re.UNICODE)
RE_NUMERO = re.compile(r"\d")
RE_DATA = re.compile(r"\b\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}\b|\b\d{4}\b")


def classifica_lingua(testo: str) -> str:
    parole = RE_PAROLA.findall(testo.lower())
    it = sum(1 for p in parole if p in PAROLE_ITALIANE)
    en = sum(1 for p in parole if p in PAROLE_INGlesi)
    if it >= 2 and (en == 0 or it / en > 1.5):
        return "italiano"
    if en >= 2 and (it == 0 or en / it > 1.5):
        return "inglese"
    return "misto/indeterminato"


def estrai_osservazioni(testo: str) -> list[str]:
    out = []
    for riga in testo.splitlines():
        riga = riga.strip()
        if riga.startswith("- "):
            out.append(riga[2:].strip())
    return out


def ha_numeri(testo: str) -> bool:
    return bool(RE_NUMERO.search(testo))


def ha_date(testo: str) -> bool:
    return bool(RE_DATA.search(testo))


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
        {"ruolo": r["ruolo"], "contenuto": r["contenuto"] or "", "ts": r["ts"]}
        for r in rows
    ]


def formatta_messaggi(messaggi: list[dict]) -> str:
    righe = []
    for m in messaggi:
        ruolo = m["ruolo"]
        contenuto = m["contenuto"].strip()
        if not contenuto:
            continue
        righe.append(f"[{ruolo}] {contenuto}")
    return "\n".join(righe)


def chiama_ollama(prompt: str) -> dict:
    payload = {
        "model": MODELLO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "seed": SEED,
        },
    }
    r = requests.post(f"{OLLAMA}/api/generate", json=payload, timeout=300)
    r.raise_for_status()
    return r.json()


def scrivi_osservazioni(nome: str, variante: str, messaggi: list[dict], osservazioni: list[str]) -> None:
    percorso = OUT / f"{nome}-{variante}.md"
    righe = [
        f"# {nome} (variante {variante})",
        "",
        f"- messaggi analizzati: {len(messaggi)}",
        f"- osservazioni estratte: {len(osservazioni)}",
        "",
        "## Osservazioni",
        "",
    ]
    for o in osservazioni:
        righe.append(f"- {o}")
    percorso.write_text("\n".join(righe), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rilancia l'estrazione Honcho con istruzione di lingua esplicita."
    )
    parser.add_argument(
        "--variante",
        choices=["a", "b"],
        required=True,
        help="Variante dell'istruzione di lingua: a (inglese) o b (italiano).",
    )
    args = parser.parse_args()

    db_files = sorted(ARCHIVIO.glob("*.db"))
    if len(db_files) < 3:
        print(f"errore: trovati solo {len(db_files)} file .db in archivio/", file=sys.stderr)
        return 1

    lingua_istruzione = VARIANTI[args.variante]
    print(f"Prompt Honcho: {PROMPT_URL}")
    print(f"Revisione: {PROMPT_REVISION}")
    print(f"Variante lingua: {args.variante}")
    print(f"Istruzione aggiunta: {lingua_istruzione!r}")
    print(f"Campionamento: tutti i file .db in archivio/, in ordine lessicografico ({len(db_files)} file)")
    print(f"Output: {OUT}")

    with energia.blocco("prova-estrazione-lingua"), energia.riserva_gpu("prova-estrazione-lingua"):
        risultati = []
        for db in db_files:
            nome = db.stem
            print(f"\n--- {nome} ---")
            messaggi = carica_messaggi(db)
            testo_messaggi = formatta_messaggi(messaggi)
            prompt = PROMPT_TEMPLATE_COMUNE.format(
                peer_id=PEER_ID,
                messages=testo_messaggi,
                lingua_istruzione=lingua_istruzione,
            )

            t0 = time.time()
            risposta = chiama_ollama(prompt)
            durata = time.time() - t0

            out_text = risposta.get("response", "")
            osservazioni = estrai_osservazioni(out_text)
            lingue = [classifica_lingua(o) for o in osservazioni]
            conteggi_lingua = {
                "italiano": lingue.count("italiano"),
                "inglese": lingue.count("inglese"),
                "misto/indeterminato": lingue.count("misto/indeterminato"),
            }

            misura = {
                "file": nome,
                "messaggi": len(messaggi),
                "osservazioni": len(osservazioni),
                "lingue": conteggi_lingua,
                "zero_osservazioni": len(osservazioni) == 0,
                "tempo_s": round(durata, 2),
                "prompt_tokens": risposta.get("prompt_eval_count"),
                "output_tokens": risposta.get("eval_count"),
                "con_numeri": sum(1 for o in osservazioni if ha_numeri(o)),
                "con_date": sum(1 for o in osservazioni if ha_date(o)),
            }
            risultati.append(misura)
            print(f"  messaggi: {misura['messaggi']}, osservazioni: {misura['osservazioni']}, "
                  f"italiano: {conteggi_lingua['italiano']}, inglese: {conteggi_lingua['inglese']}, "
                  f"tempo: {misura['tempo_s']}s, prompt tokens: {misura['prompt_tokens']}")
            scrivi_osservazioni(nome, args.variante, messaggi, osservazioni)

    totali = [m["osservazioni"] for m in risultati]
    zero = sum(1 for m in risultati if m["zero_osservazioni"])
    tempi = [m["tempo_s"] for m in risultati]
    prompt_tokens = [m["prompt_tokens"] for m in risultati]
    output_tokens = [m["output_tokens"] for m in risultati]
    numeri = [m["con_numeri"] for m in risultati]
    date = [m["con_date"] for m in risultati]
    it = sum(m["lingue"]["italiano"] for m in risultati)
    en = sum(m["lingue"]["inglese"] for m in risultati)
    mix = sum(m["lingue"]["misto/indeterminato"] for m in risultati)
    tot_oss = sum(totali)

    aggregati = {
        "variante": args.variante,
        "conversazioni": len(risultati),
        "totale_messaggi": sum(m["messaggi"] for m in risultati),
        "osservazioni_min": min(totali) if totali else 0,
        "osservazioni_mediana": statistics.median(totali) if totali else 0,
        "osservazioni_max": max(totali) if totali else 0,
        "conversazioni_zero_osservazioni": zero,
        "tempo_totale_s": round(sum(tempi), 2),
        "tempo_medio_s": round(statistics.mean(tempi), 2) if tempi else 0,
        "prompt_tokens_tot": sum(t for t in prompt_tokens if t is not None),
        "output_tokens_tot": sum(t for t in output_tokens if t is not None),
        "osservazioni_italiane": it,
        "osservazioni_inglesi": en,
        "osservazioni_miste": mix,
        "pct_italiano": round(100 * it / tot_oss, 1) if tot_oss else 0,
        "osservazioni_con_numeri": sum(numeri),
        "osservazioni_con_date": sum(date),
    }

    (OUT / f"misure-{args.variante}.json").write_text(
        json.dumps({"per_conversazione": risultati, "aggregati": aggregati}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Aggregati ===")
    print(json.dumps(aggregati, indent=2, ensure_ascii=False))
    print(f"\nFile da leggere: {OUT}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
