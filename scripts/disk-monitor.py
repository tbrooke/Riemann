#!/usr/bin/env python3
import os
import time
import socket
import shutil
import subprocess
import json

def send_to_riemann(service, value, state="ok", description="", tags=None):
    """Send event to Riemann server"""
    if tags is None:
        tags = []
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_TCP)
        sock.connect(('localhost', 5555))
        
        event = {
            'service': service,
            'metric': value,
            'state': state,
            'description': description,
            'tags': tags,
            'host': 'trust-server',
            'time': int(time.time())
        }
        
        # Simple JSON protocol (Riemann can accept this)
        message = json.dumps(event) + "\n"
        sock.send(message.encode('utf-8'))
        sock.close()
        
        print(f"Sent to Riemann: {service} = {value} ({state})")
        
    except Exception as e:
        print(f"Error sending to Riemann: {e}")

def get_disk_usage():
    """Get disk usage information"""
    try:
        # Get disk usage for root filesystem
        total, used, free = shutil.disk_usage('/')
        
        # Convert to GB
        total_gb = total / (1024**3)
        used_gb = used / (1024**3)
        free_gb = free / (1024**3)
        usage_percent = used / total if total > 0 else 0
        
        # Determine state based on usage
        if usage_percent >= 0.90:
            state = "critical"
        elif usage_percent >= 0.80:
            state = "warning"
        else:
            state = "ok"
        
        # Send metrics to Riemann
        send_to_riemann('disk.root.usage.percent', usage_percent, state, 
                       f'Root disk {usage_percent*100:.1f}% used', ['disk', 'usage'])
        
        send_to_riemann('disk.root.free.gb', free_gb, 'ok',
                       f'{free_gb:.1f}GB free space', ['disk', 'free'])
        
        send_to_riemann('disk.root.used.gb', used_gb, 'ok', 
                       f'{used_gb:.1f}GB used space', ['disk', 'used'])
        
        send_to_riemann('disk.root.total.gb', total_gb, 'ok',
                       f'{total_gb:.1f}GB total space', ['disk', 'total'])
        
        print(f"Disk usage: {usage_percent*100:.1f}% ({used_gb:.1f}GB / {total_gb:.1f}GB)")
        
    except Exception as e:
        print(f"Error getting disk usage: {e}")
        send_to_riemann('disk.root.error', 1, 'critical', str(e), ['disk', 'error'])

if __name__ == '__main__':
    print("Starting disk monitoring...")
    while True:
        get_disk_usage()
        time.sleep(60)  # Check every minute
