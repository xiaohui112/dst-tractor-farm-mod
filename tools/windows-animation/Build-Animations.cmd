@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
set "AOM_MOD=%~dp0AgeOfMachines"
set "AOM_SCML=%~1"
if not defined AOM_SCML if exist "%ProgramFiles(x86)%\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe" set "AOM_SCML=%ProgramFiles(x86)%\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe"
if not defined AOM_SCML if exist "%ProgramFiles%\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe" set "AOM_SCML=%ProgramFiles%\Steam\steamapps\common\Don't Starve Mod Tools\mod_tools\scml.exe"
if defined AOM_SCML goto tool_found
echo Find scml.exe inside the installed Don't Starve Mod Tools folder.
echo Drag scml.exe into this window, then press Enter.
set /p "AOM_SCML=Full path: "
:tool_found
set "AOM_SCML=%AOM_SCML:"=%"
if not exist "%AOM_SCML%" goto missing_tool
if not exist "%AOM_MOD%\modinfo.lua" goto missing_mod
if not exist "%~dp0logs" mkdir "%~dp0logs"
echo.
echo [1/3] Building tractor chassis...
"%AOM_SCML%" "%AOM_MOD%\exported\aom_tractor_chassis\aom_tractor_chassis.scml" "%AOM_MOD%" > "%~dp0logs\aom_tractor_chassis.log" 2>&1
if errorlevel 1 goto build_failed
echo [2/3] Building attachment items...
"%AOM_SCML%" "%AOM_MOD%\exported\aom_attachment_shared\aom_attachment_shared.scml" "%AOM_MOD%" > "%~dp0logs\aom_attachment_shared.log" 2>&1
if errorlevel 1 goto build_failed
echo [3/3] Building attachment symbols...
"%AOM_SCML%" "%AOM_MOD%\exported\aom_attachment_symbols\aom_attachment_symbols.scml" "%AOM_MOD%" > "%~dp0logs\aom_attachment_symbols.log" 2>&1
if errorlevel 1 goto build_failed
echo.
call "%~dp0Collect-Results.cmd"
exit /b %errorlevel%
:missing_tool
echo ERROR: scml.exe was not found. Install Don't Starve Mod Tools in Steam.
echo Keep the whole tool folder. Do not copy scml.exe alone.
goto failed
:missing_mod
echo ERROR: AgeOfMachines folder missing. Extract the complete ZIP first.
goto failed
:build_failed
echo ERROR: Compilation failed. See the logs folder.
echo Send logs and Source-Manifest.json back for diagnosis.
:failed
pause
exit /b 1
