@echo off
cd /d %~dp0
start server.exe
timeout /t 1 /nobreak >nul
upload_boot.exe
del id.bin 2>nul
vm.exe
