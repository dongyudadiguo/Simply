@echo off
setlocal EnableDelayedExpansion
cd /d %~dp0
set RL=raylib-6.0_win64_mingw-w64
echo [1/5] server...
gcc server.c -o server.exe -lws2_32
gcc upload_boot.c net.c -o upload_boot.exe -lws2_32
echo [2/5] block.dll（执行核心：block+vmstate+net+sha256；导出 + 生成导入库 libblock.dll.a）...
gcc -shared -O2 -I. block.c vmstate.c net.c sha256.c -o block.dll -Wl,--export-all-symbols,--out-implib,libblock.dll.a -lws2_32
echo [3/5] 插件 DLL（token→sha256→<sha256>.dll，链接 block 导入库）...
gcc -shared -O2 -I. editor.c -o 1553cc62ff246044c683a61e203e65541990e7fcd4af9443d22b9557ecc9ac54.dll -L. -lblock -I%RL%\include -L%RL%\lib -lraylib -lopengl32 -lgdi32 -lwinmm
gcc -shared -O2 -I. plugins\rerun.c -o 1fae2d16b59d6f7805146bff66f1e5dd6d2746b633323a073e75381bd87bb198.dll -L. -lblock
gcc -shared -O2 -I. plugins\add.c -o 7e9e5ac30f2216fd0fd6f5faed316f2d5983361a4203c3330cfa46ef65bb4767.dll -L. -lblock
gcc -shared -O2 -I. plugins\read.c -o 3316348dbadfb7b11c7c2ea235949419e23f9fa898ad2c198f999617912a9925.dll -L. -lblock
gcc -shared -O2 -I. plugins\set.c -o 6ee0eb490ff832101cf82a3d387c35f29e4230be786978f7acf9e811febf6723.dll -L. -lblock
gcc -shared -O2 -I. plugins\cond.c -o 0ab2dd2f64c9fd4e4310cfbb82556f0596060583dec1a7ab2d178603c3eb61d0.dll -L. -lblock
gcc -shared -O2 -I. plugins\handrun.c -o 1efbbfe37152c8aac8656b92eb9931cfab51a9f6551f5615dd194f45232002c0.dll -L. -lblock
gcc -shared -O2 -I. plugins\condrerun.c -o 8494db7bf4e15548b5190d1931af3def87cc6e78e65dd0063661f0152d34bf45.dll -L. -lblock
gcc -shared -O2 -I. plugins\push_int.c -o 7eba37840d6a2b1a450bc928b1c609d6b6ce898404adb31aeb89922d983d86eb.dll -L. -lblock
gcc -shared -O2 -I. plugins\in_int.c -o 6c9c489a2623567f145be88deb55d57dea54390b01f487e1d0b232c93284e8ef.dll -L. -lblock
gcc -shared -O2 -I. plugins\out.c -o 762069bc07a6e1b5df123a5ae7bd91c10daa04694fbaa17fba0cd6a8dcce8f22.dll -L. -lblock
gcc -shared -O2 -I. plugins\rand.c -o 1c1c65e8f2de96f1f1dd8a3b574871477a13cc8fbd46b591e988206170735238.dll -L. -lblock
gcc -shared -O2 -I. plugins\gt.c -o e294affa6863e16fbecdff7cffbaf1237a8f2ee2ab2805bb3cacc7fc16d079b2.dll -L. -lblock
gcc -shared -O2 -I. plugins\lt.c -o 67d4143062b55c25f383c9fabbbf1422fad06a2fe0644b43da67c17886dd4bd4.dll -L. -lblock
gcc -shared -O2 -I. plugins\eq.c -o 7d601f9d20703a97b8cb530538dbbadaa3e4bdfa5f333977e4232f51eebdc47a.dll -L. -lblock
gcc -shared -O2 -I. plugins\mul.c -o 29df0906e1730ea20667b4788939c47a20cf1cde6fa8ca173307efde7088f458.dll -L. -lblock
gcc -shared -O2 -I. plugins\ret_int.c -o d664ad15d6e646438631c4c10fce62d447e9f4e8ec4f07dcf1e33239578bc8ba.dll -L. -lblock
echo [4/5] vm.exe（独立编译，命令不变）...
gcc vm.c -o vm.exe
echo [5/5] raylib.dll...
copy /Y %RL%\lib\raylib.dll . >nul
echo BUILD OK
