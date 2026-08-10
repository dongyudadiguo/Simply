
#include <stdio.h>
#include <time.h>
#include <stdlib.h>

unsigned imp(unsigned n, unsigned acc);          /* 外部定义，不可内联 */

static inline unsigned mix(unsigned x) {         /* 可内联的运算 */
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return x;
}

/* ① 纯迭代（基准） */
unsigned loop_iter(unsigned n) {
    unsigned acc = 0;
    while (n) { --n; acc = mix(acc + n); }
    return acc;
}

/* ② 尾递归（靠编译器 TCO） */
unsigned loop_tail(unsigned n, unsigned acc) {
    if (n == 0) return acc;
    return loop_tail(n - 1, mix(acc + (n - 1)));
}
unsigned tail_wrap(unsigned n) { return loop_tail(n, 0); }

/* ③ 蹦床：for(;;){imp();}，imp 单独编译单元（真实 call 开销） */
unsigned loop_tramp_sep(unsigned n) {
    unsigned acc = 0;
    for (;;) {
        if (n == 0) return acc;
        acc = imp(n - 1, acc);
        --n;
    }
}

/* ④ 蹦床：imp 内联（等价于纯循环） */
unsigned loop_tramp_inl(unsigned n) {
    unsigned acc = 0;
    for (;;) {
        if (n == 0) return acc;
        acc = mix(acc + (n - 1));
        --n;
    }
}

double bench(unsigned (*f)(unsigned), unsigned n, int reps) {
    clock_t t0 = clock();
    volatile unsigned sink = 0;
    for (int r = 0; r < reps; ++r) sink += f(n);
    clock_t t1 = clock();
    return (double)(t1 - t0) / CLOCKS_PER_SEC;
}

int main(int argc, char** argv) {
    unsigned n    = (unsigned)atoi(argv[1]);
    int reps      = atoi(argv[2]);
    struct { const char* name; unsigned (*f)(unsigned); } tab[] = {
        {"① 纯迭代(基准)     ", loop_iter},
        {"② 尾递归(TCO)      ", tail_wrap},
        {"③ 蹦床-外部imp(不内联)", loop_tramp_sep},
        {"④ 蹦床-内联imp     ", loop_tramp_inl},
    };
    int k = sizeof(tab)/sizeof(tab[0]);
    for (int i = 0; i < k; ++i)
        printf("%s : %7.3f ms\n", tab[i].name, bench(tab[i].f, n, reps) * 1000.0);
    return 0;
}
