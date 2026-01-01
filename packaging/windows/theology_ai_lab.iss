; ============================================================================
; Theology AI Lab v2 - Inno Setup 스크립트
; ============================================================================
;
; 빌드 방법:
;   1. Inno Setup 설치: https://jrsoftware.org/isinfo.php
;   2. 이 파일을 Inno Setup Compiler로 열기
;   3. Build > Compile (Ctrl+F9)
;
; ============================================================================

#define MyAppName "Theology AI Lab"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "케리그마출판사"
#define MyAppURL "https://www.kerygma.co.kr"
#define MyAppExeName "INSTALL_ONECLICK.bat"

[Setup]
; 앱 정보
AppId={{B5C7E8F9-A1D2-4E3F-B6C8-D9E0F1A2B3C4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 설치 경로
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; 출력 설정
OutputDir=..\..\dist
OutputBaseFilename=Theology_AI_Lab_v{#MyAppVersion}_Setup
Compression=lzma2
SolidCompression=yes

; 권한
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 비주얼
WizardStyle=modern
SetupIconFile=..\resources\icon.ico
UninstallDisplayIcon={app}\resources\icon.ico

; 언어
; 한국어 지원을 위해 별도 언어 파일 필요
; 기본은 영어

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel1=Welcome to [name] Setup
WelcomeLabel2=This will install [name/ver] on your computer.%n%nIMPORTANT: Docker Desktop is required.%nIf not installed, you will be prompted to download it.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 프로젝트 파일 복사
Source: "..\..\01_Library\*"; DestDir: "{app}\01_Library"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\02_Brain\*"; DestDir: "{app}\02_Brain"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\03_System\*"; DestDir: "{app}\03_System"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "venv\*,__pycache__\*,*.pyc"
Source: "..\..\docker-compose.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\INSTALL_ONECLICK.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\*.example"; DestDir: "{app}"; Flags: ignoreversion
; 리소스
Source: "..\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName} 설치 실행"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} 폴더 열기"; Filename: "{app}"
Name: "{group}\README"; Filename: "{app}\README.md"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; 설치 후 Docker 확인 및 설치 스크립트 실행 여부
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,설치 시작}"; Flags: nowait postinstall skipifsilent shellexec

[Code]
// Docker Desktop 설치 확인
function DockerInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c docker --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

// Docker 미설치 시 경고
procedure CurPageChanged(CurPageID: Integer);
var
  Msg: String;
begin
  if CurPageID = wpReady then
  begin
    if not DockerInstalled() then
    begin
      Msg := 'Docker Desktop이 설치되어 있지 않습니다.' + #13#10 + #13#10 +
             'Theology AI Lab을 사용하려면 Docker Desktop이 필요합니다.' + #13#10 +
             '설치 완료 후 Docker Desktop을 먼저 설치해 주세요.' + #13#10 + #13#10 +
             'Docker Desktop 다운로드: https://www.docker.com/products/docker-desktop/';
      MsgBox(Msg, mbInformation, MB_OK);
    end;
  end;
end;

// 설치 후 README 열기 옵션
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 필요시 추가 작업
  end;
end;
