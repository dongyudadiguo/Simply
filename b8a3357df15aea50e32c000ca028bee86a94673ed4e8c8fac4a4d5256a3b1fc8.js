// first_editor.js
const http = require("http");
const net = require("net");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const HOST = "124.221.146.23";
const PORT = 9000;
const WEB_PORT = 7070;

const REGISTER        = 1;
const UPLOAD_FILE     = 2;
const DOWNLOAD_FILE   = 3;
const ADD_CHILD       = 4;
const STREAM_CHILDREN = 5;
const USER_SET_HASH   = 6;
const USER_GET_HASH   = 7;

const C = globalThis.CVM;

function sha256(b) {
    return crypto.createHash("sha256").update(b).digest();
}

function str_sha(s) {
    return sha256(Buffer.from(s));
}

function hex(b) {
    return Buffer.from(b).toString("hex");
}

function unhex(s) {
    return Buffer.from(s.replace(/\s+/g, ""), "hex");
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

function next_of(p) {
    return {
        buf: p.buf,
        off: p.off + 4 + block_size(p)
    };
}

function ptr_at(buf, off = 0) {
    return { buf, off };
}

function printable(b) {
    for (let x of b) {
        if (x === 9 || x === 10 || x === 13)
            continue;

        if (x < 32 || x > 126)
            return false;
    }

    return true;
}

function socket() {
    return new Promise(resolve => {
        let s = net.createConnection(PORT, HOST, () => resolve(s));
    });
}

function recv_all(s, n) {
    return new Promise(resolve => {
        let chunks = [];
        let len = 0;

        function ondata(data) {
            chunks.push(data);
            len += data.length;

            if (len >= n) {
                s.off("data", ondata);

                let buf = Buffer.concat(chunks, len);
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
    if (fs.existsSync("id.bin"))
        return fs.readFileSync("id.bin");

    let s = await socket();

    s.write(Buffer.from([REGISTER]));

    await recv_all(s, 1);
    let id = await recv_all(s, 32);

    s.end();

    fs.writeFileSync("id.bin", id);

    return id;
}

async function upload_file(data) {
    let s = await socket();

    let n = Buffer.alloc(4);
    n.writeUInt32BE(data.length);

    s.write(Buffer.concat([
        Buffer.from([UPLOAD_FILE]),
        n,
        data
    ]));

    await recv_all(s, 1);
    let h = await recv_all(s, 32);

    s.end();
    return h;
}

async function download_raw(h) {
    let s = await socket();

    s.write(Buffer.from([DOWNLOAD_FILE]));
    s.write(h);

    let st = (await recv_all(s, 1))[0];

    if (st !== 0)
        throw new Error("download failed: " + hex(h));

    let nb = await recv_all(s, 4);
    let n = nb.readUInt32BE(0);

    let data = await recv_all(s, n);

    s.end();
    return data;
}

async function download_file(h, ext = ".bin") {
    let data = await download_raw(h);
    let name = hex(h) + ext;
    let full = path.resolve(process.cwd(), name);

    fs.writeFileSync(full, data);

    return {
        path: full,
        data
    };
}

async function add_child(parent, child) {
    let s = await socket();

    s.write(Buffer.from([ADD_CHILD]));
    s.write(parent);
    s.write(child);

    await recv_all(s, 1);

    s.end();
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

async function stream_children(parent) {
    let s = await socket();

    s.write(Buffer.from([STREAM_CHILDREN]));
    s.write(parent);

    let out = [];

    while (1) {
        let st = (await recv_all(s, 1))[0];

        if (st === 2)
            break;

        if (st === 0)
            out.push(await recv_all(s, 32));
        else
            break;
    }

    s.end();
    return out;
}

async function user_set_hash(key, val) {
    let s = await socket();

    s.write(Buffer.from([USER_SET_HASH]));
    s.write(C.ID);
    s.write(key);
    s.write(val);

    await recv_all(s, 1);

    s.end();
}

async function user_get_hash(key) {
    let s = await socket();

    s.write(Buffer.from([USER_GET_HASH]));
    s.write(C.ID);
    s.write(key);

    let st = (await recv_all(s, 1))[0];

    if (st) {
        s.end();
        return null;
    }

    let h = await recv_all(s, 32);

    s.end();
    return h;
}

async function load_js(h) {
    let file = await download_file(h, ".js");

    delete require.cache[file.path];

    let mod = require(file.path);

    if (!mod.run)
        throw new Error("module has no run: " + file.path);

    return mod;
}

/* runtime */

C.ID = null;

C.sha256 = sha256;
C.str_sha = str_sha;
C.hex = hex;

C.read_i32 = read_i32;
C.block_size = block_size;
C.block_data = block_data;
C.next_of = next_of;

C.socket = socket;
C.recv_all = recv_all;

C.register_id = register_id;
C.upload_file = upload_file;
C.download_file = download_file;
C.download_raw = download_raw;
C.add_child = add_child;
C.get_first_child = get_first_child;
C.stream_children = stream_children;
C.user_set_hash = user_set_hash;
C.user_get_hash = user_get_hash;
C.load_js = load_js;

C.STD = Buffer.alloc(4096);
C.STD_OFFSET = 0;

C.VAR_SIZE = 4;
C.VARS = new Map();

C.FRAMES = [];
C.STACK = [];
C.CHECKLIST = [];

C.next_block = function () {
    C.PTR = C.next_of(C.PTR);
};

C.skip_all_data = function () {
    while (C.read_i32(C.PTR) < 0)
        C.next_block();
};

C.skip_data_of = function (p) {
    while (C.read_i32(p) < 0)
        p = C.next_of(p);

    return p;
};

C.continue_ = async function () {
    C.next_block();
    C.skip_all_data();

    await C.run_block_set(C.PTR);
};

C.block_end = async function () {
    let p = C.FRAMES.pop();

    if (!p)
        return;

    C.PTR = p;

    await C.run_block_auto(C.PTR);
};

C.check_all = async function () {
    for (let x of C.CHECKLIST) {
        let now = sha256(x.data);

        if (!now.equals(x.sha)) {
            let h = await upload_file(x.data);

            x.sha = h;

            await user_set_hash(x.key, h);
        }
    }
};

C.add_check = function (key, sha, data) {
    C.CHECKLIST.push({ key, sha, data });
};

C.execute_set = function (mod) {
    C.IMP = mod.run;
};

C.execute_call = async function (mod) {
    if (mod.run)
        await mod.run();
};

C.run_block_exec = async function (block, call) {
    C.PTR = block;

    while (1) {
        C.skip_all_data();

        let size = C.read_i32(C.PTR);

        let payload = C.PTR.buf.subarray(
            C.PTR.off + 4,
            C.PTR.off + 4 + size
        );

        let key = sha256(payload);

        let target = await user_get_hash(key);

        if (!target)
            target = await get_first_child(key);

        try {
            let mod = await load_js(target);

            if (call)
                await C.execute_call(mod);
            else
                C.execute_set(mod);

            return;
        } catch {
            let data = await download_raw(target);

            C.add_check(key, target, data);
            C.STACK.push(data);

            C.PTR = ptr_at(data, 0);
        }
    }
};

C.run_block_set = async block => C.run_block_exec(block, false);
C.run_block_call = async block => C.run_block_exec(block, true);
C.run_block_auto = async block => C.run_block_exec(block, true);

/* block parser */

function parse_blocks(buf) {
    let out = [];
    let off = 0;

    while (off + 4 <= buf.length) {
        let n = buf.readInt32LE(off);
        let sz = Math.abs(n);

        if (off + 4 + sz > buf.length)
            break;

        let data = buf.subarray(off + 4, off + 4 + sz);

        out.push({
            off,
            size: n,
            abs: sz,
            text: printable(data) ? data.toString("utf8") : null,
            hex: hex(data)
        });

        off += 4 + sz;
    }

    return out;
}

/* web */

function send(res, obj) {
    res.writeHead(200, {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
    });

    res.end(JSON.stringify(obj));
}

function send_html(res, html) {
    res.writeHead(200, {
        "Content-Type": "text/html; charset=utf-8"
    });

    res.end(html);
}

function body(req) {
    return new Promise(resolve => {
        let chunks = [];

        req.on("data", d => chunks.push(d));
        req.on("end", () => resolve(Buffer.concat(chunks)));
    });
}

const html_page = `
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>CVM Editor</title>
<style>
body{margin:0;background:#111;color:#ddd;font-family:Consolas,monospace}
#top{height:36px;background:#222;display:flex;align-items:center;padding:4px;gap:8px}
#main{display:grid;grid-template-columns:300px 1fr 420px;height:calc(100vh - 44px)}
.panel{border-right:1px solid #333;overflow:auto;padding:8px}
button,input{background:#222;color:#ddd;border:1px solid #555;padding:4px}
.item{padding:4px;border-bottom:1px solid #222;cursor:pointer}
.item:hover{background:#333}
.pos{color:#80ff80}
.neg{color:#ff8080}
.hex{color:#888;word-break:break-all}
textarea{width:100%;height:70vh;background:#080808;color:#ddd;border:1px solid #444;font-family:Consolas,monospace}
</style>
</head>
<body>
<div id="top">
<button onclick="openRoot()">Croot</button>
<input id="hashInput" style="width:520px" placeholder="hash hex">
<button onclick="openHash()">open</button>
<button onclick="saveHex()">save hex</button>
<span id="status"></span>
</div>
<div id="main">
<div class="panel"><h3>children</h3><div id="children"></div></div>
<div class="panel"><h3>blocks</h3><div id="blocks"></div></div>
<div class="panel"><h3>hex</h3><textarea id="hexedit"></textarea></div>
</div>

<script>
function qs(x){return document.querySelector(x)}

async function api(path,obj){
    let opt=obj?{
        method:"POST",
        body:JSON.stringify(obj),
        headers:{"Content-Type":"application/json"}
    }:{};
    let r=await fetch(path,opt);
    return await r.json();
}

function esc(s){
    return s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
}

function status(s){qs("#status").textContent=s}

function prettyHex(s){
    return s.match(/.{1,32}/g)?.join("\\n")||"";
}

async function openRoot(){
    let r=await api("/api/root");
    await openHashHex(r.hash);
}

async function openHash(){
    await openHashHex(qs("#hashInput").value.trim());
}

async function openHashHex(h){
    qs("#hashInput").value=h;
    status("loading");

    let d=await api("/api/download/"+h);
    qs("#hexedit").value=prettyHex(d.hex);
    drawBlocks(d.blocks);

    let c=await api("/api/children/"+h);
    drawChildren(c.children);

    status("ok");
}

function drawChildren(arr){
    let e=qs("#children");
    e.innerHTML="";
    for(let h of arr){
        let div=document.createElement("div");
        div.className="item";
        div.textContent=h;
        div.onclick=()=>openHashHex(h);
        e.appendChild(div);
    }
}

function drawBlocks(arr){
    let e=qs("#blocks");
    e.innerHTML="";
    for(let b of arr){
        let div=document.createElement("div");
        div.className="item";
        let cls=b.size<0?"neg":"pos";
        let body=b.text!==null
            ? '"' + esc(b.text) + '"'
            : '<span class="hex">'+b.hex+'</span>';
        div.innerHTML='<span class="'+cls+'">['+b.size+']</span> @'+b.off+' '+body;
        e.appendChild(div);
    }
}

async function saveHex(){
    let h=qs("#hexedit").value.replace(/\\s+/g,"");
    let r=await api("/api/upload_hex",{hex:h});
    status("saved "+r.hash);
    await openHashHex(r.hash);
}

openRoot();
</script>
</body>
</html>
`;

async function handle(req, res) {
    let url = new URL(req.url, "http://x");

    try {
        if (url.pathname === "/") {
            send_html(res, html_page);
            return;
        }

        if (url.pathname === "/api/root") {
            send(res, { hash: hex(str_sha("Croot")) });
            return;
        }

        if (url.pathname.startsWith("/api/download/")) {
            let h = unhex(url.pathname.split("/").pop());
            let data = await download_raw(h);

            send(res, {
                hash: hex(h),
                hex: hex(data),
                blocks: parse_blocks(data)
            });
            return;
        }

        if (url.pathname.startsWith("/api/children/")) {
            let h = unhex(url.pathname.split("/").pop());
            let children = await stream_children(h);

            send(res, {
                children: children.map(hex)
            });
            return;
        }

        if (url.pathname === "/api/upload_hex") {
            let b = JSON.parse((await body(req)).toString());
            let data = unhex(b.hex);
            let h = await upload_file(data);

            send(res, { hash: hex(h) });
            return;
        }

        send(res, { error: "unknown" });
    } catch (e) {
        send(res, { error: String(e.stack || e) });
    }
}

let started = false;

exports.run = async function () {
    if (started)
        return;

    started = true;

    C.ID = await register_id();

    http.createServer((req, res) => {
        handle(req, res);
    }).listen(WEB_PORT);

    console.log("CVM editor:");
    console.log("http://127.0.0.1:" + WEB_PORT);
};