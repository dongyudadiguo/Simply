// vm.c —— vm 导出 imp；加载执行核心 block.dll；run_block 引导后 for(;;){imp()} 零错误处理，不引用任何文件
typedef unsigned char u8;
typedef unsigned int u32;
typedef struct { u32 n; const u8 *d; } data;   /* 与 block.dll 的 run_block(data) 对齐 */
typedef void (*run_block_fn)(data);
typedef void (*imp_fn)(void);

extern void *LoadLibraryA(const char *name);
extern void *GetProcAddress(void *module, const char *name);

__declspec(dllexport) imp_fn imp;

int main(void){
    data empty = {0, 0};                                            /* 空 key：入口引导 */
    ((run_block_fn)GetProcAddress(LoadLibraryA("block.dll"), "run_block"))(empty);
    for (;;){imp();}
}
