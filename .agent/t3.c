
int abc(int n, int acc);
int def(int n, int acc);

int abc(int n, int acc) {
    if (n <= 0) return acc;
    return def(n - 1, acc + n);     /* 尾调用 */
}

int def(int n, int acc) {
    if (n <= 0) return acc;
    return abc(n - 1, acc + n);     /* 尾调用 */
}
