; FM-Modmon-ms installer: one exe for a brand-new Windows PC.
; Installs radioconda, the SDRplay API (RSP1A USB driver and service), the SoapySDRPlay3
; module, nrsc5, ffmpeg (via winget) and the monitor itself, then checks the RSP1A is seen.
; Build with build.ps1, which gathers payload\ and passes the version defines.

Unicode true
ManifestDPIAware true
SetCompressor lzma   ; not solid, so the bundled installers can be stored uncompressed

!include MUI2.nsh
!include LogicLib.nsh
!include WordFunc.nsh
!include x64.nsh

!define APP "FM-Modmon-ms"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"
!define CONDA "$APPDATA\radioconda"   ; C:\ProgramData\radioconda: .onInit sets the all-users context
!define SDRPLAY_KEY "SOFTWARE\SDRplay\Service\API"
!define STARTUP_LNK "Microsoft\Windows\Start Menu\Programs\Startup\fm-modmon-ms.lnk"
!ifndef VERSION
  !define VERSION "dev"
!endif
!ifndef RADIOCONDA_VERSION
  !define RADIOCONDA_VERSION "?"
!endif
!ifndef SDRPLAY_VERSION
  !define SDRPLAY_VERSION "3.15"
!endif

Name "${APP}"
OutFile "dist\${APP}-setup-${VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP}"
InstallDirRegKey HKLM "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel admin
BrandingText "${APP} ${VERSION}"
VIProductVersion "0.0.0.0"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "${APP} installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "GPL-3.0-or-later"

!define MUI_ICON "payload\app\fm-modmon-ms.ico"
!define MUI_UNICON "payload\app\fm-modmon-ms.ico"
!define MUI_ABORTWARNING
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_WELCOMEPAGE_TEXT "This installs ${APP}, the multi-station FM modulation and RDS monitor, \
with everything it needs on a new PC:$\r$\n$\r$\n\
  - radioconda ${RADIOCONDA_VERSION} (GNU Radio 3.10, Python)$\r$\n\
  - SDRplay API ${SDRPLAY_VERSION} (RSP1A driver and service)$\r$\n\
  - SoapySDRPlay3, nrsc5 and ffmpeg$\r$\n$\r$\n\
Anything already installed is left as it is. Installing radioconda takes several minutes.$\r$\n$\r$\n\
Leave the RSP1A unplugged for now; you'll be asked to plug it in at the end."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APP}"
!define MUI_FINISHPAGE_RUN_FUNCTION StartApp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "payload\app\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "${APP} needs 64-bit Windows 10 or 11." /SD IDOK
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext all
FunctionEnd

Section "radioconda ${RADIOCONDA_VERSION} (GNU Radio 3.10)" SecConda
  SectionIn RO
  ${If} ${FileExists} "${CONDA}\python.exe"
    DetailPrint "radioconda is already installed in ${CONDA}"
  ${Else}
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    SetCompress off
    File "payload\radioconda-installer.exe"
    SetCompress auto
    DetailPrint "Installing radioconda in ${CONDA} (this takes several minutes)..."
    ; constructor installer: /D must be last and unquoted
    ExecWait '"$PLUGINSDIR\radioconda-installer.exe" /InstallationType=AllUsers /RegisterPython=0 /AddToPath=0 /S /D=${CONDA}' $0
    Delete "$PLUGINSDIR\radioconda-installer.exe"
    ${IfNot} ${FileExists} "${CONDA}\python.exe"
      MessageBox MB_ICONSTOP "radioconda didn't install (exit code $0). Setup can't continue." /SD IDOK
      Abort
    ${EndIf}
  ${EndIf}
SectionEnd

Section "SDRplay API ${SDRPLAY_VERSION} (RSP1A driver)" SecSdrplay
  SectionIn RO
  ReadRegStr $1 HKLM "${SDRPLAY_KEY}" "Version"
  StrCpy $2 2
  ${If} $1 != ""
    ${VersionCompare} "$1" "${SDRPLAY_VERSION}" $2   ; 2: installed one is older
  ${EndIf}
  ${If} $2 == 2
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    SetCompress off
    File "payload\sdrplay-api-installer.exe"
    SetCompress auto
    DetailPrint "Installing the SDRplay API ${SDRPLAY_VERSION} and RSP USB driver..."
    ExecWait '"$PLUGINSDIR\sdrplay-api-installer.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-' $0
    Delete "$PLUGINSDIR\sdrplay-api-installer.exe"
    ${IfNot} ${FileExists} "$PROGRAMFILES64\SDRplay\API\x64\sdrplay_api.dll"
      MessageBox MB_ICONSTOP "The SDRplay API didn't install (exit code $0). Setup can't continue." /SD IDOK
      Abort
    ${EndIf}
  ${Else}
    DetailPrint "SDRplay API $1 is already installed"
  ${EndIf}
  ; The monitor talks to the RSP1A through this service: make sure it runs now and at boot.
  nsExec::ExecToLog 'sc.exe config SDRplayAPIService start= auto'
  Pop $0
  nsExec::ExecToLog 'sc.exe start SDRplayAPIService'
  Pop $0
SectionEnd

Section "${APP} ${VERSION}" SecApp
  SectionIn RO
  SetOutPath "$INSTDIR\app"
  File "payload\app\fm-modmon-ms.py"
  File "payload\app\fm-modmon-ms-web.html"
  File "payload\app\fm-modmon-ms.ico"
  File "payload\app\LICENSE"
  File "payload\app\README.md"
  SetOutPath "$INSTDIR\app\examples"
  File /r "payload\app\examples\*"
  ; Found by the monitor at ..\soapysdrplay3-build\modules, as in the source layout.
  SetOutPath "$INSTDIR\soapysdrplay3-build\modules"
  File "payload\sdrPlaySupport.dll"
  SetOutPath "$INSTDIR"
  File "check_rsp.py"

  ; Settings and event logs are written beside the script: let users change them.
  nsExec::ExecToLog 'icacls "$INSTDIR\app" /grant *S-1-5-32-545:(OI)(CI)M /T /Q'
  Pop $0

  SetOutPath "$INSTDIR\app"
  CreateShortcut "$SMPROGRAMS\${APP}.lnk" "${CONDA}\pythonw.exe" '"$INSTDIR\app\fm-modmon-ms.py"' \
    "$INSTDIR\app\fm-modmon-ms.ico" 0 SW_SHOWNORMAL "" "FM modulation and RDS monitor"

  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${APP}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\app\fm-modmon-ms.ico"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "nrsc5 (HD Radio / IBOC decoding)" SecNrsc5
  ; Found by the monitor at ..\nrsc5*\build\src, as in the source layout.
  SetOutPath "$INSTDIR\nrsc5\build\src"
  File "payload\nrsc5.exe"
SectionEnd

Section "ffmpeg for web audio (downloaded with winget)" SecFfmpeg
  DetailPrint "Installing ffmpeg with winget (needs internet)..."
  nsExec::ExecToLog 'cmd.exe /c winget install --id Gyan.FFmpeg.Shared --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity'
  Pop $0
  ${If} $0 != 0
    DetailPrint "ffmpeg wasn't installed (winget exit $0); the web page will have no audio until it is."
  ${EndIf}
SectionEnd

Section "Desktop shortcut" SecDesktop
  SetOutPath "$INSTDIR\app"
  CreateShortcut "$DESKTOP\${APP}.lnk" "${CONDA}\pythonw.exe" '"$INSTDIR\app\fm-modmon-ms.py"' \
    "$INSTDIR\app\fm-modmon-ms.ico" 0 SW_SHOWNORMAL "" "FM modulation and RDS monitor"
SectionEnd

Section "-Check the RSP1A"
  DetailPrint "Looking for the RSP1A..."
check:
  nsExec::ExecToStack '"${CONDA}\python.exe" -I "$INSTDIR\check_rsp.py" "$INSTDIR\soapysdrplay3-build\modules"'
  Pop $0
  Pop $1
  ${If} $0 == 0
    DetailPrint "Found: $1"
  ${Else}
    MessageBox MB_RETRYCANCEL|MB_ICONINFORMATION "No SDRplay RSP was found.$\r$\n$\r$\n\
Plug the RSP1A into a USB port on the PC itself (not a hub), wait for Windows to finish \
setting it up, then click Retry.$\r$\n$\r$\nCancel finishes setup without it; the monitor \
will find the RSP1A when it's plugged in later." /SD IDCANCEL IDRETRY check
    DetailPrint "No RSP1A found yet; plug it in before starting ${APP}."
  ${EndIf}
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecConda} "GNU Radio 3.10 with gr-rds, SoapySDR, NumPy, SciPy and PyQt5. Skipped if already installed."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecSdrplay} "SDRplay's API service and the RSP1A USB driver. Skipped if this version or newer is installed."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp} "The monitor, its web page and the SoapySDRPlay3 module."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecNrsc5} "Decodes HD Radio: status, audio, station logos and alerts."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecFfmpeg} "Audio in the web version. Downloaded from winget at install time."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "A desktop shortcut to start the monitor."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function StartApp
  ; Through Explorer, so the monitor runs as the signed-in user, not elevated.
  Exec '"$WINDIR\explorer.exe" "$SMPROGRAMS\${APP}.lnk"'
FunctionEnd

Section "Uninstall"
  SetRegView 64
  ; The monitor's own "start with Windows" shortcut is per user.
  SetShellVarContext current
  Delete "$APPDATA\${STARTUP_LNK}"
  SetShellVarContext all
  Delete "$SMPROGRAMS\${APP}.lnk"
  Delete "$DESKTOP\${APP}.lnk"

  Delete "$INSTDIR\app\fm-modmon-ms.py"
  Delete "$INSTDIR\app\fm-modmon-ms-web.html"
  Delete "$INSTDIR\app\fm-modmon-ms.ico"
  Delete "$INSTDIR\app\LICENSE"
  Delete "$INSTDIR\app\README.md"
  RMDir /r "$INSTDIR\app\examples"
  RMDir /r "$INSTDIR\app\__pycache__"
  RMDir /r "$INSTDIR\soapysdrplay3-build"
  RMDir /r "$INSTDIR\nrsc5"
  Delete "$INSTDIR\check_rsp.py"
  MessageBox MB_YESNO|MB_DEFBUTTON2 "Also delete ${APP}'s settings and event logs?" /SD IDNO IDNO keep
  RMDir /r "$INSTDIR\app"
keep:
  RMDir "$INSTDIR\app"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${UNINST_KEY}"
  DetailPrint "radioconda, the SDRplay API and ffmpeg are left installed; remove them in Settings > Apps if wanted."
SectionEnd
