# Trust Server Monitoring System Manual

## Overview
This document provides a comprehensive guide to the monitoring system implemented on the trust server (trust.tmb), including Riemann event processing, InfluxDB time-series storage, and Grafana visualization dashboards.

## System Architecture

### Components
- **Riemann**: Event processing engine (Clojure-based) running on port 5555
- **InfluxDB**: Time-series database for metrics storage (Docker container: `riemann-influxdb`)
- **Grafana**: Visualization dashboard platform running on port 3001
- **Python Monitoring Scripts**: Custom data collectors for system metrics

### Data Flow
```
Python Scripts → Riemann (5555) → InfluxDB (8086) → Grafana (3001)
```

## Current Monitoring Capabilities

### 1. System Monitoring (Simple System Monitor Dashboard)
**Dashboard ID**: `f37f23cc-1c7a-458b-8e12-951654ae3b7f`
**URL**: http://trust.tmb:3001/d/f37f23cc-1c7a-458b-8e12-951654ae3b7f/simple-system-monitor

**Metrics Tracked**:
- **CPU Usage**: Current percentage and historical trends
- **Memory Usage**: Current percentage utilization  
- **Root Disk Usage**: Current percentage and historical trends (7.5% as of last check)

**Panels**:
- CPU Usage (stat gauge)
- Memory Usage (stat gauge) 
- Root Disk Usage (stat gauge with thresholds: green <60%, yellow <80%, red ≥80%)
- CPU Usage Over Time (time series chart)
- Disk Usage Over Time (time series chart)

### 2. Backup Monitoring Dashboard
**Metrics Tracked**:
- `backup.count.total`: Total number of backups
- `backup.storage.total_mb`: Total storage used by backups in MB
- `backup.freshness.age_hours`: Age of most recent backup in hours
- `backup.health.score`: Overall backup system health score

**Dashboard Issues Fixed**: Updated queries from underscore format (`backup_count_total`) to dot notation (`backup.count.total`) to match actual InfluxDB measurement names.

## System Locations and Configuration

### File Locations
```
/home/tmb/riemann/                    # Main Riemann directory
├── riemann.config                    # Riemann configuration file
├── venv/                            # Python virtual environment
├── scripts/
│   └── disk-monitor-fixed.py       # Disk monitoring script
├── disk-monitor.log                 # Disk monitoring logs
└── riemann.jar                     # Riemann executable
```

### Docker Containers
- **riemann-influxdb**: InfluxDB 1.8 container (127.0.0.1:8086→8086/tcp)

### Service Ports
- **Riemann**: 5555 (TCP/UDP event ingestion)
- **InfluxDB**: 8086 (HTTP API)
- **Grafana**: 3001 (Web interface)

## Authentication & Access

### Grafana Access
- **URL**: http://trust.tmb:3001 or http://127.0.0.1:3001
- **Username**: admin
- **Password**: riemann123

### InfluxDB Database
- **Database Name**: riemann
- **Access**: Via Docker exec or HTTP API on port 8086

## Monitoring Scripts

### Disk Monitor Script
**Location**: `/home/tmb/riemann/scripts/disk-monitor-fixed.py`
**Python Environment**: `/home/tmb/riemann/venv/bin/python`

**Features**:
- Monitors root filesystem (`/`) usage
- Sends metrics every 60 seconds
- Uses riemann-client library for reliable event transmission
- Includes state thresholds: ok (<80%), warning (80-90%), critical (>90%)

**Metrics Sent**:
- `disk.root.usage.percent`: Usage percentage (0.0-1.0)
- `disk.root.free.gb`: Available space in GB

**Current Status**: Running and sending data successfully (7.5% usage, 800.6GB free)

## InfluxDB Measurements

### Available Measurements
```
backup.count.total           # Backup count metrics
backup.freshness.age_hours   # Backup age metrics  
backup.health.score          # Backup health metrics
backup.storage.total_mb      # Backup storage metrics
cpu                          # CPU usage metrics
disk.root.free.gb           # Disk free space metrics
disk.root.usage.percent     # Disk usage percentage metrics
load                         # System load metrics
memory                       # Memory usage metrics
```

### Legacy Measurements (Deprecated)
- `backup_count_total`, `backup_freshness_age_hours`, etc. (underscore format)

## Operational Procedures

### Starting/Stopping Services

#### Riemann
```bash
# Start Riemann
cd /home/tmb/riemann
java -jar riemann.jar riemann.config

# Check if running
ps aux | grep riemann
```

#### Disk Monitor
```bash
# Start disk monitoring
cd /home/tmb/riemann
source venv/bin/activate
nohup python scripts/disk-monitor-fixed.py > disk-monitor.log 2>&1 &

# Check status
ps aux | grep disk-monitor
tail -f disk-monitor.log
```

#### InfluxDB (Docker)
```bash
# Check container status
docker ps | grep influx

# Access InfluxDB CLI
docker exec riemann-influxdb influx -database riemann

# Query data
docker exec riemann-influxdb influx -execute 'SELECT * FROM "disk.root.usage.percent" ORDER BY time DESC LIMIT 5' -database riemann
```

### Dashboard Management

#### Access Grafana API
```bash
# Get dashboard
curl -u admin:riemann123 'http://127.0.0.1:3001/api/dashboards/uid/f37f23cc-1c7a-458b-8e12-951654ae3b7f'

# Update dashboard
curl -X POST -H 'Content-Type: application/json' -u admin:riemann123 'http://127.0.0.1:3001/api/dashboards/db' -d @dashboard.json

# Search dashboards
curl -u admin:riemann123 'http://127.0.0.1:3001/api/search?query=system'
```

### Troubleshooting

#### Common Issues
1. **No data in dashboard**: Check if monitoring scripts are running and Riemann is processing events
2. **Grafana connection issues**: Verify InfluxDB container is running and accessible
3. **Dashboard query errors**: Ensure measurement names match InfluxDB (use dot notation)

#### Diagnostic Commands
```bash
# Check all running processes
ps aux | grep -E "(riemann|influx|grafana|disk-monitor)"

# Check InfluxDB measurements
docker exec riemann-influxdb influx -execute 'SHOW MEASUREMENTS' -database riemann

# Check recent disk data
docker exec riemann-influxdb influx -execute 'SELECT * FROM "disk.root.usage.percent" ORDER BY time DESC LIMIT 5' -database riemann

# Check Riemann connectivity
python3 -c 'import socket; s = socket.socket(); s.connect(("localhost", 5555)); print("Riemann OK"); s.close()'
```

## Dashboard Configurations

### Simple System Monitor Dashboard Structure
- **Grid Layout**: 24-unit width
- **Refresh Rate**: 5 seconds
- **Time Range**: Last 1 hour (configurable)
- **Panel Types**: Stat gauges and time series charts

### Panel Queries
- **CPU**: `SELECT last(value) * 100 FROM cpu WHERE host = 'trust'`
- **Memory**: `SELECT last(value) * 100 FROM memory WHERE host = 'trust'`
- **Disk**: `SELECT last(value) * 100 FROM "disk.root.usage.percent" WHERE host = 'trust'`

## Implementation History

### Recent Changes
1. **Dashboard Creation**: Built Simple System Monitor dashboard with CPU and memory tracking
2. **Backup Monitoring Fix**: Corrected measurement names in backup monitoring dashboard
3. **Disk Monitoring Addition**: Added comprehensive disk usage monitoring with both current stats and historical trends
4. **Script Optimization**: Upgraded disk monitoring script to use riemann-client library for reliable data transmission

### Current System Status
- ✅ **Riemann**: Running and processing events
- ✅ **InfluxDB**: Collecting and storing time-series data  
- ✅ **Grafana**: Displaying real-time dashboards
- ✅ **Disk Monitoring**: Active and reporting 7.5% usage
- ✅ **System Monitoring**: CPU, Memory, and Disk metrics all operational
- ✅ **Backup Monitoring**: Dashboard queries fixed and operational

## Future Enhancements

### Recommended Additions
1. **Network Monitoring**: Track bandwidth usage and connection metrics
2. **Service Monitoring**: Monitor specific services (Alfresco, nginx, etc.)
3. **Alerting**: Configure email/SMS notifications for critical thresholds
4. **Log Aggregation**: Centralized logging with ELK stack integration
5. **Performance Baselines**: Establish normal operating ranges for all metrics

### Scaling Considerations
- Consider Riemann clustering for high availability
- Implement InfluxDB retention policies for long-term storage management
- Add more granular disk monitoring for multiple mount points
- Implement monitoring for Docker containers individually

---

**Document Version**: 1.0  
**Last Updated**: 2025-09-05  
**System Status**: Operational  
**Contact**: tmb@trust for system administration