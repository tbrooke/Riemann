# Riemann Monitoring Setup for Trust Server

## Overview
Complete Riemann-based monitoring solution for the Trust server infrastructure including:
- Alfresco document management
- PostgreSQL database
- Docker containers
- GraphRAG/LLM services
- System resources (CPU, memory, disk, network)

## Services

### Core Monitoring Stack
- **Riemann Server**: Event processing and alerting (port 5555)
- **Riemann Dashboard**: Web interface (port 4567)
- **InfluxDB**: Time-series database for metrics storage (port 8086)
- **Grafana**: Advanced dashboarding and visualization (port 3001)

### Monitoring Agents
- **System Monitor**: Python script collecting system metrics every 30 seconds
- **Docker Monitor**: Container status and resource usage
- **PostgreSQL Monitor**: Connection count and availability
- **Alfresco Monitor**: Response time and availability

## Quick Start

1. **Start the monitoring stack**:
   ```bash
   cd ~/riemann
   ./start-riemann.sh
   ```

2. **Access dashboards**:
   - Riemann Dashboard: http://trustblocks.com/riemann/
   - Grafana: http://monitor.trustblocks.com/ (admin/riemann123)

3. **Stop the system**:
   ```bash
   docker-compose down
   kill $(cat monitor.pid)  # Stop system monitor
   ```

## Configuration Files

- `docker-compose.yml`: Container orchestration
- `riemann.config`: Main Riemann configuration (Clojure)
- `scripts/system-monitor.py`: System metrics collection
- `start-riemann.sh`: Startup script

## Monitored Metrics

### System Metrics
- CPU usage (%)
- Memory usage (%)
- Disk usage (%) per partition
- Load average (per core)
- Network I/O (bytes)

### Service Metrics
- **PostgreSQL**: Connection count, availability
- **Alfresco**: Response time, availability
- **Docker Containers**: Status, CPU usage
- **LLM Services**: Memory usage, response times

### Alerting
- High CPU usage (>80%)
- High memory usage (>85%)
- High disk usage (>90%)
- High load average (>2.0 per core)
- Service downtime
- Slow response times

## Ports Used
- 5555: Riemann TCP/UDP
- 5556: Riemann WebSockets
- 5557: Riemann REPL
- 4567: Riemann Dashboard
- 3001: Grafana
- 8086: InfluxDB

## Logs
- Riemann logs: `logs/riemann.log`
- Container logs: `docker-compose logs`
- Monitor output: Console when running start script

## Extending Monitoring

### Add New Metrics
Edit `scripts/system-monitor.py` and add new functions to collect additional metrics.

### Add New Alerts
Edit `riemann.config` and add new stream processing rules.

### Custom Dashboards
Access Grafana at http://monitor.trustblocks.com/ to create custom dashboards.

## Troubleshooting

1. **Check service status**:
   ```bash
   docker-compose ps
   ```

2. **View logs**:
   ```bash
   docker-compose logs -f riemann
   ```

3. **Test Riemann connection**:
   ```bash
   telnet localhost 5555
   ```

4. **Restart services**:
   ```bash
   docker-compose restart
   ```

## Architecture

```
System Monitor (Python) → Riemann Server (Clojure) → InfluxDB
                              ↓
                         Riemann Dashboard
                              ↓
                           Grafana
```

The system uses Riemann as the central event processing engine, written in Clojure, which provides powerful stream processing capabilities for real-time monitoring and alerting.
