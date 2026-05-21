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