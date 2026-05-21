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