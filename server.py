#!/usr/bin/env python3
"""Local single-player HTTP entry point (Python 3.11+, standard library only)."""
import argparse
import json
import logging
import math
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from game import config, rules
from game.storage import Store

STATIC=Path(__file__).resolve().parent/'static'
FILES={'/':('index.html','text/html; charset=utf-8'),'/index.html':('index.html','text/html; charset=utf-8'),'/styles.css':('styles.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8')}


class GameServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,store):
        self.store=store
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    server_version='Guixu/1.2'
    def log_message(self,fmt,*args):logging.info('%s %s',self.address_string(),fmt%args)
    def send(self,status,data,ctype='application/json; charset=utf-8'):
        body=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if isinstance(data,dict) else data
        self.send_response(status)
        self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(body)
    def error(self,status,code,message,revision=None):
        data={'ok':False,'error':{'code':code,'message':message}}
        if revision is not None:data['revision']=revision
        self.send(status,data)
    def check_host(self):
        host=self.headers.get('Host','')
        try:
            parsed=urlsplit('//'+host)
            allowed={self.server.server_address[0],'localhost','127.0.0.1'}
            valid=parsed.hostname in allowed and parsed.port==self.server.server_port and parsed.path=='' and parsed.username is None
        except ValueError:valid=False
        if not valid:raise rules.GameError('FORBIDDEN_ORIGIN','请求来源不被允许。',403)
        return host
    def do_GET(self):
        try:
            self.check_host()
            path=urlsplit(self.path).path
            if path=='/api/health':self.server.store.snapshot();self.send(200,{'ok':True,'schema_version':config.SCHEMA_VERSION})
            elif path=='/api/state':self.send(200,self.server.store.snapshot())
            elif path in FILES:
                name,ctype=FILES[path]
                file=STATIC/name
                if not file.is_file():self.error(404,'NOT_FOUND','页面资源尚未就绪。')
                else:self.send(200,file.read_bytes(),ctype)
            else:self.error(404,'NOT_FOUND','未找到此页面或接口。')
        except rules.GameError as exc:self.error(exc.status,exc.code,exc.message)
        except (sqlite3.Error,ValueError,OSError):logging.exception('读取存档失败');self.error(503,'SAVE_FAILED','存档无法读取，请保留数据并检查服务日志。')
        except Exception:logging.exception('GET失败');self.error(500,'INTERNAL_ERROR','服务暂时无法处理请求。')
    def do_POST(self):
        try:
            host=self.check_host()
            origin=self.headers.get('Origin')
            if self.headers.get('X-Game-Client')!='guixu-web' or origin is not None and origin!='http://'+host:
                raise rules.GameError('FORBIDDEN_ORIGIN','请从本游戏页面提交操作。',403)
            path=urlsplit(self.path).path
            if path not in {'/api/new-game','/api/action','/api/save','/api/load'}:
                self.error(404,'NOT_FOUND','未找到此接口。');return
            if self.headers.get_content_type()!='application/json' or self.headers.get('Transfer-Encoding'):
                raise rules.GameError('BAD_REQUEST','请求必须使用JSON格式。',400)
            try:length=int(self.headers.get('Content-Length','-1'))
            except ValueError:length=-1
            if not 0<length<=16384:raise rules.GameError('BAD_REQUEST','请求体为空或超过16KiB。',400)
            try:
                def no_constant(value):raise ValueError('non-finite JSON')
                def finite_float(value):
                    number=float(value)
                    if not math.isfinite(number):raise ValueError('non-finite JSON')
                    return number
                payload=json.loads(self.rfile.read(length).decode('utf-8'),parse_constant=no_constant,parse_float=finite_float)
            except (ValueError,UnicodeError):raise rules.GameError('BAD_REQUEST','JSON格式不正确。',400)
            if not isinstance(payload,dict):raise rules.GameError('BAD_REQUEST','请求须为JSON对象。',400)
            self.send(200,self.server.store.write(path[5:],payload))
        except rules.GameError as exc:self.error(exc.status,exc.code,exc.message,getattr(exc,'revision',None))
        except (sqlite3.Error,OSError,ValueError):logging.exception('写入存档失败');self.error(503,'SAVE_FAILED','操作未能保存，请检查磁盘与服务日志。')
        except Exception:logging.exception('POST失败');self.error(500,'INTERNAL_ERROR','服务暂时无法处理请求。')


def main():
    parser=argparse.ArgumentParser(description='归墟修行手札：本地单人文字修仙')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8000);parser.add_argument('--data-dir',default=str(Path(__file__).resolve().parent/'data'))
    parser.add_argument('--migrate-save',action='store_true',help='先验证并备份第1版存档，再显式迁移至第2版；请先停服')
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    try:store=Store(args.data_dir,migrate=args.migrate_save)
    except Exception as exc:parser.exit(1,'存档初始化失败（原件未重置）：%s\n'%exc)
    if store.migration_backup:
        logging.info('第1版存档已迁移至第2版，原件备份：%s',store.migration_backup)
    server=GameServer((args.host,args.port),store)
    logging.info('归墟修行手札已启动，监听 %s:%d；数据：%s',args.host,server.server_port,store.path)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
