@echo off
setlocal DisableDelayedExpansion
set "AOM_DRIVER_ROOT=%~dp0"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { Add-Type -AssemblyName System.IO.Compression.FileSystem; $root=$env:AOM_DRIVER_ROOT; $mod=Join-Path $root 'Tractor'; $path=Join-Path $mod 'anim\aom_tractor_driver.zip'; $manifest=Join-Path $mod 'scripts\aom_driver_visual_bank.lua'; if(!(Test-Path -LiteralPath $path) -or !(Test-Path -LiteralPath $manifest)) {throw 'Missing driver output'}; if((Get-Content -Raw -LiteralPath $manifest) -notmatch 'available\s*=\s*true') {throw 'Driver build was not enabled; see logs'}; $zip=[IO.Compression.ZipFile]::OpenRead($path); try { foreach($spec in @(@('build.bin','BILD'),@('anim.bin','ANIM'),@('atlas-0.tex','KTEX'))) { $entry=$zip.GetEntry($spec[0]); if(!$entry -or $entry.Length -lt 16){throw ('Missing '+$spec[0])}; $s=$entry.Open();try{$b=New-Object byte[] 4;$n=$s.Read($b,0,4);if($n -ne 4 -or [Text.Encoding]::ASCII.GetString($b) -ne $spec[1]){throw ('Invalid '+$spec[0])}}finally{$s.Dispose()} } }finally{$zip.Dispose()}; $staging=Join-Path $root 'Driver-Results'; New-Item -ItemType Directory -Path (Join-Path $staging 'anim') -Force | Out-Null; New-Item -ItemType Directory -Path (Join-Path $staging 'scripts') -Force | Out-Null; Copy-Item -LiteralPath $path -Destination (Join-Path $staging 'anim') -Force; Copy-Item -LiteralPath $manifest -Destination (Join-Path $staging 'scripts') -Force; Copy-Item -LiteralPath (Join-Path $mod 'Driver-Build-Report.json') -Destination $staging -Force; Copy-Item -LiteralPath (Join-Path $root 'Source-Manifest.json') -Destination $staging -Force; Copy-Item -LiteralPath (Join-Path $root 'logs') -Destination $staging -Recurse -Force; $out=Join-Path $root 'Driver-Results.zip'; Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $out -Force; Write-Host ('SUCCESS: '+$out); exit 0 }catch{Write-Host ('ERROR: '+$_.Exception.Message);exit 1}"
if errorlevel 1 goto failed
echo Send Driver-Results.zip back. It includes the driver bank and activation file.
echo Keep the entire Tractor folder if you also test it on Windows.
pause
exit /b 0
:failed
echo Verification failed. Send logs instead of an old ZIP.
pause
exit /b 1
