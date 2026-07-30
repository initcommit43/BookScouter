# Zentrale Konfigurationswerte, u.a. für Rate-Limiting und User-Agent.

import os
import sys
from pathlib import Path

USER_AGENT = "BookScouter/0.1 (lokales Preisvergleichs-Tool; privat genutzt)"

# Mindestabstand zwischen aufeinanderfolgenden Requests an denselben Shop, in Sekunden.
REQUEST_DELAY_SECONDS = 2.0


def _daten_verzeichnis() -> Path:
    """Fester Ablageort für die Preis-Datenbank im Benutzerprofil.

    Ein relativer Pfad würde dem Arbeitsverzeichnis folgen: als
    PyInstaller-Onefile-.exe startet die App dort, wo gerade doppelgeklickt
    wird, und jeder Ordner bekäme seine eigene, leere Preishistorie.
    """
    if sys.platform == "win32":
        basis = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        basis = Path.home() / "Library" / "Application Support"
    else:
        basis = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(basis) / "BookScouter"


DB_PATH = str(_daten_verzeichnis() / "bookscouter.db")
