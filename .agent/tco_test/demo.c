
#include <stdio.h>
int calls = 0;

/* 尾递归版：递归调用自身 */
int tail(int n, int acc, int depth) {
    if (n <= 0) return acc;
    if (calls++ < 4)
        printf("[tail  ] depth=%d 本帧地址=%p\n", depth, (void*)&n);
    return tail(n - 1, acc, depth + 1);
}

/* for(;;){imp();} 版：imp 每次做一步并返回 */
int imp(int n, int acc, int depth) {
    if (calls++ < 4)
        printf("[for(;;) ] depth=%d 本帧地址=%p\n", depth, (void*)&n);
    if (n <= 0) return acc;
    return acc;   /* 占位，实际循环里会更新状态 */
}
int looper(int n) {
    int acc = 1;
    for (;;) {
        int r = imp(n, acc, 0);
        if (n <= 0) return r;
        acc *= n;
        n -= 1;
    }
}

int main() {
    calls = 0;
    printf("--- 尾递归 tail(100,1) ---\n");
    tail(100, 1, 0);
    calls = 0;
    printf("--- for(;;){imp();} ---\n");
    looper(100);
    return 0;
}
