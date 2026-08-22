// vm.c —— vm 导出 imp；加载执行核心 block.dll；run_block 引导后 for(;;){imp()} 零错误处理，不引用任何文件
typedef void (*run_block_fn)(void);
typedef void (*imp_fn)(void);

extern void *LoadLibraryA(const char *name);
extern void *GetProcAddress(void *module, const char *name);

__declspec(dllexport) imp_fn imp;

int main(void){
    ((run_block_fn)GetProcAddress(LoadLibraryA("block.dll"), "run"))();
    for (;;){imp();}
}
