#!/bin/bash
# Complete Riemann monitoring stack startup

echo "=== Starting Complete Riemann Monitoring Stack ==="

cd /home/tmb/riemann

# Stop any existing monitoring
echo "Stopping existing services..."
docker-compose down 2>/dev/null
pkill -f riemann-health 2>/dev/null
pkill -f system-monitor.py 2>/dev/null
pkill -f graphrag-monitor.py 2>/dev/null

# Start Docker services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 15

# Check service status
echo "Checking service status:"
docker-compose ps

# Start riemann-health
echo "Starting riemann-health..."
riemann-health --host localhost --interval 10 > /dev/null 2>&1 &
HEALTH_PID=$!
echo "riemann-health started with PID: $HEALTH_PID"

# Start system monitor
echo "Starting system monitor..."
python3 scripts/system-monitor.py > system-monitor.log 2>&1 &
SYSTEM_PID=$!
echo "system-monitor started with PID: $SYSTEM_PID"

# Start GraphRAG monitor
# Start metrics senderecho "Starting metrics sender..."./scripts/send-metrics.sh > metrics-sender.log 2>&1 &METRICS_PID=$!echo "metrics-sender started with PID: "
echo "Starting GraphRAG monitor..."
python3 scripts/graphrag-monitor.py > graphrag-monitor.log 2>&1 &
GRAPHRAG_PID=$!
METRICS_PID=
echo "graphrag-monitor started with PID: $GRAPHRAG_PID"

# Save PIDs for easy stopping
cat > monitor-pids.txt << EOL
HEALTH_PID=$HEALTH_PID
SYSTEM_PID=$SYSTEM_PID  
GRAPHRAG_PID=$GRAPHRAG_PID
METRICS_PID=
EOL

echo ""
echo "=== Riemann Monitoring Stack Started ==="
echo "Services:"
echo "  Riemann Server:    http://localhost:5555 (TCP/UDP)"
echo "  Riemann WebSocket: http://localhost:5556"
echo "  Riemann REPL:      telnet localhost 5557"
echo "  Grafana:           http://monitor.trustblocks.com/ (admin/riemann123)"
echo "  InfluxDB:          http://localhost:8086"
echo ""
echo "Monitoring agents:"
echo "  riemann-health:    PID $HEALTH_PID"
echo "  system-monitor:    PID $SYSTEM_PID"  
echo "  graphrag-monitor:  PID $GRAPHRAG_PID"
echo ""
echo "Logs:"
echo "  Docker services:   docker-compose logs -f"
echo "  System monitor:    tail -f system-monitor.log"
echo "  GraphRAG monitor:  tail -f graphrag-monitor.log"
echo ""
echo "To stop all monitoring:"
echo "  ./stop-monitoring.sh"
