#!/usr/bin/env python3
"""
Image Optimizer - En skrivbordsapp för bildoptimering
Skalar ner, konverterar till WebP och komprimerar bilder med TinyPNG API
"""

import os
import sys

# Fixa macOS Tkinter-meny problem INNAN tkinter importeras
if sys.platform == 'darwin':
    os.environ['TK_SILENCE_DEPRECATION'] = '1'

# Fixa SSL-certifikat för PyInstaller bundle
if getattr(sys, 'frozen', False):
    # Körs som bundlad app
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from pathlib import Path
import subprocess


def _paths_from_argv():
    """Filer/mappar från argv (t.ex. släppta på app-ikonen). Ignorerar macOS-flaggor som -psn_…."""
    out = []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            continue
        try:
            p = Path(arg).expanduser()
            if not p.exists():
                continue
            if p.is_file():
                out.append(str(p.resolve()))
            elif p.is_dir():
                for pattern in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
                    out.extend(str(x.resolve()) for x in p.glob(pattern))
        except OSError:
            continue
    return out


def main():
    def can_start_tk():
        """Checkar om Tk kan startas utan att krascha processen (dev-läge).

        VIKTIGT: I PyInstaller/.app pekar sys.executable på **själva appbinären**, inte Python.
        Att köra subprocess med [sys.executable, '-c', ...] startar då en ny fullständig app
        som också kör main() → can_start_tk() igen → oändligt många instanser (fork bomb).
        """
        if getattr(sys, 'frozen', False):
            return True
        try:
            res = subprocess.run(
                [sys.executable, "-c", "import tkinter as tk; r=tk.Tk(); r.destroy()"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    # Filer från argv (släppta på app-ikonen / Öppna med …) — läggs bara i listan i GUI, ingen auto-konvertering.
    argv_paths = _paths_from_argv()
    initial_files = argv_paths if argv_paths else None

    # tkinterdnd2 kräver ett fungerande Tk. Undvik hård abort genom att först testa i en subprocess.
    if not can_start_tk():
        print(
            "GUI kunde inte starta (Tk abortade i denna miljö). "
            "Prova en annan Python-installation med fungerande Tk, eller kör från terminal: python3 main.py"
        )
        return

    # Lazy-import GUI (Tk) så py2app kan bygga utan att ladda Tk vid import av main.
    import tkinter as tk
    from gui_app import ImageOptimizerApp

    # TkinterDnD.Tk() behövs för drag-n-drop i fönstret; fall tillbaka om import/init misslyckas.
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except Exception as e:
        print(f"TkinterDnD otillgänglig ({e}), använder tk.Tk() — drag-n-drop i fönstret kan saknas.")
        root = tk.Tk()

    # Fixa macOS-menyproblem (historiskt) - men i frysta .app-byggen kan
    # Tk aborta när menyraden sätts. Därför hoppar vi över fixen i frozen-läge.
    if sys.platform == 'darwin' and not getattr(sys, 'frozen', False):
        try:
            menubar = tk.Menu(root)
            root.config(menu=menubar)
        except Exception as e:
            print(f"Varning: Kunde inte skapa menubar: {e}")

    app = ImageOptimizerApp(root, initial_files=initial_files)
    root.mainloop()


if __name__ == "__main__":
    main()
