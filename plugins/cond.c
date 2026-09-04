#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    data cond_val = read_stk();
    int v = 0;
    if (cond_val.size >= 4) v = *(int*)cond_val.ptr;
    else if (cond_val.size > 0) v = *(uint8_t*)cond_val.ptr;
    if (v != 0 && payload.size > 4) {
        if (payload.size >= 8) {
            uint32_t tlen = *(uint32_t*)((char*)payload.ptr + 4);
            if (tlen > 0 && tlen <= payload.size - 8) {
                drill((data){(char*)payload.ptr + 8, tlen});
                return;
            }
        }
        drill((data){(char*)payload.ptr + 4, payload.size - 4});
    } else {
        run_next();
    }
}
