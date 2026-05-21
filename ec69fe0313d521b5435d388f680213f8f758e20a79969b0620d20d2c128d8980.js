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