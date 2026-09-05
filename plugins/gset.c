#include "plug_api.h"

__declspec(dllexport) void run(void) {
    var_unit* var = find_or_add_var(&global_var, &global_var_count, read_payload());
    free(var->data.ptr);
    int size = num[num_off++];
    var->data.ptr = memcpy(malloc(size), stk_off, size);
    stk_off += size;
    run_next();
}
