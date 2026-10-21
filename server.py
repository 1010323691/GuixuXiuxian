#!/usr/bin/env python3
"""Multi-account HTTP entry point (Python 3.11+, standard library only)."""
import argparse
import json
import logging
import math
import sqlite3
import sys
import time
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from game import admin, config, legacy, rules
from game.auth import AuthService
from game.settings import Settings
from game.storage import Database, LayoutError, LegacyLayoutError, Store

STATIC=Path(__file__).resolve().parent/'static'
FILES={'/':('index.html','text/html; charset=utf-8'),'/index.html':('index.html','text/html; charset=utf-8'),'/styles.css':('styles.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/battle_replay.js':('battle_replay.js','text/javascript; charset=utf-8')}
JSON_TYPE='application/json; charset=utf-8'
GAME_WRITES={'/api/new-game','/api/action'}
AUTH_POSTS={'/api/register','/api/login','/api/logout','/api/password'}
POST_ROUTES=GAME_WRITES|AUTH_POSTS
NEEDS_SESSION={'/api/password','/api/new-game','/api/action'}
STRICT_FIELDS={'/api/register':{'username','password'},'/api/login':{'username','password'},'/api/logout':set(),'/api/password':{'old_password','new_password'}}
MSG_SERVICE='服务暂时无法处理请求。'
MSG_WRITE_FAILED='进度保存失败，请稍后重试，当前操作未生效。'
MSG_READ_FAILED='进度暂时无法读取，请稍后重试或联系管理员。'
MSG_UNAVAILABLE='服务暂时不可用，请稍后重试。'


class App:
    """Process-wide services: settings, the single data/game.db and the account service."""

    def __init__(self,data_dir,settings=None,clock=None):
        self.data_dir=Path(data_dir)
        self.settings=settings if settings is not None else Settings()
        self._clock=clock if clock is not None else time.time
        self.db=Database(self.data_dir,clock=self.clock)
        self.auth=AuthService(self.db,self.settings,self.clock)

    def clock(self):
        return self._clock()

    def store_for(self,user_id):
        """Stateless, cheap per-account Store; user_id must come from an authenticated Principal."""
        return Store(self.db,user_id,clock=self.clock)


def error_body(code,message,revision=None,field=None,retry_after=None):
    data={'ok':False,'error':{'code':code,'message':message}}
    if field is not None:data['error']['field']=field
    if retry_after is not None:data['error']['retry_after']=retry_after
    if revision is not None:data['revision']=revision
    return data


def check_host(headers,server_address,settings=None):
    """Allow only the listen address, localhost and configured hosts (anti DNS rebinding)."""
    host=headers.get('Host','')
    try:
        parsed=urlsplit('//'+host)
        valid=parsed.path=='' and parsed.username is None and parsed.hostname is not None
        if valid:
            port=parsed.port
            listen=server_address[1]
            allowed=port==listen and parsed.hostname in {str(server_address[0]).lower(),'localhost','127.0.0.1'}
            for entry in (settings.allowed_hosts if settings is not None else ()):
                item=urlsplit('//'+entry)
                if item.hostname!=parsed.hostname:continue
                if item.port is None and port in (None,listen) or item.port is not None and item.port==port:allowed=True
            valid=allowed
    except ValueError:valid=False
    if not valid:raise rules.GameError('FORBIDDEN_ORIGIN','请求来源不被允许。',403)
    return host


def check_csrf(headers,host,settings=None):
    """POST must come from the game page: custom header plus matching Origin."""
    origin=headers.get('Origin')
    origins={'http://'+host}
    if settings is not None and settings.secure_cookies:origins.add('https://'+host)
    if headers.get('X-Game-Client')!='guixu-web' or origin is not None and origin not in origins:
        raise rules.GameError('FORBIDDEN_ORIGIN','请从本游戏页面提交操作。',403)


def _headers(headers):
    if isinstance(headers,Message):return headers
    message=Message()
    for key,value in headers.items():message[key]=value
    return message


def _read_json(headers,body):
    if headers.get_content_type()!='application/json' or headers.get('Transfer-Encoding'):
        raise rules.GameError('BAD_REQUEST','请求必须使用JSON格式。',400)
    try:length=int(headers.get('Content-Length','-1'))
    except ValueError:length=-1
    if not 0<length<=16384:raise rules.GameError('BAD_REQUEST','请求体为空或超过16KiB。',400)
    try:
        def no_constant(value):raise ValueError('non-finite JSON')
        def finite_float(value):
            number=float(value)
            if not math.isfinite(number):raise ValueError('non-finite JSON')
            return number
        raw=body(length) if callable(body) else body[:length]
        payload=json.loads(raw.decode('utf-8'),parse_constant=no_constant,parse_float=finite_float)
    except (ValueError,UnicodeError):raise rules.GameError('BAD_REQUEST','JSON格式不正确。',400)
    if not isinstance(payload,dict):raise rules.GameError('BAD_REQUEST','请求须为JSON对象。',400)
    return payload


def dispatch_full(app,method,target,headers,body,server_address,client_ip='127.0.0.1'):
    """Route one request without sockets: returns (status, bytes, content type, extra headers).

    Order: Host -> route -> CSRF/Origin -> authentication -> read body. The HTTP
    Handler and the white-box tests share this exact code path. The account id
    comes only from the session Cookie, never from the request.
    """
    headers=_headers(headers)
    out={}
    settings=app.settings
    def respond(status,data,ctype=JSON_TYPE):
        return status,(json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if isinstance(data,dict) else data),ctype,out
    def session_cookie(token,max_age=None):
        age=min(settings.session_idle_seconds,settings.session_absolute_seconds) if max_age is None else max_age
        out['Set-Cookie']=app.auth.cookie_for(token,age)
    def with_account(result,principal):
        result=dict(result);result['account']={'username':principal.username}
        if principal.set_cookie:out['Set-Cookie']=principal.set_cookie
        return result
    path=''
    try:
        host=check_host(headers,server_address,settings)
        path=urlsplit(target).path
        cookie=headers.get('Cookie')
        if method=='GET':
            if path=='/api/health':
                info=app.auth.ping()
                return respond(200,{'ok':True,'schema_version':config.SCHEMA_VERSION,'layout_version':info['layout_version'],'registration_open':info['registration_open']})
            if path=='/api/session':
                info=app.auth.session_info(cookie)
                refreshed=info.pop('set_cookie',None)
                if refreshed:out['Set-Cookie']=refreshed
                result={'ok':True};result.update(info);result['registration_open']=settings.registration_open
                return respond(200,result)
            if path=='/api/state':
                principal=app.auth.authenticate(cookie)
                return respond(200,with_account(app.store_for(principal.account_id).snapshot(),principal))
            if path in FILES:
                name,ctype=FILES[path]
                file=STATIC/name
                if not file.is_file():return respond(404,error_body('NOT_FOUND','页面资源尚未就绪。'))
                return respond(200,file.read_bytes(),ctype)
            return respond(404,error_body('NOT_FOUND','未找到此页面或接口。'))
        if method!='POST':return respond(405,error_body('METHOD_NOT_ALLOWED','不支持此请求方式。'))
        if path not in POST_ROUTES:return respond(404,error_body('NOT_FOUND','未找到此接口。'))
        check_csrf(headers,host,settings)
        principal=app.auth.authenticate(cookie) if path in NEEDS_SESSION else None
        payload=_read_json(headers,body)
        if path in STRICT_FIELDS and set(payload)!=STRICT_FIELDS[path]:
            raise rules.GameError('BAD_REQUEST','请求字段不正确。',400)
        if path=='/api/register':
            who,token=app.auth.register(payload['username'],payload['password'],client_ip)
            session_cookie(token);return respond(200,{'ok':True,'account':{'username':who.username}})
        if path=='/api/login':
            who,token=app.auth.login(payload['username'],payload['password'],client_ip)
            session_cookie(token);return respond(200,{'ok':True,'account':{'username':who.username}})
        if path=='/api/logout':
            app.auth.logout(app.auth.token_hash_from(cookie))
            out['Set-Cookie']=app.auth.clear_cookie();return respond(200,{'ok':True})
        if path=='/api/password':
            app.auth.change_password(principal,payload['old_password'],payload['new_password'],client_ip)
            return respond(200,{'ok':True})
        return respond(200,with_account(app.store_for(principal.account_id).write(path[5:],payload),principal))
    except rules.GameError as exc:
        if getattr(exc,'clear_cookie',False):out['Set-Cookie']=app.auth.clear_cookie()
        retry=getattr(exc,'retry_after',None)
        if retry:out['Retry-After']=str(retry)
        return respond(exc.status,error_body(exc.code,exc.message,getattr(exc,'revision',None),getattr(exc,'field',None),retry))
    except (sqlite3.Error,OSError,ValueError):
        if path in GAME_WRITES:logging.exception('写入进度失败');message=MSG_WRITE_FAILED
        elif path=='/api/state':logging.exception('读取进度失败');message=MSG_READ_FAILED
        else:logging.exception('服务数据库访问失败');message=MSG_UNAVAILABLE
        return respond(503,error_body('SAVE_FAILED',message))
    except Exception:logging.exception('请求处理失败');return respond(500,error_body('INTERNAL_ERROR',MSG_SERVICE))


def dispatch(app,method,target,headers,body,server_address):
    """Three-tuple wrapper over dispatch_full (loopback client, response headers dropped)."""
    return dispatch_full(app,method,target,headers,body,server_address)[:3]


def client_ip_of(headers,peer,settings):
    """Source address for rate limits; X-Forwarded-For only when --trust-proxy is set."""
    if settings.trust_proxy:
        last=(headers.get('X-Forwarded-For') or '').split(',')[-1].strip()
        if last:return last[:64]
    return peer


class GameServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,app):
        self.app=app
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    server_version='Guixu/1.2'
    timeout=30  # 套接字读写超时：半截请求体的慢连接不能无限占用线程
    def log_message(self,fmt,*args):logging.info('%s %s',self.address_string(),fmt%args)
    def send(self,status,body,ctype,headers=None):
        self.send_response(status)
        self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        for name,value in (headers or {}).items():self.send_header(name,value)
        self.end_headers();self.wfile.write(body)
    def _serve(self,method,body):
        app=self.server.app
        ip=client_ip_of(self.headers,self.client_address[0],app.settings)
        self.send(*dispatch_full(app,method,self.path,self.headers,body,(self.server.server_address[0],self.server.server_port),ip))
    def do_GET(self):self._serve('GET',b'')
    def do_POST(self):self._serve('POST',self.rfile.read)


def build_parser():
    parser=argparse.ArgumentParser(description='归墟修行手札：多账号文字修仙服务')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8000);parser.add_argument('--data-dir',default=str(Path(__file__).resolve().parent/'data'))
    parser.add_argument('--migrate-data','--migrate-save',dest='migrate_data',action='store_true',help='与 --migrate-multiuser 合用：确认迁移第1版旧数据（先备份再升级；--migrate-save 为旧名，仍可用）')
    parser.add_argument('--allowed-host',action='append',default=[],metavar='HOST',help='追加允许的访问主机名，可重复，形如 game.example.com 或 192.168.1.5:8000')
    parser.add_argument('--secure-cookies',action='store_true',help='登录凭证加 Secure 与 __Host- 前缀，并允许 https 来源（需 HTTPS 反向代理）')
    parser.add_argument('--no-register',action='store_true',help='关闭开放注册，账号由 --create-user 创建')
    parser.add_argument('--trust-proxy',action='store_true',help='使用 X-Forwarded-For 最右一段作为来源地址（仅在可信反向代理之后启用）')
    ops=parser.add_argument_group('一次性运维命令（互斥，执行后退出，请先停服）')
    ops.add_argument('--create-user',metavar='用户名',help='交互输入密码并创建账号');ops.add_argument('--reset-password',metavar='用户名',help='交互重置密码并使其全部会话失效')
    ops.add_argument('--migrate-multiuser',action='store_true',help='备份并把旧版 data/game.db 迁入待认领区（第1版数据需追加 --migrate-save）');ops.add_argument('--claim-legacy',metavar='用户名',help='把待认领的旧版数据归属给已存在的账号')
    ops.add_argument('--force',action='store_true',help='配合 --claim-legacy：目标账号已有进度时覆盖（覆盖前自动备份）');ops.add_argument('--legacy-status',action='store_true',help='查看待认领区状态')
    ops.add_argument('--backup',action='store_true',help='在线备份数据库到 data/backups/game.<时间>.bak.db（可不停服）')
    ops.add_argument('--backup-all',dest='backup',action='store_true',help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    parser=build_parser()
    args=parser.parse_args(argv);logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    try:command=admin.selected_command(args)
    except ValueError as exc:parser.error(str(exc))
    if args.force and command!='claim_legacy':parser.error('--force 只能与 --claim-legacy 一起使用')
    if args.migrate_data and command!='migrate_multiuser':
        if legacy.legacy_format_present(args.data_dir):parser.error('--migrate-save（--migrate-data）须与 --migrate-multiuser 一起使用')
        parser.exit(0,'无需迁移：当前已是多账号布局。\n')
    data_dir=Path(args.data_dir)
    if command=='migrate_multiuser':return admin.run(args,None)
    settings=Settings.from_args(args)
    try:app=App(data_dir,settings)
    except LegacyLayoutError as exc:parser.exit(1,'%s\n'%exc)
    except Exception as exc:parser.exit(1,'数据初始化失败（原数据未改动）：%s\n'%exc)
    if command is not None:return admin.run(args,app)
    try:server=GameServer((args.host,args.port),app)
    except OSError as exc:parser.exit(1,'无法监听 %s:%d：%s\n'%(args.host,args.port,exc))
    pending=legacy.status(app.db)
    if pending is not None and pending.status!=legacy.CLAIMED:logging.info('存在待认领的旧版数据（状态：%s），由管理员使用 --claim-legacy 处理',pending.status)
    if args.host in ('0.0.0.0','::') and not settings.allowed_hosts:logging.warning('监听所有网卡但未配置 --allowed-host：通过局域网地址访问会被拒绝，请添加允许的主机名')
    logging.info('归墟修行手札已启动，监听 %s:%d；数据目录：%s；开放注册：%s；允许主机：%s；Secure Cookie：%s',args.host,server.server_port,data_dir,'是' if settings.registration_open else '否',','.join(settings.allowed_hosts) or '无',  '是' if settings.secure_cookies else '否')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return server

if __name__=='__main__':
    result=main()
    if isinstance(result,int):sys.exit(result)
