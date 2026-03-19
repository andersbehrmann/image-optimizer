# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

datas = [('config.json', '.')]
datas += collect_data_files('certifi')
datas += collect_data_files('tkinterdnd2')

# --- Tcl/Tk: måste följa med appen på macOS 26+ (systemets Tk 8.5 kraschar i TkpInit).
# python.org-installerade Python har Tcl.framework + Tk.framework under sys.base_prefix.
_base = Path(getattr(sys, 'base_prefix', sys.prefix)).resolve()

_fw_tcl = _base / 'Frameworks' / 'Tcl.framework'
_fw_tk = _base / 'Frameworks' / 'Tk.framework'
_has_frameworks = _fw_tcl.is_dir() and _fw_tk.is_dir()

# Layout 1: frameworks (Tcl.framework / Tk.framework)
if _has_frameworks:
    for _name in ('Tcl.framework', 'Tk.framework'):
        _src = _base / 'Frameworks' / _name
        if _src.is_dir():
            # PyInstaller expects hook-style 2-tuples: (src_dir_or_glob, trg_dir)
            datas.append((str(_src), _name))

# Layout 2: lib/tcl8.x + lib/tk8.x (utan *.framework)
else:
    _lib = _base / 'lib'
    if _lib.is_dir():
        _tcl_dirs = sorted(_lib.glob('tcl8.*'))
        _tk_dirs = sorted(_lib.glob('tk8.*'))
        if _tcl_dirs:
            _tcl = _tcl_dirs[-1]  # senaste matchen
            datas.append((str(_tcl), _tcl.name))
        if _tk_dirs:
            _tk = _tk_dirs[-1]  # senaste matchen
            datas.append((str(_tk), _tk.name))

a = Analysis(
    ['boot.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'certifi',
        'gui_app',
        'tkinterdnd2',
        'PIL',
        'tinify',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Image Optimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Image Optimizer',
)
app = BUNDLE(
    coll,
    name='Image Optimizer.app',
    icon='icon.icns',
    bundle_identifier='com.imageoptimizer.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleDisplayName': 'Image Optimizer',
        'CFBundleName': 'Image Optimizer',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'JPEG Image',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['public.jpeg', 'public.png'],
                'CFBundleTypeExtensions': ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG'],
            }
        ],
    },
)
