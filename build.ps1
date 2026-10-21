<#
.SYNOPSIS
    Builds the Raiden OS ISO on Windows (uses WSL 2 with Ubuntu 26.04).

.DESCRIPTION
    1. Makes sure a dedicated WSL distro "RaidenOS-Build" (Ubuntu 26.04) exists.
    2. Runs scripts/build.sh inside it as root.
    3. The finished ISO and its SHA256 checksum appear in the "out" folder
       ("out\public" for the public edition).

    The first build downloads about 5 GB and takes 30-60 minutes. Later builds
    reuse finished stages; use -Clean to start from scratch or -Redo <stage>
    to rebuild from a stage (host, bootstrap, aptsetup, base, desktop,
    configure, squashfs, iso).

    -Public builds the edition for sharing (see EDITION in build.conf) in a
    separate work folder, so it never mixes with your personal build.

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Redo desktop
    .\build.ps1 -Public
    .\build.ps1 -Clean
#>
param(
    [switch]$Clean,
    [string]$Redo = "",
    [switch]$Public
)
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"
$Distro = "RaidenOS-Build"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
# your own build distro name, if you set one: WSL_DISTRO="..." in personal\build.conf
$personalConf = Join-Path $Here "personal\build.conf"
if ((Test-Path $personalConf) -and ((Get-Content $personalConf -Raw) -match '(?m)^WSL_DISTRO="([^"]+)"')) {
    $Distro = $Matches[1]
}

function To-WslPath([string]$p) {
    $drive = $p.Substring(0, 1).ToLower()
    return "/mnt/$drive" + ($p.Substring(2) -replace '\\', '/')
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL is not installed. Run 'wsl --install' in an administrator terminal, reboot, and try again."
}
$installed = (wsl.exe -l -q) -replace "`0", "" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($installed -notcontains $Distro) {
    Write-Host "Creating the $Distro WSL distro (Ubuntu 26.04)..."
    wsl.exe --install Ubuntu-26.04 --name $Distro --no-launch
    if ($LASTEXITCODE -ne 0) { throw "Could not install the Ubuntu 26.04 WSL distro." }
}

$script = (To-WslPath (Join-Path $Here "scripts\build.sh"))
$outDir = Join-Path $Here "out"
$envArgs = @()
if ($Public) {
    $outDir = Join-Path $Here "out\public"
    $envArgs = @("env", "EDITION=public", "WORK=/var/tmp/raiden-build-public", "OUT_DIR=$(To-WslPath $outDir)")
}
$buildArgs = @()
if ($Clean) { wsl.exe -d $Distro -u root --exec @envArgs bash $script --clean }
if ($Redo)  { $buildArgs = @("--redo", $Redo) }

Write-Host "Building Raiden OS (this can take a while)..."
wsl.exe -d $Distro -u root --exec @envArgs bash $script @buildArgs
if ($LASTEXITCODE -ne 0) { throw "The build failed; see the messages above." }
Write-Host ""
Write-Host "Done. Your ISO is in: $outDir"
