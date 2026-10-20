"""Isolated R5 experiment server. No production imports, storage or rewards."""
import argparse
import json
import math
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import engine

ROOT=Path(__file__).resolve().parent/'static'
MAX_BODY=16384


def finite_float(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('non-finite number')
    return result


def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key')
        result[key]=value
    return result


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def reply(self,status,data):
        body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)

    def do_GET(self):
        if self.path=='/api/health':return self.reply(200,{'ok':True,'experimental':True,'persistent':False,'rewards':False})
        if self.path=='/api/config':return self.reply(200,engine.configuration())
        if self.path.startswith('/api/'):return self.reply(404,{'error':'NOT_FOUND'})
        path=self.path.split('?',1)[0]
        if path=='/':path='/index.html'
        target=(ROOT/path.lstrip('/')).resolve()
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():return self.reply(404,{'error':'NOT_FOUND'})
        body=target.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(target.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)

    def do_POST(self):
        if self.path!='/api/simulate':return self.reply(404,{'error':'NOT_FOUND'})
        try:
            if self.headers.get('Transfer-Encoding'):raise ValueError('不支持分块请求。')
            lengths=self.headers.get_all('Content-Length',[])
            if len(lengths)!=1 or not lengths[0].isdigit():raise ValueError('须提供合法Content-Length。')
            length=int(lengths[0])
            if length>MAX_BODY:return self.reply(413,{'error':'BODY_TOO_LARGE','message':'实验请求最多16KiB。'})
            if self.headers.get_content_type()!='application/json':raise ValueError('请使用application/json。')
            data=json.loads(self.rfile.read(length).decode('utf-8'),object_pairs_hook=unique_object,parse_float=finite_float,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('不支持非有限数。')))
            result=engine.simulate(data)
        except (ValueError,UnicodeError,RecursionError) as exc:return self.reply(400,{'error':'BAD_REQUEST','message':str(exc)})
        return self.reply(200,result)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8001);args=parser.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print('R5 实验 http://%s:%d（独立实验，无存档/奖励）'%(args.host,server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
