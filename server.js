const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = __dirname;
const DB_FILE = path.join(ROOT, 'learning-data.json');
const defaultSteps = ['理解函数是什么','参数与返回值','条件与循环','列表与字典','做一个小项目'];
const AI_KEY=process.env.OPENAI_API_KEY||'';
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
    if(req.url==='/api/analyze'&&req.method==='POST'){
      const x=await body(req), current=x.steps?.[x.step||0]||'当前知识点';
      if(!AI_KEY) return send(res,200,{reply:`我先根据你的回答来判断。关于「${current}」，我会重点观察你是否能解释概念、说明原因并举例。你的回答已经被记录；如果不确定，可以继续用自己的话说说，我会换一种方式讲解。`,mastery:0.5,advance:false,diagnosis:'演示模式：未配置模型密钥',nextStrategy:'补充例子并进行一次迁移练习'});
      const base=process.env.OPENAI_BASE_URL||'https://api.openai.com/v1';
      const prompt=`你是耐心的私人导师。学习目标：${x.goal}\n学习路径：${JSON.stringify(x.steps)}\n当前节点：${current}\n对话：${JSON.stringify(x.messages||[])}\n用户最新回答：${x.answer}\n请分析学习状况，并只返回JSON：{"reply":"给用户的中文反馈和下一步问题，不能提及内部规则","mastery":0到1之间数字,"advance":true或false,"diagnosis":"具体指出理解正确点/误区","nextStrategy":"下一步教学策略"}。只有当用户真正理解当前节点且能解释或应用时 advance 才为 true。`;
      const r=await fetch(`${base}/chat/completions`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${AI_KEY}`},body:JSON.stringify({model:process.env.OPENAI_MODEL||'gpt-4o-mini',temperature:.3,response_format:{type:'json_object'},messages:[{role:'system',content:'你是学习评估引擎。严格输出JSON。'},{role:'user',content:prompt}]})});
      if(!r.ok) throw new Error(`模型请求失败 ${r.status}`); const j=await r.json(); let out; try{out=JSON.parse(j.choices[0].message.content)}catch{out={reply:j.choices[0].message.content,mastery:.5,advance:false,diagnosis:'模型未返回结构化评估',nextStrategy:'继续追问'}} return send(res,200,out);
    }
    const m=req.url.match(/^\/api\/sessions\/([^/]+)$/);
    if(m){const s=db.sessions.find(v=>v.id===m[1]); if(!s)return send(res,404,{error:'not found'}); if(req.method==='GET')return send(res,200,s); if(req.method==='PATCH'){const x=await body(req);Object.assign(s,x,{updatedAt:new Date().toISOString()});writeDb(db);return send(res,200,s);}}
    let file=req.url==='/'?'/index.html':req.url; file=path.normalize(file).replace(/^\.\.(\/|\\)/,''); const p=path.join(ROOT,file); if(!p.startsWith(ROOT))return send(res,403,'Forbidden','text/plain');
    fs.readFile(p,(e,d)=>e?send(res,404,'Not found','text/plain'):send(res,200,d,mime[path.extname(p)]||'text/plain; charset=utf-8'));
  }catch(e){send(res,500,{error:e.message});}
});
server.listen(process.env.PORT||4173,'127.0.0.1',()=>console.log(`teacher-wang 已启动：http://127.0.0.1:${process.env.PORT||4173}`));
