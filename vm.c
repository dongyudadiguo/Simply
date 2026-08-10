// vm.c —— 虚拟机入口：一行 run_block 空 key 引导，不引用任何文件
void run_block(const unsigned char *key, unsigned int klen);   /* 自声明（block.c 实现） */

int main(void) {
    run_block(0, 0);          /* 从 token 大小为零开始（尾调用执行链接管全部） */
}
