const apiBase = "http://124.221.146.23:9000";
const enc = new TextEncoder();
const zero = "00".repeat(32);

const hex = (b) =>
  [...b].map((x) => x.toString(16).padStart(2, "0")).join("");

const unhex = (h) =>
  new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));

const sha256 = async (x) =>
  new Uint8Array(
    await crypto.subtle.digest(
      "SHA-256",
      typeof x === "string" ? enc.encode(x) : x
    )
  );

const api = async (path, options) => {
  const res = await fetch(apiBase + path, options);
  const json = await res.json();
  if (!json.ok) throw new Error(json.error || path);
  return json.data;
};

const upload = async (data) =>
  (await api("/api/upload", { method: "POST", body: data })).hash;

const edge = async (parent, child) =>
  api(`/api/edge/${parent}/${child}`, { method: "POST" });

const vote = async (user, parent, child) => {
  if (!user) return;
  try {
    await api(`/api/vote/${user}/${parent}/${child}`, { method: "POST" });
  } catch (err) {
    console.warn("vote skipped:", err.message);
  }
};

const bodyOf = (fn) => {
  const s = fn.toString();
  return s.slice(s.indexOf("{") + 1, s.lastIndexOf("}"));
};

async function OneShell() {
  const apiBase =
    typeof globalThis.apiBase !== "undefined"
      ? globalThis.apiBase
      : "http://124.221.146.23:9000";

  const cvm = globalThis.CVM;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const hex = (x) =>
    typeof x === "string"
      ? x
      : [...x].map((b) => b.toString(16).padStart(2, "0")).join("");

  const unhex = (h) =>
    new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));

  const bytes = (x) =>
    x instanceof Uint8Array
      ? x
      : x instanceof ArrayBuffer
        ? new Uint8Array(x)
        : ArrayBuffer.isView(x)
          ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength)
          : enc.encode(String(x ?? ""));

  const short = (h) => hex(h).slice(0, 12) + "...";
  const zero = "00".repeat(32);

  const api = async (path, options) => {
    const res = await fetch(apiBase + path, options);
    const json = await res.json();
    if (!json.ok) throw new Error(json.error || path);
    return json.data;
  };

  cvm.sha256 ??= async (x) =>
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes(x)));

  cvm.execute_call ??= async (src) =>
    Function(
      "CVM",
      "apiBase",
      `return (async()=>{${src}\n})()`
    )(cvm, apiBase);

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  const download = async (h) => {
    const k = hex(h);
    if (!cvm.FC.has(k)) cvm.FC.set(k, await cvm.download_file(unhex(k)));
    return cvm.FC.get(k);
  };

  const upload = async (file) =>
    unhex((await api("/api/upload", { method: "POST", body: bytes(file) })).hash);

  const children = async (h) =>
    (await api("/api/children/" + hex(h))).children;

  const first = async (h) =>
    unhex((await children(h))[0].hash);

  const edge = async (p, c) =>
    api(`/api/edge/${hex(p)}/${hex(c)}`, { method: "POST" });

  const vote = async (p, c) => {
    if (!S.user) throw new Error("missing user");
    return api(`/api/vote/${S.user}/${hex(p)}/${hex(c)}`, { method: "POST" });
  };

  const u32 = (b, o) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  const w32 = (b, o, n) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).setUint32(o, n, true);

  const zhash = (b, o) => {
    if (o + 32 > b.length) return true;
    for (let i = o; i < o + 32; i++) if (b[i]) return false;
    return true;
  };

  cvm.buildBlock ??= (xs) => {
    xs = xs.map((x) =>
      typeof x === "string" ? { hash: x, data: new Uint8Array() } : x
    );

    const b = new Uint8Array(
      xs.reduce((n, x) => n + 36 + bytes(x.data).length, 32)
    );

    let o = 0;
    for (const x of xs) {
      const d = bytes(x.data);
      b.set(unhex(hex(x.hash)), o);
      o += 32;
      w32(b, o, d.length);
      o += 4;
      b.set(d, o);
      o += d.length;
    }

    return b;
  };

  cvm.parseBlock ??= (b) => {
    const xs = [];
    for (let o = 0; !zhash(b, o);) {
      const n = u32(b, o + 32);
      xs.push({
        hash: hex(b.subarray(o, o + 32)),
        data: b.slice(o + 36, o + 36 + n),
      });
      o += 36 + n;
    }
    return xs;
  };

  cvm.override ??= (keyHash, file) =>
    cvm.OV.set(hex(keyHash), bytes(file));

  cvm.user ??= (userId) => {
    cvm.USER = hex(userId);
    cvm.HC.clear();
  };

  cvm.data ??= () => {
    const n = zhash(cvm.PTR.buf, cvm.PTR.off)
      ? 0
      : u32(cvm.PTR.buf, cvm.PTR.off + 32);
    return cvm.PTR.buf.subarray(cvm.PTR.off + 36, cvm.PTR.off + 36 + n);
  };

  cvm.setprog ??= async (prog) => {
    const file = cvm.buildBlock(prog);
    cvm.PTR = { buf: file, off: 0 };
    cvm.override(new Uint8Array(32), file);
  };

  const style = document.createElement("style");
  style.textContent = `
    *{box-sizing:border-box}
    body{margin:0;font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;background:#f6f7f9;color:#20242a}
    #os{height:100vh;display:grid;grid-template-rows:48px 1fr 78px}
    header,footer{background:#fff;border-bottom:1px solid #d9dee7;display:flex;align-items:center;gap:10px;padding:8px 14px}
    footer{border-top:1px solid #d9dee7;border-bottom:0;display:block;overflow:auto;font-size:12px;color:#5b6678}
    main{min-height:0;display:grid;grid-template-columns:260px 1fr 330px}
    aside{background:#fff;border-right:1px solid #d9dee7;padding:12px;overflow:auto}
    aside:last-child{border-right:0;border-left:1px solid #d9dee7}
    section{padding:14px;overflow:auto}
    button,input,textarea{font:inherit}
    button{border:1px solid #b9c2d0;background:#fff;border-radius:6px;padding:6px 9px;cursor:pointer}
    button.primary{background:#2563eb;color:#fff;border-color:#2563eb}
    input,textarea{width:100%;border:1px solid #cbd3df;border-radius:6px;padding:7px;background:#fff}
    textarea{min-height:180px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
    h3{margin:4px 0 10px;font-size:15px}
    .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    .grow{flex:1}
    .node{padding:8px;border:1px solid #d9dee7;border-radius:6px;background:#fff;margin:7px 0;cursor:pointer}
    .node.active{border-color:#2563eb;background:#eff6ff}
    .muted{color:#687386;font-size:12px}
    code{word-break:break-all;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}
    .split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  `;
  document.head.appendChild(style);

  const S = {
    user: localStorage.cvm_user || "",
    node: zero,
    selected: "",
    kids: [],
    src: `// @name Hello CVM
CVM.mount.innerHTML = "<h2>Hello CVM</h2><p>running from the hash graph.</p>";`,
    logs: ["OneShell ready"],
  };

  const log = (x) => {
    S.logs.unshift(new Date().toLocaleTimeString() + " " + x);
    draw();
  };

  const refresh = async () => {
    S.kids = await children(S.node).catch(() => []);
    draw();
  };

  const openNode = async (h) => {
    S.node = hex(h);
    S.selected = "";
    await refresh();
  };

  const runHash = async (h) => {
    cvm.mount = document.querySelector("#stage");
    cvm.mount.innerHTML = "";
    const src = dec.decode(await download(h));
    log("run " + short(h));
    await cvm.execute_call(src);
  };

  const publish = async () => {
    const name = (S.src.match(/@name\s+(.+)/) || [, "Untitled"])[1].trim();
    const js = await upload(S.src);
    const key = await cvm.sha256("app:" + name + ":" + Date.now() + ":" + hex(js));
    await edge(key, js);
    await edge(new Uint8Array(32), key);
    log("published " + name + " " + short(key));
    await openNode(zero);
  };

  const copy = async (x) => {
    await navigator.clipboard.writeText(x);
    log("copied");
  };

  const draw = () => {
    document.body.innerHTML = `
      <div id="os">
        <header>
          <b>OneShell</b>
          <span class="muted">CVM desktop</span>
          <input class="grow" id="user" placeholder="user id" value="${S.user}">
          <button id="saveUser">保存身份</button>
          <button id="root">root</button>
          <button id="reload">刷新</button>
        </header>

        <main>
          <aside>
            <h3>Children</h3>
            ${S.kids.map((x) => `
              <div class="node ${x.hash === S.selected ? "active" : ""}" data-pick="${x.hash}">
                <code>${short(x.hash)}</code>
                <div class="muted">score ${x.score}</div>
              </div>
            `).join("")}
          </aside>

          <section>
            <div class="split">
              <div>
                <h3>发布 JS 程序</h3>
                <textarea id="src">${S.src.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</textarea>
                <div class="row">
                  <button class="primary" id="publish">上传发布</button>
                  <button id="runSelected">运行选中</button>
                </div>
              </div>
              <div>
                <h3>当前启动块</h3>
                ${cvm.parseBlock(cvm.PTR.buf).map((x, i) => `
                  <div class="node">
                    <b>${i + 1}</b> <code>${short(x.hash)}</code>
                    <div class="muted">${x.data.length} bytes data</div>
                  </div>
                `).join("")}
                <div class="muted">end: ${zero}</div>
              </div>
            </div>
            <hr>
            <div id="stage"></div>
          </section>

          <aside>
            <h3>检查器</h3>
            <p class="muted">current</p>
            <code>${S.node}</code>
            <p class="muted">selected</p>
            <code>${S.selected || "none"}</code>
            <hr>
            <div class="row">
              <button id="copy">复制</button>
              <button id="vote">投票</button>
              <button id="open">打开</button>
            </div>
          </aside>
        </main>

        <footer>${S.logs.slice(0, 6).map((x) => `<div>${x}</div>`).join("")}</footer>
      </div>
    `;

    document.querySelector("#user").oninput = (e) => (S.user = e.target.value.trim());
    document.querySelector("#src").oninput = (e) => (S.src = e.target.value);
    document.querySelector("#saveUser").onclick = () => {
      localStorage.cvm_user = S.user;
      if (S.user) cvm.user(S.user);
      log("user saved");
    };
    document.querySelector("#root").onclick = () => openNode(zero);
    document.querySelector("#reload").onclick = refresh;
    document.querySelector("#publish").onclick = () => publish().catch((e) => log(e.message));
    document.querySelector("#runSelected").onclick = () =>
      S.selected ? runHash(S.selected).catch((e) => log(e.message)) : log("no selection");
    document.querySelector("#copy").onclick = () => copy(S.selected || S.node);
    document.querySelector("#vote").onclick = () =>
      S.selected ? vote(S.node, S.selected).then(refresh).catch((e) => log(e.message)) : log("no selection");
    document.querySelector("#open").onclick = () =>
      S.selected ? openNode(S.selected) : log("no selection");

    for (const el of document.querySelectorAll("[data-pick]")) {
      el.onclick = () => {
        S.selected = el.dataset.pick;
        draw();
      };
    }
  };

  if (S.user) cvm.user(S.user);
  await refresh();
}

const user = process.env.USER_ID || "";
const loaderKey = await sha256("OneShell.loader/v1");
const loaderKeyHex = hex(loaderKey);

const appHash = await upload(enc.encode(bodyOf(OneShell)));
await edge(loaderKeyHex, appHash);
await vote(user, loaderKeyHex, appHash);

const boot = new Uint8Array(32 + 4 + 32);
boot.set(loaderKey, 0);

const bootHash = await upload(boot);
await edge(zero, bootHash);
await vote(user, zero, bootHash);

console.log({
  loaderKey: loaderKeyHex,
  appHash,
  bootHash,
  root: zero,
  note: user
    ? "uploaded and voted: root -> boot -> loaderKey -> OneShell.js"
    : "uploaded; provide USER_ID to vote it to the top",
});
