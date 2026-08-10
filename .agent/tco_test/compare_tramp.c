
typedef struct { int n; int acc; int done; } State;
State step2(State s) {
    if (s.n <= 1) { s.done = 1; return s; }
    s.acc *= s.n;
    s.n   -= 1;
    return s;
}
int factorial3(int n) {
    State s = { n, 1, 0 };
    for (;;) {                      // ← for(;;){imp();} 蹦床
        if (s.done) return s.acc;
        s = step2(s);               // 每次普通调用，返回，栈不涨
    }
}
