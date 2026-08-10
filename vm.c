// vm.c —— 虚拟机入口（对齐 vm.py）：run_block 空 key 引导 → while(1) exec(imp) 零错误处理
#include "vm.h"
#include <stdlib.h>
#include <stdio.h>

int main(void) {
    VM vm = {0};
    block_init(&vm);
    run_block(&vm, NULL, 0);                 /* 空 key 引导 → boot 插件接管 */
    for (;;) {                               /* while(1){exec(imp)} */
        if (!vm.imp) break;                  /* 全部走完（ret 栈空 + 无命中） */
        vm.imp(&vm, vm.imp_payload, vm.imp_plen);
    }
    return 0;
}
