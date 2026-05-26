#!/usr/bin/env python3
"""
行程小程序 - 本地服务器
同时提供：
  1. 静态文件服务（index.html, admin.html, view.html）
  2. 数据 API（GET/POST /data）
  3. GitHub 同步（写入 data.json 后自动推送到 GitHub）
"""
import json
import sys
import os
import subprocess
import base64
import hashlib
import urllib.request
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

# GitHub 配置
GITHUB_OWNER = 'adillojesus310-create'
GITHUB_REPO = 'xingcheng'
GITHUB_BRANCH = 'master'

# 从 config.js 提取 Token
def load_token():
    config_path = os.path.join(BASE_DIR, 'config.js')
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                if 'GITHUB_TOKEN_FROM_CONFIG' in line:
                    # 提取单引号或双引号内的值
                    for q in ["'", '"']:
                        if q in line:
                            start = line.index(q) + 1
                            end = line.rindex(q)
                            if start < end:
                                return line[start:end]
    return ''

GH_TOKEN = load_token()
_last_pushed_hash = None
_last_push_time = 0
GH_PUSH_MIN_INTERVAL = 60  # 同一内容/高频更新最少 60s 才推一次 GitHub
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.ico': 'image/x-icon',
}

class Handler(BaseHTTPRequestHandler):
    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, If-None-Match')
        self.send_header('Access-Control-Expose-Headers', 'ETag')

    def _send_json(self, code, data):
        self.send_response(code)
        self._cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _send_text(self, code, text, content_type='text/plain; charset=utf-8'):
        self.send_response(code)
        self._cors_headers()
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(text.encode() if isinstance(text, str) else text)

    def _serve_static(self, path):
        """提供静态文件"""
        # 默认首页
        if path == '/' or path == '':
            path = '/index.html'
        # 安全：防止目录穿越
        clean = os.path.normpath(path.lstrip('/'))
        filepath = os.path.join(BASE_DIR, clean)
        if not filepath.startswith(BASE_DIR):
            self._send_json(403, {'error': 'forbidden'})
            return
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            self._send_json(404, {'error': 'not found'})
            return

        ext = os.path.splitext(filepath)[1]
        content_type = MIME_TYPES.get(ext, 'application/octet-stream')
        try:
            with open(filepath, 'rb') as f:
                self.send_response(200)
                self._cors_headers()
                self.send_header('Content-Type', content_type)
                self.end_headers()
                self.wfile.write(f.read())
        except Exception as e:
            self._send_json(500, {'error': str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/data':
            # 返回当前数据 (带 ETag,客户端 If-None-Match 命中时返回 304)
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'rb') as f:
                    raw = f.read()
            else:
                raw = json.dumps({'items': [], 'note': '', 'loc': None}, ensure_ascii=False).encode()

            etag = '"' + hashlib.md5(raw).hexdigest() + '"'
            client_etag = self.headers.get('If-None-Match')
            if client_etag == etag:
                self.send_response(304)
                self._cors_headers()
                self.send_header('ETag', etag)
                self.end_headers()
                return

            self.send_response(200)
            self._cors_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('ETag', etag)
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(raw)
        elif parsed.path == '/github-push-url':
            # 返回 GitHub Raw URL（供 view.html 使用）
            url = f'https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data.json'
            self._send_text(200, url)
        elif parsed.path.startswith('/api/'):
            self._send_json(404, {'error': 'unknown api'})
        else:
            self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/data':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)

                # 保存到本地文件
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # 后台推送 GitHub（不阻塞响应）
                threading.Thread(target=self._push_github, args=(data,), daemon=True).start()

                self._send_json(200, {'status': 'ok', 'saved': True})
            except json.JSONDecodeError:
                self._send_json(400, {'error': 'invalid json'})
        else:
            self._send_json(404, {'error': 'not found'})

    def _push_github(self, data):
        """后台推送到 GitHub (去重 + 节流,避免位置高频更新刷屏)"""
        global _last_pushed_hash, _last_push_time
        if not GH_TOKEN:
            print('[GitHub] 未配置 Token，跳过推送')
            return

        body_str = json.dumps(data, ensure_ascii=False, indent=2)
        cur_hash = hashlib.md5(body_str.encode()).hexdigest()
        now = time.time()
        # 内容没变 → 跳过
        if cur_hash == _last_pushed_hash:
            return
        # 距上次推送太近 → 跳过(下次保存或带行程变更时再推)
        if now - _last_push_time < GH_PUSH_MIN_INTERVAL:
            print(f'[GitHub] 节流中,跳过 (距上次 {int(now - _last_push_time)}s)')
            return

        api_url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/data.json'

        try:
            # 获取当前 SHA
            req = urllib.request.Request(api_url, headers={
                'Authorization': f'token {GH_TOKEN}',
                'User-Agent': 'xingcheng-server'
            })
            sha = ''
            try:
                resp = urllib.request.urlopen(req, timeout=10)
                info = json.loads(resp.read())
                sha = info.get('sha', '')
            except Exception:
                pass

            # 推送新内容
            content_b64 = base64.b64encode(body_str.encode('utf-8')).decode()

            body = {
                'message': f'update schedule via server',
                'content': content_b64,
                'branch': GITHUB_BRANCH
            }
            if sha:
                body['sha'] = sha

            req = urllib.request.Request(api_url, data=json.dumps(body).encode(), method='PUT', headers={
                'Authorization': f'token {GH_TOKEN}',
                'Content-Type': 'application/json',
                'User-Agent': 'xingcheng-server'
            })
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read())
            _last_pushed_hash = cur_hash
            _last_push_time = now
            print(f'[GitHub] 推送成功: {result.get("commit", {}).get("sha", "?")[:8]}')
        except Exception as e:
            print(f'[GitHub] 推送失败: {e}')

    def log_message(self, format, *args):
        print(f'[行程服务器] {args[0]} {args[1]} {args[2]}')


def open_browser(port):
    """延迟打开浏览器"""
    time.sleep(1)
    url = f'http://localhost:{port}'
    try:
        if sys.platform == 'win32':
            os.system(f'start {url}')
        elif sys.platform == 'darwin':
            os.system(f'open {url}')
        else:
            os.system(f'xdg-open {url}')
    except Exception:
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

    token_status = '✅ 已配置' if GH_TOKEN else '⚠️ 未配置（查看端只能本地访问）'
    print('=' * 50)
    print('  📋 行程小程序服务器')
    print('=' * 50)
    print(f'  地址: http://localhost:{port}')
    print(f'  数据: {DATA_FILE}')
    print(f'  GitHub 同步: {token_status}')
    print()
    print(f'  📄 首页:    http://localhost:{port}/')
    print(f'  📝 管理:    http://localhost:{port}/admin.html')
    print(f'  👀 查看端:  http://localhost:{port}/view.html')
    print(f'  📡 API:     POST/GET http://localhost:{port}/data')
    print()
    print(f'  💡 把 http://localhost:{port} 发给男朋友就能看到你的信息')
    print(f'  （如果在同一局域网，用你的电脑IP替换 localhost）')
    print('=' * 50)

    server = HTTPServer(('0.0.0.0', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 服务器已停止')
        server.server_close()
