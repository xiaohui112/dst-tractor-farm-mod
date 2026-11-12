@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
set "AOM_MOD=%~dp0Tractor"
set "AOM_TOOL=%~1"
set "AOM_GAME=%~2"
if not defined AOM_TOOL if exist "%ProgramFiles(x86)%\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe" set "AOM_TOOL=%ProgramFiles(x86)%\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe"
if defined AOM_TOOL goto tool_ready
echo Drag scml.exe from the complete installed Don't Starve Mod Tools folder here.
set /p "AOM_TOOL=Full path to scml.exe: "
:tool_ready
set "AOM_TOOL=%AOM_TOOL:"=%"
if not exist "%AOM_TOOL%" goto no_tool
for %%F in ("%AOM_TOOL%") do set "AOM_TOOL_ROOT=%%~dpF"
if not defined AOM_GAME if exist "%ProgramFiles(x86)%\Steam\steamapps\common\Don't Starve Together\data" set "AOM_GAME=%ProgramFiles(x86)%\Steam\steamapps\common\Don't Starve Together"
if defined AOM_GAME goto game_ready
echo In Steam: Don't Starve Together - Manage - Browse local files.
echo Drag the GAME FOLDER here, not a shortcut or the exe.
set /p "AOM_GAME=Full path to game folder: "
:game_ready
set "AOM_GAME=%AOM_GAME:"=%"
if not exist "%AOM_GAME%\data" goto no_game
set "AOM_PY=%AOM_TOOL_ROOT%buildtools\windows\Python27\python.exe"
if exist "%AOM_PY%" goto python_ready
set "AOM_PY=%AOM_TOOL_ROOT%buildtools\win32\Python27\python.exe"
if exist "%AOM_PY%" goto python_ready
echo The bundled Python was not found. Search the complete Mod Tools folder for python.exe.
echo Python 2.7 or Python 3 are both supported. Do not change system security settings.
set /p "AOM_PY=Full path to python.exe: "
set "AOM_PY=%AOM_PY:"=%"
if not exist "%AOM_PY%" goto no_python
:python_ready
if not exist "%~dp0logs" mkdir "%~dp0logs"
copy /y "%~dp0Driver-Pending.lua" "%AOM_MOD%\scripts\aom_driver_visual_bank.lua" >nul
echo [1/2] Compiling the cabin's three views and foreground/background layers...
"%AOM_TOOL%" "%AOM_MOD%\exported\aom_tractor_cabin\aom_tractor_cabin.scml" "%AOM_MOD%" > "%~dp0logs\cabin.log" 2>&1
if errorlevel 1 goto failed
echo [2/2] Reusing the installed game's riding poses, preserving skins and six facings...
"%AOM_PY%" "%~dp0driver_animation.py" --game "%AOM_GAME%" --mod "%AOM_MOD%" --config "%~dp0seat-layout.json" > "%~dp0logs\driver.log" 2>&1
if errorlevel 1 goto failed
call "%~dp0Collect-Driver-Results.cmd"
exit /b %errorlevel%
:no_tool
echo ERROR: scml.exe not found. Keep the entire Mod Tools installation.
goto failed
:no_game
echo ERROR: This is not a Don't Starve Together game folder containing data.
goto failed
:no_python
echo ERROR: Python executable not found.
:failed
echo ERROR: Build incomplete. Send the logs folder back; do not send old results.
pause
exit /b 1
