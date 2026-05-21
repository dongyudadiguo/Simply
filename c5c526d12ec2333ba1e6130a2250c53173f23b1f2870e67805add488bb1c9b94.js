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