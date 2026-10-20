"""Isolated subprocess HTTP harness. Does not import any production module."""
import json
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

LAB=Path(__file__).resolve().parents[1]
REPO=LAB.parents[1]
ARTIFACTS=REPO/'artifacts/r5-review/qa'

class LabServer:
    def __init__(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        self.url='http://127.0.0.1:'+str(self.port)
        self.process=None
    def start(self):
        self.process=subprocess.Popen([sys.executable,str(LAB/'server.py'),'--host','127.0.0.1','--port',str(self.port)],cwd=LAB,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            if self.process.poll() is not None:raise RuntimeError(self.process.stderr.read().decode())
            try:
                if self.request('GET','/api/health')[0]==200:return self
            except OSError:pass
            time.sleep(.03)
        self.close();raise RuntimeError('isolated lab did not start')
    def request(self,method,path,payload=None,raw=None,content_type='application/json'):
        data=raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(self.url+path,data=data,method=method,headers={'Content-Type':content_type})
        try:
            with urllib.request.urlopen(req,timeout=15) as response:return response.status,json.loads(response.read())
        except urllib.error.HTTPError as response:return response.code,json.loads(response.read())
    def close(self):
        if self.process:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.process.stderr.close();self.process=None
