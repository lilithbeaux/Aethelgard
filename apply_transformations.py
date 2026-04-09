"""
ÆTHELGARD OS — Mass Transformation Script
Applies all name/language changes to remaining source files.

Run this from the moruk-os project root:
  python apply_transformations.py

It will modify files in-place.
"""

import re
import os
from pathlib import Path

# ── Substitution rules (order matters — most specific first) ──────────
SUBSTITUTIONS = [
    # Brand names
    ("Moruk AI OS",             "ÆTHELGARD OS"),
    ("Moruk OS",                "ÆTHELGARD OS"),
    ("MORUK OS",                "ÆTHELGARD OS"),
    ("Moruk",                   "ÆTHELGARD OS"),
    ("MORUK",                   "ÆTHELGARD OS"),
    ("moruk-os",                "aethelgard"),
    ("moruk_os",                "aethelgard"),
    ("moruk",                   "aethelgard"),

    # German → English common phrases in code
    ("Lade",                    "Loading"),
    ("Fehler",                  "Error"),
    ("Warnung",                 "Warning"),
    ("Einstellungen",           "Settings"),
    ("Speichern",               "Save"),
    ("Abbrechen",               "Cancel"),
    ("Bestätigen",              "Confirm"),
    ("Schließen",               "Close"),
    ("Laden",                   "Load"),
    ("Neu",                     "New"),
    ("Alle",                    "All"),
    ("Keine",                   "None"),
    ("Verbindung",              "Connection"),
    ("Modell",                  "Model"),
    ("Anbieter",                "Provider"),
    ("Schlüssel",               "Key"),
    ("Sitzung",                 "Session"),
    ("Protokoll",               "Log"),
    ("Aufgaben",                "Tasks"),
    ("Ziele",                   "Goals"),
    ("Erinnerung",              "Memory"),
    ("Reflexion",               "Reflection"),
    ("Statistiken",             "Statistics"),
    ("Autonomie",               "Autonomy"),
    ("Gedächtnis",              "Memory"),
    ("Wiederherstellung",       "Recovery"),
    ("Gesundheit",              "Health"),
    ("aktiv",                   "active"),
    ("inaktiv",                 "inactive"),
    ("wird ausgeführt",         "executing"),
    ("abgeschlossen",           "completed"),
    ("fehlgeschlagen",          "failed"),
    ("Aufgabe erstellt",        "Task created"),
    ("Konfigurieren",           "Configure"),
    ("Konfiguration",           "Configuration"),

    # UI strings
    ("Guten Morgen",            "Good Morning"),
    ("Guten Abend",             "Good Evening"),
    ("Willkommen",              "Welcome"),
    ("Herzlich",                "Warmly"),
    ("Bitte warten",            "Please wait"),
    ("Verarbeite",              "Processing"),
    ("Denke nach",              "Thinking"),
    ("Neustart",                "Restart"),
    ("Herunterfahren",          "Shutdown"),
    ("Starten",                 "Start"),
    ("Stoppen",                 "Stop"),
    ("Pause",                   "Pause"),
    ("Fortsetzen",              "Resume"),
    ("Löschen",                 "Delete"),

    # File/data refs (lowercase only — avoid mangling Python syntax)
    ('data/logs',               'data/logs'),  # Keep as-is
    ('"moruk"',                 '"aethelgard"'),
    ("'moruk'",                 "'aethelgard'"),

    # Title bar
    ("MORUK",                   "ÆTHELGARD OS"),
]

# Files to skip
SKIP_DIRS  = {'.git', 'venv', '__pycache__', 'node_modules', '.mypy_cache'}
SKIP_FILES = {'apply_transformations.py', 'TRANSFORMATION_MANIFEST.md'}

def transform_file(path: Path) -> int:
    """Apply all substitutions to a file. Returns count of changes."""
    try:
        original = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"  SKIP (read error): {path}: {e}")
        return 0

    modified = original
    for old, new in SUBSTITUTIONS:
        modified = modified.replace(old, new)

    if modified != original:
        try:
            path.write_text(modified, encoding='utf-8')
            count = sum(original.count(old) for old, _ in SUBSTITUTIONS)
            return max(1, count)
        except Exception as e:
            print(f"  FAIL (write error): {path}: {e}")
    return 0

def main():
    root = Path(__file__).parent
    total_files   = 0
    total_changes = 0

    for ext in ['*.py', '*.txt', '*.md', '*.json', '*.sh']:
        for path in root.rglob(ext):
            # Skip excluded dirs
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            if path.name in SKIP_FILES:
                continue

            n = transform_file(path)
            if n > 0:
                print(f"  ✓ {path.relative_to(root)} ({n} changes)")
                total_files   += 1
                total_changes += n

    print(f"\n{'='*50}")
    print(f"Transformation complete: {total_files} files, ~{total_changes} changes")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
