#include "plug_api.h"

__declspec(dllexport) void run(void) {
    off_reset();
    data payload = read_payload();
    data id = (data){payload.ptr, 8};
    var_unit *var = find_or_add_var(&global_var, &global_var_count, id);
    if (!var->data.ptr) {
        var->data = (data){calloc(1, 8), 8};
    }
}
