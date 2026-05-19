#!/usr/bin/env python3
"""
CirKit dev server — no Django required.
Usage:  python ui/server.py [port]     (default 8080)
Open:   http://localhost:8080/
"""
import json, os, subprocess, sys, tempfile, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT   = Path(__file__).parent.parent
UI_DIR = Path(__file__).parent
sys.path.insert(0, str(UI_DIR))

from circuit_utils import validate_circuit, parse_cirkit_line


class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        if self.path.split('?')[0] in ('/', '/index.html'):
            data = (UI_DIR / 'index.html').read_bytes()
            self._send(200, 'text/html; charset=utf-8', data)
        else:
            self._send(404, 'text/plain', b'not found')

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except json.JSONDecodeError:
            self._send(400, 'application/json', b'{"error": "Invalid JSON body"}')
            return

        if self.path == '/cirkit/validate/':
            errors = validate_circuit(body.get('circuit', {}))
            self._json({'valid': not errors, 'errors': errors})
        elif self.path == '/cirkit/run/':
            circuit = body.get('circuit')
            prompt = body.get('prompt', '')
            if not circuit or not prompt:
                self._send(400, 'application/json', b'{"error": "circuit and prompt are required"}')
                return
            errors = validate_circuit(circuit)
            if errors:
                self._send(400, 'application/json', json.dumps({'valid': False, 'errors': errors}).encode())
                return
            self._stream(circuit, prompt)
        else:
            self._send(404, 'text/plain', b'not found')

    # ── response helpers ─────────────────────────────────────────

    def _cors(self, code):
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-CSRFToken')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def _send(self, code, ct, data):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(data))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        self._send(200, 'application/json', json.dumps(obj).encode())

    def _stream(self, circuit, prompt):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            json.dump(circuit, f, indent=2)
            tmp = f.name

        proc = None
        try:
            env = {**os.environ,
                   'PYTHONPATH': str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')}
            proc = subprocess.Popen(
                [sys.executable, '-m', 'cirkit', 'run', tmp, prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env, cwd=str(ROOT),
            )

            stderr_lines = []
            stderr_thread = threading.Thread(
                target=lambda: stderr_lines.extend(
                    l.rstrip('\n') for l in proc.stderr if l.strip()
                )
            )
            stderr_thread.start()

            output = []
            for raw in proc.stdout:
                line = raw.rstrip('\n')
                ev = parse_cirkit_line(line)
                if ev is not None:
                    self._chunk(json.dumps(ev) + '\n')
                else:
                    output.append(line)

            if content := '\n'.join(output).strip():
                self._chunk(json.dumps({'type': 'output', 'content': content}) + '\n')

            stderr_thread.join()
            for err in stderr_lines:
                self._chunk(json.dumps({'type': 'error', 'message': err}) + '\n')

        except Exception as ex:
            self._chunk(json.dumps({'type': 'error', 'message': str(ex)}) + '\n')
        finally:
            if proc is not None:
                try:
                    proc.kill()
                except OSError:
                    pass
                proc.wait()
            Path(tmp).unlink(missing_ok=True)
            self._end()

    def _chunk(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.wfile.write(data)
        self.wfile.flush()

    def _end(self):
        pass

    def log_message(self, fmt, *args):
        print(f'  {self.address_string()}  {fmt % args}')


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('', port), Handler)
    print(f'\n  CirKit  ->  http://localhost:{port}/\n  Ctrl+C to stop.\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  stopped.')
