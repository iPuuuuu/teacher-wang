import json, os, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).parent
DB_FILE = ROOT / 'learning-data.json'
DEFAULT_STEPS = ['理解函数是什么', '参数与返回值', '条件与循环', '列表与字典', '做一个小项目']

def now(): return datetime.now(timezone.utc).isoformat()
def read_db():
    try: return json.loads(DB_FILE.read_text(encoding='utf-8'))
    except Exception: return {'sessions': []}
def write_db(db): DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def json(self, code, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(raw)
    def read_json(self):
        n = int(self.headers.get('Content-Length', 0)); return json.loads(self.rfile.read(n) or b'{}')
    def do_OPTIONS(self):
        self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
    def do_GET(self):
        if self.path == '/api/sessions': return self.json(200, read_db()['sessions'])
        if self.path.startswith('/api/sessions/'):
            sid = self.path.rsplit('/', 1)[-1]; s = next((x for x in read_db()['sessions'] if x['id'] == sid), None)
            return self.json(200, s) if s else self.json(404, {'error':'not found'})
        file = ROOT / ('index.html' if self.path == '/' else self.path.lstrip('/'))
        if not file.resolve().is_relative_to(ROOT.resolve()) or not file.exists(): self.send_error(404); return
        types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}
        self.send_response(200); self.send_header('Content-Type', types.get(file.suffix, 'text/plain; charset=utf-8')); self.end_headers(); self.wfile.write(file.read_bytes())
    def do_POST(self):
        if self.path == '/api/sessions':
            x=self.read_json(); db=read_db(); s={'id':str(uuid.uuid4()),'title':x.get('title','Python 基础'),'goal':x.get('goal','Python 基础'),'steps':x.get('steps',DEFAULT_STEPS),'step':0,'messages':x.get('messages',[]),'assessments':[],'createdAt':now(),'updatedAt':now()}; db['sessions'].insert(0,s); write_db(db); return self.json(201,s)
        if self.path == '/api/analyze': return self.analyze(self.read_json())
        self.json(404, {'error':'not found'})
    def do_PATCH(self):
        if not self.path.startswith('/api/sessions/'): return self.json(404, {'error':'not found'})
        sid=self.path.rsplit('/',1)[-1]; db=read_db(); s=next((x for x in db['sessions'] if x['id']==sid),None)
        if not s:return self.json(404, {'error':'not found'})
        s.update(self.read_json()); s['updatedAt']=now(); write_db(db); self.json(200,s)
    def analyze(self, x):
        key=os.getenv('OPENAI_API_KEY'); current=(x.get('steps') or DEFAULT_STEPS)[x.get('step',0)]
        if not key: return self.json(200, {'reply':f'我先根据你的回答来判断。关于「{current}」，我会观察你是否能解释概念、说明原因并举例。你的回答已记录；如果不确定，可以继续用自己的话说说，我会换一种方式讲解。','mastery':0.5,'advance':False,'diagnosis':'演示模式：未配置模型密钥','nextStrategy':'补充例子并进行一次迁移练习'})
        prompt=f'''你是私人学习导师。目标：{x.get('goal')}\n路径：{json.dumps(x.get('steps'),ensure_ascii=False)}\n当前节点：{current}\n对话：{json.dumps(x.get('messages',[]),ensure_ascii=False)}\n最新回答：{x.get('answer')}\n只返回JSON：{{"reply":"中文反馈和下一步问题","mastery":0到1,"advance":true或false,"diagnosis":"具体理解点和误区","nextStrategy":"下一步策略"}}。只有真正理解并能解释或应用时 advance 才为 true。'''
        payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'temperature':.3,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':'你是学习评估引擎，严格输出JSON。'},{'role':'user','content':prompt}]}).encode()
        req=Request(os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1')+'/chat/completions',data=payload,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        try:
            with urlopen(req, timeout=60) as r: out=json.loads(json.loads(r.read())['choices'][0]['message']['content'])
            self.json(200,out)
        except (HTTPError, Exception) as e: self.json(502, {'error':f'模型请求失败: {e}'})

if __name__ == '__main__':
    port=int(os.getenv('PORT','4173')); print(f'teacher-wang Python 服务已启动：http://127.0.0.1:{port}', flush=True); ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
