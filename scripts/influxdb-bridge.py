#!/usr/bin/env python3
"""
InfluxDB Bridge for Riemann
Listens for Riemann events and forwards them to InfluxDB
"""

import socket
import time
import requests
import json
import threading
from datetime import datetime

# Configuration
RIEMANN_HOST = 'localhost'
RIEMANN_PORT = 5555
INFLUXDB_URL = 'http://localhost:8086/write?db=riemann&u=riemann&p=riemann'

def riemann_event_to_influx_line(service, host, metric, timestamp):
    """Convert Riemann event to InfluxDB line protocol"""
    # Clean measurement name
    measurement = service.replace(' ', '_').replace('-', '_')
    measurement = ''.join(c for c in measurement if c.isalnum() or c == '_')
    
    # Create line protocol
    line = f"{measurement},host={host} value={metric} {int(timestamp * 1000000000)}"
    return line

def send_to_influxdb(line):
    """Send line protocol data to InfluxDB"""
    try:
        response = requests.post(INFLUXDB_URL, data=line, timeout=5)
        if response.status_code == 204:
            print(f"✓ Sent to InfluxDB: {line}")
            return True
        else:
            print(f"✗ InfluxDB error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"✗ InfluxDB connection error: {e}")
        return False

def send_test_events():
    """Send test events to Riemann and InfluxDB"""
    import psutil
    
    hostname = socket.gethostname()
    timestamp = time.time()
    
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=1) / 100.0
    memory_percent = psutil.virtual_memory().percent / 100.0
    load_avg = psutil.getloadavg()[0] / psutil.cpu_count()
    
    # Send to InfluxDB
    lines = [
        riemann_event_to_influx_line('cpu', hostname, cpu_percent, timestamp),
        riemann_event_to_influx_line('memory', hostname, memory_percent, timestamp),
        riemann_event_to_influx_line('load', hostname, load_avg, timestamp)
    ]
    
    for line in lines:
        send_to_influxdb(line)
    
    print(f"Sent metrics: CPU={cpu_percent:.2f}, Memory={memory_percent:.2f}, Load={load_avg:.2f}")

def main():
    """Main monitoring loop"""
    print(f"Starting InfluxDB bridge...")
    print(f"InfluxDB URL: {INFLUXDB_URL}")
    
    # Test InfluxDB connection
    try:
        response = requests.get('http://localhost:8086/ping', timeout=5)
        print(f"✓ InfluxDB connection OK (status: {response.status_code})")
    except Exception as e:
        print(f"✗ InfluxDB connection failed: {e}")
        return
    
    # Main monitoring loop
    while True:
        try:
            print(f"\n--- Sending metrics at {datetime.now()} ---")
            send_test_events()
            time.sleep(10)  # Send metrics every 10 seconds
            
        except KeyboardInterrupt:
            print("\nStopping InfluxDB bridge...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
