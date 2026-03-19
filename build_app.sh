#!/bin/bash

# Bygger macOS-app med PyInstaller.
# Kräver Python med inbyggda Tcl/Tk-frameworks (t.ex. python.org-installer),
# annars använder PyInstaller Apples Tk 8.5 → krasch på macOS 26 (TkpInit / Tcl_Panic).

set -euo pipefail

echo "🎨 Bygger Image Optimizer.app (PyInstaller)..."
echo ""

echo "Kontrollerar Tcl/Tk i denna Python-installation..."
python3 <<'PY'
import sys
from pathlib import Path

base = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()

fw_tcl = base / "Frameworks" / "Tcl.framework"
fw_tk = base / "Frameworks" / "Tk.framework"

has_frameworks = fw_tcl.is_dir() and fw_tk.is_dir()

lib = base / "lib"
has_lib_tcl = False
has_lib_tk = False
if lib.is_dir():
    # Vissa python.org-distributioner levererar Tcl/Tk som lib/tcl8.x + lib/tk8.x (utan *.framework).
    has_lib_tcl = any((d / "init.tcl").is_file() for d in lib.glob("tcl8.*"))
    has_lib_tk = any((d / "tk.tcl").is_file() for d in lib.glob("tk8.*"))

if not (has_frameworks or (has_lib_tcl and has_lib_tk)):
    print("")
    print("❌ Den här Python-installationen verkar sakna Tcl/Tk som går att bunta.")
    print("")
    print("   Förväntade antingen:")
    print("   - Frameworks-läget: Tcl.framework + Tk.framework")
    print("   - Alternativt lib-läget: .../lib/tcl8.x/init.tcl + .../lib/tk8.x/tk.tcl")
    print("")
    print("   Utan detta bundlas Apples system-Tk 8.5 → appen kraschar vid start på macOS 26+ (TkpInit).")
    print("")
    print("   Gör så här:")
    print("   1) Använd en python.org-Python-installation som faktiskt innehåller Tcl/Tk lokalt.")
    print("   2) Bygg med den pythonen (exempel för 3.12):")
    print('      /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m PyInstaller "Image Optimizer.spec"')
    print("")
    sys.exit(1)

if has_frameworks:
    print(f"✓ Tcl/Tk hittade under {base / 'Frameworks'}")
else:
    print(f"✓ Tcl/Tk hittade under {base / 'lib'} (lib/tcl8.x + lib/tk8.x)")
PY

echo ""
echo "Rensar tidigare byggen..."
rm -rf build dist

echo "Bygger..."
python3 -m PyInstaller "Image Optimizer.spec"

if [ -d "dist/Image Optimizer.app" ]; then
    echo ""
    echo "✅ Byggd!"
    echo "📦 dist/Image Optimizer.app"
    echo ""
    echo "💡 Test: dubbelklicka appen, lägg filer i listan, klicka Optimera."
    echo ""
    open dist
else
    echo "❌ Ingen .app skapades"
    exit 1
fi
