import json
import logging
import re
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import types

logger = logging.getLogger(__name__)


class NginxHTTPStatsHandler(BaseHTTPRequestHandler):
    def __init__(self, server_zones, zero_counters_queues, *args, **kwargs):
        """
        https://stackoverflow.com/a/52046062
        """
        self.server_zones = server_zones
        self.server_zone_event_queues = zero_counters_queues
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

    def handle_root(self):
        payload = json.dumps(["http"]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_http(self):
        payload = json.dumps(["server_zones"]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def handle_http_server_zones(self):
        payload = json.dumps(self.server_zones, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

        # Reset counters on read, to emulate the Nginx API.
        logger.debug("resetting counters")
        for q in self.server_zone_event_queues:
            logger.debug("resetting counters for queue N")
            q.put(
                {
                    "type": types.EventType.ZERO_COUNTERS,
                }
            )

    def do_GET(self):
        for route, handler in {
            re.compile(r"^//?\d/?$"): self.handle_root,
            re.compile(r"^//?\d/http/?$"): self.handle_http,
            re.compile(r"^//?\d/http/server_zones/?"): self.handle_http_server_zones,
        }.items():
            if route.match(self.path):
                return handler()

        payload = b"not found"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_server(config, server_zones, server_zone_event_queues, event_shutdown):
    server_address = config.get("bind_addr", "127.0.0.1"), config.get("bind_port", 8080)
    request_handler = partial(
        NginxHTTPStatsHandler, server_zones, server_zone_event_queues
    )
    server = HTTPServer(server_address, request_handler)

    logger.debug("starting server thread", extra={"server_address": server_address})
    threading.Thread(target=server.serve_forever).start()

    event_shutdown.wait()
    server.shutdown()
    server.server_close()
    logger.info("server stopped")
