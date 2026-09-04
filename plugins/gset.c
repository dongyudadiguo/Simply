#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    data read = read_stk();
    var_unit* var = find_or_add_var(&global_var, &global_var_count, payload);
    if (!var->data.ptr || var->data.size < read.size) {
        var->data.ptr = malloc(read.size ? read.size : 1);
    }
    var->data.size = read.size;
    if (read.size) memcpy(var->data.ptr, read.ptr, read.size);
    run_next();
}
