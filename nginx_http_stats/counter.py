import json
import logging

logger = logging.getLogger(__name__)


def run(log_input_queue, server_zone):
    """
    https://demo.nginx.com/swagger-ui/
    """

    for line in iter(log_input_queue.get, None):
        logger.debug("counter got event", extra={"event": line})
        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("json decode error", extra={"error": e, "input": line})

        if "status" not in data:
            logger.warning("required field 'status' not found", extra={"input": data})

        status_code = data["status"]
        if isinstance(status_code, int):
            # All JSON keys are strings.
            status_code = str(status_code)

        # Update the per-status counters.
        server_zone["responses"]["codes"][status_code] += 1

        # Update the "2xx"-style group counters.
        server_zone["responses"][f"{int(status_code) // 100}xx"] += 1

        logger.debug("server_zone counters updated", extra={"server_zone": server_zone})


# {
#   "site1": {
#     "processing": 2,
#     "requests": 736395,
#     "responses": {
#       "1xx": 0,
#       "2xx": 727290,
#       "3xx": 4614,
#       "4xx": 934,
#       "5xx": 1535,
#       "codes": {
#         "200": 727270,
#         "301": 4614,
#         "404": 930,
#         "503": 1535
#       },
#       "total": 734373
#     },
#     "discarded": 2020,
#     "received": 180157219,
#     "sent": 20183175459
#   },
#   ...
