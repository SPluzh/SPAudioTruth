# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).parent
BIN_DIR = ROOT / "bin"

FFMPEG_FILES = [
    "ffmpeg.exe",
    "ffprobe.exe",
    "avcodec-61.dll",
    "avfilter-10.dll",
    "avformat-61.dll",
    "avutil-59.dll",
    "swresample-5.dll",
]

# Place ffmpeg/ffprobe and their DLLs in datas so PyInstaller does not
# scan their dependencies and duplicate av*.dll in _internal\.
ffmpeg_datas = [
    (str(BIN_DIR / name), "bin")
    for name in FFMPEG_FILES
    if (BIN_DIR / name).is_file()
]

version_file = ROOT / "src" / "version.txt"
if version_file.is_file():
    ffmpeg_datas.append((str(version_file), "src"))

EXCLUDES = [
    "scipy",
    "PyQt5",
    "PyQt6",
    "tkinter",
    "pytest",
    "IPython",
    "jupyter",
    # Unused stdlib / networking / dev tools
    "ssl",
    "_ssl",
    "certifi",
    "urllib3",
    "charset_normalizer",
    "http",
    "xmlrpc",
    "ftplib",
    "smtplib",
    "socketserver",
    "pydoc",
    "doctest",
    "pdb",
    "bdb",
    "profile",
    "cProfile",
    "pstats",
    "venv",
    "ensurepip",
    "distutils",
    "setuptools",
    "pkg_resources",
    "psutil",
    "yaml",
    "markupsafe",
    "win32com",
    "pywin32",
    "win32api",
    "pythoncom",
    "pywintypes",
    "multiprocessing",
    # Unused matplotlib backends
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_wxagg",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_gtk4agg",
    "matplotlib.backends.backend_macosx",
    "matplotlib.backends.backend_webagg",
    "matplotlib.backends.backend_pgf",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_ps",
    "matplotlib.backends.backend_svg",
    # Unused PySide6 modules
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DExtras",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtSql",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtTest",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
]

a = Analysis(
    [str(ROOT / "src" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=ffmpeg_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,
)

# Post-filter unused binaries (Qt plugins/DLLs, PIL codecs, OpenSSL)
_DROP_BINARY_SUBSTRINGS = (
    "opengl32sw.dll",
    "qt6quick",
    "qt6qml",
    "qt6pdf",
    "qt6opengl",
    "qt6network",
    "qtnetwork.pyd",
    "qt6virtualkeyboard",
    "qt6shadertools",
    "qdirect2d.dll",
    "libcrypto-3.dll",
    "libssl-3.dll",
    "_avif",
    "_webp",
    "_imagingcms",
    "_imagingtk",
)
_DROP_IMAGEFORMATS = (
    "qpdf.dll",
    "qjpeg.dll",
    "qwebp.dll",
    "qtiff.dll",
    "qgif.dll",
    "qicns.dll",
    "qtga.dll",
    "qwbmp.dll",
)

_DROP_FFMPEG_ROOT_DLLS = {
    "avcodec-61.dll",
    "avfilter-10.dll",
    "avformat-61.dll",
    "avutil-59.dll",
    "swresample-5.dll",
}


def _keep_binary(entry) -> bool:
    name = entry[0].replace("\\", "/").lower()
    if not name.startswith("bin/") and name.rsplit("/", 1)[-1] in _DROP_FFMPEG_ROOT_DLLS:
        return False
    if any(s in name for s in _DROP_BINARY_SUBSTRINGS):
        return False
    if "imageformats/" in name and any(name.endswith(x) for x in _DROP_IMAGEFORMATS):
        return False
    return True


a.binaries = [b for b in a.binaries if _keep_binary(b)]

# Post-filter unused data files (Qt translations, extra matplotlib fonts & sample_data)
_KEEP_MPL_FONTS = {
    "dejavusans.ttf",
    "dejavusans-bold.ttf",
    "dejavusansmono.ttf",
    "lastresorthe-regular.ttf",
}


def _keep_data(entry) -> bool:
    name = entry[0].replace("\\", "/").lower()
    if "pyside6/translations/" in name:
        return False
    if "matplotlib/mpl-data/fonts/" in name:
        fname = name.rsplit("/", 1)[-1]
        return fname in _KEEP_MPL_FONTS
    if "matplotlib/mpl-data/sample_data/" in name or "matplotlib/mpl-data/stylelib/" in name:
        return False
    return True


a.datas = [d for d in a.datas if _keep_data(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SPAudioTruth",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SPAudioTruth",
)
