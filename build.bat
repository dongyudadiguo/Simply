@echo off
cd /d %~dp0
set RL=raylib-6.0_win64_mingw-w64
echo [1/3] core...
gcc server.c -o server.exe -lws2_32
gcc upload_boot.c net.c -o upload_boot.exe -lws2_32
echo [2/3] vm + plugins（全部内建，链 raylib）...
set SRC=vm.c block.c vmstate.c net.c
for %%f in (plugins\*.c) do set SRC=%%SRC%% %%f
gcc -O2 %SRC% editor.c -o vm.exe -I%RL%\include -L%RL%\lib -lraylib -lopengl32 -lgdi32 -lwinmm -lws2_32
echo [3/3] raylib.dll...
copy /Y %RL%\lib\raylib.dll . >nul
echo BUILD OK
