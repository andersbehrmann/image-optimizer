"""
Setup script för att bygga macOS app med py2app
"""
from setuptools import setup
from pathlib import Path
import re


def read_version() -> str:
    version_path = Path(__file__).with_name("VERSION")
    version = version_path.read_text(encoding="utf-8").strip()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError(
            f"Ogiltigt versionsformat i {version_path}: {version!r}. Förväntat: MAJOR.MINOR.PATCH"
        )
    return version


VERSION = read_version()

APP = ['boot.py']
DATA_FILES = [
    ('', ['config.json']),
]
OPTIONS = {
    'argv_emulation': True,  # Viktigt för att hantera filer som släpps på ikonen
    'iconfile': 'icon.icns',  # App-ikon
    'plist': {
        'CFBundleName': 'Image Optimizer',
        'CFBundleDisplayName': 'Image Optimizer',
        'CFBundleIdentifier': 'com.imageoptimizer.app',
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
        'NSHumanReadableCopyright': '© 2025 Image Optimizer',
        'LSUIElement': False,  # Visa i Dock
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'JPEG Image',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['public.jpeg'],
                'CFBundleTypeExtensions': ['jpg', 'jpeg', 'JPG', 'JPEG'],
            }
        ],
        'NSHighResolutionCapable': True,
    },
    # Inkludera tkinterdnd2 explicit så drag-n-drop fungerar i py2app-bygget.
    'packages': ['PIL', 'tinify', 'tkinterdnd2', 'gui_app'],
    'includes': ['tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox', '_tkinter'],
    'excludes': ['tkinter.test'],
}

setup(
    name='ImageOptimizer',
    version=VERSION,
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
