@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ===== 배치가 있는 폴더(프로젝트 폴더)로 이동 =====
set "PROJ=%~dp0"
cd /d "%PROJ%" || goto :err_path

REM ===== 파이썬 실행 경로 =====
set "PYTHON_EXE=D:\Miniconda\envs\py39\python.exe"

REM ===== 로그 파일(날짜/시간 포함) =====
if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do set "D=%%a%%b%%c"
for /f "tokens=1-3 delims=:." %%a in ("%time%") do set "T=%%a%%b%%c"
set "LOG=logs\run_%D%_%T%.log"

echo ======================================
echo  뉴스레터 실행 시작
echo  PROJ: %PROJ%
echo  PYTHON: %PYTHON_EXE%
echo  LOG: %LOG%
echo ======================================

REM ===== 실행 (콘솔 + 파일 동시 출력) =====
powershell -NoProfile -Command ^
    "& '%PYTHON_EXE%' -u run.py 2>&1 | Tee-Object -FilePath '%LOG%'"
set "ERR=%ERRORLEVEL%"

if not "%ERR%"=="0" goto :err_run

echo.
echo ======================================
echo  SUCCESS (exit code 0)
echo  로그: %LOG%
echo ======================================
exit /b 0

:err_path
echo.
echo [ERROR] 프로젝트 경로 이동 실패
echo PROJ=%PROJ%
pause
exit /b 1

:err_run
echo.
echo ======================================
echo  [ERROR] run.py 실행 실패 (exit code=%ERR%)
echo  로그 파일을 확인하세요:
echo  %LOG%
echo ======================================
pause
exit /b %ERR%
