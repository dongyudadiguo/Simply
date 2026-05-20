import os, socket, struct, hashlib

HOST = "124.221.146.23"
PORT = 9000

UPLOAD_FILE = 2
ADD_CHILD = 4

OUT = "ins_js"

FILES = {
"CONTINUE.js": r'''
(async () => {
    await CVM.continue_();
})();
''',

"BLOCK_END.js": r'''
(async () => {
    await CVM.block_end();
})();
''',

"IF.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);

    let trueblock = {
        buf: data.buf,
        off: data.off + 4
    };

    let after = C.next_of(data);
    after = C.skip_data_of(after);

    if (C.STD[0]) {
        C.FRAMES.push(after);
        await C.run_block_auto(trueblock);
    } else {
        C.PTR = after;
        await C.run_block_auto(C.PTR);
    }
})();
''',

"IFF.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);

    let trueblock = {
        buf: data.buf,
        off: data.off + 4
    };

    let falseblock = C.next_of(trueblock);

    let after = C.next_of(data);
    after = C.skip_data_of(after);

    C.FRAMES.push(after);

    if (C.STD[0])
        await C.run_block_auto(trueblock);
    else
        await C.run_block_auto(falseblock);
})();
''',

"CLEAR.js": r'''
(async () => {
    CVM.STD.fill(0);
    CVM.STD_OFFSET = 0;
    await CVM.continue_();
})();
''',

"VARSIZE.js": r'''
(async () => {
    let data = CVM.next_of(CVM.PTR);
    CVM.VAR_SIZE = CVM.block_size(data);
    await CVM.continue_();
})();
''',

"VARSET.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let id = C.block_data(data).toString("hex");

    let v = Buffer.alloc(C.VAR_SIZE);

    C.STD.copy(v, 0, 0, C.VAR_SIZE);

    C.VARS.set(id, v);

    await C.continue_();
})();
''',

"VARGET.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let id = C.block_data(data).toString("hex");

    let v = C.VARS.get(id);

    if (!v)
        v = Buffer.alloc(C.VAR_SIZE);

    v.copy(C.STD, C.STD_OFFSET, 0, C.VAR_SIZE);

    C.STD_OFFSET += C.VAR_SIZE;

    await C.continue_();
})();
''',

"INT.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let v = C.block_data(data).readInt32LE(0);

    C.STD.writeInt32LE(v, C.STD_OFFSET);
    C.STD_OFFSET += 4;

    await C.continue_();
})();
''',

"RANDOM_INT.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let d = C.block_data(data);

    let min = d.readInt32LE(0);
    let max = d.readInt32LE(4);

    let v = min + Math.floor(Math.random() * (max - min + 1));

    C.STD.writeInt32LE(v, C.STD_OFFSET);
    C.STD_OFFSET += 4;

    await C.continue_();
})();
''',

"CMP_EQ.js": r'''
(async () => {
    const C = CVM;

    let a = C.STD.readInt32LE(0);
    let b = C.STD.readInt32LE(4);

    C.STD[0] = a === b ? 1 : 0;
    C.STD_OFFSET = 1;

    await C.continue_();
})();
''',

"CMP_LT.js": r'''
(async () => {
    const C = CVM;

    let a = C.STD.readInt32LE(0);
    let b = C.STD.readInt32LE(4);

    C.STD[0] = a < b ? 1 : 0;
    C.STD_OFFSET = 1;

    await C.continue_();
})();
''',

"CMP_GT.js": r'''
(async () => {
    const C = CVM;

    let a = C.STD.readInt32LE(0);
    let b = C.STD.readInt32LE(4);

    C.STD[0] = a > b ? 1 : 0;
    C.STD_OFFSET = 1;

    await C.continue_();
})();
''',

"TEXT.js": r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let text = C.block_data(data).toString("utf8");

    console.log(text);

    await C.continue_();
})();
''',

"PRINT_INT.js": r'''
(async () => {
    let v = CVM.STD.readInt32LE(0);

    console.log(v);

    await CVM.continue_();
})();
''',

"INPUT_INT.js": r'''
(async () => {
    const readline = require("readline/promises");
    const C = CVM;

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    let s = await rl.question("> ");

    rl.close();

    let v = parseInt(s, 10);

    if (Number.isNaN(v))
        v = 0;

    C.STD.writeInt32LE(v, C.STD_OFFSET);
    C.STD_OFFSET += 4;

    await C.continue_();
})();
''',
}

INS = {
    "CONTINUE": "CONTINUE.js",
    "BLOCK_END": "BLOCK_END.js",
    "IF": "IF.js",
    "IFF": "IFF.js",
    "CLEAR": "CLEAR.js",
    "VARSIZE": "VARSIZE.js",
    "VARSET": "VARSET.js",
    "VARGET": "VARGET.js",
    "INT": "INT.js",
    "RANDOM_INT": "RANDOM_INT.js",
    "CMP_EQ": "CMP_EQ.js",
    "CMP_LT": "CMP_LT.js",
    "CMP_GT": "CMP_GT.js",
    "TEXT": "TEXT.js",
    "PRINT_INT": "PRINT_INT.js",
    "INPUT_INT": "INPUT_INT.js",
}

def sha(b):
    return hashlib.sha256(b).digest()

def key(name):
    return sha(name.encode())

def conn():
    return socket.create_connection((HOST, PORT))

def recvn(s, n):
    b = b""
    while len(b) < n:
        x = s.recv(n - len(b))
        if not x:
            raise Exception("closed")
        b += x
    return b

def upload(data):
    s = conn()
    s.sendall(bytes([UPLOAD_FILE]))
    s.sendall(struct.pack(">I", len(data)))
    s.sendall(data)
    recvn(s, 1)
    h = recvn(s, 32)
    s.close()
    return h

def add_child(parent, child):
    s = conn()
    s.sendall(bytes([ADD_CHILD]))
    s.sendall(parent)
    s.sendall(child)
    recvn(s, 1)
    s.close()

def write_files():
    os.makedirs(OUT, exist_ok=True)

    for name, code in FILES.items():
        path = os.path.join(OUT, name)

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(code.strip() + "\n")

def upload_ins():
    for ins, file in INS.items():
        path = os.path.join(OUT, file)

        with open(path, "rb") as f:
            data = f.read()

        h = upload(data)
        add_child(key(ins), h)

        print(f"{ins:12} {file:18} {h.hex()}")

def main():
    write_files()
    upload_ins()

if __name__ == "__main__":
    main()