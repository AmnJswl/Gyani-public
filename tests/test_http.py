"""HTTP integration checks with a local OpenAI-compatible fixture (no API key)."""
import copy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from gyani import config, server
from gyani.session import SessionManager


class ModelFixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path != '/v1/chat/completions' or not payload.get('messages'):
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        for delta in ({'role': 'assistant'}, {'content': 'Hello from Gyani'}):
            event = {'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]}
            self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode())
        self.wfile.write(b'data: [DONE]\n\n')


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = HTTPServer(('127.0.0.1', 0), ModelFixture)
        threading.Thread(target=self.model.serve_forever, daemon=True).start()
        cfg = copy.deepcopy(config.DEFAULT_CONFIG)
        cfg['agents']['defaults']['workspace'] = self.temp.name
        cfg['providers'] = {'ollama': {'api_key': 'fixture', 'api_base': f'http://127.0.0.1:{self.model.server_port}/v1'}}
        server._cfg = cfg
        server._mgr = SessionManager(cfg)
        self.app = HTTPServer(('127.0.0.1', 0), server.GyaniHandler)
        threading.Thread(target=self.app.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.app.server_port}'

    def tearDown(self):
        for service in (self.app, self.model):
            service.shutdown()
            service.server_close()
        self.temp.cleanup()

    def test_ui_status_and_tools(self):
        page = requests.get(self.url, timeout=5)
        self.assertEqual(page.status_code, 200)
        self.assertIn('<title>Gyani by Vivek</title>', page.text)
        status = requests.get(self.url + '/api/status', timeout=5).json()
        self.assertTrue(status['configured'])
        self.assertIn('read_file', status['tools'])
        tools = requests.get(self.url + '/api/tools', timeout=5).json()
        self.assertIn('spawn_subagent', [tool['name'] for tool in tools])

    def test_memory_and_skill_roundtrip(self):
        response = requests.post(self.url + '/api/memory', json={'content': 'Test memory'}, timeout=5)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(requests.get(self.url + '/api/memory', timeout=5).text, 'Test memory')
        self.assertEqual((Path(self.temp.name) / 'USER.md').read_text(), 'Test memory')
        response = requests.post(self.url + '/api/skills', json={'name': 'test-skill', 'content': '# Test'}, timeout=5)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(requests.get(self.url + '/api/skills', timeout=5).json()[0]['content'], '# Test')
        response = requests.post(self.url + '/api/skills/delete', json={'name': 'test-skill'}, timeout=5)
        self.assertTrue(response.json()['ok'])
        self.assertFalse((Path(self.temp.name) / 'skills/test-skill').exists())

    def test_two_chat_requests_stream_and_keep_history(self):
        for message in ('hello', 'hello again'):
            response = requests.post(self.url + '/api/chat', json={'message': message, 'session_id': 'test'}, timeout=10)
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
            self.assertEqual([e['content'] for e in events if e['type'] == 'token'], ['Hello from Gyani'])
            self.assertEqual(events[-1], {'type': 'done', 'content': 'Hello from Gyani'})
            self.assertNotIn('error', [e['type'] for e in events])
        self.assertEqual(len(server._mgr.history('test')), 4)
        requests.post(self.url + '/api/clear', json={'session_id': 'test'}, timeout=5)
        self.assertEqual(server._mgr.history('test'), [])
