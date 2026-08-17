#!/usr/bin/env python3
"""Gestione dei worktree per sessione di lavoro su Elechim.

Principio: il codice si isola, lo stato si condivide.
Ogni worktree ha una copia indipendente del codice, ma condivide con il repo
principale le directory che contengono stato, cache e lock:

    stato/, markdown/, documenti/in, documenti/falliti, archivio/, .venv

I collegamenti sono symlink relativi, perche' un flock su due inode diversi non
esclude nulla (vedi INCARICO-worktree.md).

Il worktree viene creato fuori dal repo principale, in:

    <parente-del-repo>/.lavori/<nome>

così `git worktree add` non si lamenta che il percorso sia dentro l'albero.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Directory condivise con il repo principale, espresse come percorsi relativi
# alla radice del worktree. I symlink puntano a queste directory nel repo
# principale, calcolate relativamente dal worktree stesso.
COLLEGAMENTI: list[tuple[str, str]] = [
    ("stato", "stato"),
    ("markdown", "markdown"),
    ("documenti/in", "documenti/in"),
    ("documenti/falliti", "documenti/falliti"),
    ("archivio", "archivio"),
    (".venv", ".venv"),
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _nome_branch(nome: str) -> str:
    return f"lavoro/{nome}"


def _radice_worktree(nome: str) -> Path:
    repo = _repo_root()
    return repo.parent / ".lavori" / nome


def _git(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def _crea_symlink_condivisi(worktree: Path, repo: Path) -> None:
    """Crea i symlink dalle directory del worktree a quelle del repo principale."""
    for dentro_wt, dentro_repo in COLLEGAMENTI:
        target = repo / dentro_repo
        target.mkdir(parents=True, exist_ok=True)
        link = worktree / dentro_wt
        rel = os.path.relpath(target, link.parent)
        if link.is_symlink():
            if os.readlink(link) == rel:
                continue
            link.unlink()
        elif link.exists():
            # Se esiste una directory vuota (possibile se git l'ha creata),
            # la rimuoviamo; altrimenti non sovrascriviamo dati.
            if link.is_dir() and not any(link.iterdir()):
                link.rmdir()
            else:
                raise RuntimeError(
                    f"{link} esiste gia' e non e' un symlink vuoto; non lo sovrascrivo"
                )
        link.symlink_to(rel, target_is_directory=True)


def _rimuovi_symlink_condivisi(worktree: Path) -> None:
    """Rimuove i symlink creati da _crea_symlink_condivisi, se presenti."""
    for dentro_wt, _ in COLLEGAMENTI:
        link = worktree / dentro_wt
        if link.is_symlink():
            link.unlink()


def apri(nome: str) -> Path:
    """Crea un worktree per la sessione <nome> e condivide lo stato."""
    if "/" in nome or nome.startswith(".") or not nome:
        raise ValueError(f"nome non valido: {nome!r}")

    repo = _repo_root()
    branch = _nome_branch(nome)
    worktree = _radice_worktree(nome)

    if worktree.exists():
        raise RuntimeError(f"il percorso {worktree} esiste gia'")

    # Crea la directory genitore se manca.
    worktree.parent.mkdir(parents=True, exist_ok=True)

    # Crea il worktree e il ramo.
    _git(
        ["worktree", "add", "-b", branch, str(worktree), "HEAD"],
        cwd=repo,
        check=True,
    )

    try:
        _crea_symlink_condivisi(worktree, repo)
    except Exception:
        # Se qualcosa va storto, lasciamo pulito.
        _rimuovi_symlink_condivisi(worktree)
        _git(["worktree", "remove", "-f", str(worktree)], cwd=repo, check=False)
        raise

    rel = os.path.relpath(worktree, Path.cwd())
    print(rel)
    return worktree


def _worktree_attuali(repo: Path) -> list[dict[str, str]]:
    """Legge `git worktree list --porcelain` e torna una lista di worktree."""
    r = _git(["worktree", "list", "--porcelain"], cwd=repo, check=True)
    worktrees: list[dict[str, str]] = []
    corrente: dict[str, str] = {}
    for riga in r.stdout.splitlines():
        if not riga:
            if corrente:
                worktrees.append(corrente)
                corrente = {}
            continue
        if " " in riga:
            chiave, valore = riga.split(" ", 1)
        else:
            chiave, valore = riga, ""
        corrente[chiave] = valore
    if corrente:
        worktrees.append(corrente)
    return worktrees


def _modifiche_non_committate(worktree: Path) -> list[str]:
    """Restituisce le righe non vuote di `git status --porcelain`."""
    r = _git(["status", "--porcelain"], cwd=worktree, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def _format_durata(secondi: float) -> str:
    if secondi < 60:
        return f"{int(secondi)}s"
    if secondi < 3600:
        return f"{int(secondi / 60)}m"
    if secondi < 86400:
        return f"{int(secondi / 3600)}h"
    return f"{int(secondi / 86400)}g"


def _fermo_da(worktree: Path) -> float | None:
    """Quanti secondi fa e' stata l'ultima attivita' nel worktree.

    Usa il piu' recente fra l'ultimo commit e la mtime della directory .git del
    worktree, cosi' anche modifiche non committate (file toccati) aggiornano il
    contatore.
    """
    ultimo = 0.0
    r = _git(["log", "-1", "--format=%ct"], cwd=worktree, check=False)
    if r.returncode == 0 and r.stdout.strip():
        ultimo = max(ultimo, int(r.stdout.strip()))
    git_file = worktree / ".git"
    if git_file.exists():
        ultimo = max(ultimo, git_file.stat().st_mtime)
    if ultimo == 0.0:
        return None
    return time.time() - ultimo


def stato() -> list[dict[str, str]]:
    """Elenca i worktree aperti con ramo, stato modifiche e tempo di inattivita'."""
    repo = _repo_root()
    worktrees = _worktree_attuali(repo)
    risultato: list[dict[str, str]] = []
    for wt in worktrees:
        percorso = wt.get("worktree", "")
        branch = wt.get("branch", "")
        if not percorso or not branch:
            continue
        if branch == "(detached HEAD)":
            continue
        wt_path = Path(percorso)
        if not wt_path.exists():
            continue
        modifiche = _modifiche_non_committate(wt_path)
        fermo = _fermo_da(wt_path)
        risultato.append(
            {
                "percorso": percorso,
                "branch": branch,
                "modifiche": f"{len(modifiche)}" if modifiche else "pulito",
                "fermo": _format_durata(fermo) if fermo is not None else "?",
            }
        )
    return risultato


def chiudi(nome: str, forza: bool = False) -> None:
    """Fonde il ramo lavoro/<nome> in main e rimuove il worktree."""
    repo = _repo_root()
    branch = _nome_branch(nome)
    worktree = _radice_worktree(nome)

    if not worktree.exists():
        raise RuntimeError(f"nessun worktree trovato per '{nome}'")

    # Verifica che git lo conosca.
    wts = _worktree_attuali(repo)
    conosciuto = any(wt.get("branch", "") == branch for wt in wts)
    if not conosciuto:
        raise RuntimeError(f"{worktree} non e' un worktree git noto")

    modifiche = _modifiche_non_committate(worktree)
    if modifiche and not forza:
        raise RuntimeError(
            f"il worktree '{nome}' ha {len(modifiche)} modifiche non committate; "
            "committa o usa --forza per eliminarlo perdendo il lavoro"
        )

    # Merge nel repo principale.
    _git(["merge", "--no-ff", branch, "-m", f"chiude {branch}"], cwd=repo, check=True)

    # Toglie i symlink prima di rimuovere il worktree, perche' git worktree
    # remove potrebbe lamentarsi di directory puntate fuori.
    _rimuovi_symlink_condivisi(worktree)

    _git(["worktree", "remove", str(worktree)], cwd=repo, check=True)

    # Il ramo, dopo il merge, puo' essere cancellato.
    _git(["branch", "-d", branch], cwd=repo, check=False)

    # Se la directory .lavori e' vuota, la rimuoviamo.
    parent = worktree.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()

    print(f"worktree '{nome}' chiuso e {branch} unito a main")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Worktree per sessione di Elechim")
    sub = ap.add_subparsers(dest="comando", required=True)

    p_apri = sub.add_parser("apri", help="crea un worktree per la sessione")
    p_apri.add_argument("nome", help="nome della sessione (diventa ramo lavoro/<nome>)")

    sub.add_parser("stato", help="elenca i worktree aperti")

    p_chiudi = sub.add_parser("chiudi", help="fonde il ramo in main e rimuove il worktree")
    p_chiudi.add_argument("nome", help="nome della sessione")
    p_chiudi.add_argument("--forza", action="store_true", help="chiudi anche se ci sono modifiche non committate")

    args = ap.parse_args(argv)

    try:
        if args.comando == "apri":
            apri(args.nome)
        elif args.comando == "stato":
            righe = stato()
            if not righe:
                print("nessun worktree aperto")
                return 0
            print(f"{'worktree':<40} {'branch':<25} {'modifiche':<10} fermo")
            for riga in righe:
                print(
                    f"{riga['percorso']:<40} "
                    f"{riga['branch']:<25} "
                    f"{riga['modifiche']:<10} "
                    f"{riga['fermo']}"
                )
        elif args.comando == "chiudi":
            chiudi(args.nome, forza=args.forza)
    except RuntimeError as e:
        print(f"errore: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"errore: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
