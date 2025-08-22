#!/usr/bin/env python3
import psutil
import time
import requests

while True:
    try:
        # Get current metrics
        cpu = psutil.cpu_percent(interval=1) / 100.0
        memory = psutil.virtual_memory().percent / 100.0
        load = psutil.getloadavg()[0] / psutil.cpu_count()
        timestamp = int(time.time() * 1000000000)
        host = 'trust'

        # Send to InfluxDB
        data = f'cpu,host={host} value={cpu} {timestamp}\nmemory,host={host} value={memory} {timestamp}\nload,host={host} value={load} {timestamp}'
        response = requests.post('http://localhost:8086/write?db=riemann&u=riemann&p=riemann', data=data)
        
        print(f'{time.strftime("%H:%M:%S")} - CPU: {cpu:.3f}, Memory: {memory:.3f}, Load: {load:.3f} - Status: {response.status_code}')
        
    except Exception as e:
        print(f'Error: {e}')
    
    time.sleep(10)