#ifndef PLUG_API_H
#define PLUG_API_H
#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define Add_size(...) \
    add_size((int)(sizeof((int[]){__VA_ARGS__}) / sizeof(int)), \
      (int[]){__VA_ARGS__})

typedef uint32_t u32;

typedef struct {
    union { void *d; void *ptr; };
    union { unsigned n; unsigned size; };
} data;

typedef struct var_unit {
    data id;
    data data;
} var_unit;

static inline void *get_vm_proc(const char *name) {
    return (void*)GetProcAddress(GetModuleHandleA(0), name);
}

static inline void run_next(void) {
    typedef void (*fn)(void);
    ((fn)get_vm_proc("run_next"))();
}

static inline void drill(data k) {
    typedef void (*fn)(data);
    ((fn)get_vm_proc("drill"))(k);
}

static inline void rerun(void) {
    typedef void (*fn)(void);
    ((fn)get_vm_proc("rerun"))();
}

static inline data read_payload(void) {
    typedef data (*fn)(void);
    return ((fn)get_vm_proc("read_payload"))();
}

static inline data ptr_to_data(void *ptr) {
    typedef data (*fn)(void *);
    return ((fn)get_vm_proc("ptr_to_data"))(ptr);
}

static inline void off_reset(void) {
    typedef void (*fn)(void);
    ((fn)get_vm_proc("off_reset"))();
}

static inline void add_size(int count, int *arr) {
    typedef void (*fn)(int, int *);
    ((fn)get_vm_proc("add_size"))(count, arr);
}

static inline var_unit *find_or_add_var(var_unit **p_vars, int *p_count, data payload) {
    typedef var_unit *(*fn)(var_unit**, int*, data);
    return ((fn)get_vm_proc("find_or_add_var"))(p_vars, p_count, payload);
}

static inline void **get_stk_ptr(void) { return (void**)get_vm_proc("stk"); }
static inline void **get_stk_off_ptr(void) { return (void**)get_vm_proc("stk_off"); }
static inline var_unit **get_local_var_ptr(void) { return (var_unit**)get_vm_proc("local_var"); }
static inline int *get_local_var_count_ptr(void) { return (int*)get_vm_proc("local_var_count"); }
static inline var_unit **get_global_var_ptr(void) { return (var_unit**)get_vm_proc("global_var"); }
static inline int *get_global_var_count_ptr(void) { return (int*)get_vm_proc("global_var_count"); }

#define stk (*get_stk_ptr())
#define stk_off (*get_stk_off_ptr())
#define local_var (*get_local_var_ptr())
#define local_var_count (*get_local_var_count_ptr())
#define global_var (*get_global_var_ptr())
#define global_var_count (*get_global_var_count_ptr())
#define num_off (*(int*)get_vm_proc("num_off"))
#define num ((int*)get_vm_proc("num"))

#endif
