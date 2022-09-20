import json
import logging
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


def run_server(config, server_zones):
    server_address = config.get("bind_addr", "127.0.0.1"), config.get("bind_port", 8080)
    request_handler = partial(NginxHTTPStatsHandler, server_zones)
    server = HTTPServer(server_address, request_handler)

    logger.debug("starting server", extra={"server_address": server_address})
    try:
        # FIXME handle shutdown and call server.shutdown()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    logger.error("server stopped")
