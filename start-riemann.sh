#!/bin/bash
# Riemann monitoring stack startup script

echo "Starting Riemann monitoring stack..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    exit 1
fi

# Create network if it doesn't exist
docker network create riemann-net 2>/dev/null || true

# Start the monitoring stack
cd /home/tmb/riemann
docker-compose up -d

echo "Waiting for services to start..."
sleep 10

# Check service status
echo "Checking service status:"
docker-compose ps

echo ""
echo "Services available at:"
echo "  Riemann Dashboard: http://localhost:4567"
echo "  Grafana:          http://localhost:3001 (admin/riemann123)"
echo "  InfluxDB:         http://localhost:8086"
echo ""
echo "Starting system monitor..."
python3 scripts/system-monitor.py &
MONITOR_PID=$!
echo "System monitor started with PID: $MONITOR_PID"
echo "Monitor PID saved to monitor.pid"
echo $MONITOR_PID > monitor.pid

echo ""
echo "Riemann monitoring stack is ready!"
echo "Use 'docker-compose logs -f' to view logs"
echo "Use 'kill $MONITOR_PID' or 'kill \$(cat monitor.pid)' to stop the monitor"
