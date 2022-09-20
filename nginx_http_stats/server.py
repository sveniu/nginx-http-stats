import json
import logging
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


class NginxHTTPStatsHandler(BaseHTTPRequestHandler):
    def __init__(self, server_zones, *args, **kwargs):
        """
        https://stackoverflow.com/a/52046062
        """
        self.server_zones = server_zones
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        payload = json.dumps(self.server_zones, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_server(config, server_zones, event_shutdown):
    server_address = config.get("bind_addr", "127.0.0.1"), config.get("bind_port", 8080)
    request_handler = partial(NginxHTTPStatsHandler, server_zones)
    server = HTTPServer(server_address, request_handler)

    logger.debug("starting server thread", extra={"server_address": server_address})
    threading.Thread(target=server.serve_forever).start()

    event_shutdown.wait()
    server.shutdown()
    server.server_close()
    logger.info("server stopped")
