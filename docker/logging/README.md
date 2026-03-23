# FluentBit + VictoriaLogs Stack

## Quick Start

```bash
docker compose up -d
```

Go to `http://localhost:9428` for victorialogs UI.

## Directory Layout

```
.
├── docker-compose.yml
└── fluent-bit/
    ├── fluent-bit.conf   # Main FluentBit pipeline config
    └── parsers.conf      # JSON / syslog parsers
```

## Ports

| Service      | Port  | Purpose                           |
|--------------|-------|-----------------------------------|
| VictoriaLogs | 9428  | HTTP API, query UI, ingest        |
| Fluent Bit   | 24224 | Forward input (Docker log driver) |
| Fluent Bit   | 2020  | HTTP server / self-metrics        |

## Forwarding Docker Container Logs

Add this `logging` block to any service whose logs should be shipped:

```yaml
logging:
  driver: fluentd
  options:
    fluentd-address: "localhost:24224"
    fluentd-async: "true"
    tag: "docker.<your-service-name>"
```

## Querying Logs

VictoriaLogs uses **LogsQL**. Open http://localhost:9428 and query:

```
# All logs
*

# Logs from a specific stream
{hostname="docker-host"}

# Filter by message content
{environment="production"} error

# Last 5 minutes, filter by container
{container_name="example-app"} _time:5m
```

## Environment Variables

| Variable      | Default       | Description                     |
|---------------|---------------|---------------------------------|
| `HOSTNAME`    | `docker-host` | Label added to every log record |
| `ENVIRONMENT` | `production`  | Label added to every log record |

Override them in a `.env` file or export before running `docker compose up`.

## Retention

Default retention is **4 weeks**. Change the `-retentionPeriod` flag in the
`victorialogs` service command, e.g. `30d`, `6w`, `12w`.

## Stopping

```bash
docker compose down          # keep volumes
docker compose down -v       # also delete stored log data
```