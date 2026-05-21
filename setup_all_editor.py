import socket, struct, hashlib, os

HOST = "124.221.146.23"
PORT = 9000

UPLOAD_FILE = 2
ADD_CHILD = 4
RECOMMEND_EDGE = 8

def sha(b): return hashlib.sha256(b).digest()
def key(s): return sha(s.encode())

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

def block(data):
    return struct.pack("<i", len(data)) + data

def read_id():
    if not os.path.exists("id.bin"):
        raise RuntimeError("missing id.bin")
    id = open("id.bin", "rb").read()
    if len(id) != 32:
        raise RuntimeError("bad id.bin")
    return id

def put_edge(name, data, id):
    h = upload(data.encode("utf-8"))
    p = key(name)
    add_child(p, h)
    recommend(p, h, id)
    print(f"{name:16} {h.hex()}")
    return h

LOADER_JS = r'''
(async()=>{
const C=globalThis.CVM;
async function mod(name){
 let k=C.str_sha(name),h=null;
 if(C.user_get_hash)h=await C.user_get_hash(k);
 if(!h)h=await C.get_first_child(k);
 let js=await C.load_js(h);
 await C.execute_call(js);
}
await mod("EDITOR_RUNTIME");
await mod("EDITOR_WEB");
await mod("EDITOR_HTML");
if(C.start_editor)await C.start_editor();
})();
'''.strip()

RUNTIME_JS = r'''
(async()=>{
const net=require("net"),fs=require("fs"),path=require("path"),crypto=require("crypto");
const C=globalThis.CVM;
C.HOST="124.221.146.23";C.PORT=9000;C.WEB_PORT=7070;
C.TURNSTILE_SITEKEY="0x4AAAAAADNgS66XXyfkgQMZ";
C.REGISTER=1;C.UPLOAD_FILE=2;C.DOWNLOAD_FILE=3;C.ADD_CHILD=4;C.STREAM_CHILDREN=5;C.USER_SET_HASH=6;C.USER_GET_HASH=7;C.RECOMMEND_EDGE=8;

C.sha256=b=>crypto.createHash("sha256").update(b).digest();
C.str_sha=s=>C.sha256(Buffer.from(s));
C.hex=b=>Buffer.from(b).toString("hex");
C.unhex=s=>Buffer.from(String(s||"").replace(/\s+/g,""),"hex");

C.read_i32=p=>p.buf.readInt32LE(p.off);
C.block_size=p=>{let n=C.read_i32(p);return n<0?-n:n};
C.block_data=p=>p.buf.subarray(p.off+4,p.off+4+C.block_size(p));
C.next_of=p=>({buf:p.buf,off:p.off+4+C.block_size(p)});
C.ptr_at=(buf,off=0)=>({buf,off});

C.printable=b=>{
 for(let x of b){
  if(x===9||x===10||x===13)continue;
  if(x<32||x>126)return false;
 }
 return true;
};

C.socket=()=>new Promise(r=>{
 let s=net.createConnection(C.PORT,C.HOST,()=>r(s));
});

C.recv_all=(s,n)=>{
 if(!s._buf)s._buf=Buffer.alloc(0);
 return new Promise(r=>{
  function done(){
   if(s._buf.length<n)return false;
   let o=s._buf.subarray(0,n);
   s._buf=s._buf.subarray(n);
   s.off("data",ondata);
   r(o);
   return true;
  }
  function ondata(d){
   s._buf=Buffer.concat([s._buf,d]);
   done();
  }
  if(done())return;
  s.on("data",ondata);
 });
};

C.load_id=()=>{
 if(!fs.existsSync("id.bin"))return null;
 let id=fs.readFileSync("id.bin");
 return id.length===32?id:null;
};

C.has_id=()=>Buffer.isBuffer(C.ID)&&C.ID.length===32;

C.register_token=async token=>{
 let data=Buffer.from(token,"utf8");
 let n=Buffer.alloc(4);n.writeUInt32BE(data.length);
 let s=await C.socket();
 s.write(Buffer.concat([Buffer.from([C.REGISTER]),n,data]));
 let st=(await C.recv_all(s,1))[0];
 if(st){s.end();throw new Error("register failed")}
 let id=await C.recv_all(s,32);
 s.end();
 fs.writeFileSync("id.bin",id);
 C.ID=id;
 return id;
};

C.upload_file=async data=>{
 let s=await C.socket();
 let n=Buffer.alloc(4);n.writeUInt32BE(data.length);
 s.write(Buffer.concat([Buffer.from([C.UPLOAD_FILE]),n,data]));
 let st=(await C.recv_all(s,1))[0];
 if(st){s.end();throw new Error("upload failed")}
 let h=await C.recv_all(s,32);
 s.end();
 return h;
};

C.download_raw=async h=>{
 let s=await C.socket();
 s.write(Buffer.from([C.DOWNLOAD_FILE]));
 s.write(h);
 let st=(await C.recv_all(s,1))[0];
 if(st){s.end();throw new Error("download failed "+C.hex(h))}
 let nb=await C.recv_all(s,4);
 let n=nb.readUInt32BE(0);
 let d=await C.recv_all(s,n);
 s.end();
 return d;
};

C.download_file=async(h,ext=".bin")=>{
 let data=await C.download_raw(h);
 let full=path.resolve(process.cwd(),C.hex(h)+ext);
 fs.writeFileSync(full,data);
 return{path:full,data};
};

C.load_js=async h=>(await C.download_file(h,".js")).data.toString("utf8");

C.add_child=async(parent,child)=>{
 let s=await C.socket();
 s.write(Buffer.from([C.ADD_CHILD]));
 s.write(parent);s.write(child);
 let st=(await C.recv_all(s,1))[0];
 s.end();
 if(st)throw new Error("add_child failed");
};

C.stream_children=async parent=>{
 let s=await C.socket();
 s.write(Buffer.from([C.STREAM_CHILDREN]));
 s.write(parent);
 let out=[];
 while(1){
  let st=(await C.recv_all(s,1))[0];
  if(st===2)break;
  if(st===0)out.push(await C.recv_all(s,32));
  else break;
 }
 s.end();
 return out;
};

C.get_first_child=async parent=>{
 let a=await C.stream_children(parent);
 if(!a.length)throw new Error("no child "+C.hex(parent));
 return a[0];
};

C.recommend_edge=async(parent,child)=>{
 if(!C.has_id())throw new Error("no id");
 let s=await C.socket();
 s.write(Buffer.from([C.RECOMMEND_EDGE]));
 s.write(C.ID);s.write(parent);s.write(child);
 let st=(await C.recv_all(s,1))[0];
 s.end();
 if(st)throw new Error("recommend failed");
};

C.user_set_hash=async(key,val)=>{
 if(!C.has_id())throw new Error("no id");
 let s=await C.socket();
 s.write(Buffer.from([C.USER_SET_HASH]));
 s.write(C.ID);s.write(key);s.write(val);
 let st=(await C.recv_all(s,1))[0];
 s.end();
 if(st)throw new Error("USER_SET_HASH failed");
};

C.user_get_hash=async key=>{
 if(!C.has_id())return null;
 let s=await C.socket();
 s.write(Buffer.from([C.USER_GET_HASH]));
 s.write(C.ID);s.write(key);
 let st=(await C.recv_all(s,1))[0];
 if(st){s.end();return null}
 let h=await C.recv_all(s,32);
 s.end();
 return h;
};

C.parse_blocks=buf=>{
 let out=[],off=0;
 while(off+4<=buf.length){
  let n=buf.readInt32LE(off),sz=Math.abs(n);
  if(off+4+sz>buf.length)break;
  let d=buf.subarray(off+4,off+4+sz);
  out.push({off,size:n,abs:sz,text:C.printable(d)?d.toString("utf8"):null,hex:C.hex(d),key:C.hex(C.sha256(d))});
  off+=4+sz;
 }
 return out;
};

C.ID=C.load_id();

C.STD=C.STD||Buffer.alloc(4096);
C.STD_OFFSET=C.STD_OFFSET||0;
C.VAR_SIZE=C.VAR_SIZE||4;
C.VARS=C.VARS||new Map();
C.FRAMES=C.FRAMES||[];
C.STACK=C.STACK||[];
C.CHECKLIST=C.CHECKLIST||[];

C.next_block=()=>{C.PTR=C.next_of(C.PTR)};
C.skip_all_data=()=>{while(C.read_i32(C.PTR)<0)C.next_block()};
C.skip_data_of=p=>{while(C.read_i32(p)<0)p=C.next_of(p);return p};

C.continue_=async()=>{
 C.next_block();
 C.skip_all_data();
 await C.run_block_set(C.PTR);
};

C.block_end=async()=>{
 let p=C.FRAMES.pop();
 if(!p)return;
 C.PTR=p;
 await C.run_block_auto(C.PTR);
};

C.add_check=(key,sha,data)=>C.CHECKLIST.push({key,sha,data});

C.check_all=async()=>{
 for(let x of C.CHECKLIST){
  let now=C.sha256(x.data);
  if(!now.equals(x.sha)){
   let h=await C.upload_file(x.data);
   x.sha=h;
   await C.user_set_hash(x.key,h);
  }
 }
};

C.execute_set=file=>{
 C.IMP_FILE=file;
 C.IMP=async()=>{await eval(C.IMP_FILE)};
};

C.execute_call=async file=>{await eval(file)};

C.run_block_exec=async(block,call)=>{
 C.PTR=block;
 while(1){
  C.skip_all_data();
  let size=C.read_i32(C.PTR);
  let payload=C.PTR.buf.subarray(C.PTR.off+4,C.PTR.off+4+size);
  let key=C.sha256(payload);
  let target=await C.user_get_hash(key);
  if(!target)target=await C.get_first_child(key);
  try{
   let file=await C.load_js(target);
   if(call)await C.execute_call(file);
   else C.execute_set(file);
   return;
  }catch(e){
   let data=await C.download_raw(target);
   C.add_check(key,target,data);
   C.STACK.push(data);
   C.PTR=C.ptr_at(data,0);
  }
 }
};

C.run_block_set=b=>C.run_block_exec(b,false);
C.run_block_call=b=>C.run_block_exec(b,true);
C.run_block_auto=b=>C.run_block_exec(b,true);
})();
'''.strip()

WEB_JS = r'''
(async()=>{
const http=require("http");
const C=globalThis.CVM;

C.send_json=(res,obj)=>{
 res.writeHead(200,{"Content-Type":"application/json","Access-Control-Allow-Origin":"*"});
 res.end(JSON.stringify(obj));
};

C.send_html=(res,html)=>{
 res.writeHead(200,{"Content-Type":"text/html; charset=utf-8"});
 res.end(html);
};

C.body=req=>new Promise(r=>{
 let a=[];
 req.on("data",d=>a.push(d));
 req.on("end",()=>r(Buffer.concat(a)));
});

C.handle_editor_req=async(req,res)=>{
 let url=new URL(req.url,"http://x");
 try{
  if(url.pathname==="/"){C.send_html(res,C.EDITOR_HTML||"missing html");return}

  if(url.pathname==="/api/id"){
   C.send_json(res,C.has_id()?{ok:true,id:C.hex(C.ID)}:{ok:false});
   return;
  }

  if(url.pathname==="/api/register"){
   let b=JSON.parse((await C.body(req)).toString());
   try{
    let id=await C.register_token(b.token);
    C.send_json(res,{ok:true,id:C.hex(id)});
   }catch(e){C.send_json(res,{ok:false,error:String(e.message||e)})}
   return;
  }

  if(url.pathname==="/api/root"){
   C.send_json(res,{hash:C.hex(C.str_sha("Croot"))});
   return;
  }

  if(url.pathname.startsWith("/api/download/")){
   let h=C.unhex(url.pathname.split("/").pop());
   try{
    let data=await C.download_raw(h);
    C.send_json(res,{hash:C.hex(h),hex:C.hex(data),blocks:C.parse_blocks(data)});
   }catch(e){C.send_json(res,{hash:C.hex(h),error:"not file"})}
   return;
  }

  if(url.pathname.startsWith("/api/children/")){
   let h=C.unhex(url.pathname.split("/").pop());
   let ch=await C.stream_children(h);
   C.send_json(res,{children:ch.map(C.hex)});
   return;
  }

  if(url.pathname==="/api/upload_hex"){
   let b=JSON.parse((await C.body(req)).toString());
   let h=await C.upload_file(C.unhex(b.hex));
   C.send_json(res,{hash:C.hex(h)});
   return;
  }

  if(url.pathname==="/api/add_child"){
   let b=JSON.parse((await C.body(req)).toString());
   try{
    await C.add_child(C.unhex(b.parent),C.unhex(b.child));
    C.send_json(res,{ok:true});
   }catch(e){C.send_json(res,{ok:false,error:String(e.message||e)})}
   return;
  }

  if(url.pathname==="/api/recommend"){
   let b=JSON.parse((await C.body(req)).toString());
   try{
    await C.recommend_edge(C.unhex(b.parent),C.unhex(b.child));
    C.send_json(res,{ok:true});
   }catch(e){C.send_json(res,{ok:false,error:String(e.message||e)})}
   return;
  }

  if(url.pathname==="/api/user_set"){
   let b=JSON.parse((await C.body(req)).toString());
   try{
    await C.user_set_hash(C.unhex(b.key),C.unhex(b.val));
    C.send_json(res,{ok:true});
   }catch(e){C.send_json(res,{ok:false,error:String(e.message||e)})}
   return;
  }

  if(url.pathname.startsWith("/api/user_get/")){
   let key=C.unhex(url.pathname.split("/").pop());
   let val=await C.user_get_hash(key);
   C.send_json(res,{ok:true,val:val?C.hex(val):null});
   return;
  }

  C.send_json(res,{error:"unknown"});
 }catch(e){
  C.send_json(res,{error:String(e.stack||e)});
 }
};

C.start_editor=async()=>{
 if(C.EDITOR_STARTED)return;
 C.EDITOR_STARTED=true;
 http.createServer((req,res)=>C.handle_editor_req(req,res)).listen(C.WEB_PORT);
 console.log("CVM editor:");
 console.log("http://127.0.0.1:"+C.WEB_PORT);
};
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
#main{display:grid;grid-template-columns:330px 1fr 460px;height:calc(100vh - 90px)}
.panel{border-right:1px solid #333;overflow:auto;padding:8px}
button,input{background:#222;color:#ddd;border:1px solid #555;padding:4px;margin:2px}
.item{padding:4px;border-bottom:1px solid #222;cursor:pointer}
.item:hover{background:#333}
.pos{color:#80ff80}.neg{color:#ff8080}
.hash{color:#88aaff;word-break:break-all}
.hex{color:#888;word-break:break-all}
textarea{width:100%;height:66vh;background:#080808;color:#ddd;border:1px solid #444;font-family:Consolas,monospace}
.small{font-size:12px;color:#aaa}
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
<div class="panel"><h3>children</h3><div id="children"></div></div>
<div class="panel"><h3>blocks</h3><div id="blocks"></div></div>
<div class="panel">
<h3>builder</h3>
<textarea id="builder" style="height:160px" placeholder="+ TEXT&#10;- hello&#10;+ CONTINUE"></textarea>
<br>
<button onclick="buildBlocks()">build -> hex</button>

<h3>hex</h3>
<textarea id="hexedit"></textarea>
<div class="small">last uploaded: <span id="lastUploaded"></span></div>
</div>
</div>

<script>
let LAST_UPLOADED="";
function qs(x){return document.querySelector(x)}
async function api(path,obj){
 let opt=obj?{method:"POST",body:JSON.stringify(obj),headers:{"Content-Type":"application/json"}}:{};
 let r=await fetch(path,opt);
 return await r.json();
}
function esc(s){return s.replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
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
 }else status("register failed: "+r.error);
}

async function openRoot(){
 let r=await api("/api/root");
 await openHashHex(r.hash);
}
async function openHash(){await openHashHex(currentHash())}

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
 let e=qs("#children");e.innerHTML="";
 for(let h of arr){
  let div=document.createElement("div");div.className="item";
  let span=document.createElement("div");span.className="hash";span.textContent=h;span.onclick=()=>openHashHex(h);
  let rec=document.createElement("button");rec.textContent="recommend";
  rec.onclick=async ev=>{
   ev.stopPropagation();
   let r=await api("/api/recommend",{parent:currentHash(),child:h});
   status(r.ok?"recommended":"recommend failed: "+r.error);
  };
  div.appendChild(span);div.appendChild(rec);e.appendChild(div);
 }
}

function drawBlocks(arr){
 let e=qs("#blocks");e.innerHTML="";
 for(let b of arr){
  let div=document.createElement("div");div.className="item";
  let cls=b.size<0?"neg":"pos";
  let body=b.text!==null?'"'+esc(b.text)+'"':'<span class="hex">'+b.hex+'</span>';
  div.innerHTML='<div><span class="'+cls+'">['+b.size+']</span> @'+b.off+'</div><div>'+body+'</div><div class="small">key: <span class="hash">'+b.key+'</span></div>';

  let openKey=document.createElement("button");openKey.textContent="open key";openKey.onclick=()=>openHashHex(b.key);

  let setOverride=document.createElement("button");setOverride.textContent="set override -> last uploaded";
  setOverride.onclick=async()=>{
   if(!LAST_UPLOADED){status("no last uploaded");return}
   let r=await api("/api/user_set",{key:b.key,val:LAST_UPLOADED});
   status(r.ok?"override set":"override failed: "+r.error);
  };

  let getOverride=document.createElement("button");getOverride.textContent="get override";
  getOverride.onclick=async()=>{
   let r=await api("/api/user_get/"+b.key);
   status(r.ok&&r.val?"override: "+r.val:"no override");
  };

  div.appendChild(openKey);div.appendChild(setOverride);div.appendChild(getOverride);
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

function buildBlocks(){
    let lines=qs("#builder").value.split(/\\r?\\n/);
    let parts=[];

    for(let line of lines){
        if(!line.trim())continue;

        let sign=line[0];
        let text=line.slice(1).trimStart();
        let data=utf8(text);

        if(sign==="+"){
            parts.push(i32le(data.length));
            parts.push(data);
        }else if(sign==="-"){
            parts.push(i32le(-data.length));
            parts.push(data);
        }else{
            status("bad line: "+line);
            return;
        }
    }

    let all=concat(parts);
    qs("#hexedit").value=prettyHex(toHex(all));
    status("built "+all.length+" bytes");
}

async function saveHex(){
 let h=qs("#hexedit").value.replace(/\\s+/g,"");
 let r=await api("/api/upload_hex",{hex:h});
 if(r.error){status("save failed: "+r.error);return}
 LAST_UPLOADED=r.hash;
 qs("#lastUploaded").textContent=r.hash;
 status("saved "+r.hash);
 await openHashHex(r.hash);
}

async function addUploadedToCurrent(){
 if(!LAST_UPLOADED){status("no last uploaded");return}
 let parent=currentHash();
 let r=await api("/api/add_child",{parent,child:LAST_UPLOADED});
 if(r.ok){status("child added");await openHashHex(parent)}
 else status("add failed: "+r.error);
}

async function recommendUploadedToCurrent(){
 if(!LAST_UPLOADED){status("no last uploaded");return}
 let parent=currentHash();
 let r=await api("/api/recommend",{parent,child:LAST_UPLOADED});
 if(r.ok){status("recommended uploaded");await openHashHex(parent)}
 else status("recommend failed: "+r.error);
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

    print("upload modules")

    loader_h = put_edge("FIRST_EDITOR", LOADER_JS, id)
    runtime_h = put_edge("EDITOR_RUNTIME", RUNTIME_JS, id)
    web_h = put_edge("EDITOR_WEB", WEB_JS, id)
    html_h = put_edge("EDITOR_HTML", HTML_JS, id)

    print()
    print("upload first block")

    payload = b"FIRST_EDITOR"
    first_block = block(payload)
    first_h = upload(first_block)

    p_start = key("Cstart")
    add_child(p_start, first_h)
    recommend(p_start, first_h, id)

    print(f"{'Cstart block':16} {first_h.hex()}")
    print()
    print("done")
    print("FIRST_EDITOR ->", loader_h.hex())
    print("EDITOR_RUNTIME ->", runtime_h.hex())
    print("EDITOR_WEB     ->", web_h.hex())
    print("EDITOR_HTML    ->", html_h.hex())
    print("Cstart         ->", first_h.hex())

if __name__ == "__main__":
    main()