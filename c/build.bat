@echo off
cd /d %~dp0
set RL=..\raylib-6.0_win64_mingw-w64
echo [1/3] core...
gcc server.c -o server.exe -lws2_32
gcc upload_boot.c net.c -o upload_boot.exe -lws2_32
gcc vm.c block.c vmstate.c net.c sha256.c -o vm.exe -lws2_32
echo [2/3] plugins...
for %%f in (plugins\*.c) do (
  if "%%~nf"=="1553cc62ff246044c683a61e203e65541990e7fcd4af9443d22b9557ecc9ac54" (
    gcc -shared -o plugins\%%~nf.dll %%f -I. -I%%RL%%\include -L%%RL%%\lib -lraylib -lopengl32 -lgdi32 -lwinmm
  ) else (
    gcc -shared -o plugins\%%~nf.dll %%f -I.
  )
)
echo [3/3] raylib.dll...
copy /Y %%RL%%\lib\raylib.dll . >nul
echo BUILD OK
