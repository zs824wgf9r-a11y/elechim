#!/usr/bin/env python3
"""Estrae fatti dal proprietario senza nessun modello.

Principio: un fatto e' una frase del proprietario, con il suo timestamp e
l'identificatore del messaggio. Non si parafrasa, non si normalizza, non si
attribuisce perche' si prende solo da messaggi [user].

Libreria standard soltanto.
"""

from __future__ import annotations

import json
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARCHIVIO = BASE / "archivio"
STATO = BASE / "stato"
OUT = STATO / "prova-estrazione-deterministica"
OUT.mkdir(parents=True, exist_ok=True)

# Abbreviazioni che portano un punto ma non chiudono la frase.
ABBREVIAZIONI = {
    "ecc",
    "etc",
    "cioe",
    "cioè",
    "es",
    "ad es",
    "p es",
    "p.es",
    "n.b",
    "nb",
    "dott",
    "sig",
    "sig.ra",
    "sira",
    "prof",
    "prof.ssa",
    "avv",
    "dr",
    "dr.ssa",
    "gg",
    "mm",
    "sec",
    "min",
    "ore",
    "n",
    "vol",
    "pag",
    "pp",
    "cap",
    "art",
    "cfr",
    "ca",
    "circa",
    "vs",
    "oz",
    "ibid",
    "op cit",
    "all",
    "all'",
    "proff",
    "ing",
    "on",
    "n°",
    "num",
    "nr",
    "lit",
    "bd",
    "vol",
    "ed",
}

# Parole che indicano che la frase dice qualcosa del parlante.
INDICATORI_PARLANTE = {
    # pronomi e aggettivi possessivi/prima persona
    "io", "me", "mi", "mio", "mia", "miei", "mie",
    "noi", "ci", "nostro", "nostra", "nostri", "nostre",
    # verbi ausiliari/modali alla prima persona
    "ho", "sono", "sto", "ero", "ero", "avevo", "avevo",
    "vado", "vado", "facio", "faccio", "fò", "fo",
    "penso", "credo", "preferisco", "voglio", "devo", "posso",
    "uso", "utilizzo", "prendo", "mangio", "bevo", "dormo",
    "lavoro", "abito", "vivo", "studio", "gioco", "leggo", "scrivo",
    "sento", "vedo", "alleno", "cammino", "corro", "nuoto",
    "farò", "faro", "userò", "usero", "andrò", "andro", "sarò", "saro",
    "avrei", "farei", "darei", "prenderei", "userei", "vorrei", "potrei", "dovrei",
    "abbiamo", "siamo", "stiamo", "vogliamo", "dobbiamo", "possiamo",
    "facciamo", "andiamo", "usiamo", "prendiamo", "vediamo",
    "useremo", "faremo", "andremo", "saremo", "avremo", "sceglieremo",
    "decidiamo", "scegliamo", "ho deciso", "ho scelto",
    "restiamo", "rimaniamo",
    "mi serve", "mi servono", "mi piace", "mi piacciono", "mi sembra", "mi pare",
    "mi fa piacere", "mi dispiace", "mi sento", "mi chiamo",
}

# Verbi di inizio che, all'imperativo, indicano richiesta all'interlocutore.
VERBI_IMPERATIVO = {
    "fammi", "dimmi", "dammi", "mostrami", "spiegami", "aiutami",
    "trovami", "cercami", "scrivimi", "mandami", "inoltiami", "inviami",
    "leggimi", "aprimi", "chiudimi", "avviami", "fermami", "riavviami",
    "fai", "dai", "di'", "dì", "digli", "fagli", "dagli", "vai", "guarda",
    "ascolta", "prova", "usa", "cerca", "scrivi", "manda", "inoltra", "invia",
    "leggi", "apri", "chiudi", "avvia", "ferma", "riavvia", "spiega",
    "controlla", "verifica", "genera", "crea", "disegna", "mostra",
    "sentiti", "cercalo", "inizia", "comincia", "finisci", "smetti",
}

# Inizi che quasi sempre sono domande o imperativi rivolti all'assistente.
INIZI_SCARTO = {
    "puoi", "potresti", "mi fai", "mi faresti", "mi puoi", "mi potresti",
    "puoi farmi", "potresti farmi", "puoi dirmi", "potresti dirmi",
    "come", "quando", "dove", "quanto", "quanta", "quanti", "quante",
    "quale", "quali", "chi", "perche", "perché", "perchè",
    "tu", "ti", "te", "hai", "sei", "stai",
}

RE_PAROLA = re.compile(r"\b\w+\b", re.UNICODE)
RE_NUMERO = re.compile(r"\d")
RE_DATA = re.compile(r"\b\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}\b|\b\d{4}\b")


def pulisci_testo_messaggio(testo: str) -> str:
    """Toglie i marker di media/immagine che non sono parole del proprietario."""
    righe = []
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga:
            continue
        if riga.startswith("[") and ":" in riga and riga.endswith("]"):
            # Marker tipo [immagine: ...], [audio], [documento: ...]
            continue
        righe.append(riga)
    return " ".join(righe)


def parola_prima_del_punto(testo: str, pos: int) -> str:
    """Restituisce la parola (minuscola, senza punteggiatura) che precede
    il punto in pos."""
    # Cerca l'inizio della parola: prima del punto, saltiamo spazi/punteggiatura.
    i = pos - 1
    while i >= 0 and testo[i] in " \t\n\r\"'":
        i -= 1
    fine = i + 1
    while i >= 0 and testo[i] not in " \t\n\r":
        i -= 1
    parola = testo[i + 1 : fine]
    # Normalizza: toglie punteggiatura iniziale/finale, passa a minuscolo.
    parola = parola.strip("'\"()[]{}").lower()
    while parola and parola[-1] in ".:,;!?":
        parola = parola[:-1]
    while parola and parola[0] in "'\"()[]{}·":
        parola = parola[1:]
    return parola


def e_numero_decimale(testo: str, pos: int) -> bool:
    """True se il punto in pos e' un separatore decimale (3.5)."""
    if pos <= 0 or pos + 1 >= len(testo):
        return False
    return testo[pos - 1].isdigit() and testo[pos + 1].isdigit()


def taglia_frasi(testo: str) -> list[str]:
    """Taglia in frasi senza spezzare abbreviazioni e numeri decimali."""
    frasi = []
    inizio = 0
    i = 0
    n = len(testo)
    while i < n:
        c = testo[i]
        if c in ".!?":
            # Non spezzare se e' un numero decimale.
            if c == "." and e_numero_decimale(testo, i):
                i += 1
                continue
            # Non spezzare se la parola precedente e' un'abbreviazione.
            if c == ".":
                parola = parola_prima_del_punto(testo, i)
                if parola in ABBREVIAZIONI:
                    i += 1
                    continue
            # Consuma tutti i segni di fine frase consecutivi.
            j = i
            while j < n and testo[j] in ".!?:":
                j += 1
            # Taglia qui; la prossima frase iniziera' dopo eventuali spazi.
            fine = j
            frase = testo[inizio:fine].strip()
            if frase:
                frasi.append(frase)
            inizio = fine
            i = j
            continue
        if c in ";:":
            # Consuma eventuali : o ; ripetuti.
            j = i
            while j < n and testo[j] in ";:":
                j += 1
            frase = testo[inizio:j].strip()
            if frase:
                frasi.append(frase)
            inizio = j
            i = j
            continue
        i += 1

    # Ultima frase.
    rimanente = testo[inizio:].strip()
    if rimanente:
        frasi.append(rimanente)
    return frasi


def normalizza_per_match(frase: str) -> str:
    """Minuscolo e senza punteggiatura, per confronti su parole."""
    frase = frase.lower()
    frase = re.sub(r"[^\w\s']", " ", frase)
    frase = re.sub(r"\s+", " ", frase).strip()
    return frase


def prime_parole(frase: str, n: int) -> list[str]:
    """Restituisce le prime n parole normalizzate."""
    parole = RE_PAROLA.findall(normalizza_per_match(frase))
    return parole[:n]


def e_domanda(frase: str) -> bool:
    """Domanda se finisce con '?'."""
    return frase.rstrip().endswith("?")


def e_imperativo(frase: str) -> bool:
    """Euristiche conservative per scartare richieste all'interlocutore.

    Controlla anche le prime parole dopo connettivi come "allora", "ora".
    """
    parole = prime_parole(frase, 5)
    if not parole:
        return False

    # Inizio con verbo imperativo noto.
    if parole[0] in VERBI_IMPERATIVO:
        return True
    if " ".join(parole[:2]) in VERBI_IMPERATIVO:
        return True

    # Imperativo dopo connettivo o avverbio di tempo ("allora fammi", "ora scrivimi").
    for i in range(1, min(4, len(parole))):
        if parole[i] in VERBI_IMPERATIVO:
            return True

    # Inizio con "puoi / potresti / mi fai ...".
    if parole[0] in {"puoi", "potresti"}:
        return True
    if len(parole) >= 2 and " ".join(parole[:2]) in {
        "mi fai", "mi faresti", "mi puoi", "mi potresti",
        "puoi farmi", "potresti farmi", "puoi dirmi", "potresti dirmi",
    }:
        return True

    return False


def ha_indicatore_prima_persona(frase: str) -> bool:
    """True se la frase contiene almeno un indicatore di prima persona."""
    parole = RE_PAROLA.findall(normalizza_per_match(frase))
    testo = " " + " ".join(parole) + " "
    for bigramma in {"mi serve", "mi servono", "mi piace", "mi piacciono",
                     "mi sembra", "mi pare", "mi sento", "mi chiamo",
                     "ho deciso", "ho scelto"}:
        if f" {bigramma} " in testo:
            return True
    for p in parole:
        if p in INDICATORI_PARLANTE:
            return True
    return False


def e_sull_assistente(frase: str) -> bool:
    """Frasi che hanno come soggetto l'interlocutore (tu/ti/te/hai/sei/puoi).

    Se la frase contiene indicatori di prima persona, non la scartiamo qui:
    il proprietario puo' parlare dell'interlocutore in una frase che comunque
    rivela qualcosa di se ("ti parlo solo tramite telegram").
    """
    if ha_indicatore_prima_persona(frase):
        return False

    parole = prime_parole(frase, 5)
    testo = " " + " ".join(parole) + " "
    if not parole:
        return False

    if parole[0] in {"tu", "te"}:
        return True
    # "ti" come pronome clitico ("ti inoltro", "ti mando") indica l'interlocutore.
    if " ti " in testo:
        return True
    # "hai", "sei", "stai", "puoi", "potresti" da soli indicano l'interlocutore.
    if parole[0] in {"hai", "sei", "stai", "puoi", "potresti"}:
        return True
    # "non riesci..." riguarda l'interlocutore.
    if parole[0] == "non" and len(parole) > 1 and parole[1] in {"riesci", "sei", "hai", "stai", "puoi", "potresti"}:
        return True
    # Forme con pronome + verbo: "dove puoi", "cosa useresti", "come te la caveresti".
    if " puoi " in testo or " potresti " in testo or " useresti " in testo:
        return True
    return False


def classifica_fatto(frase: str) -> tuple[bool, str]:
    """Restituisce (tenere, motivo_scarto_o_tipo).

    Ordine dei filtri:
    1. scarta domande;
    2. scarta imperativi;
    3. scarta frasi sull'assistente;
    4. scarta frasi troppo corte;
    5. tieni se contiene indicatori di prima persona.
    """
    frase_pulita = frase.strip()
    if not frase_pulita:
        return False, "vuota"

    if e_domanda(frase_pulita):
        return False, "domanda"

    if e_imperativo(frase_pulita):
        return False, "imperativo"

    if e_sull_assistente(frase_pulita):
        return False, "sull'assistente"

    parole = RE_PAROLA.findall(normalizza_per_match(frase_pulita))
    if len(parole) < 2:
        return False, "troppo breve"

    if ha_indicatore_prima_persona(frase_pulita):
        return True, "prima persona"

    return False, "non sul parlante"


def estrai_fatti_da_messaggio(messaggio: dict) -> list[dict]:
    """Estrae i fatti da un singolo messaggio [user].

    Se una frasa del messaggio contiene un indicatore di prima persona, anche le
    frasi vicine dello stesso messaggio (che non siano domande, imperativi o
    rivolte all'interlocutore) vengono tenute come contesto dello stesso
    pensiero/azione.
    """
    testo = pulisci_testo_messaggio(messaggio["contenuto"])
    if not testo:
        return []

    frasi = taglia_frasi(testo)
    # Primo passo: individua se il messaggio parla del proprietario.
    ha_indicatore_prima_persona = any(
        classifica_fatto(frase)[0] for frase in frasi
    )

    fatti = []
    for frase in frasi:
        tenere, motivo = classifica_fatto(frase)
        if tenere:
            fatti.append({
                "testo": frase,
                "ts": messaggio["ts"],
                "msg_id": messaggio["id"],
            })
            continue

        # Contesto: se il messaggio e' in prima persona, le frasi che non sono
        # domande, imperativi, sull'assistente o troppo corte sono parte dello
        # stesso pensiero.
        if ha_indicatore_prima_persona and motivo == "non sul parlante":
            if not e_domanda(frase) and not e_imperativo(frase) and not e_sull_assistente(frase):
                parole = RE_PAROLA.findall(normalizza_per_match(frase))
                if len(parole) >= 2:
                    fatti.append({
                        "testo": frase,
                        "ts": messaggio["ts"],
                        "msg_id": messaggio["id"],
                        "contesto": True,
                    })
                    continue

        fatti.append({
            "testo": frase,
            "ts": messaggio["ts"],
            "msg_id": messaggio["id"],
            "scartata": True,
            "motivo": motivo,
        })
    return fatti


def carica_messaggi(percorso: Path) -> list[dict]:
    conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, ruolo, contenuto, ts FROM messaggi ORDER BY ts, id"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": r["id"], "ruolo": r["ruolo"], "contenuto": r["contenuto"] or "", "ts": r["ts"]}
        for r in rows
    ]


def scrivi_fatti(nome: str, messaggi: list[dict], fatti: list[dict]) -> Path:
    percorso = OUT / f"{nome}.md"
    messaggi_user = [m for m in messaggi if m["ruolo"] == "user"]
    fatti_tenuti = [f for f in fatti if not f.get("scartata")]
    scartate = [f for f in fatti if f.get("scartata")]

    righe = [
        f"# {nome}",
        "",
        f"- messaggi totali: {len(messaggi)}",
        f"- messaggi [user] analizzati: {len(messaggi_user)}",
        f"- fatti estratti: {len(fatti_tenuti)}",
        f"- frasi scartate: {len(scartate)}",
        "",
        "## Fatti",
        "",
    ]
    for f in fatti_tenuti:
        righe.append(f'- "{f["testo"]}" — ts={f["ts"]} msg_id={f["msg_id"]}')

    if scartate:
        righe.extend(["", "## Scartate", ""])
        conteggi = {}
        for f in scartate:
            conteggi[f["motivo"]] = conteggi.get(f["motivo"], 0) + 1
        for motivo, n in sorted(conteggi.items()):
            righe.append(f"- {motivo}: {n}")
        righe.append("")
        for f in scartate:
            righe.append(f'- "{f["testo"]}" — motivo={f["motivo"]} msg_id={f["msg_id"]}')

    percorso.write_text("\n".join(righe), encoding="utf-8")
    return percorso


def main() -> int:
    db_files = sorted(ARCHIVIO.glob("*.db"))
    if len(db_files) < 3:
        print(f"errore: trovati solo {len(db_files)} file .db in archivio/", file=sys.stderr)
        return 1

    print(f"Campionamento: tutti i file .db in archivio/ ({len(db_files)} file)")
    print(f"Output: {OUT}")

    risultati = []
    for db in db_files:
        nome = db.stem
        print(f"\n--- {nome} ---")
        t0 = time.time()
        messaggi = carica_messaggi(db)
        messaggi_user = [m for m in messaggi if m["ruolo"] == "user"]

        fatti = []
        for m in messaggi_user:
            fatti.extend(estrai_fatti_da_messaggio(m))

        percorso = scrivi_fatti(nome, messaggi, fatti)
        durata_ms = (time.time() - t0) * 1000

        fatti_tenuti = [f for f in fatti if not f.get("scartata")]
        scartate = [f for f in fatti if f.get("scartata")]
        conteggi_scarto = {}
        for f in scartate:
            conteggi_scarto[f["motivo"]] = conteggi_scarto.get(f["motivo"], 0) + 1

        misura = {
            "file": nome,
            "messaggi": len(messaggi),
            "messaggi_user": len(messaggi_user),
            "frasi_totali": len(fatti),
            "fatti": len(fatti_tenuti),
            "scartate": conteggi_scarto,
            "tempo_ms": round(durata_ms, 2),
            "output": str(percorso.relative_to(BASE)),
        }
        risultati.append(misura)
        print(f"  messaggi: {misura['messaggi']}, user: {misura['messaggi_user']}, "
              f"frasi: {misura['frasi_totali']}, fatti: {misura['fatti']}, "
              f"tempo: {misura['tempo_ms']} ms")
        print(f"  scartate: {conteggi_scarto}")

    totali = [m["fatti"] for m in risultati]
    tempi = [m["tempo_ms"] for m in risultati]
    scartate_totali = {}
    for m in risultati:
        for k, v in m["scartate"].items():
            scartate_totali[k] = scartate_totali.get(k, 0) + v

    aggregati = {
        "conversazioni": len(risultati),
        "totale_messaggi": sum(m["messaggi"] for m in risultati),
        "totale_messaggi_user": sum(m["messaggi_user"] for m in risultati),
        "fatti_min": min(totali) if totali else 0,
        "fatti_mediana": statistics.median(totali) if totali else 0,
        "fatti_max": max(totali) if totali else 0,
        "fatti_totali": sum(totali),
        "tempo_totale_ms": round(sum(tempi), 2),
        "tempo_medio_ms": round(statistics.mean(tempi), 2) if tempi else 0,
        "scartate": scartate_totali,
    }

    (OUT / "misure.json").write_text(
        json.dumps({"per_conversazione": risultati, "aggregati": aggregati}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Aggregati ===")
    print(json.dumps(aggregati, indent=2, ensure_ascii=False))
    print(f"\nFile da leggere: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
