# Builds installer\dist\FM-Modmon-ms-setup-<version>.exe: gathers installer\payload, runs NSIS.
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1
# Defaults: the newest radioconda and SDRplay API installers in Downloads, and the
# SoapySDRPlay3 module and nrsc5 built beside this repo (as the monitor finds them), and the
# WinGet ffmpeg (Gyan.FFmpeg.Shared: ffmpeg.exe and its DLLs, with its licence).
param(
    [string]$Version = (Get-Date -Format 'yyyy.MM.dd'),
    [string]$Radioconda = '',
    [string]$Sdrplay = '',
    [string]$SoapyModule = '',
    [string]$Nrsc5 = '',
    [string]$Ffmpeg = '',
    [string]$Makensis = "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$repo = Split-Path $here
$downloads = Join-Path $env:USERPROFILE 'Downloads'

function Newest($pattern, $what) {
    $f = Get-ChildItem $pattern -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $f) { throw "$what not found ($pattern); pass it as a parameter" }
    $f.FullName
}
if (-not $Radioconda) { $Radioconda = Newest (Join-Path $downloads 'radioconda-*-Windows-x86_64.exe') 'radioconda installer' }
if (-not $Sdrplay) { $Sdrplay = Newest (Join-Path $downloads 'SDRplay_RSP_API-Windows-*.exe') 'SDRplay API installer' }
if (-not $SoapyModule) { $SoapyModule = Newest (Join-Path $repo '..\soapysdrplay3-build\modules\sdrPlaySupport.dll') 'SoapySDRPlay3 module' }
if (-not $Nrsc5) { $Nrsc5 = Newest (Join-Path $repo '..\nrsc5*\build\src\nrsc5.exe') 'nrsc5.exe' }
if (-not $Ffmpeg) {
    $Ffmpeg = Newest (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe') 'ffmpeg.exe'
}
if (-not (Test-Path $Makensis)) { throw "NSIS not found at $Makensis (winget install NSIS.NSIS)" }

$condaVersion = if ((Split-Path $Radioconda -Leaf) -match 'radioconda-([\d.]+)-') { $Matches[1] } else { '?' }
$sdrplayVersion = if ((Split-Path $Sdrplay -Leaf) -match 'Windows-([\d.]+)\.exe') { $Matches[1] } else { '3.15' }

$payload = Join-Path $here 'payload'
if (Test-Path $payload) { Remove-Item $payload -Recurse -Force }
New-Item -ItemType Directory -Force "$payload\app\examples", "$payload\ffmpeg", (Join-Path $here 'dist') | Out-Null
foreach ($f in 'fm-modmon-ms.py', 'fm-modmon-ms-web.html', 'fm-modmon-ms.ico', 'LICENSE', 'README.md') {
    Copy-Item (Join-Path $repo $f) "$payload\app\"
}
Copy-Item (Join-Path $repo 'examples\*') "$payload\app\examples\" -Recurse
Copy-Item $Radioconda "$payload\radioconda-installer.exe"
Copy-Item $Sdrplay "$payload\sdrplay-api-installer.exe"
Copy-Item $SoapyModule "$payload\sdrPlaySupport.dll"
Copy-Item $Nrsc5 "$payload\nrsc5.exe"
$ffbin = Split-Path $Ffmpeg
Copy-Item $Ffmpeg, "$ffbin\*.dll" "$payload\ffmpeg\"
foreach ($f in 'LICENSE', 'README.txt') {   # ffmpeg's licence and source notice go with it
    $doc = Join-Path (Split-Path $ffbin) $f
    if (Test-Path $doc) { Copy-Item $doc "$payload\ffmpeg\" }
}

Write-Host "radioconda $condaVersion, SDRplay API $sdrplayVersion, version $Version"
$nsisArgs = @('/V2', '/WX', '/INPUTCHARSET', 'UTF8', "/DVERSION=$Version", "/DRADIOCONDA_VERSION=$condaVersion",
              "/DSDRPLAY_VERSION=$sdrplayVersion", (Join-Path $here 'fm-modmon-ms.nsi'))
& $Makensis @nsisArgs
if ($LASTEXITCODE) { throw "makensis failed ($LASTEXITCODE)" }
Remove-Item $payload -Recurse -Force
Get-Item (Join-Path $here "dist\FM-Modmon-ms-setup-$Version.exe")
