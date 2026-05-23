#!/usr/bin/env python3
"""
Package the deployment artifact
- Zip up azurephotos/
- Exclude tests/, other non-prod files, and git-ignored items

Output: out/azurephotos-<sha>.zip
"""

import itertools
import subprocess
import sys
import threading
import zipfile

from pathlib import Path
from typing import TypeVar

REPO_ROOT = Path(__file__).resolve().parent
SOURCE_DIR = REPO_ROOT / "azurephotos"
OUT_DIR = REPO_ROOT / "out"

# Anything matching these relative paths will be excluded
EXCLUDE_DIRS = {"tests"}


class Spinner:
    """Background spinner that ticks on a timer, independent of work pace."""

    def __init__(self, interval: float = 0.1) -> None:
        self._interval = interval
        self._frames = itertools.cycle("|/-\\")
        self._message = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = sys.stdout.isatty()

    def update(self, message: str) -> None:
        self._message = message  # atomic in CPython; no lock needed

    def _run(self) -> None:
        # Event.wait returns True only when .set() is called; False on timeout.
        while not self._stop.wait(self._interval):
            sys.stdout.write(f"\r\x1b[2K{next(self._frames)} {self._message}")
            sys.stdout.flush()

    def __enter__(self) -> "Spinner":
        if self._enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._thread is not None:
            self._stop.set()
            self._thread.join()
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()


def main() -> int:
    if not SOURCE_DIR.is_dir():
        print(f"Error: Source directory {SOURCE_DIR} does not exist")
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    git_sha = get_git_sha()
    artifact = OUT_DIR / f"azurephotos-{git_sha}.zip"
    if artifact.exists():
        artifact.unlink()  # Remove existing artifact

    count = 0
    files = [p for p in tracked_files() if not should_skip(p)]
    with Spinner() as spinner, zipfile.ZipFile(
        artifact, "w", zipfile.ZIP_DEFLATED
    ) as zf:
        for path in files:
            if not path.is_file():
                continue

            spinner.update(str(path))

            zf.write(path, path.relative_to(SOURCE_DIR))
            count += 1

    print(f"Packaged {count} files into {artifact}")
    print_tree(files, SOURCE_DIR)
    return 0


def get_git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT
            )
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError:
        return "local"


def tracked_files() -> list[Path]:
    try:
        raw = subprocess.check_output(
            ["git", "ls-files", "azurephotos"],
            cwd=REPO_ROOT,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"error: git ls-files failed: ({e})", file=sys.stderr)
        sys.exit(1)

    return [REPO_ROOT / line.strip() for line in raw.splitlines() if line.strip()]


def should_skip(path: Path) -> bool:
    if any(p in EXCLUDE_DIRS for p in path.relative_to(SOURCE_DIR).parts):
        return True

    return False


def print_tree(paths: list[Path], root: Path) -> None:
    """Print paths grouped by directory in a tree layout."""
    tree: dict = {}
    for p in sorted(paths):
        node = tree
        for part in p.relative_to(root).parts:
            node = node.setdefault(part, {})

    def walk(node: dict, prefix: str = "") -> None:
        items = sorted(node.items())
        for i, (name, child) in enumerate(items):
            last = i == len(items) - 1
            connector = "└── " if last else "├── "
            print(f"{prefix}{connector}{name}")
            if child:
                walk(child, prefix + ("    " if last else "│   "))

    print(f"{root.name}/")
    walk(tree)


if __name__ == "__main__":
    sys.exit(main())
