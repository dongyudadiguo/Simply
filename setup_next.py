import socket, struct, hashlib, os

HOST = "124.221.146.23"
PORT = 9000

UPLOAD_FILE = 2
ADD_CHILD = 4
RECOMMEND_EDGE = 8

def sha(b):
    return hashlib.sha256(b).digest()

def key(s):
    return sha(s.encode())

def conn():
    return socket.create_connection((HOST, PORT))

def recvn(s, n):
    b = b""
    while len(b) < n:
        x = s.recv(n - len(b))
        if not x:
            raise RuntimeError("closed")
        b += x
    return b

def upload(data):
    s = conn()
    s.sendall(bytes([UPLOAD_FILE]))
    s.sendall(struct.pack(">I", len(data)))
    s.sendall(data)

    st = recvn(s, 1)[0]
    if st:
        s.close()
        raise RuntimeError("upload failed")

    h = recvn(s, 32)
    s.close()
    return h

def add_child(parent, child):
    s = conn()
    s.sendall(bytes([ADD_CHILD]))
    s.sendall(parent)
    s.sendall(child)

    st = recvn(s, 1)[0]
    s.close()

    if st:
        raise RuntimeError("add_child failed")

def recommend(parent, child, id):
    s = conn()
    s.sendall(bytes([RECOMMEND_EDGE]))
    s.sendall(id)
    s.sendall(parent)
    s.sendall(child)

    st = recvn(s, 1)[0]
    s.close()

    if st:
        raise RuntimeError("recommend failed")

def read_id():
    if not os.path.exists("id.bin"):
        raise RuntimeError("missing id.bin")

    id = open("id.bin", "rb").read()

    if len(id) != 32:
        raise RuntimeError("bad id.bin")

    return id

def put(name, code, id):
    h = upload(code.encode("utf-8"))
    p = key(name)

    add_child(p, h)
    recommend(p, h, id)

    print(f"{name:16} {h.hex()}")
    return h

LOOP_JS = r'''
(async () => {
    const C = CVM;

    let data = C.next_of(C.PTR);

    let body = {
        buf: data.buf,
        off: data.off + 4
    };

    let after = C.next_of(data);
    after = C.skip_data_of(after);

    C.FRAMES.push({
        type: "loop",
        body,
        after
    });

    await C.run_block_auto(body);
})();
'''.strip()

BREAK_JS = r'''
(async () => {
    const C = CVM;

    while (C.FRAMES.length) {
        let f = C.FRAMES.pop();

        if (f && f.type === "loop") {
            C.PTR = f.after;
            await C.run_block_auto(C.PTR);
            return;
        }
    }
})();
'''.strip()

BLOCK_END_JS = r'''
(async () => {
    const C = CVM;

    let f = C.FRAMES.pop();

    if (!f)
        return;

    if (f && f.type === "loop") {
        C.FRAMES.push(f);
        await C.run_block_auto(f.body);
        return;
    }

    C.PTR = f;
    await C.run_block_auto(C.PTR);
})();
'''.strip()

HTML_JS = r'''
(async()=>{
const C=globalThis.CVM;

C.EDITOR_HTML=`
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>CVM Editor</title>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<style>
body{margin:0;background:#111;color:#ddd;font-family:Consolas,monospace}
#top{min-height:36px;background:#222;display:flex;align-items:center;padding:4px;gap:8px;flex-wrap:wrap}
#auth{padding:8px;background:#181818}
#main{display:grid;grid-template-columns:330px 1fr 520px;height:calc(100vh - 90px)}
.panel{border-right:1px solid #333;overflow:auto;padding:8px}
button,input{background:#222;color:#ddd;border:1px solid #555;padding:4px;margin:2px}
.item{padding:4px;border-bottom:1px solid #222;cursor:pointer}
.item:hover{background:#333}
.pos{color:#80ff80}.neg{color:#ff8080}
.hash{color:#88aaff;word-break:break-all}
.hex{color:#888;word-break:break-all}
textarea{width:100%;background:#080808;color:#ddd;border:1px solid #444;font-family:Consolas,monospace}
#builder{height:220px}
#hexedit{height:360px}
.small{font-size:12px;color:#aaa}
pre{background:#080808;border:1px solid #333;padding:6px;white-space:pre-wrap}
</style>
</head>
<body>
<div id="top">
<button onclick="openRoot()">Croot</button>
<input id="hashInput" style="width:520px" placeholder="hash hex">
<button onclick="openHash()">open</button>
<button onclick="saveHex()">upload hex</button>
<button onclick="addUploadedToCurrent()">add uploaded as child</button>
<button onclick="recommendUploadedToCurrent()">recommend uploaded</button>
<span id="idstatus">id: checking</span>
<span id="status"></span>
</div>

<div id="auth">
<div class="cf-turnstile" data-sitekey="${C.TURNSTILE_SITEKEY}" data-callback="onToken"></div>
</div>

<div id="main">
<div class="panel">
<h3>children</h3>
<div id="children"></div>
</div>

<div class="panel">
<h3>blocks</h3>
<div id="blocks"></div>
</div>

<div class="panel">
<h3>builder</h3>
<textarea id="builder" placeholder="+ TEXT
- hello
+ CONTINUE

+ LOOP
[
  + TEXT
  - in loop
  + BLOCK_END
]
"></textarea>
<br>
<button onclick="buildBlocks()">build -> hex</button>
<button onclick="insertGuessDemo()">insert guess-number skeleton</button>

<h3>hex</h3>
<textarea id="hexedit"></textarea>
<div class="small">last uploaded: <span id="lastUploaded"></span></div>

<h3>builder syntax</h3>
<pre>
+ NAME       positive executable block
- text       negative data block utf8
# comment

Nested data block:
+ LOOP
[
  + TEXT
  - hello
  + BLOCK_END
]

The [] content becomes one negative data block.
</pre>
</div>
</div>

<script>
let LAST_UPLOADED="";

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
function currentHash(){return qs("#hashInput").value.trim()}
function prettyHex(s){return s.match(/.{1,32}/g)?.join("\\n")||""}

async function refreshId(){
 let r=await api("/api/id");
 if(r.ok){
  qs("#idstatus").textContent="id: "+r.id.slice(0,16);
  qs("#auth").style.display="none";
 }else{
  qs("#idstatus").textContent="id: none";
  qs("#auth").style.display="block";
 }
}

async function onToken(token){
 status("registering");
 let r=await api("/api/register",{token});
 if(r.ok){
  qs("#idstatus").textContent="id: "+r.id.slice(0,16);
  qs("#auth").style.display="none";
  status("registered");
 }else{
  status("register failed: "+r.error);
 }
}

async function openRoot(){
 let r=await api("/api/root");
 await openHashHex(r.hash);
}

async function openHash(){
 await openHashHex(currentHash());
}

async function openHashHex(h){
 qs("#hashInput").value=h;
 status("loading");

 let c=await api("/api/children/"+h);
 drawChildren(c.children||[]);

 let d=await api("/api/download/"+h);

 if(d.error){
  qs("#hexedit").value="";
  qs("#blocks").innerHTML='<div class="item neg">not file / directory only</div>';
 }else{
  qs("#hexedit").value=prettyHex(d.hex);
  drawBlocks(d.blocks||[]);
 }

 status("ok");
}

function drawChildren(arr){
 let e=qs("#children");
 e.innerHTML="";

 for(let h of arr){
  let div=document.createElement("div");
  div.className="item";

  let span=document.createElement("div");
  span.className="hash";
  span.textContent=h;
  span.onclick=()=>openHashHex(h);

  let rec=document.createElement("button");
  rec.textContent="recommend";
  rec.onclick=async ev=>{
   ev.stopPropagation();
   let r=await api("/api/recommend",{parent:currentHash(),child:h});
   status(r.ok?"recommended":"recommend failed: "+r.error);
  };

  div.appendChild(span);
  div.appendChild(rec);
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

  div.innerHTML=
   '<div><span class="'+cls+'">['+b.size+']</span> @'+b.off+'</div>'+
   '<div>'+body+'</div>'+
   '<div class="small">key: <span class="hash">'+b.key+'</span></div>';

  let openKey=document.createElement("button");
  openKey.textContent="open key";
  openKey.onclick=()=>openHashHex(b.key);

  let setOverride=document.createElement("button");
  setOverride.textContent="set override -> last uploaded";
  setOverride.onclick=async()=>{
   if(!LAST_UPLOADED){status("no last uploaded");return}
   let r=await api("/api/user_set",{key:b.key,val:LAST_UPLOADED});
   status(r.ok?"override set":"override failed: "+r.error);
  };

  let getOverride=document.createElement("button");
  getOverride.textContent="get override";
  getOverride.onclick=async()=>{
   let r=await api("/api/user_get/"+b.key);
   status(r.ok&&r.val?"override: "+r.val:"no override");
  };

  div.appendChild(openKey);
  div.appendChild(setOverride);
  div.appendChild(getOverride);
  e.appendChild(div);
 }
}

function i32le(n){
 let b=new Uint8Array(4);
 new DataView(b.buffer).setInt32(0,n,true);
 return b;
}

function utf8(s){
 return new TextEncoder().encode(s);
}

function toHex(a){
 return Array.from(a).map(x=>x.toString(16).padStart(2,"0")).join("");
}

function concat(arr){
 let n=arr.reduce((s,a)=>s+a.length,0);
 let out=new Uint8Array(n);
 let off=0;
 for(let a of arr){
  out.set(a,off);
  off+=a.length;
 }
 return out;
}

function blockBytes(sign,data){
 let n=sign==="+"?data.length:-data.length;
 return concat([i32le(n),data]);
}

function parseBuilderLines(){
 let raw=qs("#builder").value.split(/\\r?\\n/);
 let lines=[];
 for(let x of raw){
  let t=x.trim();
  if(!t || t.startsWith("#"))continue;
  lines.push(t);
 }
 return lines;
}

function buildRange(lines,pos){
 let parts=[];

 while(pos.i<lines.length){
  let line=lines[pos.i++];

  if(line==="]")break;

  if(line==="["){
   throw new Error("unexpected [");
  }

  let sign=line[0];
  let text=line.slice(1).trimStart();

  if(sign!== "+" && sign!=="-")
   throw new Error("bad line: "+line);

  if(pos.i<lines.length && lines[pos.i]==="["){
   pos.i++;
   let inner=buildRange(lines,pos);
   parts.push(blockBytes(sign,inner));
  }else{
   parts.push(blockBytes(sign,utf8(text)));
  }
 }

 return concat(parts);
}

function buildBlocks(){
 try{
  let lines=parseBuilderLines();
  let data=buildRange(lines,{i:0});
  qs("#hexedit").value=prettyHex(toHex(data));
  status("built "+data.length+" bytes");
 }catch(e){
  status("build failed: "+e.message);
 }
}

function insertGuessDemo(){
 qs("#builder").value =
\`+ CLEAR
+ RANDOM_INT
- \\x01\\x00\\x00\\x00\\x64\\x00\\x00\\x00
+ VARSIZE
- xxxx
+ VARSET
- answer
+ TEXT
- guess number 1..100
+ LOOP
[
  + CLEAR
  + INPUT_INT
  + VARGET
  - answer
  + CMP_EQ
  + IFF
  [
    + TEXT
    - correct
    + BREAK
  ]
  [
    + TEXT
    - wrong
    + BLOCK_END
  ]
]\`;
 status("inserted skeleton; RANDOM_INT binary line needs hex builder later");
}

async function saveHex(){
 let h=qs("#hexedit").value.replace(/\\s+/g,"");
 let r=await api("/api/upload_hex",{hex:h});

 if(r.error){
  status("save failed: "+r.error);
  return;
 }

 LAST_UPLOADED=r.hash;
 qs("#lastUploaded").textContent=r.hash;

 status("saved "+r.hash);
 await openHashHex(r.hash);
}

async function addUploadedToCurrent(){
 if(!LAST_UPLOADED){status("no last uploaded");return}

 let parent=currentHash();
 let r=await api("/api/add_child",{parent,child:LAST_UPLOADED});

 if(r.ok){
  status("child added");
  await openHashHex(parent);
 }else{
  status("add failed: "+r.error);
 }
}

async function recommendUploadedToCurrent(){
 if(!LAST_UPLOADED){status("no last uploaded");return}

 let parent=currentHash();
 let r=await api("/api/recommend",{parent,child:LAST_UPLOADED});

 if(r.ok){
  status("recommended uploaded");
  await openHashHex(parent);
 }else{
  status("recommend failed: "+r.error);
 }
}

refreshId();
openRoot();
</script>
</body>
</html>
`;
})();
'''.strip()

def main():
    id = read_id()

    print("upload editor html + loop instructions")

    put("EDITOR_HTML", HTML_JS, id)

    put("LOOP", LOOP_JS, id)
    put("BREAK", BREAK_JS, id)
    put("BLOCK_END", BLOCK_END_JS, id)

    print("done")

if __name__ == "__main__":
    main()