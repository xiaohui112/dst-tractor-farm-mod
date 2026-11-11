# 把 mod/AgeOfMachines 安装到《饥荒联机版》的 mods 目录，并逐文件校验 SHA-256。
# 用法： powershell -ExecutionPolicy Bypass -File tools/install_to_game.ps1
#        powershell -ExecutionPolicy Bypass -File tools/install_to_game.ps1 -GameRoot "D:\SteamLibrary\steamapps\common\Don't Starve Together"
param(
    [string]$GameRoot = '',
    [string]$Source = (Join-Path $PSScriptRoot '..\mod\AgeOfMachines')
)
$ErrorActionPreference = 'Stop'

function Get-GameCandidates {
    $roots = @()
    $steam = (Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam' -Name SteamPath -ErrorAction SilentlyContinue).SteamPath
    if ($steam) {
        $roots += $steam
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($match in [regex]::Matches((Get-Content -Raw -LiteralPath $vdf), '"path"\s+"([^"]+)"')) {
                $roots += ($match.Groups[1].Value -replace '\\\\', '\')
            }
        }
    }
    $roots | Select-Object -Unique | ForEach-Object {
        Join-Path $_ "steamapps\common\Don't Starve Together"
    }
}

$Source = (Resolve-Path -LiteralPath $Source).Path
if (-not (Test-Path -LiteralPath (Join-Path $Source 'modinfo.lua'))) {
    throw "找不到 Mod 源目录：$Source"
}
if (-not $GameRoot) {
    $GameRoot = Get-GameCandidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'data') } | Select-Object -First 1
}
if (-not $GameRoot) {
    throw '没有自动找到饥荒联机版，请用 -GameRoot 指定包含 data 目录的游戏根目录。'
}
$GameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $GameRoot 'data'))) {
    throw "这不是完整的游戏根目录（缺少 data）：$GameRoot"
}
$mods = (New-Item -ItemType Directory -Path (Join-Path $GameRoot 'mods') -Force).FullName
$target = Join-Path $mods 'AgeOfMachines'
if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
Copy-Item -LiteralPath $Source -Destination $target -Recurse -Force

$bad = 0
$files = Get-ChildItem -LiteralPath $Source -Recurse -File
foreach ($file in $files) {
    $installed = Join-Path $target $file.FullName.Substring($Source.Length + 1)
    if (-not (Test-Path -LiteralPath $installed)) { Write-Host "缺少：$($file.Name)"; $bad++; continue }
    if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath $installed).Hash) {
        Write-Host "内容不一致：$($file.Name)"; $bad++
    }
}
if ($bad -ne 0) { throw "安装校验失败：$bad 个文件与项目不一致" }
$driver = Join-Path $target 'anim\aom_tractor_driver.zip'
Write-Host "已安装 $($files.Count) 个文件到 $target"
if (Test-Path -LiteralPath $driver) {
    Write-Host ("驾驶室动画：{0:N1} MiB，已启用" -f ((Get-Item -LiteralPath $driver).Length / 1MB))
} else {
    Write-Host '驾驶室动画未包含，人物保持原版骑乘显示。'
}
Write-Host '进游戏 → Mods → 勾选「拖拉机（Tractor）」→ 已有存档需要重启世界；所有联机客户端使用同一版本。'
