import collections
import logging
import os
import queue
import sys
import threading
import traceback

import yaml

from . import counter, server, tail
from .log import CustomJsonFormatter

logger = logging.getLogger()

config_file_paths = [
    "./config.yml",
    "~/.config/nginx-limit-ipset/config.yml",
    "/etc/nginx-limit-ipset/config.yml",
]


def main():
    # If supplied, treat the first argument as the configuration file.
    if len(sys.argv) > 1:
        config_file_paths.insert(0, sys.argv[1])

    config = None
    for fn in config_file_paths:
        try:
            with open(os.path.expanduser(fn), "r") as f:
                config = yaml.safe_load(f)
                break
        except FileNotFoundError as e:
            logger.debug("config file not found", extra={"path": fn, "exception": e})

    if config is None:
        logger.error(
            "no config file found",
            extra={
                "attempted_paths": config_file_paths,
            },
        )
        raise RuntimeError(
            f"no config file found; tried: {'; '.join(config_file_paths)}"
        )

    # Update log level from config.
    logger.setLevel(config.get("log_level", logging.INFO))

    if "sources" not in config or len(config["sources"]) < 1:
        raise RuntimeError("no sources defined in config")

    # Keep track of all threads and log input queues.
    threads = []
    log_input_queues = []

    # The server zones structure from the Nginx API.
    server_zones = {}

    for source in config["sources"]:
        if "access_log_path" not in source:
            logger.warning("source is missing field 'access_log_path'", extra={"source": source})
            continue

        if "server_zone" not in source:
            logger.warning("source is missing field 'server_zone'", extra={"source": source})
            continue

        # A per-zone queue for passing lines from tail to the counter.
        log_input_queue = queue.Queue(1_000)
        log_input_queues.append(log_input_queue)

        # A per-zone structure with a nested counter for status code groups like
        # "2xx" and actual status codes. This is from the Nginx API.
        server_zone = {
            "responses": collections.Counter({"codes": collections.Counter()}),
        }
        server_zones[source["server_zone"]] = server_zone

        # Thread: tail
        threads.append(
            threading.Thread(
                target=tail.tail_with_retry,
                args=(source["access_log_path"], log_input_queue),
            )
        )

        # Thread: counter
        threads.append(
            threading.Thread(target=counter.run, args=(log_input_queue, server_zone))
        )

    if len(threads) == 0:
        raise RuntimeError("no sources could be configured")


    # Thread: web server
    threads.append(
        threading.Thread(
            target=server.run_server, args=(config.get("server", {}), server_zones)
        )
    )

    # Start all threads.
    [t.start() for t in threads]

    try:
        # Wait for all threads to complete.
        [t.join() for t in threads]
    except KeyboardInterrupt:
        for q in log_input_queues:
            q.put(None)
        [t.join(0.2) for t in threads]
        raise RuntimeError("keyboard interrupt")


def cli():
    logHandler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter("%(timestamp)s %(name)s %(level)s %(message)s")
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    logger.setLevel(logging.NOTSET)

    try:
        main()
    except Exception as e:
        logger.error(
            "unhandled exception; exiting",
            extra={"exception": e, "traceback": traceback.format_exc()},
        )
        sys.exit(1)