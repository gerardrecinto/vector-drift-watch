"""Tiny local HTTP receiver that prints whatever alert payload it gets.

Stands in for a real Slack incoming webhook for the demo, since posting to an
actual Slack workspace isn't something this repo can do unattended. The
payload shape (see alerts.build_slack_payload) matches Slack's format, so
pointing --webhook-url at a real Slack webhook URL instead of this script
works with no code changes.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        payload = json.loads(body)
        # flush=True: run_demo.sh redirects this process's stdout to a log
        # file, which makes stdout fully buffered instead of line-buffered.
        # The process is stopped with a plain `kill` (SIGTERM), which does
        # not flush stdio buffers, so without an explicit flush every one of
        # these lines is silently lost and the log file ends up empty even
        # though the alert really was received.
        print(f"[mock webhook] received alert: {payload['text']}", flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


def main() -> None:
    server = HTTPServer(("127.0.0.1", 8787), Handler)
    print("mock webhook listening on http://127.0.0.1:8787", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
