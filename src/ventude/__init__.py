"""Ventude: Dynamic Island e launcher para Windows."""

__version__ = "0.3.0"


def main() -> int:
    from ventude.app import run

    return run()
