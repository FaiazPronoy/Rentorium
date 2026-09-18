@echo off
setlocal
title Rentorium
cd /d "%~dp0"

echo ==========================================
echo   RENTORIUM  -  CSE471
echo ==========================================
echo.

REM ------------------------------------------------------------------
REM  0. Find a Python we can actually use.
REM     The "py" launcher is tried first, because it finds a real
REM     python.org install and skips a conda base environment, which
REM     is usually too new for the pinned packages.
REM ------------------------------------------------------------------
set "PY="

if not defined PY (
  py -3.12 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3.12"
)
if not defined PY (
  py -3.11 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3.11"
)
if not defined PY (
  py -3.13 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3.13"
)
if not defined PY (
  py -3.10 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3.10"
)
if not defined PY (
  py -3 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  python -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo [X] No Python found.
  echo     Install Python 3.11 or 3.12 from python.org and tick
  echo     "Add python.exe to PATH" on the first installer screen.
  echo.
  pause
  exit /b 1
)

echo [0/5] Using: %PY%
%PY% -c "import sys;print('      Python '+sys.version.split()[0]+'  ->  '+sys.executable)"
echo.

REM ------------------------------------------------------------------
REM  1. Unpack, only if it has never been unpacked.
REM ------------------------------------------------------------------
if not exist "Rentorium-v2\" (
  echo [1/5] Extracting Rentorium-v2.zip ...
  powershell -NoProfile -Command "Expand-Archive -Path 'Rentorium-v2.zip' -DestinationPath '.' -Force"
) else (
  echo [1/5] Already extracted.
)

cd "Rentorium-v2"
set "VENV=%CD%\.venv"
set "VPY=%VENV%\Scripts\python.exe"

REM ------------------------------------------------------------------
REM  2. The virtual environment.
REM     A folder alone is not proof: if python.exe is not inside it the
REM     environment is half built, activate.bat silently does nothing,
REM     and every command afterwards runs against the wrong Python.
REM     So the folder is thrown away and made again.
REM ------------------------------------------------------------------
if exist "%VENV%\" (
  if not exist "%VPY%" (
    echo [2/5] The old virtual environment is broken - rebuilding it ...
    rmdir /s /q "%VENV%"
  )
)

if not exist "%VPY%" (
  echo [2/5] Creating the virtual environment ...
  %PY% -m venv "%VENV%"
) else (
  echo [2/5] Virtual environment ready.
)

if not exist "%VPY%" (
  echo.
  echo [X] The virtual environment could not be created.
  echo     Try once by hand, from inside this folder:
  echo         %PY% -m venv .venv
  echo.
  pause
  exit /b 1
)

REM ------------------------------------------------------------------
REM  3. Packages. Every call uses the environment's own python.exe by
REM     full path, never "python" off the PATH, so there is nothing for
REM     activate.bat to get wrong.
REM ------------------------------------------------------------------
echo [3/5] Installing Django and Pillow ...
"%VPY%" -m pip install --quiet --disable-pip-version-check --upgrade pip setuptools wheel
"%VPY%" -m pip install --quiet --disable-pip-version-check -r "requirements.txt"

"%VPY%" -c "import django, PIL" >nul 2>&1
if errorlevel 1 (
  echo       that did not work - trying the newest versions instead ...
  "%VPY%" -m pip install --disable-pip-version-check --upgrade "Django" "Pillow"
)

"%VPY%" -c "import django, PIL" >nul 2>&1
if errorlevel 1 (
  echo.
  echo [X] Django or Pillow would not install.
  echo     Run this by hand to see the real error:
  echo         "%VPY%" -m pip install Django Pillow
  echo.
  pause
  exit /b 1
)
"%VPY%" -c "import django,PIL;print('      Django '+django.get_version()+'   Pillow '+PIL.__version__)"

REM ------------------------------------------------------------------
REM  4. Database.
REM ------------------------------------------------------------------
cd "Rentorium"

set "FRESH=0"
if not exist "db.sqlite3" set "FRESH=1"

echo [4/5] Preparing the database ...
"%VPY%" manage.py migrate --noinput
if errorlevel 1 (
  echo.
  echo [X] The database could not be prepared. See the error above.
  pause
  exit /b 1
)
if "%FRESH%"=="1" (
  echo       Loading demo data ...
  "%VPY%" manage.py seed_demo
)

REM ------------------------------------------------------------------
REM  5. Serve.
REM ------------------------------------------------------------------
echo [5/5] Starting the server ...
echo.
echo   Open  http://127.0.0.1:8000/
echo.
echo   Owner    faiaz@rentorium.test  /  Rentorium@2026
echo   Agent    agent@rentorium.test  /  Agent@2026
echo   Renter   rafid@rentorium.test  /  Rentorium@2026
echo   Django admin at /admin/   admin / Admin@2026
echo.
echo   Press Ctrl+C in this window to stop.
echo.

REM open the browser a few seconds later, once the server is actually up
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:8000/"

"%VPY%" manage.py runserver
pause
