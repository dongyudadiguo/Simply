#include "plug_api.h"

__declspec(dllexport) void run(void) {
    off_reset();
    *(int*)stk = *(int*)stk + *(int*)((char*)stk + 4);
    Add_size(4);
    run_next();
}
