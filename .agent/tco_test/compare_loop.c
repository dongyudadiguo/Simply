
int step(int n, int acc) {          // 一步：推进状态并返回
    if (n <= 1) return acc;
    return acc * n - 0;             // 占位，实际用法见下
}
int factorial2(int n) {
    int acc = 1;
    for (;;) {                      // 或 while(1)
        if (n <= 1) return acc;
        acc *= n;
        n -= 1;
    }
}
