const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = __dirname;
const DB_FILE = path.join(ROOT, 'learning-data.json');
const defaultSteps = ['理解函数是什么','参数与返回值','条件与循环','列表与字典','做一个小项目'];
function readDb(){ try{return JSON.parse(fs.readFileSync(DB_FILE,'utf8'));}catch{return {sessions:[]};} }
function writeDb(db){ fs.writeFileSync(DB_FILE, JSON.stringify(db,null,2)); }
function send(res,status,data,type='application/json'){res.writeHead(status,{'Content-Type':type,'Access-Control-Allow-Origin':'*'});res.end(type==='application/json'?JSON.stringify(data):data);}
function body(req){return new Promise((resolve,reject)=>{let b='';req.on('data',c=>b+=c);req.on('end',()=>{try{resolve(b?JSON.parse(b):{});}catch(e){reject(e);}});});}
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json'};
const server=http.createServer(async (req,res)=>{
  if(req.method==='OPTIONS'){res.writeHead(204,{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type'});return res.end();}
  try{
    const db=readDb();
    if(req.url==='/api/sessions'&&req.method==='GET') return send(res,200,db.sessions);
    if(req.url==='/api/sessions'&&req.method==='POST'){
      const x=await body(req), now=new Date().toISOString(); const s={id:crypto.randomUUID(),title:x.title||'Python 基础',goal:x.goal||x.title||'Python 基础',steps:x.steps||defaultSteps,step:0,messages:[],createdAt:now,updatedAt:now}; db.sessions.unshift(s); writeDb(db); return send(res,201,s);
    }
    const m=req.url.match(/^\/api\/sessions\/([^/]+)$/);
    if(m){const s=db.sessions.find(v=>v.id===m[1]); if(!s)return send(res,404,{error:'not found'}); if(req.method==='GET')return send(res,200,s); if(req.method==='PATCH'){const x=await body(req);Object.assign(s,x,{updatedAt:new Date().toISOString()});writeDb(db);return send(res,200,s);}}
    let file=req.url==='/'?'/index.html':req.url; file=path.normalize(file).replace(/^\.\.(\/|\\)/,''); const p=path.join(ROOT,file); if(!p.startsWith(ROOT))return send(res,403,'Forbidden','text/plain');
    fs.readFile(p,(e,d)=>e?send(res,404,'Not found','text/plain'):send(res,200,d,mime[path.extname(p)]||'text/plain; charset=utf-8'));
  }catch(e){send(res,500,{error:e.message});}
});
server.listen(process.env.PORT||4173,'127.0.0.1',()=>console.log(`陪你学已启动：http://127.0.0.1:${process.env.PORT||4173}`));
