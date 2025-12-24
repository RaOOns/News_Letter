@echo off
chcp 65001 > nul

REM ===== 프로젝트 경로 =====
cd /d "C:\Users\user\OneDrive\01. Codings\00. 개인 작업\Agent\New_letter"

REM ===== Python 환경 경로 =====
set PYTHON_EXE=D:\Miniconda\envs\py39\python.exe

REM ===== 실행 =====
echo ======================================
echo  뉴스레터 생성 프로그램 실행 중...
echo ======================================
%PYTHON_EXE% run.py

echo.
echo ======================================
echo  작업 완료. 아무 키나 누르면 종료됩니다.
echo ======================================
pause
