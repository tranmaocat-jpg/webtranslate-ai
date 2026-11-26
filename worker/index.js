const LANGS={en:"English",vi:"Tiếng Việt",zh:"中文",ja:"日本語",ko:"한국어",fr:"Français",de:"Deutsch",es:"Español",th:"ไทย",ru:"Русский",pt:"Português",it:"Italiano",ar:"العربية"};
const MAX_HTML=1_500_000, MAX_TEXT=35, MAX_CHARS=15_000;
function bad(message,status=400){return new Response(message,{status,headers:{"content-type":"text/plain;charset=utf-8"}})}
function checkURL(raw){
 let u; try{u=new URL(raw)}catch{return null}
 if(!["http:","https:"].includes(u.protocol)||u.username||u.password||u.port&& !["80","443"].includes(u.port))return null;
 const h=u.hostname.toLowerCase();
 if(h==="localhost"||h.endsWith(".localhost")||h.endsWith(".local")||h.endsWith(".internal")||h==="metadata.google.internal")return null;
 if(/^\[/.test(h))return null;
 const ip=h.match(/^(\d{1,3}\.){3}\d{1,3}$/);
 if(ip){const n=h.split(".").map(Number);if(n.some(v=>v>255)||n[0]===10||n[0]===127||n[0]===0||n[0]===169&&n[1]===254||n[0]===172&&n[1]>=16&&n[1]<=31||n[0]===192&&n[1]===168||n[0]===100&&n[1]>=64&&n[1]<=127||n[0]===192&&n[1]===0||n[0]===198&&[18,19].includes(n[1])||n[0]>=224)return null;}
 return u;
}
async function translate(text,source,target){
 const t=text.trim(); if(!t||source===target)return text;
 const keyData=new TextEncoder().encode(source+"|"+target+"|"+t);
 const digest=await crypto.subtle.digest("SHA-256",keyData);
 const key=[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,"0")).join("");
 const cacheReq=new Request("https://webtranslate-cache.invalid/"+key);
 const cached=await caches.default.match(cacheReq);if(cached)return cached.text();
 const q=new URL("https://api.mymemory.translated.net/get");q.searchParams.set("q",t.slice(0,450));q.searchParams.set("langpair",source+"|"+target);q.searchParams.set("mt","1");
 const r=await fetch(q.toString(),{headers:{"Accept":"application/json"}});
 if(!r.ok)return text;
 const j=await r.json();if(j.responseStatus!==200||j.quotaFinished)return text;
 const result=j.responseData?.translatedText||text;
 if(result!==text)await caches.default.put(cacheReq,new Response(result,{headers:{"Cache-Control":"public, max-age=86400"}}));
 return result;
}
function page(){return `<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WebTranslate AI</title><style>*{box-sizing:border-box}body{font:16px system-ui;background:linear-gradient(135deg,#e5efff,#f7f8fc);min-height:100vh;margin:0;display:grid;place-items:center;padding:20px;color:#18283f}main{width:min(720px,100%);background:white;padding:clamp(24px,5vw,42px);border-radius:24px;box-shadow:0 18px 60px #10203018}h1{font-size:clamp(28px,5vw,40px);margin:.3em 0}input,select,button{width:100%;padding:14px;margin:8px 0;border:1px solid #cbd5e1;border-radius:12px;font:inherit}button{background:#1c63d5;color:white;border:0;font-weight:bold;cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.hint{font-size:13px;color:#64748b;line-height:1.5}@media(max-width:520px){.grid{grid-template-columns:1fr}}</style><main><b style="color:#1b65d5">🌐 WebTranslate AI · Free</b><h1>Dịch website, giữ bố cục</h1><p>Nhập URL website và chọn ngôn ngữ.</p><form action="/translate"><label>URL website</label><input name="url" type="url" required placeholder="https://example.com"><div class="grid"><div><label>Ngôn ngữ gốc</label><select name="source">${Object.entries(LANGS).map(([k,v])=>`<option value="${k}" ${k==="en"?"selected":""}>${v}</option>`).join("")}</select></div><div><label>Dịch sang</label><select name="target">${Object.entries(LANGS).map(([k,v])=>`<option value="${k}" ${k==="vi"?"selected":""}>${v}</option>`).join("")}</select></div></div><button>Dịch trang →</button></form><p class="hint">Bản MVP dịch văn bản qua MyMemory miễn phí (có hạn mức). Giữ markup, ảnh và CSS ở mức khả thi. JavaScript gốc bị loại bỏ để an toàn; một số trang tương tác có thể không hoạt động.</p></main>`;}
export default {async fetch(request,env,ctx){
 const u=new URL(request.url);
 if(u.pathname==="/health")return Response.json({status:"ok",platform:"Cloudflare Workers"});
 if(u.pathname==="/"||u.pathname==="/index.html")return new Response(page(),{headers:{"content-type":"text/html;charset=utf-8"}});
 if(u.pathname!=="/translate")return bad("Not found",404);
 const url=checkURL(u.searchParams.get("url")||"");if(!url)return bad("URL bị từ chối: chỉ cho phép HTTP(S) host công khai, không credentials, cổng 80/443.",403);
 const target=u.searchParams.get("target")||"vi",source=u.searchParams.get("source")||"en";
 if(!LANGS[target]||!LANGS[source])return bad("Ngôn ngữ không hợp lệ.");
 let fetched;
 try{
  let current=url;
  for(let i=0;i<=4;i++){
   const validated=checkURL(current.href);if(!validated)return bad("Redirect tới host bị chặn.",403);
   fetched=await fetch(validated.href,{redirect:"manual",headers:{"User-Agent":"WebTranslateAI/Workers","Accept":"text/html"}});
   if([301,302,303,307,308].includes(fetched.status)){const loc=fetched.headers.get("location");if(!loc||i===4)return bad("Redirect quá nhiều.",400);current=new URL(loc,current);continue;}
   break;
  }
 }catch{return bad("Không tải được website nguồn.",502)}
 if(!fetched||!fetched.ok)return bad("Website nguồn lỗi.",502);
 if(!(fetched.headers.get("content-type")||"").toLowerCase().includes("text/html"))return bad("URL không trả về HTML.",415);
 const reader=fetched.body?.getReader();if(!reader)return bad("HTML rỗng.",502);
 let size=0,chunks=[];while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>MAX_HTML){await reader.cancel();return bad("Trang vượt 1.5 MB.",413);}chunks.push(value);}
 const buffer=new Uint8Array(size);let idx=0;for(const c of chunks){buffer.set(c,idx);idx+=c.length;}
 const sourceHTML=new TextDecoder().decode(buffer);
 let count=0,chars=0;
 let rewriter=new HTMLRewriter().on("script,iframe,object,embed", {element(e){e.remove();}})
 .on("head", {element(e){e.append(`<base href="${url.href.replace(/&/g,"&amp;").replace(/"/g,"&quot;")}">`,{html:true});}})
 .on("a[href]",{element(e){const href=e.getAttribute("href");if(!href)return;try{const dest=new URL(href,url);if(dest.hostname===url.hostname&&["http:","https:"].includes(dest.protocol))e.setAttribute("href","/translate?"+new URLSearchParams({url:dest.href,target,source}));}catch{}}})
 .on("[src]",{element(e){const s=e.getAttribute("src");if(s&&!s.startsWith("data:"))try{e.setAttribute("src",new URL(s,url).href)}catch{}}})
 .on("[alt],[title],[placeholder],[aria-label]",{async element(e){for(const attr of ["alt","title","placeholder","aria-label"]){const v=e.getAttribute(attr);if(v&&count<MAX_TEXT){count++;chars+=v.length;if(chars<MAX_CHARS)try{e.setAttribute(attr,await translate(v,source,target))}catch{}}}}})
 .on("*",{async text(t){const v=t.text;if(!v.trim()||count>=MAX_TEXT||chars+v.length>MAX_CHARS)return;count++;chars+=v.length;try{t.replace(await translate(v,source,target));}catch{}}});
 return rewriter.transform(new Response(sourceHTML,{headers:{"content-type":"text/html;charset=utf-8"}}));
}};
