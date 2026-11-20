# FM-Modmon-ms setup for Windows 10/11: installs the monitor and everything it needs, from GitHub.
# In PowerShell:
#   irm https://raw.githubusercontent.com/RAEApps/FM-Modmon-ms/main/install.ps1 | iex
# Installs radioconda (GNU Radio 3.10), the SDRplay API (RSP1A driver and service), the
# SoapySDRPlay3 module, nrsc5, ffmpeg and the monitor from main, skipping what's already
# there, then checks the RSP1A is found. Run it again to update the monitor (settings are
# kept). Uninstall from Settings > Apps. Downloads are pinned and SHA-256 checked; the
# SDRplay API comes from sdrplay.com through the browser and is checked by its signature.
param(
    [string]$InstallDir = (Join-Path $env:ProgramFiles 'FM-Modmon-ms'),
    [switch]$Uninstall,
    [switch]$Launcher   # internal: the unelevated window that started setup will start the monitor
)

$App = 'FM-Modmon-ms'
$Repo = 'RAEApps/FM-Modmon-ms'
$ScriptUrl = "https://raw.githubusercontent.com/$Repo/main/install.ps1"
$Conda = Join-Path $env:ProgramData 'radioconda'
# A radioconda already installed just for this user is used rather than adding a second copy.
$UserConda = Join-Path $env:USERPROFILE 'radioconda'
if (-not (Test-Path (Join-Path $Conda 'python.exe')) -and (Test-Path (Join-Path $UserConda 'python.exe'))) {
    $Conda = $UserConda
}
$Cache = Join-Path $env:TEMP 'fm-modmon-ms-setup'
$SdrplayMin = [version]'3.15'
$SdrplayPage = 'https://www.sdrplay.com/api/'
$SdrplaySigner = 'CN=SDRPLAY LIMITED,*'
$UninstKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$App"
$Deps = "https://github.com/$Repo/releases/download/deps-2026.11"
$Pinned = @{
    radioconda = @{
        File = 'radioconda-2025.03.14-Windows-x86_64.exe'
        Url = 'https://github.com/ryanvolz/radioconda/releases/download/2025.03.14/radioconda-2025.03.14-Windows-x86_64.exe'
        Sha256 = 'd64c316df6f5e76d9f46eaf5e1409aa5fc633e125f5a7d49e8931fa6453b2fee'
    }
    ffmpeg = @{
        File = 'ffmpeg-8.0.1-essentials_build.zip'
        Url = 'https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/ffmpeg-8.0.1-essentials_build.zip'
        Sha256 = 'e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673'
        ExeSha256 = '5af82a0d4fe2b9eae211b967332ea97edfc51c6b328ca35b827e73eac560dc0d'   # its bin\ffmpeg.exe
    }
    soapy = @{
        File = 'sdrPlaySupport.dll'
        Url = "$Deps/sdrPlaySupport.dll"
        Sha256 = '056db849271dc45bc4fba5ebb932f475f7a36083eac1ecdd4e0f147a48883f44'
    }
    nrsc5 = @{
        File = 'nrsc5.exe'
        Url = "$Deps/nrsc5.exe"
        Sha256 = 'b0015835d173eaa5339511d6be0e22f04a53aaccee31d4b1e2885907aa599c3b'
    }
}
# Run by radioconda's python: is an RSP visible through SoapySDR? Prints its label.
$CheckRsp = @'
import os, sys
os.environ['SOAPY_SDR_PLUGIN_PATH'] = sys.argv[1]
os.environ['PATH'] = os.pathsep.join([r'C:\Program Files\SDRplay\API\x64',
                                      os.path.join(sys.prefix, 'Library', 'bin'), os.environ.get('PATH', '')])
import SoapySDR
SoapySDR.setLogLevel(SoapySDR.SOAPY_SDR_ERROR)
found = SoapySDR.Device.enumerate('driver=sdrplay')
if not found:
    sys.exit(1)
print(found[0]['label'] if 'label' in found[0] else 'SDRplay RSP')
'@

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Note($text) { Write-Host "    $text" }

function Test-Admin {
    $id = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    $id.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-Download($url, $path) {
    & curl.exe -fL --retry 3 --progress-bar -o $path $url
    if ($LASTEXITCODE) { throw "Download failed (curl exit $LASTEXITCODE): $url" }
}

# A pinned download in the cache, fetched unless already there with the right SHA-256.
function Get-Pinned($name) {
    $p = $Pinned[$name]
    $path = Join-Path $Cache $p.File
    if ((Test-Path $path) -and (Get-FileHash $path -Algorithm SHA256).Hash -eq $p.Sha256) { return $path }
    Note "Downloading $($p.File)..."
    Get-Download $p.Url $path
    $hash = (Get-FileHash $path -Algorithm SHA256).Hash
    if ($hash -ne $p.Sha256) {
        Remove-Item $path -Force
        throw "$($p.File) doesn't match its pinned SHA-256 (got $hash); not installing it."
    }
    $path
}

# Is the file there with this SHA-256 (already installed, nothing to download)?
function Test-Current($path, $sha256) {
    (Test-Path $path) -and (Get-FileHash $path -Algorithm SHA256).Hash -eq $sha256
}

function Install-Radioconda {
    Step 'radioconda (GNU Radio 3.10)'
    if (Test-Path (Join-Path $Conda 'python.exe')) { Note "Already installed in $Conda"; return }
    $exe = Get-Pinned 'radioconda'
    Note "Installing in $Conda (this takes several minutes)..."
    # constructor installer: /D must be last and unquoted
    $p = Start-Process $exe "/InstallationType=AllUsers /RegisterPython=0 /AddToPath=0 /S /D=$Conda" -Wait -PassThru
    if (-not (Test-Path (Join-Path $Conda 'python.exe'))) { throw "radioconda didn't install (exit $($p.ExitCode))." }
}

function Get-SdrplayVersion {
    $v = (Get-ItemProperty 'HKLM:\SOFTWARE\SDRplay\Service\API' -ErrorAction SilentlyContinue).Version
    if ($v) { [version]$v } else { $null }
}

# The newest SDRplay API installer in Downloads that's new enough and signed by SDRplay.
function Find-SdrplayInstaller {
    $downloads = (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path
    Get-ChildItem $downloads -Filter 'SDRplay_RSP_API-Windows-*.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'Windows-([\d.]+)\.exe$' -and [version]$Matches[1] -ge $SdrplayMin } |
        Sort-Object LastWriteTime -Descending |
        Where-Object {
            $sig = Get-AuthenticodeSignature $_.FullName
            $sig.Status -eq 'Valid' -and $sig.SignerCertificate.Subject -like $SdrplaySigner
        } | Select-Object -First 1
}

function Install-Sdrplay {
    Step 'SDRplay API (RSP1A driver and service)'
    $have = Get-SdrplayVersion
    if ($have -and $have -ge $SdrplayMin) {
        Note "SDRplay API $have is already installed"
    } else {
        $exe = Find-SdrplayInstaller
        if (-not $exe) {
            Note "SDRplay only offers the API from its website, after its licence."
            Note "Opening $SdrplayPage in your browser:"
            Note "  download the Windows API $SdrplayMin or newer to your Downloads folder."
            Note "Setup carries on by itself when the download finishes (Ctrl+C to stop)."
            Start-Process $SdrplayPage
            while (-not ($exe = Find-SdrplayInstaller)) { Start-Sleep -Seconds 3 }
        }
        Note "Installing $($exe.Name)..."
        $p = Start-Process $exe.FullName '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' -Wait -PassThru
        if (-not (Get-SdrplayVersion)) { throw "The SDRplay API didn't install (exit $($p.ExitCode))." }
    }
    # The monitor reaches the RSP1A through this service: run it now and at boot.
    $out = & sc.exe config SDRplayAPIService start= auto
    if ($LASTEXITCODE) { Write-Warning "Couldn't set the SDRplay API service to start at boot (sc.exe $LASTEXITCODE): $out" }
    # It can crash when an RSP is closed and reopened quickly (API 3.15: access violation in
    # sdrplay_apiService.exe); Windows then leaves it stopped. Have Windows restart it instead,
    # every time (the failure count resets after a day), so the monitor never needs a hand.
    $out = & sc.exe failure SDRplayAPIService reset= 86400 actions= restart/2000/restart/2000/restart/5000
    if ($LASTEXITCODE) { Write-Warning "Couldn't set the SDRplay API service to restart after a crash (sc.exe $LASTEXITCODE): $out" }
    $out = & sc.exe start SDRplayAPIService
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 1056) {   # 1056: already running
        Write-Warning "The SDRplay API service didn't start (sc.exe $LASTEXITCODE): $out"
        Write-Warning 'The monitor won''t see the RSP1A until it runs: try Services > SDRplay API Service > Start, or reboot.'
    }
}

function Install-Monitor {
    Step "$App from GitHub"
    $ref = 'main'
    try {
        $commit = Invoke-RestMethod "https://api.github.com/repos/$Repo/commits/main" -Headers @{ 'User-Agent' = 'fm-modmon-ms-setup' }
        $ref = $commit.sha
        Note "main at $($ref.Substring(0, 7)), $($commit.commit.committer.date)"
    } catch { Note 'Using the latest main' }
    $zip = Join-Path $Cache 'fm-modmon-ms.zip'
    $src = Join-Path $Cache 'src'
    Get-Download "https://codeload.github.com/$Repo/zip/$ref" $zip
    if (Test-Path $src) { Remove-Item $src -Recurse -Force }
    Expand-Archive $zip $src
    $root = (Get-ChildItem $src -Directory | Select-Object -First 1).FullName

    $appDir = Join-Path $InstallDir 'app'
    New-Item -ItemType Directory -Force (Join-Path $appDir 'examples'), (Join-Path $appDir 'tools') | Out-Null
    foreach ($f in 'fm-modmon-ms.py', 'fm-modmon-ms-web.html', 'fm-modmon-ms.ico', 'LICENSE', 'README.md') {
        Copy-Item (Join-Path $root $f) $appDir -Force
    }
    Copy-Item (Join-Path $root 'examples\*') (Join-Path $appDir 'examples') -Recurse -Force
    Copy-Item (Join-Path $root 'tools\*') (Join-Path $appDir 'tools') -Recurse -Force
    Copy-Item (Join-Path $root 'install.ps1') $InstallDir -Force   # for updates and uninstalling
    # Settings and event logs are written beside the script: let users change them.
    & icacls.exe $appDir /grant '*S-1-5-32-545:(OI)(CI)M' /T /Q | Out-Null
    if ($ref -eq 'main') { (Get-Date).ToString('yyyy.MM.dd') } else { $ref.Substring(0, 7) }
}

function Install-Helpers {
    Step 'SoapySDRPlay3, nrsc5 and ffmpeg'
    # Where the monitor looks, relative to its folder: ..\soapysdrplay3-build\modules,
    # ..\nrsc5*\build\src and ..\ffmpeg.
    $modules = Join-Path $InstallDir 'soapysdrplay3-build\modules'
    $nrsc5 = Join-Path $InstallDir 'nrsc5\build\src'
    $ffmpeg = Join-Path $InstallDir 'ffmpeg'
    New-Item -ItemType Directory -Force $modules, $nrsc5, $ffmpeg | Out-Null
    foreach ($item in @(@('soapy', $modules, 'SoapySDRPlay3'), @('nrsc5', $nrsc5, 'nrsc5'))) {
        $name, $dir, $label = $item
        if (Test-Current (Join-Path $dir $Pinned[$name].File) $Pinned[$name].Sha256) { Note "$label is up to date" }
        else { Copy-Item (Get-Pinned $name) $dir -Force }
    }
    if (Test-Current (Join-Path $ffmpeg 'ffmpeg.exe') $Pinned.ffmpeg.ExeSha256) { Note 'ffmpeg is up to date'; return }
    $zip = Get-Pinned 'ffmpeg'
    $out = Join-Path $Cache 'ffmpeg'
    if (Test-Path $out) { Remove-Item $out -Recurse -Force }
    Note 'Unpacking ffmpeg...'
    Expand-Archive $zip $out
    $exe = Get-ChildItem $out -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1
    Copy-Item $exe.FullName $ffmpeg -Force
    foreach ($f in 'LICENSE', 'README.txt') {   # ffmpeg's licence and source notice go with it
        $doc = Join-Path (Split-Path (Split-Path $exe.FullName)) $f
        if (Test-Path $doc) { Copy-Item $doc $ffmpeg -Force }
    }
    Remove-Item $out -Recurse -Force
}

# The monitor sets this taskbar ID (APP_ID in fm-modmon-ms.py); its shortcuts must carry it
# too, or the taskbar can't match the window to them and may show no icon.
$AppId = 'fm-modmon-ms.monitor'
$LnkAppIdCode = @'
using System;
using System.Runtime.InteropServices;
public static class LnkAppId {
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        [PreserveSig] int GetCount(out uint count);
        [PreserveSig] int GetAt(uint index, out PropertyKey key);
        [PreserveSig] int GetValue(ref PropertyKey key, out PropVariant value);
        [PreserveSig] int SetValue(ref PropertyKey key, ref PropVariant value);
        [PreserveSig] int Commit();
    }
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PropertyKey { public Guid fmtid; public uint pid; }
    [StructLayout(LayoutKind.Explicit, Size = 16)]
    struct PropVariant { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr ptr; }
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHGetPropertyStoreFromParsingName(string path, IntPtr bindCtx, int flags, ref Guid iid,
        [MarshalAs(UnmanagedType.Interface)] out IPropertyStore store);
    // Sets System.AppUserModel.ID on a .lnk file.
    public static void Set(string lnk, string appId) {
        Guid iid = typeof(IPropertyStore).GUID;
        IPropertyStore store;
        Marshal.ThrowExceptionForHR(SHGetPropertyStoreFromParsingName(lnk, IntPtr.Zero, 2, ref iid, out store));
        PropertyKey key = new PropertyKey { fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
        PropVariant value = new PropVariant { vt = 31, ptr = Marshal.StringToCoTaskMemUni(appId) };  // VT_LPWSTR
        try {
            Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref value));
            Marshal.ThrowExceptionForHR(store.Commit());
        } finally {
            Marshal.FreeCoTaskMem(value.ptr);
            Marshal.ReleaseComObject(store);
        }
    }
}
'@

function New-Shortcut($path) {
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
    $s.TargetPath = Join-Path $Conda 'pythonw.exe'
    $s.Arguments = '"' + (Join-Path $InstallDir 'app\fm-modmon-ms.py') + '"'
    $s.WorkingDirectory = Join-Path $InstallDir 'app'
    $s.IconLocation = Join-Path $InstallDir 'app\fm-modmon-ms.ico'
    $s.Description = 'FM modulation and RDS monitor'
    $s.Save()
    if (-not ('LnkAppId' -as [type])) { Add-Type -TypeDefinition $LnkAppIdCode }
    [LnkAppId]::Set($path, $AppId)
}

function Register-Monitor($version) {
    Step 'Shortcuts'
    New-Shortcut (Join-Path ([Environment]::GetFolderPath('CommonPrograms')) "$App.lnk")
    New-Shortcut (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) "$App.lnk")
    New-Item $UninstKey -Force | Out-Null
    $script = Join-Path $InstallDir 'install.ps1'
    $values = @{
        DisplayName = $App; DisplayVersion = $version; Publisher = $App
        DisplayIcon = Join-Path $InstallDir 'app\fm-modmon-ms.ico'; InstallLocation = $InstallDir
        UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`" -Uninstall"
    }
    foreach ($k in $values.Keys) { Set-ItemProperty $UninstKey $k $values[$k] }
    Set-ItemProperty $UninstKey NoModify 1 -Type DWord
    Set-ItemProperty $UninstKey NoRepair 1 -Type DWord
}

function Test-Rsp {
    Step 'Looking for the RSP1A'
    $check = Join-Path $InstallDir 'check_rsp.py'
    Set-Content $check $CheckRsp -Encoding ASCII
    $python = Join-Path $Conda 'python.exe'
    $modules = Join-Path $InstallDir 'soapysdrplay3-build\modules'
    $ErrorActionPreference = 'Continue'   # 5.1 turns a native program's stderr into errors
    while ($true) {
        $label = & $python -I $check $modules 2>$null
        if ($LASTEXITCODE -eq 0) { Note "Found: $label"; return }
        Note 'No SDRplay RSP found. Plug the RSP1A into a USB port on the PC itself (not a hub)'
        Note 'and wait for Windows to finish setting it up.'
        $answer = Read-Host '    Press Enter to look again, or S to skip'
        if ($answer -match '^[sS]') { Note "Skipped: the monitor finds the RSP1A once it's plugged in."; return }
    }
}

function Install-All {
    New-Item -ItemType Directory -Force $Cache | Out-Null
    Install-Radioconda
    Install-Sdrplay
    $version = Install-Monitor
    Install-Helpers
    Register-Monitor $version
    Test-Rsp
    Step "$App is installed in $InstallDir"
    Note 'Start it from the Start menu or the desktop shortcut. Run this setup again to update it.'
    Remove-Item $Cache -Recurse -Force -ErrorAction SilentlyContinue
    (Read-Host '    Start it now? [Y/n]') -notmatch '^[nN]'
}

function Get-MonitorProcess {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like '*fm-modmon-ms.py*' }
}

# Start the monitor from its shortcut and wait to see it running. Unelevated, it starts as
# this user; elevated (no window to hand it back to), through Explorer, which runs as the
# signed-in user.
function Start-Monitor {
    $lnk = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) "$App.lnk"
    Step "Starting $App (its window opens in a few seconds)"
    if (Test-Admin) { Start-Process explorer.exe "`"$lnk`"" } else { Start-Process $lnk }
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Get-MonitorProcess) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    Start-Sleep -Seconds 5   # still there once GNU Radio has loaded?
    if (Get-MonitorProcess) { Note "$App is running."; return }
    Write-Host "    $App didn't start. To see why, run in a terminal:" -ForegroundColor Yellow
    Note "& '$(Join-Path $Conda 'python.exe')' '$(Join-Path $InstallDir 'app\fm-modmon-ms.py')'"
}

function Uninstall-All {
    Step "Uninstalling $App from $InstallDir"
    # The monitor's own "start with Windows" shortcut is per user.
    Remove-Item (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\fm-modmon-ms.lnk') -ErrorAction SilentlyContinue
    Remove-Item (Join-Path ([Environment]::GetFolderPath('CommonPrograms')) "$App.lnk") -ErrorAction SilentlyContinue
    Remove-Item (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) "$App.lnk") -ErrorAction SilentlyContinue
    foreach ($d in 'soapysdrplay3-build', 'nrsc5', 'ffmpeg', 'app\examples', 'app\tools', 'app\__pycache__') {
        Remove-Item (Join-Path $InstallDir $d) -Recurse -Force -ErrorAction SilentlyContinue
    }
    foreach ($f in 'app\fm-modmon-ms.py', 'app\fm-modmon-ms-web.html', 'app\fm-modmon-ms.ico', 'app\LICENSE',
                   'app\README.md', 'check_rsp.py', 'install.ps1') {
        Remove-Item (Join-Path $InstallDir $f) -Force -ErrorAction SilentlyContinue
    }
    $appDir = Join-Path $InstallDir 'app'
    if ((Test-Path $appDir) -and (Read-Host "    Also delete $App's settings and event logs? [y/N]") -match '^[yY]') {
        Remove-Item $appDir -Recurse -Force
    }
    foreach ($d in $appDir, $InstallDir) {
        if ((Test-Path $d) -and -not (Get-ChildItem $d -Force)) { Remove-Item $d -Force }
    }
    Remove-Item $UninstKey -Force -ErrorAction SilentlyContinue
    Note 'radioconda and the SDRplay API are left installed; remove them in Settings > Apps if wanted.'
}

function Main {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'   # Expand-Archive's progress bar is very slow in 5.1
    if (-not (Test-Admin)) {
        # Relaunch elevated; when piped through iex there's no file, so fetch it first.
        $self = $PSCommandPath
        if (-not $self) {
            $self = Join-Path $env:TEMP 'fm-modmon-ms-install.ps1'
            Get-Download $ScriptUrl $self
        }
        $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$self`" -InstallDir `"$InstallDir`""
        $argList += if ($Uninstall) { ' -Uninstall' } else { ' -Launcher' }
        Write-Host "$App setup needs administrator rights; continuing in a new window."
        try { $p = Start-Process powershell.exe $argList -Verb RunAs -PassThru -Wait }
        catch { Write-Host "Setup needs administrator rights: $($_.Exception.Message)" -ForegroundColor Red; return }
        # Exit code 10: setup finished and the monitor should start, here, as this user.
        if ($p.ExitCode -eq 10) { Start-Monitor }
        return
    }
    if ($Uninstall -and $PSCommandPath) { $script:InstallDir = Split-Path $PSCommandPath }
    $start = $false
    try {
        if ($Uninstall) { Uninstall-All } else { $start = [bool](Install-All | Select-Object -Last 1) }
    } catch {
        Write-Host "`nSetup stopped: $_" -ForegroundColor Red
    }
    if ($start -and $Launcher) { exit 10 }   # the window that started setup starts the monitor
    if ($start) { Start-Monitor }
    if ($PSCommandPath) { Read-Host "`nPress Enter to close" | Out-Null }
}

Main
