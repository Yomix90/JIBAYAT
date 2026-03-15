@echo off
title JIBAYAT — Build EXE (PyInstaller)
color 0A
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     JIBAYAT — Construction de l'EXE     ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

set PYTHON=C:\Python314\python.exe

REM ── Vérification Python ─────────────────────
if not exist "%PYTHON%" (
    color 0C
    echo  ❌ Python 3.14 introuvable : %PYTHON%
    echo     Vérifiez l'installation de Python.
    pause
    exit /b 1
)

REM ── Vérification PyInstaller ─────────────────
%PYTHON% -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ⚠️  PyInstaller non installé. Installation en cours...
    %PYTHON% -m pip install pyinstaller
)

REM ── Lecture version ─────────────────────────
set /p VERSION=<version.txt
echo  📦 Version actuelle : %VERSION%
echo.

REM ── Nettoyage ancien build ───────────────────
echo [1/3] Nettoyage des anciens fichiers...
if exist "dist\JIBAYAT" (
    rmdir /s /q "dist\JIBAYAT"
)
if exist "build\launcher" (
    rmdir /s /q "build\launcher"
)

REM ── Build PyInstaller ────────────────────────
echo.
echo [2/3] Construction de l'EXE (peut prendre 2-4 minutes)...
echo.
%PYTHON% -m PyInstaller launcher.spec

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  ❌ Erreur lors du build !
    pause
    exit /b 1
)

REM ── Vérification résultat ────────────────────
if not exist "dist\JIBAYAT\JIBAYAT.exe" (
    color 0C
    echo  ❌ EXE non trouvé après le build !
    pause
    exit /b 1
)

REM ── Résultat ─────────────────────────────────
echo.
echo [3/3] Calcul de la taille...
for /f %%s in ('powershell -command "(Get-ChildItem -Recurse dist\JIBAYAT | Measure-Object -Property Length -Sum).Sum / 1MB"') do set SIZE=%%s

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   ✅ BUILD RÉUSSI — Version %VERSION%       
echo  ║   📁 dist\JIBAYAT\JIBAYAT.exe            ║
echo  ║   💾 Taille : ~%SIZE% MB                 
echo  ╚══════════════════════════════════════════╝
echo.
echo  Pour distribuer : copiez le dossier dist\JIBAYAT\ entier.
echo  N'oubliez pas d'y ajouter : fiscalite.db + config.json
echo.

REM ── Ouvrir le dossier dist ───────────────────
set /p OPEN="Ouvrir le dossier dist\ maintenant ? (O/N) : "
if /i "%OPEN%"=="O" explorer "dist\JIBAYAT"

pause
