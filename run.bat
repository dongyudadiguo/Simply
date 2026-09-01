@echo off
cd /d %~dp0
start server.exe
timeout /t 1 /nobreak >nul
vm.exe
