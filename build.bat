@echo off
cd /d %~dp0
set RL=raylib-6.0_win64_mingw-w64
echo [1/4] server...
gcc server.c -o server.exe -lws2_32
gcc upload_boot.c net.c -o upload_boot.exe -lws2_32
echo [2/4] simply.dll£¨Ö´ÐÐºËÐÄ£ºblock+vmstate+net+plugins+editor£¬Á´ raylib£©...
set SRC=block.c vmstate.c net.c
for %%f in (plugins\*.c) do set SRC=%%SRC%% %%f
gcc -shared -O2 -I. %SRC% editor.c -o simply.dll -Wl,--export-all-symbols -I%RL%\include -L%RL%\lib -lraylib -lopengl32 -lgdi32 -lwinmm -lws2_32
echo [3/4] vm.exe£¨¶ÀÁ¢±àÒë£¬ÃüÁî²»±ä£©...
gcc vm.c -o vm.exe
echo [4/4] raylib.dll...
copy /Y %RL%\lib\raylib.dll . >nul
echo BUILD OK
