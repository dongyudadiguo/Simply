
void abc(int n);
void def(int n);

void abc(int n) {
    if (n <= 0) return;
    def(n - 1);      /* 尾调用 def() */
}

void def(int n) {
    if (n <= 0) return;
    abc(n - 1);      /* 尾调用 abc() */
}
