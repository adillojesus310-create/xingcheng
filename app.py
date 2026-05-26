"""
行程小程序 - PythonAnywhere / Render 通用部署版
纯 Python 标准库，无需安装任何依赖
运行: python app.py
"""
import json
import os
import time
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({'items': [], 'note': '', 'loc': None}, f)

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png':  'image/png',
    '.ico':  'image/x-icon',
}

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, If-None-Match')
        self.send_header('Access-Control-Expose-Headers', 'ETag')

    def _json(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _file(self, path):
        fn = os.path.normpath(path.lstrip('/'))
        fp = os.path.join(BASE_DIR, fn)
        if not fp.startswith(BASE_DIR) or not os.path.isfile(fp):
            self._json(404, {'error': 'not found'})
            return
        ext = os.path.splitext(fp)[1]
        ct = MIME.get(ext, 'application/octet-stream')
        with open(fp, 'rb') as f:
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', ct)
            self.end_headers()
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == '/data':
            with open(DATA_FILE, 'rb') as f:
                raw = f.read()
            etag = '"' + hashlib.md5(raw).hexdigest() + '"'
            if self.headers.get('If-None-Match') == etag:
                self.send_response(304)
                self._cors()
                self.send_header('ETag', etag)
                self.end_headers()
                return
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('ETag', etag)
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(raw)
        else:
            path = p.path if p.path != '/' else '/index.html'
            self._file(path)

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == '/data':
            try:
                cl = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(cl))
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._json(200, {'status': 'ok'})
            except Exception as e:
                self._json(400, {'error': str(e)})
        else:
            self._json(404, {'error': 'not found'})

    def log_message(self, fmt, *args):
        t = time.strftime('%H:%M:%S')
        print('[' + t + '] ' + str(args[0]))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    print('=' * 50)
    print('  📋 行程小程序云服务器')
    print('  http://0.0.0.0:' + str(port))
    print('=' * 50)
    HTTPServer(('0.0.0.0', port), H).serve_forever()
