import logging
import queue
import signal
import subprocess
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


def reader(pipe, qstdio):
    """
    Read lines from the given pipe (io.BufferedReader). Handle lines according
    to the stream type (stdout vs stderr).
    """

    with pipe:
        for line in iter(pipe.readline, b""):
            qstdio.put(line)


def tail(fn, qstdout, qstderr):
    """
    Tail the specified file using tail(1). Write stdout lines to a queue.

    Execute the system tail(1); don't output any lines on startup; follow files
    through renames.
    """

    argv = ["tail", "-n", "0", "-F", fn]
    logger.debug("tail process starting", extra={"file_path": fn, "argv": argv})
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    logger.debug("tail process started", extra={"file_path": fn, "argv": argv})

    threads = [
        threading.Thread(target=reader, args=(p.stdout, qstdout)),
        threading.Thread(target=reader, args=(p.stderr, qstderr)),
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]

    # Wait for process to exit.
    r = p.wait()

    # FIXME Close the queues?
    return r

def qstdout_handler(qin, qout):
    for line in iter(qin.get, None):
        s = line.decode("utf-8").strip()
        qout.put(s)
        logger.debug("read from stdout and enqueued", extra={"stdout": s})

def qstderr_handler(q):
    for line in iter(q.get, None):
        s = line.decode("utf-8").strip()
        logger.info("read from stderr", extra={"stderr": s})

def tail_with_retry(fn, event_queue):
    """
    Tail the specified file using tail(1). Write stdout lines to a queue. Retry
    on failure.
    """
    while True:
        qstdout = queue.Queue(1000)
        qstderr = queue.Queue(1000)

        threads = [
            threading.Thread(target=qstdout_handler, args=(qstdout, event_queue)),
            threading.Thread(target=qstderr_handler, args=(qstderr,)),
        ]
        [t.start() for t in threads]

        rc = tail(fn, qstdout, qstderr)

        # Close the queues.
        qstdout.put(None)
        qstderr.put(None)

        [t.join() for t in threads]

        if rc == -1 * signal.SIGINT:
            break

        logger.warn("unexpected subprocess exit", extra={"returncode": rc})
        time.sleep(2.0)
