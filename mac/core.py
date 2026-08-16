"""Nucleo dell'assistente: stato condiviso e chiamate al modello sul Mac mini.

Tutto ruota attorno alla cache del prompt sul Mac (ServerPromptCache.swift),
che ha UNA sola slot e riusa il prefill solo in due forme strette:

- `matchTextContinuation`: dopo una risposta testuale deve arrivare ESATTAMENTE
  un messaggio nuovo con ruolo `user`.
- `matchToolContinuation`: dopo un tool call devono arrivare ESATTAMENTE i
  risultati, uno per chiamata (`continuation.count == calls.count`).

Qualsiasi cosa infilata in mezzo — un promemoria, un blocco di memoria, un
secondo messaggio — fa ripartire il prefill da zero: a 8K token sono ~340s.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

import strumenti

BASE = Path(__file__).resolve().parent


def carica_env() -> dict[str, str]:
    env: dict[str, str] = {}
    percorso = BASE / ".env"
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, _, valore = riga.partition("=")
        env[chiave.strip()] = valore.strip()
    return env


ENV = carica_env()

# Entra nel contesto a ogni conversazione: si paga una volta per sessione (poi
# finisce in cache), ma ogni riga in piu la paghi in secondi sul primo turno.
# La riga sulla concisione e' la piu' redditizia di tutte: a 21 token/s ogni
# token generato costa ~48ms, quindi una risposta breve non e' stile, e' latenza.
#
# Misura dell'11 agosto, prima giornata di uso vero: 27 turni, 4.581 token
# generati (170 a turno), 310s di attesa totale di cui ~275 di sola generazione.
# **Il 90% della latenza percepita e' verbosita'**, non prefill. Da qui il tetto
# numerico sulle righe: gli aggettivi ("conciso") il modello li ignora appena il
# contesto cresce, un numero e un esempio no.
#
# Stessa giornata, zero chiamate a `cerca` nonostante due richieste esplicite di
# ricerca web. Le DEFINIZIONI degli strumenti dicono cosa fanno, non *quando*
# usarli: con 4B di parametri attivi la regola va scritta qui. Non nelle
# descrizioni dei tool, che viaggiano a ogni richiesta e devono restare
# identiche byte per byte o la cache salta (vedi strumenti.DEFINIZIONI).
# Il nome del proprietario sta nel `.env`, non qui dentro. Non e' pudore: e' che
# questo file e' versionato su un repo pubblico, e depersonalizzare la prosa di
# un prompt che *gira* ha due prezzi. Il primo e' che il modello perde un dato
# che gli serve davvero — un nome proprio e' piu' utile di "del proprietario", e a
# 4B di parametri attivi i riferimenti concreti pesano. Il secondo e' peggiore:
# il prompt di sistema e' il **prefisso** della cache, quindi cambiarne una
# parola azzera il prefill di ogni conversazione viva (a 8K token sono ~340s).
# Con la chiave a posto il prompt torna byte per byte quello di prima e la cache
# non si accorge di niente. Chi clona il repo mette il suo nome e basta.
PROPRIETARIO = ENV.get("PROPRIETARIO", "Nome")

SYSTEM_PROMPT = f"""Sei Elechim, assistente personale locale di {PROPRIETARIO}. Rispondi in italiano.

Stile:
- Vai dritto al punto. Niente saluti, preamboli o frasi tipo "Certamente, ecco...". La prima riga e' gia' la risposta.
- Massimo 8 righe. Piu' lungo solo se {PROPRIETARIO} chiede una scheda, un elenco completo o del codice: allora niente frasi di contorno, solo la roba.
- Tono asciutto e pragmatico, con ironia tagliente quando ci sta. Mai prediche, mai toni da call center.
- Elenchi con trattino. Backtick per comandi e codice. Mai titoli, mai grassetto, mai corsivo: su Telegram sono rumore.

Strumenti:
- Chiama `cerca` ogni volta che {PROPRIETARIO} nomina il web, e ogni volta che la risposta dipende da qualcosa di recente, verificabile o che potresti ricordare male. Cerca prima, rispondi dopo.
- `leggi` solo su un url uscito da `cerca`, e solo se i riassunti non bastano.
- Non dire mai di aver cercato se non hai chiamato lo strumento.

Sostanza:
- Se non sai una cosa o un comando fallisce, dillo subito in una riga. Non inventare mai dati, percorsi o nomi di file.
- Non sai se il PC fisso e' acceso, cosa gira sulle macchine o cosa e' arrivato in chat: non tirare a indovinare, di' di mandare /stato.
- Per il codice dai solo il blocco, con commenti solo dove servono. Spiegazioni solo se richieste.
- Se una richiesta e' ambigua e la differenza conta, fai una domanda secca invece di indovinare.

Dove giri: sei un Gemma 4 sul Mac mini di {PROPRIETARIO}, 21 token/s, e rileggere il contesto ti costa piu' che generarlo. Il lavoro pesante (ricerca, OCR, riassunti) sta sul PC fisso con 62GB e una RTX 4060 Ti. Quando proponi soluzioni tecniche tieni conto che tutto cio' che entra nel tuo contesto va prima compresso sul fisso.

Il tono e la misura, per esempio:
D: "chi sei?"
R: "Elechim. Il fatto che tu debba chiedermelo non depone bene per nessuno dei due."
D: "il server non parte"
R: "Prevedibile. Incolla il log, non la sinossi."
D: "la pianta la annaffio la sera o la mattina?"
R: "Indifferente. Conta solo che il vaso si asciughi: annaffia quando e' secco, scarica l'acqua in eccesso. L'orario e' folklore da giardino." """

# Tarati dal proprietario: 0.65 tiene stabile il codice lasciando spazio all'ironia,
# 0.90 esclude le parole fuori contesto. max_tokens NON rende conciso il modello
# (che non sa che esiste): e' solo una rete di sicurezza contro le risposte fiume.
TEMPERATURA = 0.65
TOP_P = 0.90
MAX_TOKEN = 800


# Il server rifiuta con `context_length_exceeded` quando il prompt supera il
# contesto configurato (--max-context 65536). Avvisiamo prima di arrivarci.
LIMITE_CONTESTO = 65536
MAX_GIRI_TOOL = 5
SOGLIA_AVVISO = 52000


class ContestoPieno(RuntimeError):
    """La conversazione ha saturato il contesto: serve /nuova."""


@dataclass
class Esito:
    testo: str
    prompt_token: int
    cached_token: int
    generati: int
    secondi: float
    strumenti: list[str] | None = None

    @property
    def percentuale_cache(self) -> float:
        if self.prompt_token == 0:
            return 0.0
        return 100.0 * self.cached_token / self.prompt_token

    @property
    def vicino_al_limite(self) -> bool:
        return self.prompt_token >= SOGLIA_AVVISO

    def riga_diagnostica(self) -> str:
        return (
            f"[{self.secondi:.1f}s | prompt {self.prompt_token} "
            f"cache {self.percentuale_cache:.0f}% | {self.generati} token"
            + (f" | tool: {','.join(self.strumenti)}" if self.strumenti else "")
            + "]"
        )


class Conversazione:
    """Stato condiviso fra Telegram e CLI.

    Una sola conversazione alla volta, di proposito: la cache del prompt sul Mac
    ha una sola slot, quindi due conversazioni alternate se la ruberebbero a
    vicenda e ogni cambio costerebbe il prefill pieno.
    """

    def __init__(self, percorso_db: str | None = None) -> None:
        self.percorso_db = percorso_db or ENV["STATO_DB"]
        self.conn = sqlite3.connect(self.percorso_db, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS messaggi ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " ruolo TEXT NOT NULL,"
            " contenuto TEXT NOT NULL,"
            " ts REAL NOT NULL)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (chiave TEXT PRIMARY KEY, valore TEXT)"
        )
        # Colonne per il loop dei tool, aggiunte dopo la fase 1.
        for colonna in ("tool_calls TEXT", "tool_call_id TEXT", "nome TEXT"):
            try:
                self.conn.execute(f"ALTER TABLE messaggi ADD COLUMN {colonna}")
            except sqlite3.OperationalError:
                pass  # gia' presente
        # L'archivio: `azzera()` ci copia dentro la conversazione prima di
        # cancellarla. Fino all'11 agosto `/nuova` faceva solo DELETE, e ogni
        # azzeramento distruggeva per sempre la materia prima del dreaming (una
        # serata intera persa alle 00:10 di quel giorno). Sta nello stesso file
        # perche' cosi' l'archiviazione e la cancellazione sono una transazione
        # sola: o si salva tutto, o non si cancella niente.
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS conversazioni ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " iniziata REAL NOT NULL,"
            " chiusa REAL NOT NULL,"
            " messaggi INTEGER NOT NULL)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS archivio ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " conversazione INTEGER NOT NULL,"
            " ruolo TEXT NOT NULL,"
            " contenuto TEXT NOT NULL,"
            " ts REAL NOT NULL,"
            " tool_calls TEXT,"
            " tool_call_id TEXT,"
            " nome TEXT)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_archivio_conv ON archivio (conversazione)"
        )
        self.conn.commit()

    # --- meta ---------------------------------------------------------------

    def leggi_meta(self, chiave: str) -> str | None:
        cur = self.conn.execute("SELECT valore FROM meta WHERE chiave = ?", (chiave,))
        riga = cur.fetchone()
        return riga[0] if riga else None

    def scrivi_meta(self, chiave: str, valore: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (chiave, valore) VALUES (?, ?)"
            " ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore",
            (chiave, valore),
        )
        self.conn.commit()

    # --- messaggi -----------------------------------------------------------

    def _aggiungi(
        self,
        ruolo: str,
        contenuto: str | None,
        tool_calls: list | None = None,
        tool_call_id: str | None = None,
        nome: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO messaggi (ruolo, contenuto, ts, tool_calls, tool_call_id, nome)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                ruolo,
                contenuto or "",
                time.time(),
                json.dumps(tool_calls) if tool_calls else None,
                tool_call_id,
                nome,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def _rimuovi(self, id_messaggio: int) -> None:
        self.conn.execute("DELETE FROM messaggi WHERE id >= ?", (id_messaggio,))
        self.conn.commit()

    def storico(self) -> list[dict]:
        cur = self.conn.execute(
            "SELECT ruolo, contenuto, tool_calls, tool_call_id, nome"
            " FROM messaggi ORDER BY id"
        )
        messaggi: list[dict] = []
        for ruolo, contenuto, chiamate, id_chiamata, nome in cur.fetchall():
            if ruolo == "tool":
                messaggi.append({
                    "role": "tool",
                    "tool_call_id": id_chiamata,
                    "name": nome,
                    "content": contenuto,
                })
            elif chiamate:
                messaggi.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": json.loads(chiamate),
                })
            else:
                messaggi.append({"role": ruolo, "content": contenuto})
        return messaggi

    def azzera(self) -> int:
        """Archivia la conversazione e poi la cancella.

        Ritorna quanti messaggi ha archiviato. Non c'e' `commit()` fra la copia
        e la cancellazione di proposito: sqlite tiene aperta una transazione
        sola, quindi se qualcosa va storto a meta' non resta ne' un archivio
        monco ne' una conversazione persa.

        Non tocca il percorso dei turni, quindi non ha effetti sulla cache: il
        prossimo primo turno e' lento perche' e' un contesto nuovo, non per
        questo.
        """
        righe = self.conn.execute(
            "SELECT ruolo, contenuto, ts, tool_calls, tool_call_id, nome"
            " FROM messaggi ORDER BY id"
        ).fetchall()

        if righe:
            cursore = self.conn.execute(
                "INSERT INTO conversazioni (iniziata, chiusa, messaggi)"
                " VALUES (?, ?, ?)",
                (righe[0][2], time.time(), len(righe)),
            )
            id_conversazione = cursore.lastrowid
            self.conn.executemany(
                "INSERT INTO archivio"
                " (conversazione, ruolo, contenuto, ts, tool_calls, tool_call_id, nome)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(id_conversazione, *riga) for riga in righe],
            )

        self.conn.execute("DELETE FROM messaggi")
        self.conn.execute("DELETE FROM meta WHERE chiave = 'prompt_sistema'")
        self.conn.commit()
        return len(righe)

    def conversazioni_archiviate(self) -> tuple[int, int]:
        """Quante conversazioni e quanti messaggi ci sono nell'archivio."""
        return self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(messaggi), 0) FROM conversazioni"
        ).fetchone()

    def prompt_sistema(self) -> str:
        """Prompt di sistema con la data, congelato per tutta la conversazione.

        Senza la data il modello cerca notizie "di oggi" nell'anno del suo
        addestramento: visto in uso reale il 2026-08-10, con query generate su
        "February 2025". Ma la data non puo' essere ricalcolata a ogni chiamata:
        cambierebbe il prefisso a mezzanotte e invaliderebbe la cache a meta'
        conversazione. Si fissa alla prima chiamata e resta finche' non si azzera.
        """
        salvato = self.leggi_meta("prompt_sistema")
        if salvato:
            return salvato
        # Mesi scritti a mano: `%B` dipende dal locale del processo, che sotto
        # systemd e' quello di default e restituirebbe "August".
        mesi = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
        adesso = datetime.now()
        oggi = f"{adesso.day} {mesi[adesso.month - 1]} {adesso.year}"
        prompt = f"{SYSTEM_PROMPT}\n\nOggi e' il {oggi}: usalo quando cerchi notizie recenti."
        self.scrivi_meta("prompt_sistema", prompt)
        return prompt

    def numero_turni(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM messaggi WHERE ruolo = 'user'")
        return cur.fetchone()[0]

    # --- chiamata al modello ------------------------------------------------

    def rispondi(self, testo_utente: str, timeout: int = 900) -> Esito:
        """Aggiunge un solo messaggio utente e chiede la risposta.

        L'append di esattamente un messaggio `user` dopo la risposta precedente
        e' cio' che tiene valida la cache lato Mac. Non aggiungere altro qui.
        """
        id_utente = self._aggiungi("user", testo_utente)
        inizio = time.time()
        strumenti_usati: list[str] = []
        ultimo_uso: dict = {}

        try:
            for _ in range(MAX_GIRI_TOOL):
                dati = self._chiama_modello(timeout)
                ultimo_uso = dati.get("usage", {})
                messaggio = dati["choices"][0]["message"]
                chiamate = messaggio.get("tool_calls") or []

                if not chiamate:
                    testo = messaggio.get("content") or ""
                    # Va salvato esattamente il testo prodotto dal modello: la
                    # cache lato Mac confronta il messaggio assistant rigenerato
                    # con quello memorizzato.
                    self._aggiungi("assistant", testo)
                    return self._esito(testo, ultimo_uso, inizio, strumenti_usati)

                # La forma stretta che matchToolContinuation pretende: il
                # messaggio assistant con le chiamate, e subito dopo ESATTAMENTE
                # un risultato per chiamata, nello stesso ordine. Niente altro in
                # mezzo, o il prefill riparte da zero.
                self._aggiungi("assistant", None, tool_calls=chiamate)
                for chiamata in chiamate:
                    funzione = chiamata["function"]
                    nome = funzione["name"]
                    try:
                        argomenti = json.loads(funzione.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        argomenti = {}
                    strumenti_usati.append(nome)
                    risultato = strumenti.esegui(nome, argomenti)
                    self._aggiungi(
                        "tool",
                        risultato,
                        tool_call_id=chiamata.get("id"),
                        nome=nome,
                    )

            # Troppi giri: meglio dirlo che restare in loop.
            testo = "Mi sono impantanato: troppi passaggi di seguito. Riformula."
            self._aggiungi("assistant", testo)
            return self._esito(testo, ultimo_uso, inizio, strumenti_usati)

        except Exception:
            # Senza questo rollback resterebbero messaggi a meta' (un `user`
            # senza risposta, o chiamate senza risultato): al turno successivo la
            # forma di continuazione sarebbe rotta e la cache non aggancerebbe
            # mai piu'.
            self._rimuovi(id_utente)
            raise

    def _chiama_modello(self, timeout: int) -> dict:
        corpo = {
            "model": ENV["MAC_MODEL"],
            "messages": [{"role": "system", "content": self.prompt_sistema()}] + self.storico(),
            # Sempre la stessa lista, byte per byte: la cache lato Mac richiede
            # `entry.tools == request.tools`.
            "tools": strumenti.DEFINIZIONI,
            "max_tokens": MAX_TOKEN,
            "temperature": TEMPERATURA,
            "top_p": TOP_P,
        }
        risposta = requests.post(
            f"{ENV['MAC_BASE_URL']}/chat/completions", json=corpo, timeout=timeout
        )
        if risposta.status_code >= 400:
            if "context_length_exceeded" in risposta.text[:500]:
                raise ContestoPieno(
                    "La conversazione ha saturato il contesto. Serve /nuova."
                )
            risposta.raise_for_status()
        return risposta.json()

    def _esito(
        self, testo: str, uso: dict, inizio: float, strumenti_usati: list[str]
    ) -> Esito:
        return Esito(
            testo=testo,
            prompt_token=uso.get("prompt_tokens", 0),
            cached_token=uso.get("prompt_tokens_details", {}).get("cached_tokens", 0),
            generati=uso.get("completion_tokens", 0),
            secondi=time.time() - inizio,
            strumenti=strumenti_usati,
        )


def modello_raggiungibile() -> tuple[bool, str]:
    try:
        r = requests.get(f"{ENV['MAC_BASE_URL']}/models", timeout=10)
        r.raise_for_status()
        nomi = [m["id"] for m in r.json().get("data", [])]
        return True, ", ".join(nomi) or "nessun modello"
    except Exception as errore:  # noqa: BLE001 - diagnostica, va mostrato tutto
        return False, str(errore)
