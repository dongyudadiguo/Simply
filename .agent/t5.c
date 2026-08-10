
typedef void (*fnptr)(int);

/* 运行时根据 n 的奇偶，不确定地选一个函数指针来尾调用 */
void dispatch(fnptr f_even, fnptr f_odd, int n) {
    if (n <= 0) return;
    if (n % 2 == 0)
        f_even(n - 1);     /* 条件分支里的尾调用 */
    else
        f_odd(n - 1);      /* 条件分支里的尾调用 */
}
