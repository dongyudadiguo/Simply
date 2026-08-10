// vm.c —— 虚拟机入口（对齐 vm.py）：run_block 空 key 引导 → while(1) exec(imp) 零错误处理
#include "vm.h"

int main(void) {
    run_block(NULL, NULL, 0);
}
