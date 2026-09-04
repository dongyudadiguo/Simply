#include "plug_api.h"

__declspec(dllexport) void run(void) {
    data payload = read_payload();
    data read = read_stk();
    var_unit* var = find_or_add_var(&local_var, &local_var_count, payload);
    void *buf = malloc(read.size ? read.size : 1);
    if (read.size) memcpy(buf, read.ptr, read.size);
    var->data = (data){buf, read.size};
    run_next();
}
