@echo off
setlocal DisableDelayedExpansion
set "AOM_KIT_ROOT=%~dp0"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { Add-Type -AssemblyName System.IO.Compression.FileSystem; $root=$env:AOM_KIT_ROOT; $anim=Join-Path $root 'Tractor\anim'; foreach($name in @('aom_tractor_chassis','aom_attachment_shared','aom_attachment_symbols')) { $path=Join-Path $anim ($name+'.zip'); if(!(Test-Path -LiteralPath $path)) { throw ('Missing compiled ZIP: '+$name) }; $zip=[IO.Compression.ZipFile]::OpenRead($path); try { foreach($spec in @(@('build.bin','BILD'),@('anim.bin','ANIM'))) { $entry=$zip.Entries | Where-Object {$_.Name -eq $spec[0]} | Select-Object -First 1; if(!$entry -or $entry.Length -lt 16) { throw ('Missing real '+$spec[0]+' in '+$name) }; $stream=$entry.Open(); try { $buf=New-Object byte[] 4; $read=$stream.Read($buf,0,4); if($read -ne 4 -or [Text.Encoding]::ASCII.GetString($buf) -ne $spec[1]) { throw ('Placeholder or invalid '+$spec[0]+' in '+$name) } } finally { $stream.Dispose() } }; $textures=@($zip.Entries | Where-Object {$_.Name -like '*.tex'}); if($textures.Count -eq 0 -and @(Get-ChildItem -LiteralPath $anim -Filter ($name+'*.tex')).Count -eq 0) { throw ('Missing texture atlas: '+$name) }; foreach($texture in $textures) { $stream=$texture.Open(); try { $buf=New-Object byte[] 4; $read=$stream.Read($buf,0,4); if($read -ne 4 -or [Text.Encoding]::ASCII.GetString($buf) -ne 'KTEX') { throw ('Invalid texture in '+$name) } } finally { $stream.Dispose() } } } finally { $zip.Dispose() }; Write-Host ('OK: '+$name) }; $staging=Join-Path $root 'Animation-Results'; if(!(Test-Path -LiteralPath $staging)) { New-Item -ItemType Directory -Path $staging | Out-Null }; foreach($name in @('aom_tractor_chassis','aom_attachment_shared','aom_attachment_symbols')) { Copy-Item -LiteralPath (Join-Path $anim ($name+'.zip')) -Destination $staging -Force }; Get-ChildItem -LiteralPath $anim -Filter '*.tex' | Copy-Item -Destination $staging -Force; if(Test-Path -LiteralPath (Join-Path $root 'logs')) { Copy-Item -LiteralPath (Join-Path $root 'logs') -Destination $staging -Recurse -Force }; Copy-Item -LiteralPath (Join-Path $root 'Source-Manifest.json') -Destination $staging -Force; $result=Join-Path $root 'Animation-Results.zip'; Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $result -Force; Write-Host ('SUCCESS: '+$result); exit 0 } catch { Write-Host ('ERROR: '+$_.Exception.Message); exit 1 }"
if errorlevel 1 goto failed
echo.
echo Send Animation-Results.zip back. It contains the compiled animations and logs.
pause
exit /b 0
:failed
echo.
echo Verification failed. No success was reported for placeholder files.
echo Send the logs folder back. Do not enable this incomplete copy in the game.
pause
exit /b 1
