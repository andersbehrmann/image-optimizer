#!/usr/bin/env python3
"""
Boot script för macOS .app: sätter miljö INNAN tkinter/main laddas.

Apples system-Tk 8.5 kraschar ofta på nyare macOS (TkpInit → Tcl_Panic).
Om PyInstaller packat med Tcl/Tk från python.org-installationen finns de under
sys._MEIPASS; vi pekar TCL_LIBRARY/TK_LIBRARY dit så _tkinter inte länkar fel Tk.
"""
import os
import sys
from pathlib import Path


def _setup_macos_embedded_tcl_tk():
    """Använd Tcl/Tk som följer med .app (från bygg-Python), inte systemets Tk 8.5.

    Stödjer både Pyhton.org-layouter:
    - Tcl.framework/Tk.framework
    - lib/tcl8.x/init.tcl och lib/tk8.x/tk.tcl
    """
    if sys.platform != 'darwin' or not getattr(sys, 'frozen', False):
        return
    if not hasattr(sys, '_MEIPASS'):
        return

    me = Path(sys._MEIPASS)

    def _find_best_tcl_file(root: Path, filename: str) -> Path | None:
        candidates = [p for p in root.rglob(filename) if p.is_file()]
        if not candidates:
            return None

        # Heuristik: om *.framework finns, preferera dem. Annars räcker lib/tcl*/lib/tk*.
        def _score(p: Path) -> int:
            sp = str(p)
            if 'Tcl.framework' in sp or 'Tk.framework' in sp:
                return 0
            if 'tcl8.' in sp or 'tk8.' in sp:
                return 1
            return 2

        return sorted(candidates, key=_score)[0]

    init_tcl = _find_best_tcl_file(me, 'init.tcl')
    tk_tcl = _find_best_tcl_file(me, 'tk.tcl')

    if init_tcl:
        os.environ['TCL_LIBRARY'] = str(init_tcl.parent)
    if tk_tcl:
        os.environ['TK_LIBRARY'] = str(tk_tcl.parent)


# Miljö innan något Tk-relaterat laddas
if sys.platform == 'darwin':
    os.environ.setdefault('TK_SILENCE_DEPRECATION', '1')
    _setup_macos_embedded_tcl_tk()

import main  # noqa: E402

if __name__ == '__main__':
    main.main()
