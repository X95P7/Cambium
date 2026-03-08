@echo off
setlocal

set BASE_DIR=%~dp0
cd /d "%BASE_DIR%"

if "%1"=="" goto all
if "%1"=="mod" goto mod
if "%1"=="backend" goto backend
if "%1"=="clients" goto clients
if "%1"=="all" goto all
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="logs" goto logs
if "%1"=="status" goto status
goto usage

:usage
echo Usage: build.bat [mod^|backend^|clients^|all^|start^|stop^|logs^|status]
echo.
echo   mod       Build the Java mod only
echo   backend   Rebuild and restart the backend container
echo   clients   Rebuild and restart headlessmc containers
echo   all       Build everything and start (default)
echo   start     Start containers without rebuilding
echo   stop      Stop all containers
echo   logs      Tail logs from all containers
echo   status    Show container status
goto end

:mod
echo =========================================
echo   Building CambiumMod...
echo =========================================
cd mod\CambiumMod
call gradlew.bat clean build
if errorlevel 1 (
    echo ERROR: Mod build failed
    goto end
)
echo Copying JAR to headlessmc\mods...
copy /Y build\libs\CambiumMod-1.0.jar ..\..\headlessmc\mods\
cd ..\..
echo Mod build complete.
if "%2"=="" goto end
goto %2

:backend
echo =========================================
echo   Building backend...
echo =========================================
docker compose up -d --build backend
echo Backend deployed.
if "%2"=="" goto end
goto %2

:clients
echo =========================================
echo   Building headlessmc clients...
echo =========================================
docker compose up -d --build headlessmc1 headlessmc2
echo Clients deployed.
goto done

:all
call :mod clients_after_mod
goto end

:clients_after_mod
call :backend
call :clients
goto end

:start
echo =========================================
echo   Starting all containers...
echo =========================================
docker compose up -d
goto done

:stop
docker compose down
goto end

:logs
docker compose logs -f
goto end

:status
docker compose ps
goto end

:done
echo.
echo =========================================
echo   Done!
echo =========================================
docker compose ps
echo.
echo Dashboard: http://localhost:8000
echo Minecraft: localhost:25565
echo.
echo View logs:  docker compose logs -f
echo Stop:       docker compose down

:end
endlocal
