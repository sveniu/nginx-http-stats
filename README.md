# Nginx HTTP statistics API from access logs

Tail JSON-formatted Nginx access logs and keep track of response status codes.
Publish the statistics on a HTTP endpoint that exposes an Nginx-compatible API.

## Overview

Configure Nginx to write an access log in JSON format.

```nginx
events {}
http {
 log_format logger escape=json '{"time": $msec, "status": $status, "uri": "$request_uri"}';

 server {
    listen 80;
    access_log /var/log/nginx/access.log logger;
    root /var/www/html;
    location / {
        try_files $uri $uri/ =404;
    }
  }
}
```

Put the following configuration into `config.yml`:

```yaml
---
server:
  bind_addr: 127.0.0.1
  bind_port: 8011

sources:
  - access_log_path: /var/log/nginx/access.log
    server_zone: myserver
```

Run the program with `nginx-http-stats config.yml` and it will log activity to
stdout. Query the API at <http://127.0.0.1:8011/> with a GET request using any
path.

## Configuration

The configuration is a single YAML file, searched at these locations:

- The first argument on the command line

- `./config.yml`

- `~/.config/nginx-http-stats/config.yml`

- `/etc/nginx-http-stats/config.yml`

See examples/config.yml for a full example configuration with documentation.

Global configuration parameters:

`log_level` (default: INFO): Control the log level. Set to `DEBUG` when
troubleshooting.

`server.bind_addr` (default: 127.0.0.1): IP address to bind to

`server.bind_port` (default: 8011): Port to bind to

## Datadog integration

```yaml
init_config: null

instances:
  - nginx_status_url: http://127.0.0.1:8011
    use_plus_api: true                  # default false
    use_plus_api_stream: false          # default true
    plus_api_version: 7                 # default 2
    only_query_enabled_endpoints: true  # default false
```
