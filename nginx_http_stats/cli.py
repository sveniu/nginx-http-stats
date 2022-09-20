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

    # A queue for passing lines from tail to the counter.
    event_queue = queue.Queue(1_000)

    # A counter for status codes.
    status_counter = collections.Counter()

    # Thread: tail
    threads = []
    threads.append(
        threading.Thread(
            target=tail.tail_with_retry,
            args=(config.get("access_log_path"), event_queue),
        )
    )

    # Thread: counter
    threads.append(
        threading.Thread(target=counter.run, args=(event_queue, status_counter))
    )

    # Thread: web server
    threads.append(
        threading.Thread(
            target=server.run_server, args=(config.get("server", {}), status_counter)
        )
    )

    # Start all threads.
    [t.start() for t in threads]

    try:
        # Wait for all threads to complete.
        [t.join() for t in threads]
    except KeyboardInterrupt:
        event_queue.put(None)
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
