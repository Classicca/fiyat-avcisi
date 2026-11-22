@echo off
cd /d "%~dp0"
py -3 local_preview.py
if errorlevel 1 pause
