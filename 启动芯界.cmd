@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
echo [BoundaryLab] Creating a local Python environment...
where py >nul 2>nul
if errorlevel 1 goto systempython
py -3 -m venv .venv
if errorlevel 1 goto error
goto dependencies
:systempython
python -m venv .venv
if errorlevel 1 goto error
:dependencies
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
:run
echo [BoundaryLab] Finding an existing workbench or an available port...
".venv\Scripts\python.exe" -m lab.launch
if errorlevel 1 goto error
goto end
:error
echo Please install Python 3.12 or newer, then try again.
echo Keep this window open to read the error above.
pause
:end
endlocal
