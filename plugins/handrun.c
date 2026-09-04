#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    if (payload.size >= 8) {
        data id = (data){payload.ptr, 8};
        var_unit *var = find_or_add_var(&global_var, &global_var_count, id);
        if (!var->data.ptr) {
            var->data.ptr = calloc(1, 8);
            var->data.size = 8;
        }
        uint8_t *b = (uint8_t*)var->data.ptr;
        data target = (data){(char*)payload.ptr + 8, payload.size - 8};
        if (b[0] != 0) {
            b[0] = 0;
            drill(target);
        } else if (b[1] != 0) {
            drill(target);
        } else {
            run_next();
        }
    } else {
        run_next();
    }
}
