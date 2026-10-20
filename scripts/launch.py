"""One-click launcher: start the local game server and open the browser.

Usage: python scripts/launch.py [--port 8000] [--data-dir ./data] [--no-browser]
Uses the real save directory (./data by default). It never passes --migrate-save; an old
schema1 save is refused with the server's own message, exactly like a manual start.
If the game is already running on the port, it only opens the browser.
"""
import argparse
import json
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def running_game(url):
    try:
        with urllib.request.urlopen(url + '/api/health', timeout=1) as response:
            return json.load(response).get('ok') is True
    except (OSError, ValueError):
        return False


def port_free(host, port):
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def open_when_ready(url, deadline=20):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if running_game(url):
            print(f'已在浏览器打开 {url}  （关闭本窗口或按 Ctrl+C 停止游戏）', flush=True)
            webbrowser.open(url)
            return
        time.sleep(.3)
    print(f'服务未在 {deadline} 秒内就绪，请查看上方日志后手动打开 {url}', flush=True)


def main():
    parser = argparse.ArgumentParser(description='归墟修行手札 一键启动')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', default=str(ROOT / 'data'))
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    host = '127.0.0.1'
    url = f'http://{host}:{args.port}'
    if running_game(url):
        print(f'游戏已在运行：{url}', flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return 0
    if not port_free(host, args.port):
        print(f'端口 {args.port} 已被其他程序占用。可改用：启动游戏.bat --port 8010', flush=True)
        return 1
    print(f'归墟修行手札 启动中…  存档目录：{Path(args.data_dir).resolve()}', flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    import server
    server.main(['--host', host, '--port', str(args.port), '--data-dir', args.data_dir])
    return 0


if __name__ == '__main__':
    sys.exit(main())
