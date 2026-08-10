// vmstate.c —— VM 运行时共享状态（对齐 vmstate.py）
#include "vm.h"
#include <stdlib.h>
#include <string.h>

void vms_push(VM *vm, const uint8_t *d, uint32_t n) {
    memcpy(vm->stk + vm->stk_off, d, n);
    vm->stk_off += n;
}
const uint8_t *vms_pop(VM *vm, uint32_t n) {
    vm->stk_off -= n;
    return vm->stk + vm->stk_off;
}
void vms_write_num(VM *vm, uint32_t sz) {
    memcpy(vm->num + vm->num_off, &sz, 4);
    vm->num_off += 4;
}

/* cur 表：按 key 存 toks（接管 tok 数组所有权），editor 维护、block 动态读 */
void vms_cur_set(VM *vm, const uint8_t *key, uint32_t klen, Tok *toks, size_t n) {
    CurEntry *e = vm->cur;
    while (e) {
        if (e->klen == klen && memcmp(e->key, key, klen) == 0) break;
        e = e->next;
    }
    if (!e) {
        e = (CurEntry*)calloc(1, sizeof(CurEntry));
        e->key = (uint8_t*)malloc(klen); memcpy(e->key, key, klen); e->klen = klen;
        e->next = vm->cur; vm->cur = e;
    } else {
        free(e->toks.tok);
    }
    e->toks.tok = toks; e->toks.n = n; e->toks.cap = n;
}
Tok *vms_cur_get(VM *vm, const uint8_t *key, uint32_t klen, size_t *out_n) {
    CurEntry *e = vm->cur;
    while (e) {
        if (e->klen == klen && memcmp(e->key, key, klen) == 0) { *out_n = e->toks.n; return e->toks.tok; }
        e = e->next;
    }
    *out_n = 0;
    return NULL;
}

/* handrun flags 表 */
void vms_hand_set(VM *vm, const uint8_t *id, uint8_t b1, uint8_t b2) {
    HandFlag *h = vm->hand;
    while (h) { if (memcmp(h->id, id, 8) == 0) { h->b1 = b1; h->b2 = b2; return; } h = h->next; }
    h = (HandFlag*)calloc(1, sizeof(HandFlag));
    memcpy(h->id, id, 8); h->b1 = b1; h->b2 = b2;
    h->next = vm->hand; vm->hand = h;
}
void vms_hand_get(VM *vm, const uint8_t *id, uint8_t *b1, uint8_t *b2) {
    HandFlag *h = vm->hand;
    while (h) { if (memcmp(h->id, id, 8) == 0) { *b1 = h->b1; *b2 = h->b2; return; } h = h->next; }
    *b1 = *b2 = 0;
}
