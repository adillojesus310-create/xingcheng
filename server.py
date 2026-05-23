#!/usr/bin/env python3
"""
数据中转服务器 - 用于行程小程序
admin.html 通过这个API写入数据
view.html 通过 GitHub Raw 读取数据
同时支持本地中转模式
"""
import json
import sys
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
TOKEN = os.environ.get('GH_TOKEN', '')

if not TOKEN:
    # 尝试从文件读取
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.token')
    if os.path.exists(token_file):
        with open(token_file) as f:
            TOKEN = f.read().strip()

class DataHandler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200, content_type='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/data':
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    data = f.read()
                self._set_headers()
                self.wfile.write(data.encode())
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({'error': 'no data'}).encode())
        elif parsed.path == '/github-data':
            # 返回 GitHub raw 链接
            repo = 'adillojesus310-create/xingcheng'
            branch = 'master'
            url = f'https://raw.githubusercontent.com/{repo}/{branch}/data.json'
            self._set_headers(content_type='text/plain')
            self.wfile.write(url.encode())
        elif parsed.path == '/link':
            # 返回查看端链接
            host = self.headers.get('Host', 'localhost:8765')
            protocol = 'https' if 'github.io' in host else 'http'
            viewer_url = f'{protocol}://{host.replace("admin", "").rstrip("/")}/view.html'
            self._set_headers(content_type='text/plain')
            self.wfile.write(viewer_url.encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'not found'}).encode())

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/data':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)

                # 保存本地
                with open(DATA_FILE, 'w') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # 推送到 GitHub（确保数据持久化）
                repo_dir = os.path.dirname(os.path.abspath(__file__))
                try:
                    subprocess.run(
                        ['git', 'add', 'data.json'],
                        cwd=repo_dir, capture_output=True, timeout=10
                    )
                    subprocess.run(
                        ['git', 'commit', '-m', 'update data.json'],
                        cwd=repo_dir, capture_output=True, timeout=10
                    )
                    env = os.environ.copy()
                    if TOKEN:
                        env['GIT_ASKPASS'] = ''
                        # 用token推
                        remote = f'https://adillojesus310-create:{TOKEN}@github.com/adillojesus310-create/xingcheng.git'
                        subprocess.run(
                            ['git', 'push', remote, 'master'],
                            cwd=repo_dir, capture_output=True, timeout=30, env=env
                        )
                    else:
                        subprocess.run(
                            ['git', 'push'],
                            cwd=repo_dir, capture_output=True, timeout=30
                        )
                except Exception as e:
                    print(f'Git push error: {e}', file=sys.stderr)

                self._set_headers()
                self.wfile.write(json.dumps({'status': 'ok', 'data': data}).encode())
            except json.JSONDecodeError:
                self._set_headers(400)
                self.wfile.write(json.dumps({'error': 'invalid json'}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'not found'}).encode())

    def log_message(self, format, *args):
        print(f'[DATA-SERVER] {args[0]} {args[1]} {args[2]}')

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(('0.0.0.0', port), DataHandler)
    print(f'📡 数据中转服务器运行在 http://localhost:{port}')
    print(f'   POST /data  → 写入行程数据')
    print(f'   GET  /data  → 读取当前数据')
    print(f'   GET  /link  → 获取查看端链接')
    print(f'   GET  /github-data → 获取 GitHub Raw 链接')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 服务器已停止')
        server.server_close()
