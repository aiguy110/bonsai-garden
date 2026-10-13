"""Inventory: diagnostics helper. Use log() instead of print()."""
import sys


def log(msg: str) -> None:
    """Inventory: write a diagnostic line to stderr."""
    sys.stderr.write(f"[inventory] {msg}\n")
