"""Live lab plus performance leaderboard; preserves frozen batch implementation."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import facet_retrieval_lab as L
from facet_combined_leaderboard import leaderboard
from facet_weighted_lab import WeightedLab


def serve(port):
    lab = WeightedLab()
    static = L.ROOT / 'tools/retrieval_lab_static'
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, value, status=200):
            body = json.dumps(value, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == '/api/status':
                    return self.send_json(lab.status())
                if parsed.path == '/api/leaderboard':
                    query = parse_qs(parsed.query)
                    return self.send_json(leaderboard(query.get('metric', ['recall_id'])[0],
                        int(query.get('limit', ['25'])[0]), query.get('cohort', ['all'])[0],
                        query.get('subset', ['all'])[0]))
                if parsed.path == '/api/batch':
                    path = L.BASE / 'batch/status.json'
                    return self.send_json(L.read(path) if path.exists() else {'status': 'pending'})
                target = (static / ('index.html' if parsed.path == '/' else parsed.path.lstrip('/'))).resolve()
                if not target.is_relative_to(static.resolve()) or not target.is_file():
                    return self.send_error(404)
                body = target.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript'}.get(target.suffix, 'application/octet-stream'))
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_json({'error': str(exc)}, 400)

        def do_POST(self):
            if self.path != '/api/replay':
                return self.send_error(404)
            try:
                count = int(self.headers.get('Content-Length', '0'))
                if not 0 < count < 100_000:
                    raise ValueError('Invalid request size')
                self.send_json(lab.replay(json.loads(self.rfile.read(count))))
            except Exception as exc:
                self.send_json({'error': str(exc)}, 400)

        def log_message(self, *_):
            pass
    print(json.dumps({'phase': 'serving', 'url': f'http://127.0.0.1:{port}/', 'leaderboard': True}), flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8770)
    serve(parser.parse_args().port)
