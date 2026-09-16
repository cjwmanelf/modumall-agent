@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================================
echo  🛍️ 모두몰 고객 응대 AI 에이전트 GUI 대시보드를 시작합니다
echo ========================================================
echo 잠시 후 웹 브라우저가 자동으로 열립니다...
python app_gui.py
pause
