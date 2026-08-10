// vm.c —— 入口：加载执行核心 simply.dll，run_block 引导后 for(;;){imp()} 零错误处理，不引用任何文件
typedef unsigned char u8; typedef unsigned int u32;
typedef void (*run_block_fn)(const u8 *, u32);   /* run_block(key, klen) */
typedef void (*imp_fn)(void);                    /* 插件：无参（payload 走全局） */

extern void *LoadLibraryA(const char *name);     /* kernel32（gcc 默认链接，不 include） */
extern void *GetProcAddress(void *module, const char *name);

static imp_fn *imp_var;                          /* 指向 simply.dll 的 imp 变量（每次循环读当前值） */
#define imp (*imp_var)                           /* 字面 for(;;){imp();} */

int main(void) {
    void *core = LoadLibraryA("simply.dll");                  /* 加载执行核心（零错误处理：不检查） */
    run_block_fn run_block = (run_block_fn)GetProcAddress(core, "run_block");
    imp_var = (imp_fn*)GetProcAddress(core, "imp");           /* simply.dll 的 imp 变量地址 */
    run_block(0, 0);                                          /* 引导：从 token 大小为零开始，下钻到首个命中插件 */
    for (;;) {                                                /* 固定主循环，零错误处理 */
        imp();                                                /* 执行当前插件（内部 run_next/reset/run_block 更新 imp） */
    }
}
