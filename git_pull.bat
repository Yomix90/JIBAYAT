@echo off
title JIBAYAT — Git Pull (Mise à jour du code)
color 0B
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   JIBAYAT — Mise à jour depuis GitHub   ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

echo [1/2] Récupération des modifications...
git pull origin main

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  ❌ Erreur lors du git pull !
    echo     Vérifiez votre connexion internet et les droits d'accès.
    pause
    exit /b 1
)

echo.
echo  ✅ Code mis à jour avec succès !
echo.
pause
