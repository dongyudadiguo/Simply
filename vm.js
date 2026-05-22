<!doctype html>
<html>
<body>
<script>
const HOST = "124.221.146.23";
const PORT = 9000;
const API_BASE = location.origin === "null" ? `http://${HOST}:${PORT}` : location.origin;

const enc = new TextEncoder();
const dec = new TextDecoder();

const CVM = globalThis.CVM = {
  BASE: null,
  PTR: null,
  IMP_FILE: "",
  IMP: null
};

function bytes(x) {
  if (x instanceof Uint8Array) return x;
  if (x instanceof ArrayBuffer) return new Uint8Array(x);
  if (ArrayBuffer.isView(x)) return new Uint8Array(x.buffer, x.byteOffset, x.byteLength);
  return enc.encode(String(x));
}

function hex(x) {
  return [...bytes(x)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function unhex(s) {
  return new Uint8Array((String(s).match(/../g) || []).map(x => parseInt(x, 16)));
}

async function sha256(x) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes(x)));
}

async function str_sha(s) {
  return sha256(s);
}

function read_i32(p) {
  return new DataView(bytes(p.buf).buffer, bytes(p.buf).byteOffset + p.off, 4).getInt32(0, true);
}

function block_size(p) {
  const n = read_i32(p);
  return n < 0 ? -n : n;
}

function block_data(p) {
  const b = bytes(p.buf);
  return b.subarray(p.off + 4, p.off + 4 + block_size(p));
}

async function get_first_child(parent) {
  const j = await (await fetch(`${API_BASE}/api/children/${hex(parent)}`)).json();
  return unhex(j.data.children[0].hash);
}

async function download_file(hash, ext = ".js") {
  const r = await fetch(`${API_BASE}/api/file/${hex(hash)}`);
  return {
    path: hex(hash) + ext,
    data: new Uint8Array(await r.arrayBuffer())
  };
}

async function load_js(hash) {
  return dec.decode((await download_file(hash, ".js")).data);
}

function execute_set(file) {
  CVM.IMP_FILE = String(file);
  CVM.IMP = () => eval(`(async()=>{\n${CVM.IMP_FILE}\n})()`);
}

async function execute_call(file) {
  return eval(`(async()=>{\n${String(file)}\n})()`);
}

Object.assign(CVM, {
  sha256,
  str_sha,
  hex,
  read_i32,
  block_size,
  block_data,
  get_first_child,
  download_file,
  load_js,
  execute_set,
  execute_call
});

async function boot() {
  const start_key = await str_sha("Cstart");
  const first_block_hash = await get_first_child(start_key);
  const first_block = await download_file(first_block_hash, ".bin");

  CVM.BASE = { buf: first_block.data, off: 0 };
  CVM.PTR = CVM.BASE;

  const payload = block_data(CVM.PTR);
  const first_key = await sha256(payload);
  const first_js_hash = await get_first_child(first_key);
  execute_set(await load_js(first_js_hash));
}

async function main() {
  await boot();
  await CVM.IMP();
}

CVM.boot = boot;
CVM.main = main;

main();
</script>
</body>
</html>