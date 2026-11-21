@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
  py server.py
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
    python server.py
  ) else (
    echo Python bulunamadi. https://www.python.org/downloads/ adresinden Python yukleyin.
  )
)
pause
