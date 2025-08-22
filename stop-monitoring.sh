#!/bin/bash
# Stop all Riemann monitoring

echo "Stopping Riemann monitoring stack..."

cd /home/tmb/riemann

# Stop monitoring agents
if [ -f monitor-pids.txt ]; then
    source monitor-pids.txt
    echo "Stopping monitoring agents..."
    kill $HEALTH_PID 2>/dev/null && echo "  riemann-health stopped"
    kill $SYSTEM_PID 2>/dev/null && echo "  system-monitor stopped"
    kill $GRAPHRAG_PID 2>/dev/null && echo "  graphrag-monitor stopped"
    rm monitor-pids.txt
fi

# Stop any remaining processes
pkill -f riemann-health 2>/dev/null
pkill -f system-monitor.py 2>/dev/null  
pkill -f graphrag-monitor.py 2>/dev/null

# Stop Docker services
echo "Stopping Docker services..."
docker-compose down

echo "All monitoring stopped."
