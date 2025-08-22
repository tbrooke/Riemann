#!/usr/bin/env python3
"""
System monitoring script for Riemann
Sends system metrics to Riemann server
"""

import time
import socket
import json
import psutil
import subprocess
import requests
from datetime import datetime

RIEMANN_HOST = 'localhost'
RIEMANN_PORT = 5555
HOSTNAME = socket.gethostname()

def send_to_riemann(service, metric, state='ok', description=''):
    """Send a metric to Riemann"""
    event = {
        'host': HOSTNAME,
        'service': service,
        'metric': metric,
        'state': state,
        'description': description,
        'time': int(time.time()),
        'ttl': 120
    }
    
    try:
        # Using UDP for simplicity - in production you might want TCP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Convert to simple text format (Riemann supports multiple protocols)
        message = f"{HOSTNAME} {service} {metric} {state}\n"
        sock.sendto(message.encode(), (RIEMANN_HOST, RIEMANN_PORT))
        sock.close()
        print(f"Sent: {service} = {metric}")
    except Exception as e:
        print(f"Error sending to Riemann: {e}")

def get_system_metrics():
    """Collect system metrics"""
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    send_to_riemann('cpu', cpu_percent / 100.0)
    
    # Memory usage
    memory = psutil.virtual_memory()
    send_to_riemann('memory', memory.percent / 100.0)
    send_to_riemann('memory available', memory.available)
    send_to_riemann('memory used', memory.used)
    
    # Disk usage
    for disk in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            disk_name = disk.mountpoint.replace('/', 'root') if disk.mountpoint == '/' else disk.mountpoint.replace('/', '_')
            send_to_riemann(f'disk {disk_name}', usage.percent / 100.0)
            send_to_riemann(f'disk {disk_name} free', usage.free)
            send_to_riemann(f'disk {disk_name} used', usage.used)
        except:
            continue
    
    # Load average
    load_avg = psutil.getloadavg()
    cpu_count = psutil.cpu_count()
    send_to_riemann('load', load_avg[0] / cpu_count)  # 1-minute load per core
    send_to_riemann('load 5min', load_avg[1] / cpu_count)
    send_to_riemann('load 15min', load_avg[2] / cpu_count)
    
    # Network IO
    net_io = psutil.net_io_counters()
    send_to_riemann('network bytes sent', net_io.bytes_sent)
    send_to_riemann('network bytes recv', net_io.bytes_recv)

def get_docker_metrics():
    """Monitor Docker containers"""
    try:
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        container_name = parts[0]
                        status = parts[1]
                        
                        # Send container status
                        state = 'ok' if 'Up' in status else 'down'
                        send_to_riemann(f'docker {container_name}', 1 if state == 'ok' else 0, state)
                        
                        # Get container stats if running
                        if state == 'ok':
                            try:
                                stats_result = subprocess.run(
                                    ['docker', 'stats', '--no-stream', '--format', 
                                     'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}', container_name],
                                    capture_output=True, text=True
                                )
                                if stats_result.returncode == 0:
                                    stats_lines = stats_result.stdout.strip().split('\n')[1:]
                                    for stats_line in stats_lines:
                                        if stats_line.strip():
                                            stats_parts = stats_line.split('\t')
                                            if len(stats_parts) >= 3:
                                                cpu_str = stats_parts[1].replace('%', '')
                                                try:
                                                    cpu_usage = float(cpu_str) / 100.0
                                                    send_to_riemann(f'docker {container_name} cpu', cpu_usage)
                                                except:
                                                    pass
                            except:
                                pass
    except Exception as e:
        print(f"Error monitoring Docker: {e}")

def get_postgres_metrics():
    """Monitor PostgreSQL"""
    try:
        # Check if PostgreSQL is running
        result = subprocess.run(['pg_isready', '-h', 'localhost'], 
                              capture_output=True)
        
        if result.returncode == 0:
            send_to_riemann('postgres status', 1, 'ok')
            
            # Get connection count (requires psql access)
            try:
                conn_result = subprocess.run([
                    'psql', '-h', 'localhost', '-U', 'postgres', '-d', 'postgres',
                    '-t', '-c', 'SELECT count(*) FROM pg_stat_activity;'
                ], capture_output=True, text=True)
                
                if conn_result.returncode == 0:
                    conn_count = int(conn_result.stdout.strip())
                    send_to_riemann('postgres connections', conn_count)
            except:
                pass
        else:
            send_to_riemann('postgres status', 0, 'down')
            
    except Exception as e:
        print(f"Error monitoring PostgreSQL: {e}")

def get_alfresco_metrics():
    """Monitor Alfresco"""
    try:
        # Check Alfresco health endpoint
        start_time = time.time()
        response = requests.get('http://localhost:8080/alfresco/api/-default-/public/alfresco/versions/1/nodes/-root-', 
                               auth=('admin', 'admin'), timeout=10)
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        if response.status_code == 200:
            send_to_riemann('alfresco status', 1, 'ok')
            send_to_riemann('alfresco response-time', response_time)
        else:
            send_to_riemann('alfresco status', 0, 'down')
            
    except Exception as e:
        print(f"Error monitoring Alfresco: {e}")
        send_to_riemann('alfresco status', 0, 'down')

def main():
    """Main monitoring loop"""
    print(f"Starting system monitor for {HOSTNAME}")
    print(f"Sending metrics to Riemann at {RIEMANN_HOST}:{RIEMANN_PORT}")
    
    while True:
        try:
            print(f"\n--- Collecting metrics at {datetime.now()} ---")
            
            get_system_metrics()
            get_docker_metrics()
            get_postgres_metrics()
            get_alfresco_metrics()
            
            print("Metrics collection complete")
            time.sleep(30)  # Collect metrics every 30 seconds
            
        except KeyboardInterrupt:
            print("\nShutting down monitor...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
