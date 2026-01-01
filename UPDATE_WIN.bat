@echo off
chcp 65001
cd /d "%~dp0"

echo.
echo 🔄 ==========================================
echo    Kerygma Theology AI Lab 업데이트
echo ==========================================
echo.

:: 1. 기존 설치 확인
echo 📋 현재 상태 확인 중...

if not exist "01_Library" (
    echo ❌ 기존 설치를 찾을 수 없습니다.
    echo    신규 설치는 1_INSTALL_WIN.bat를 사용하세요.
    pause
    exit /b 1
)

echo ✅ 데이터 폴더 확인됨:
echo    - 01_Library/ (archive, inbox)
echo    - 02_Brain/ (vector_db)

:: 2. 새 버전 압축파일 확인
for /f "delims=" %%i in ('dir /b /o-d Kerygma_*_Clean.zip 2^>nul') do (
    set NEW_ZIP=%%i
    goto :found_zip
)
echo.
echo ⚠️  새 버전 zip 파일이 없습니다.
echo    업데이트 zip 파일을 이 폴더에 넣어주세요.
pause
exit /b 1

:found_zip
echo.
echo 📦 발견된 업데이트: %NEW_ZIP%
set /p confirm="이 버전으로 업데이트하시겠습니까? [y/N] "
if /i not "%confirm%"=="y" (
    echo 업데이트가 취소되었습니다.
    exit /b 0
)

:: 3. 기존 코드 백업
echo.
echo 💾 기존 코드 백업 중...
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "BACKUP_DIR=03_System_backup_%dt:~0,8%_%dt:~8,6%"
rename 03_System "%BACKUP_DIR%"
echo    → %BACKUP_DIR%

:: 4. 새 코드 추출
echo 📂 새 버전 코드 추출 중...
powershell -command "Expand-Archive -Path '%NEW_ZIP%' -DestinationPath 'temp_update' -Force"
move temp_update\03_System 03_System >nul
rmdir /s /q temp_update

if not exist "03_System" (
    echo ❌ 추출 실패! 백업 복원 중...
    rename "%BACKUP_DIR%" 03_System
    exit /b 1
)

:: 5. 가상환경 재사용
if exist "%BACKUP_DIR%\venv" (
    echo 🐍 가상환경 재사용...
    move "%BACKUP_DIR%\venv" 03_System\venv >nul
)

:: 6. 의존성 업데이트
echo ⬇️  의존성 업데이트 중...
call 03_System\venv\Scripts\activate.bat 2>nul || (
    echo    가상환경 없음, 새로 생성...
    python -m venv 03_System\venv
    call 03_System\venv\Scripts\activate.bat
)
pip install --upgrade pip -q
pip install -r 03_System\requirements.txt -q

:: 7. 완료
echo.
echo ✅ ==========================================
echo    업데이트 완료!
echo ==========================================
echo.
echo 📊 보존된 데이터:
echo    - 01_Library/archive/ (청킹 데이터)
echo    - 02_Brain/vector_db/ (벡터 DB)
echo    - .env (API 키)
echo.
echo 💾 백업 위치: %BACKUP_DIR%
echo.

set /p run="연구소를 실행하시겠습니까? [Y/n] "
if /i not "%run%"=="n" (
    call 3_START_WIN.bat
)
