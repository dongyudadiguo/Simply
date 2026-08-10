
typedef void (*fnptr)(int);

void dispatch(fnptr f, int n) {
    if (n <= 0) return;
    f(n - 1);          /* 通过函数指针做尾调用，目标运行时才知道 */
}
