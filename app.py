import json, os, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).parent
DB_FILE = ROOT / 'learning-data.json'
DEFAULT_STEPS = ['理解函数是什么', '参数与返回值', '条件与循环', '列表与字典', '做一个小项目']

def load_env():
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                k,v=line.split('=',1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
load_env()

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
        if self.path == '/api/plan': return self.plan(self.read_json())
        self.json(404, {'error':'not found'})
    def do_PATCH(self):
        if not self.path.startswith('/api/sessions/'): return self.json(404, {'error':'not found'})
        sid=self.path.rsplit('/',1)[-1]; db=read_db(); s=next((x for x in db['sessions'] if x['id']==sid),None)
        if not s:return self.json(404, {'error':'not found'})
        s.update(self.read_json()); s['updatedAt']=now(); write_db(db); self.json(200,s)
    def analyze(self, x):
        key=os.getenv('OPENAI_API_KEY'); current=(x.get('steps') or DEFAULT_STEPS)[x.get('step',0)]
        if not key: return self.json(200, {'reply':f'我们继续判断「{current}」。请再举一个实际例子。','mastery':0.5,'advance':False,'diagnosis':'演示模式：未配置模型密钥','nextStrategy':'补充例子并进行迁移练习','nextStep':current,'nextQuestion':f'请举例说明：{current}怎么应用？'})
        prompt=f'''你是私人学习导师。目标：{x.get('goal')}\n当前路径：{json.dumps(x.get('steps'),ensure_ascii=False)}\n当前节点：{current}\n对话：{json.dumps(x.get('messages',[]),ensure_ascii=False)}\n最新回答：{x.get('answer')}\n只返回JSON：{{"reply":"中文反馈","mastery":0到1,"advance":true或false,"diagnosis":"具体理解点和误区","nextStrategy":"教学策略","nextStep":"下一节点，可复习或插入新节点","nextSteps":["后续路径"],"nextQuestion":"下一道具体问题"}}。根据理解情况动态调整，不要机械推进。只有真正理解才 advance=true。'''
        payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'temperature':.3,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':'你是学习评估引擎，严格输出JSON。'},{'role':'user','content':prompt}]}).encode()
        req=Request(os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1')+'/chat/completions',data=payload,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        try:
            with urlopen(req, timeout=60) as r: out=json.loads(json.loads(r.read())['choices'][0]['message']['content'])
            self.json(200,out)
        except (HTTPError, Exception) as e: self.json(502, {'error':f'模型请求失败: {e}'})

    def plan(self, x):
        key=os.getenv('OPENAI_API_KEY')
        if not key: return self.json(200, {'steps': DEFAULT_STEPS, 'step': 0, 'reply': f'我们先从「{DEFAULT_STEPS[0]}」开始。请用自己的话解释并举例。'})
        prompt=f'''你是课程设计导师。用户目标：{x.get('goal')}。生成个性化学习路径。只返回JSON：{{"steps":["节点"],"step":0,"reply":"首条中文教学消息和问题"}}。至少4个节点。'''
        payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'temperature':.4,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':'严格输出JSON。'},{'role':'user','content':prompt}]}).encode()
        req=Request(os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1')+'/chat/completions',data=payload,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        try:
            with urlopen(req, timeout=60) as r: out=json.loads(json.loads(r.read())['choices'][0]['message']['content'])
            self.json(200,out)
        except Exception as e: self.json(502, {'error':f'模型请求失败: {e}'})

if __name__ == '__main__':
    port=int(os.getenv('PORT','4173')); print(f'teacher-wang Python 服务已启动：http://127.0.0.1:{port}', flush=True); ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
