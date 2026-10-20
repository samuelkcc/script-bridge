Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "FileMaker Script Bridge"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\FileMaker Script Bridge"
InstallDirRegKey HKCU "Software\SCKC\FileMaker Script Bridge" "InstallDir"
RequestExecutionLevel user
SetCompressor zlib
BrandingText "FileMaker Script Bridge ${VERSION} · SCKC"
VIProductVersion "1.0.0.3"
VIAddVersionKey "ProductName" "FileMaker Script Bridge"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "FileMaker Script Bridge Windows x64 setup"
VIAddVersionKey "LegalCopyright" "Copyright © 2026 SCKC. GPL-3.0-or-later."
!define MUI_ICON "${ROOT}/Desktop/src-tauri/icons/icon.ico"
!define MUI_UNICON "${ROOT}/Desktop/src-tauri/icons/icon.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Install FileMaker Script Bridge ${VERSION} for this Windows account.$\r$\n$\r$\nThe app includes its conversion and AI engines. Qwen models are optional downloads.$\r$\n$\r$\nIf Microsoft WebView2 is missing, setup installs it from Microsoft and needs an internet connection."
!define MUI_FINISHPAGE_RUN "$INSTDIR\FileMakerScriptBridge.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open FileMaker Script Bridge"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${ROOT}/LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "This package requires 64-bit Windows."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "This package requires Windows 10 or later."
    Abort
  ${EndIf}
FunctionEnd

Section "FileMaker Script Bridge" Main
retry_close:
  FindWindow $0 "" "FileMaker Script Bridge"
  ${If} $0 != 0
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Close FileMaker Script Bridge before updating it." IDRETRY retry_close
    Abort
  ${EndIf}
  ; Microsoft documents HKLM's 32-bit view and HKCU's per-user key.
  SetRegView 32
  ReadRegStr $0 HKLM "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" "pv"
  ${EndIf}
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    InitPluginsDir
    SetOutPath "$PLUGINSDIR"
    File "${ROOT}/.build/MicrosoftEdgeWebview2Setup.exe"
    DetailPrint "Installing Microsoft WebView2 Runtime…"
    ExecWait '"$PLUGINSDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install' $0
    ${If} $0 != 0
    ${AndIf} $0 != 3010
      MessageBox MB_ICONSTOP "Microsoft WebView2 setup could not finish (code $0). Install WebView2 from Microsoft, then run this installer again."
      Abort
    ${EndIf}
  ${EndIf}
  SetRegView 64
  SetOutPath "$INSTDIR"
  File /r "${STAGE}/*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$SMPROGRAMS\FileMaker Script Bridge.lnk" "$INSTDIR\FileMakerScriptBridge.exe" "" "$INSTDIR\FileMakerScriptBridge.exe" 0
  WriteRegStr HKCU "Software\SCKC\FileMaker Script Bridge" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "DisplayName" "FileMaker Script Bridge"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "Publisher" "SCKC"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "DisplayIcon" "$INSTDIR\FileMakerScriptBridge.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetRegView 64
  !include "${UNINSTALL_FILES}"
  Delete "$SMPROGRAMS\FileMaker Script Bridge.lnk"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\SCKC\FileMaker Script Bridge"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FileMakerScriptBridge"
SectionEnd
