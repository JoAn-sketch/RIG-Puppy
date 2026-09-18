#!/usr/bin/env python3
"""Run inside the main container's network namespace; no mutations."""
import json
import socket
import sys
import urllib.request


def check():
    results = {}
    for name, url in [('server_http', 'http://127.0.0.1:8003/mcp/vision/explain'),
                      ('kokoro_http', 'http://127.0.0.1:8880/health')]:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                results[name] = response.status == 200
        except Exception:
            results[name] = False
    try:
        with socket.create_connection(('127.0.0.1', 10095), timeout=5):
            results['funasr_tcp'] = True
    except OSError:
        results['funasr_tcp'] = False
    print(json.dumps(results))
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(check())
