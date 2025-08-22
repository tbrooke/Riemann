#!/bin/bash
# Simple script to send system metrics to InfluxDB

while true; do
    HOST=\$(hostname)
    TIMESTAMP=\$(date +%s)000000000
    
    # Get system metrics using Python
    METRICS=\$(python3 -c \"
import psutil
cpu = psutil.cpu_percent(interval=1) / 100.0
mem = psutil.virtual_memory().percent / 100.0
load = psutil.getloadavg()[0] / psutil.cpu_count()
print(f'{cpu} {mem} {load}')
\")
    
    read CPU MEM LOAD <<< \$METRICS
    
    # Send to InfluxDB
    curl -s -XPOST 'http://localhost:8086/write?db=riemann&u=riemann&p=riemann' --data-binary \"cpu,host=\$HOST value=\$CPU \$TIMESTAMP\"
    curl -s -XPOST 'http://localhost:8086/write?db=riemann&u=riemann&p=riemann' --data-binary \"memory,host=\$HOST value=\$MEM \$TIMESTAMP\"
    curl -s -XPOST 'http://localhost:8086/write?db=riemann&u=riemann&p=riemann' --data-binary \"load,host=\$HOST value=\$LOAD \$TIMESTAMP\"
    
    echo \"\$(date): Sent CPU=\$CPU, Memory=\$MEM, Load=\$LOAD\"
    
    sleep 10
done
