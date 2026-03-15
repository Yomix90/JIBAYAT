# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates',      'templates'),
        ('modules',        'modules'),
        ('version.txt',    '.'),
        ('config.json',    '.'),
        ('database.py',    '.'),
        ('app.py',         '.'),
    ],
    hiddenimports=[
        'flask',
        'flask.templating',
        'jinja2',
        'werkzeug',
        'sqlite3',
        'requests',
        'PIL',
        'PIL.Image',
        'pystray',
        'pystray._win32',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'threading',
        'webbrowser',
        'modules.tnb',
        'modules.helpers',
        'modules.config',
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
    name='JIBAYAT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # Pas de fenêtre console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JIBAYAT',
)
