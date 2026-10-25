@echo off
setlocal
title Rentorium
cd /d "%~dp0"

echo ==========================================
echo   RENTORIUM
echo ==========================================
echo.

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

echo [0/4] Using: %PY%
%PY% -c "import sys;print('      Python '+sys.version.split()[0]+'  at  '+sys.executable)"
echo.

set "VENV=%CD%\.venv"
set "VPY=%VENV%\Scripts\python.exe"

if exist "%VENV%\" (
  if not exist "%VPY%" (
    echo [1/4] The old virtual environment is broken, rebuilding it ...
    rmdir /s /q "%VENV%"
  )
)

if not exist "%VPY%" (
  echo [1/4] Creating the virtual environment ...
  %PY% -m venv "%VENV%"
) else (
  echo [1/4] Virtual environment ready.
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

echo [2/4] Installing Django and Pillow ...
"%VPY%" -m pip install --quiet --disable-pip-version-check --upgrade pip setuptools wheel
"%VPY%" -m pip install --quiet --disable-pip-version-check -r "requirements.txt"

"%VPY%" -c "import django, PIL" >nul 2>&1
if errorlevel 1 (
  echo       that did not work, trying the newest versions instead ...
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

cd "Rentorium"

if not exist ".env" (
  echo       Writing a local .env from .env.example ...
  copy /y ".env.example" ".env" >nul
)

set "FRESH=0"
if not exist "db.sqlite3" set "FRESH=1"

echo [3/4] Preparing the database ...
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

echo [4/4] Starting the server ...
echo.
echo   Open  http://127.0.0.1:8000/
echo.
echo   Owner    faiaz@rentorium.test  /  Rentorium@2026
echo   Agent    agent@rentorium.test  /  Agent@2026
echo   Renter   rafid@rentorium.test  /  Rentorium@2026
echo.
echo   Press Ctrl+C in this window to stop.
echo.

start "" /min cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:8000/"

"%VPY%" manage.py runserver
pause
