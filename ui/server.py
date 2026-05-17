#!/usr/bin/env python3
"""
CirKit dev server — no Django required.
Usage:  python ui/server.py [port]     (default 8080)
Open:   http://localhost:8080/
"""
import json, os, subprocess, sys, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT   = Path(__file__).parent.parent   # project root (has cirkit/ package)
UI_DIR = Path(__file__).parent


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
        body = json.loads(self.rfile.read(n) or b'{}')
        if self.path == '/cirkit/validate/':
            errors = _validate(body.get('circuit', {}))
            self._json({'valid': not errors, 'errors': errors})
        elif self.path == '/cirkit/run/':
            self._stream(body.get('circuit', {}), body.get('prompt', ''))
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
        self.send_header('Transfer-Encoding', 'chunked')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            json.dump(circuit, f, indent=2)
            tmp = f.name

        try:
            env = {**os.environ,
                   'PYTHONPATH': str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')}
            proc = subprocess.Popen(
                [sys.executable, '-m', 'cirkit', 'run', tmp, prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env, cwd=str(ROOT),
            )
            output = []
            for raw in proc.stdout:
                line = raw.rstrip('\n')
                if line.startswith('[converged') or line.startswith('[MAX_ITER'):
                    ev = {'type': 'done',
                          'converged': 'converged after' in line,
                          'iter':  _int(line, 'after '),
                          'delta': _float(line, 'delta=')}
                elif line.startswith('[iter'):
                    ev = {'type': 'iter',
                          'iter':    _int(line, '[iter '),
                          'delta':   _float(line, 'delta='),
                          'message': line.split(']', 1)[-1].strip()}
                else:
                    output.append(line)
                    continue
                self._chunk(json.dumps(ev) + '\n')

            if content := '\n'.join(output).strip():
                self._chunk(json.dumps({'type': 'output', 'content': content}) + '\n')

            for err in proc.stderr.read().splitlines():
                if err.strip():
                    self._chunk(json.dumps({'type': 'error', 'message': err}) + '\n')

            proc.wait()
        except Exception as ex:
            self._chunk(json.dumps({'type': 'error', 'message': str(ex)}) + '\n')
        finally:
            Path(tmp).unlink(missing_ok=True)
            self._end()

    def _chunk(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.wfile.write(f'{len(data):X}\r\n'.encode() + data + b'\r\n')
        self.wfile.flush()

    def _end(self):
        self.wfile.write(b'0\r\n\r\n')
        self.wfile.flush()

    def log_message(self, fmt, *args):
        print(f'  {self.address_string()}  {fmt % args}')


# ── validation (mirrors ui/views.py) ─────────────────────────────

def _validate(circuit):
    errors = []
    cfg = circuit.get('config', {})
    eps = cfg.get('epsilon')
    if eps is None or not (0 < eps <= 1.0):
        errors.append('config.epsilon must be in (0, 1.0]')
    if not isinstance(cfg.get('max_iter'), int) or cfg['max_iter'] < 1:
        errors.append('config.max_iter must be an integer >= 1')
    nodes = {n['id']: n for n in circuit.get('nodes', [])}
    if len(nodes) != len(circuit.get('nodes', [])):
        errors.append('Duplicate node IDs')
    sink = circuit.get('sink')
    if not sink:
        errors.append('sink is required')
    elif sink not in nodes:
        errors.append(f"sink '{sink}' not in nodes")
    for w in circuit.get('wires', []):
        if w.get('from') not in nodes:
            errors.append(f"wire from unknown '{w.get('from')}'")
        if w.get('to') not in nodes:
            errors.append(f"wire to unknown '{w.get('to')}'")
        if w.get('role', 'context') not in ('context', 'peer', 'feedback'):
            errors.append(f"bad role '{w.get('role')}'")
    return errors


def _int(s, after):
    try:    return int(s.split(after, 1)[1].split()[0].rstrip(','))
    except: return None

def _float(s, after):
    try:    return float(s.split(after, 1)[1].split(']')[0].split()[0])
    except: return None


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('', port), Handler)
    print(f'\n  CirKit  ->  http://localhost:{port}/\n  Ctrl+C to stop.\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  stopped.')
