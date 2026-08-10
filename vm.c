// vm.c —— 入口（对齐 vm.py）：一行 run_block 空 key 引导，尾调用执行链接管全部
#include "api.h"
int main(void) { run_block(NULL, 0); }
