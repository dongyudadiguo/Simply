
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
unsigned imp2(unsigned acc);

unsigned pure_loop(unsigned n) {          /* 纯迭代 */
    unsigned acc = 0;
    while (n--) acc = acc + 1;
    return acc;
}
unsigned tramp_sep(unsigned n) {           /* 蹦床 + 外部 call */
    unsigned acc = 0;
    for (;;) { if (!n) return acc; acc = imp2(acc); --n; }
}
unsigned tramp_inl(unsigned n) {           /* 蹦床 + 内联 */
    unsigned acc = 0;
    for (;;) { if (!n) return acc; acc = acc + 1; --n; }
}
unsigned tail(unsigned n, unsigned acc) {  /* 尾递归(TCO) */
    if (n == 0) return acc;
    return tail(n - 1, acc + 1);
}
unsigned tail_wrap(unsigned n){ return tail(n,0); }

double bench(unsigned (*f)(unsigned), unsigned n, int reps){
    clock_t t0 = clock(); volatile unsigned s=0;
    for(int r=0;r<reps;++r) s += f(n);
    return (double)(clock()-t0)/CLOCKS_PER_SEC;
}
int main(int argc, char**argv){
    unsigned n=atoi(argv[1]); int reps=atoi(argv[2]);
    struct { const char*n; unsigned(*f)(unsigned);} t[] = {
        {"纯迭代(基准)  ", pure_loop},
        {"尾递归(TCO)   ", tail_wrap},
        {"蹦床-外部call ", tramp_sep},
        {"蹦床-内联     ", tramp_inl},
    };
    for(int i=0;i<4;++i) printf("%s : %8.3f ms\n", t[i].n, bench(t[i].f,n,reps)*1000);
    return 0;
}
