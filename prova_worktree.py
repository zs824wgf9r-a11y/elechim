#!/usr/bin/env python3
"""Collaudo dei worktree: codice isolato, stato condiviso.

I test creano worktree temporanei e li distruggono alla fine. Il caso 1 e'
il motivo di tutto l'incarico: il lock GPU deve reggere fra worktree diversi.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import lavoro

BASE_TEMP = Path("/tmp/opencode/prova_worktree")
if BASE_TEMP.exists():
    shutil.rmtree(BASE_TEMP)
BASE_TEMP.mkdir(parents=True)


def _run(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def _nome_unico(prefisso: str) -> str:
    return f"{prefisso}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _apri(nome: str) -> Path:
    wt = lavoro.apri(nome)
    return Path(wt).resolve()


def _forza_pulizia(nome: str) -> None:
    """Rimuove worktree e ramo anche in caso di incrostature."""
    branch = f"lavoro/{nome}"
    wt = lavoro._radice_worktree(nome)
    _run(["git", "worktree", "remove", "-f", str(wt)], cwd=REPO, check=False)
    _run(["git", "branch", "-D", branch], cwd=REPO, check=False)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    parent = wt.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def _python_worktree(wt: Path) -> Path:
    return (wt / ".venv" / "bin" / "python").resolve()


# ---------------------------------------------------------------------------
# Caso 1: il lock GPU regge fra repo principale e worktree
# ---------------------------------------------------------------------------

def test_lock_gpu_fra_worktree() -> None:
    nome = _nome_unico("lock-gpu")
    wt = _apri(nome)
    sync = BASE_TEMP / nome
    sync.mkdir()
    try:
        primo = _python_worktree(wt)
        codice_primo = f"""
import sys
sys.path.insert(0, {str(wt)!r})
import energia
import time
from pathlib import Path
sync = Path({str(sync)!r})
(sync / "p1_inizio").write_text(str(time.time()), encoding="ascii")
with energia.riserva_gpu("p1", timeout=30):
    (sync / "p1_preso").write_text(str(time.time()), encoding="ascii")
    time.sleep(1.2)
(sync / "p1_fine").write_text(str(time.time()), encoding="ascii")
"""
        p1 = subprocess.Popen(
            [str(primo), "-c", codice_primo],
            cwd=str(wt),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Aspetta che il primo processo abbia preso il lock.
        scadenza = time.time() + 10
        while not (sync / "p1_preso").exists():
            if p1.poll() is not None:
                out, err = p1.communicate()
                raise RuntimeError(f"p1 e' morto prematuramente: {out} / {err}")
            if time.time() > scadenza:
                p1.kill()
                raise TimeoutError("p1 non ha preso il lock in tempo")
            time.sleep(0.05)

        # Ora il secondo processo, nel repo principale, prova a prendere lo
        # stesso lock. Deve aspettare che p1 finisca.
        codice_secondo = f"""
import sys
sys.path.insert(0, {str(REPO)!r})
import energia
import time
from pathlib import Path
sync = Path({str(sync)!r})
(sync / "p2_inizio").write_text(str(time.time()), encoding="ascii")
with energia.riserva_gpu("p2", timeout=30):
    (sync / "p2_preso").write_text(str(time.time()), encoding="ascii")
    time.sleep(0.2)
(sync / "p2_fine").write_text(str(time.time()), encoding="ascii")
"""
        p2 = subprocess.Popen(
            [sys.executable, "-c", codice_secondo],
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        rc1 = p1.wait(timeout=30)
        rc2 = p2.wait(timeout=30)
        if rc1 != 0:
            out, err = p1.communicate()
            raise RuntimeError(f"p1 e' uscito {rc1}: {err}")
        if rc2 != 0:
            out, err = p2.communicate()
            raise RuntimeError(f"p2 e' uscito {rc2}: {err}")

        t1_fine = float((sync / "p1_fine").read_text(encoding="ascii"))
        t2_preso = float((sync / "p2_preso").read_text(encoding="ascii"))
        delta = t2_preso - t1_fine
        print(f"  p1 fine={t1_fine:.6f}, p2 preso={t2_preso:.6f}, delta={delta*1000:.1f}ms")
        assert delta >= -0.05, (
            f"p2 ha preso il lock {abs(delta)*1000:.1f}ms prima che p1 finisse: "
            "il mutex NON regge fra worktree"
        )
        print("OK lock GPU: il secondo processo aspetta il primo anche fra worktree.")
    finally:
        if "p1" in dir() and p1.poll() is None:
            p1.kill()
        if "p2" in dir() and p2.poll() is None:
            p2.kill()
        _forza_pulizia(nome)


# ---------------------------------------------------------------------------
# Caso 2: .coda.lock di documenti.py e' condiviso
# ---------------------------------------------------------------------------

def test_lock_coda_fra_worktree() -> None:
    nome = _nome_unico("lock-coda")
    wt = _apri(nome)
    sync = BASE_TEMP / nome
    sync.mkdir()
    try:
        import documenti

        codice = f"""
import sys
sys.path.insert(0, {str(wt)!r})
import documenti
from pathlib import Path
sync = Path({str(sync)!r})
mio = False
with documenti._coda_esclusiva() as mio:
    pass
(sync / "mio").write_text(str(mio), encoding="ascii")
"""
        with documenti._coda_esclusiva() as primo:
            assert primo is True, "la prima istanza non ha preso il lock"
            p = subprocess.Popen(
                [str(_python_worktree(wt)), "-c", codice],
                cwd=str(wt),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            rc = p.wait(timeout=10)
            if rc != 0:
                out, err = p.communicate()
                raise RuntimeError(f"processo worktree uscito {rc}: {err}")

        risultato = (sync / "mio").read_text(encoding="ascii")
        assert risultato == "False", f"il secondo ha ottenuto il lock: {risultato!r}"
        print("OK lock coda: la seconda istanza nel worktree esce senza entrare.")
    finally:
        _forza_pulizia(nome)


# ---------------------------------------------------------------------------
# Caso 3: la bandiera stato/gioco e' vista dal repo principale
# ---------------------------------------------------------------------------

def test_bandiera_gioco() -> None:
    nome = _nome_unico("gioco")
    wt = _apri(nome)
    try:
        import energia

        energia.GIOCO.unlink(missing_ok=True)
        codice = f"""
import sys
sys.path.insert(0, {str(wt)!r})
import energia
energia.GIOCO.write_text("test worktree", encoding="utf-8")
"""
        r = _run([str(_python_worktree(wt)), "-c", codice], cwd=wt, check=True)
        assert energia.in_gioco(), "la bandiera alzata nel worktree non e' vista dal repo principale"
        energia.GIOCO.unlink(missing_ok=True)
        print("OK bandiera gioco: alzata nel worktree, vista dal principale.")
    finally:
        _forza_pulizia(nome)


# ---------------------------------------------------------------------------
# Caso 4: aprire due volte lo stesso nome non rompe nulla
# ---------------------------------------------------------------------------

def test_apri_duplicato() -> None:
    nome = _nome_unico("dup")
    wt = _apri(nome)
    try:
        try:
            lavoro.apri(nome)
        except RuntimeError as e:
            assert "esiste gia'" in str(e), f"errore inaspettato: {e}"
            print("OK apri duplicato: rifiuta senza danni.")
        else:
            raise RuntimeError("apri duplicato non ha rifiutato")
    finally:
        _forza_pulizia(nome)


# ---------------------------------------------------------------------------
# Caso 5: chiudi rifiuta modifiche non committate
# ---------------------------------------------------------------------------

def test_chiudi_rifiuta_modifiche() -> None:
    nome = _nome_unico("dirty")
    wt = _apri(nome)
    try:
        (wt / "file_di_test.md").write_text("sporca", encoding="utf-8")
        try:
            lavoro.chiudi(nome)
        except RuntimeError as e:
            assert "modifiche" in str(e).lower(), f"errore inaspettato: {e}"
            # Il worktree deve essere ancora li'.
            assert wt.exists(), "chiudi ha rimosso un worktree sporco nonostante il rifiuto"
            print("OK chiudi sporco: rifiuta e lascia il worktree in piedi.")
        else:
            raise RuntimeError("chiudi ha accettato un worktree con modifiche")
    finally:
        _forza_pulizia(nome)


# ---------------------------------------------------------------------------
# Caso 6: fixture cancellate nel worktree non spariscono dal principale
# ---------------------------------------------------------------------------

def test_fixture_sopravvive() -> None:
    nome = _nome_unico("fixture")
    wt = _apri(nome)
    fixture = REPO / "documenti" / "elaborati" / "prova-due-colonne.pdf"
    try:
        assert fixture.exists(), "fixture mancante nel repo principale prima del test"
        copia_wt = wt / "documenti" / "elaborati" / "prova-due-colonne.pdf"
        assert copia_wt.exists(), "fixture non presente nel worktree"
        copia_wt.unlink()
        assert not copia_wt.exists(), "la cancellazione nel worktree non e' andata"
        assert fixture.exists(), "la fixture e' sparita dal repo principale!"
        print("OK fixture: cancellata nel worktree, rimane nel principale.")
    finally:
        _forza_pulizia(nome)


# ---------------------------------------------------------------------------
# Caso 7: .venv raggiungibile dal worktree
# ---------------------------------------------------------------------------

def test_venv_raggiungibile() -> None:
    nome = _nome_unico("venv")
    wt = _apri(nome)
    try:
        r = _run(
            [str(_python_worktree(wt)), "-c", "import energia; print('import OK')"],
            cwd=wt,
            check=True,
        )
        assert "import OK" in r.stdout, r.stdout
        print("OK .venv: raggiungibile e importa energia dal worktree.")
    finally:
        _forza_pulizia(nome)


def test_stato_elenca_worktree() -> None:
    """Controllo di coerenza del comando stato."""
    nome = _nome_unico("stato")
    wt = _apri(nome)
    try:
        righe = lavoro.stato()
        trovato = [r for r in righe if r["branch"] == f"lavoro/{nome}"]
        assert trovato, f"stato non elenca il worktree appena creato: {righe}"
        assert trovato[0]["modifiche"] == "pulito", trovato[0]
        print("OK stato: elenca il worktree come pulito.")
    finally:
        _forza_pulizia(nome)


def _nessun_worktree_di_prova() -> None:
    r = _run(["git", "worktree", "list"], cwd=REPO, check=True)
    for riga in r.stdout.splitlines():
        if "lavoro/" in riga:
            raise RuntimeError(f"worktree di prova rimasto: {riga}")


def main() -> int:
    tests = [
        test_lock_gpu_fra_worktree,
        test_lock_coda_fra_worktree,
        test_bandiera_gioco,
        test_apri_duplicato,
        test_chiudi_rifiuta_modifiche,
        test_fixture_sopravvive,
        test_venv_raggiungibile,
        test_stato_elenca_worktree,
    ]
    for t in tests:
        print(f"\n{t.__name__}")
        t()
    _nessun_worktree_di_prova()
    print("\nTUTTO VERDE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
