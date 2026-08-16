"""Bot Telegram: long polling, nessuna dipendenza da framework async.

Per un bot a utente singolo il polling con requests basta e avanza, ed e'
molto piu' facile da capire quando qualcosa non va.

Gira sul Mac mini, accanto al modello: il turno di conversazione non passa piu'
dalla rete. Vocali e immagini invece li macina il fisso, e da qui parte solo il
`file_id` — i byte non attraversano mai il tunnel. Col fisso spento Elechim
continua a rispondere, semplicemente senza strumenti.
"""

from __future__ import annotations

import sys
import threading
import time

import requests

import risveglio
import strumenti
from core import (
    ENV,
    LIMITE_CONTESTO,
    ContestoPieno,
    Conversazione,
    modello_raggiungibile,
)

API = f"https://api.telegram.org/bot{ENV['TELEGRAM_TOKEN']}"
AIUTO = (
    "Comandi:\n"
    "/nuova - azzera la conversazione (il primo turno tornera' lento)\n"
    "/stato - diagnostica di modello, fisso e conversazione\n"
    "/gioco - libera la VRAM del fisso: vocali e immagini si fermano\n"
    "/amici - rimette in VRAM i modelli di Elechim\n"
    "/energia - VRAM, modelli caricati, quanto manca alla sospensione\n"
    "/accendi - sveglia il fisso se dorme\n"
    "/aiuto - questo messaggio\n\n"
    "Puoi mandarmi vocali e immagini: li legge il PC fisso."
)


def chiama(metodo: str, **parametri):
    r = requests.post(f"{API}/{metodo}", json=parametri, timeout=70)
    r.raise_for_status()
    return r.json()


def invia(chat_id: int, testo: str) -> None:
    """Invia provando il Markdown, con fallback a testo semplice.

    Il modello usa i backtick per comandi e codice, quindi il Markdown serve.
    Ma Telegram risponde 400 se i marcatori sono malformati (un backtick non
    chiuso, un underscore dentro un nome di file), e spezzando a 4000 caratteri
    si puo' tagliare a meta' un blocco di codice. Il fallback evita che un
    problema di formattazione si trasformi in un messaggio mai recapitato.
    """
    # Telegram taglia a 4096 caratteri: spezzo per sicurezza.
    for i in range(0, len(testo), 4000):
        pezzo = testo[i : i + 4000]
        try:
            chiama("sendMessage", chat_id=chat_id, text=pezzo, parse_mode="Markdown")
        except requests.HTTPError:
            chiama("sendMessage", chat_id=chat_id, text=pezzo)


def con_indicatore(chat_id: int, azione: str, funzione, *argomenti):
    """Esegue `funzione` tenendo vivo l'indicatore di attivita' di Telegram.

    L'indicatore scade dopo ~5 secondi, ma il primo turno di una conversazione
    ne impiega 7 e un'immagine col modello di visione ancora da caricare anche
    di piu': senza rinnovarlo il bot sembra morto proprio quando sta lavorando.
    """
    risultato: dict = {}

    def lavora():
        try:
            risultato["valore"] = funzione(*argomenti)
        except BaseException as errore:  # noqa: BLE001 - rilanciata dal chiamante
            risultato["errore"] = errore

    thread = threading.Thread(target=lavora, daemon=True)
    thread.start()
    while thread.is_alive():
        try:
            chiama("sendChatAction", chat_id=chat_id, action=azione)
        except Exception:  # noqa: BLE001 - l'indicatore non deve far fallire nulla
            pass
        thread.join(timeout=4)

    if "errore" in risultato:
        raise risultato["errore"]
    return risultato.get("valore")


# --- allegati: li legge il fisso, qui arriva solo testo ---------------------


def trascrivi_vocale(chat_id: int, vocale: dict) -> str:
    """Manda il file_id al fisso e riceve il testo. L'audio non passa di qui."""
    inizio = time.time()
    testo = con_indicatore(chat_id, "typing", strumenti.trascrivi, vocale["file_id"])
    print(
        f"vocale di {vocale.get('duration', 0)}s trascritto in {time.time() - inizio:.1f}s",
        flush=True,
    )
    return testo


def leggi_immagine(chat_id: int, file_id: str, didascalia: str) -> str:
    """Manda il file_id al fisso e riceve la descrizione o il testo trascritto."""
    inizio = time.time()
    descrizione = con_indicatore(
        chat_id, "typing", strumenti.immagine, file_id, didascalia
    )
    print(
        f"immagine letta in {time.time() - inizio:.1f}s "
        f"({len(descrizione)} caratteri)",
        flush=True,
    )
    return descrizione


def allegato_immagine(messaggio: dict) -> str | None:
    """Il file_id dell'immagine, sia mandata come foto sia come file.

    Delle foto Telegram manda piu' misure, dalla miniatura all'originale: prendo
    l'ultima, che e' la piu' grande. Tanto e' il fisso a rimpicciolirla prima di
    darla al modello, e a quel punto tanto vale partire dalla migliore.
    """
    foto = messaggio.get("photo")
    if foto:
        return foto[-1]["file_id"]

    documento = messaggio.get("document") or {}
    if (documento.get("mime_type") or "").startswith("image/"):
        return documento["file_id"]
    return None


def autorizzato(conv: Conversazione, chat_id: int) -> bool:
    """Primo che scrive /start diventa il proprietario. Gli altri restano fuori."""
    proprietario = conv.leggi_meta("proprietario")
    if proprietario is None:
        conv.scrivi_meta("proprietario", str(chat_id))
        return True
    return proprietario == str(chat_id)


def gestisci(conv: Conversazione, chat_id: int, testo: str) -> None:
    comando = testo.strip().lower()

    if comando in ("/start", "/aiuto", "/help"):
        invia(chat_id, f"Ciao, sono Elechim.\n\n{AIUTO}")
        return

    if comando == "/nuova":
        archiviati = conv.azzera()
        invia(
            chat_id,
            f"Conversazione azzerata, {archiviati} messaggi archiviati. "
            "Il prossimo messaggio sara' lento.",
        )
        return

    if comando == "/stato":
        ok, dettaglio = modello_raggiungibile()
        ok_fisso, dettaglio_fisso = strumenti.gateway_raggiungibile()
        conversazioni, messaggi = conv.conversazioni_archiviate()
        invia(
            chat_id,
            f"Modello: {'ok' if ok else 'NON raggiungibile'} ({dettaglio})\n"
            f"Fisso: {'ok' if ok_fisso else 'NON raggiungibile'} ({dettaglio_fisso})\n"
            f"Turni in conversazione: {conv.numero_turni()}\n"
            f"Archivio: {conversazioni} conversazioni, {messaggi} messaggi",
        )
        return

    if comando == "/accendi":
        # `forza` perche' qui l'ha chiesto il proprietario: il freno dei due minuti
        # serve a non ripetere il pacchetto a ogni tool, non a ignorarlo.
        if risveglio.sveglia(forza=True):
            invia(chat_id, "Magic packet mandato. Il fisso dovrebbe esserci fra una ventina di secondi.")
        else:
            invia(
                chat_id,
                "Non sono riuscito a mandare il pacchetto: il cavo verso il "
                "fisso e' staccato, oppure la scheda non e' alimentata "
                "(succede da spegnimento completo con ErP attivo nel BIOS).",
            )
        return

    if comando in ("/gioco", "/amici", "/energia"):
        try:
            invia(chat_id, con_indicatore(chat_id, "typing", strumenti.energia, comando))
        except strumenti.FissoSpento as errore:
            invia(chat_id, f"Niente da fare: {errore}.")
        except Exception as errore:  # noqa: BLE001
            invia(chat_id, f"Il fisso ha risposto male: {errore}")
        return

    inizio = time.time()
    try:
        esito = con_indicatore(chat_id, "typing", conv.rispondi, testo)
    except ContestoPieno:
        invia(chat_id, "Conversazione troppo lunga per il contesto. Manda /nuova.")
        return
    except requests.Timeout:
        invia(chat_id, "Il modello non ha risposto in tempo. Riprova.")
        return
    except Exception as errore:  # noqa: BLE001
        invia(chat_id, f"Errore parlando col modello: {errore}")
        return

    invia(chat_id, esito.testo or "(risposta vuota)")
    if esito.vicino_al_limite:
        invia(
            chat_id,
            f"(conversazione a {esito.prompt_token} token su {LIMITE_CONTESTO}: "
            "conviene /nuova a breve)",
        )
    print(
        f"turno in {time.time() - inizio:.1f}s  {esito.riga_diagnostica()}",
        flush=True,
    )


def prepara_messaggio(chat_id: int, messaggio: dict) -> str | None:
    """Da un messaggio Telegram al testo da dare al modello.

    Vocali e immagini diventano testo qui, prima di toccare la conversazione:
    al modello deve arrivare esattamente un messaggio `user`, o la cache non
    aggancia.
    """
    file_immagine = allegato_immagine(messaggio)
    vocale = messaggio.get("voice") or messaggio.get("audio")

    if file_immagine:
        didascalia = (messaggio.get("caption") or "").strip()
        try:
            descrizione = leggi_immagine(chat_id, file_immagine, didascalia)
        except strumenti.FissoSpento:
            invia(chat_id, "Le immagini le legge il PC fisso, che ora e' spento.")
            return None
        except Exception as errore:  # noqa: BLE001
            invia(chat_id, f"Non sono riuscito a leggere l'immagine: {errore}")
            return None

        # Rimando quello che ha letto, come per i vocali: se ha capito male te
        # ne accorgi subito, invece di ragionare su una descrizione sbagliata.
        invia(chat_id, f"🖼 «{descrizione}»")
        return (
            f"[immagine: {didascalia}]\n{descrizione}"
            if didascalia
            else f"[immagine]\n{descrizione}"
        )

    if vocale:
        try:
            testo = trascrivi_vocale(chat_id, vocale)
        except strumenti.FissoSpento:
            invia(chat_id, "I vocali li trascrive il PC fisso, che ora e' spento.")
            return None
        except Exception as errore:  # noqa: BLE001
            invia(chat_id, f"Non sono riuscito a trascrivere il vocale: {errore}")
            return None
        if not testo:
            invia(chat_id, "Vocale vuoto o incomprensibile.")
            return None
        invia(chat_id, f"🎤 «{testo}»")
        return testo

    testo = messaggio.get("text")
    if testo:
        return testo

    # Da qui in giu' e' roba che non sappiamo ancora leggere. Prima taceva e
    # basta: l'11 agosto un PDF non gestito e' sparito senza una riga di
    # log, e il modello — che non sa cosa arriva in chat — ha risposto "non hai
    # allegato il file". Un allegato ignorato va detto dal bot, che lo sa per
    # certo, non lasciato indovinare al modello.
    documento = messaggio.get("document") or {}
    if documento:
        nome = documento.get("file_name") or "il documento"
        print(
            f"allegato non gestito: {nome} ({documento.get('mime_type')})",
            flush=True,
        )
        invia(
            chat_id,
            f"Non so ancora leggere i documenti, quindi {nome} non l'ho aperto. "
            "Per ora incollami il testo. L'OCR sul fisso arriva con la fase 4.",
        )
        return None

    tipo = next(
        (
            etichetta
            for chiave, etichetta in (
                ("video", "i video"),
                ("video_note", "i videomessaggi"),
                ("sticker", "gli sticker"),
                ("animation", "le GIF"),
                ("location", "le posizioni"),
                ("contact", "i contatti"),
                ("poll", "i sondaggi"),
            )
            if chiave in messaggio
        ),
        "questo tipo di messaggio",
    )
    print(f"messaggio non gestito: {sorted(messaggio.keys())}", flush=True)
    invia(chat_id, f"Non gestisco {tipo}. Mandami testo, un vocale o un'immagine.")
    return None


def main() -> int:
    conv = Conversazione()

    ok, dettaglio = modello_raggiungibile()
    if not ok:
        print(f"ATTENZIONE: modello non raggiungibile ({dettaglio}).", flush=True)
        print("Il server gira su questa stessa macchina: controlla turbofieldfare.", flush=True)
    else:
        print(f"modello raggiungibile: {dettaglio}", flush=True)

    ok_fisso, dettaglio_fisso = strumenti.gateway_raggiungibile()
    print(
        f"fisso: {'raggiungibile' if ok_fisso else 'NON raggiungibile'} ({dettaglio_fisso})",
        flush=True,
    )

    offset = int(conv.leggi_meta("offset_telegram") or 0)
    print("bot avviato, in ascolto", flush=True)

    while True:
        try:
            risposta = chiama("getUpdates", offset=offset, timeout=60)
        except Exception as errore:  # noqa: BLE001
            print(f"polling fallito: {errore}", flush=True)
            time.sleep(5)
            continue

        for update in risposta.get("result", []):
            offset = update["update_id"] + 1
            conv.scrivi_meta("offset_telegram", str(offset))

            messaggio = update.get("message") or {}
            chat_id = (messaggio.get("chat") or {}).get("id")
            if chat_id is None:
                continue

            if not autorizzato(conv, chat_id):
                print(f"ignorato messaggio da chat non autorizzata {chat_id}", flush=True)
                continue

            try:
                testo = prepara_messaggio(chat_id, messaggio)
                if testo:
                    gestisci(conv, chat_id, testo)
            except Exception as errore:  # noqa: BLE001
                print(f"errore gestendo il messaggio: {errore}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
