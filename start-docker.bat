@echo off
REM Script de démarrage rapide pour Docker sur Windows

echo ==========================================
echo  Piezo Dataset Builder - Docker Startup
echo ==========================================
echo.

REM Vérifier que Docker est en cours d'exécution
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [31mDocker n'est pas en cours d'execution. Veuillez demarrer Docker Desktop.[0m
    pause
    exit /b 1
)

echo [32mDocker est pret[0m
echo.

echo Choisissez une option :
echo 1. Demarrage rapide (docker-compose)
echo 2. Build et demarrage
echo 3. Arreter l'application
echo 4. Nettoyer et reconstruire
echo.
set /p choice="Votre choix [1-4] : "

if "%choice%"=="1" (
    echo.
    echo Demarrage de l'application...
    docker-compose up -d
    goto success
)

if "%choice%"=="2" (
    echo.
    echo Construction de l'image...
    docker-compose build
    echo Demarrage de l'application...
    docker-compose up -d
    goto success
)

if "%choice%"=="3" (
    echo.
    echo Arret de l'application...
    docker-compose down
    goto stopped
)

if "%choice%"=="4" (
    echo.
    echo Nettoyage complet...
    docker-compose down -v
    echo Reconstruction de l'image...
    docker-compose build --no-cache
    echo Demarrage de l'application...
    docker-compose up -d
    goto success
)

echo [31mOption invalide[0m
pause
exit /b 1

:success
echo.
echo [32mApplication demarree avec succes ![0m
echo.
echo Acces a l'application sur :
echo   http://localhost:8501
echo.
echo Voir les logs :
echo   docker-compose logs -f
echo.
echo Arreter l'application :
echo   docker-compose down
echo.
pause
exit /b 0

:stopped
echo.
echo [32mApplication arretee[0m
echo.
pause
exit /b 0
