#!/home/tmb/riemann/venv/bin/python
import os
import time
import shutil
import riemann_client.client
import riemann_client.transport

def get_disk_usage():
    """Get disk usage information and send to Riemann"""
    try:
        # Create Riemann client
        with riemann_client.client.Client(
            riemann_client.transport.TCPTransport('localhost', 5555)
        ) as client:
            
            # Get disk usage for root filesystem
            total, used, free = shutil.disk_usage('/')
            
            # Convert to percentages and GB
            usage_percent = (used / total) if total > 0 else 0
            free_gb = free / (1024**3)
            used_gb = used / (1024**3)
            total_gb = total / (1024**3)
            
            # Determine state based on usage
            if usage_percent >= 0.90:
                state = "critical"
            elif usage_percent >= 0.80:
                state = "warning"
            else:
                state = "ok"
            
            # Send disk usage percentage event
            client.event(
                service='disk.root.usage.percent',
                metric_f=usage_percent,
                state=state,
                description=f'Root disk {usage_percent*100:.1f}% used',
                tags=['disk', 'usage'],
                host='trust'
            )
            
            # Send additional disk metrics
            client.event(
                service='disk.root.free.gb',
                metric_f=free_gb,
                state='ok',
                description=f'{free_gb:.1f}GB free space',
                tags=['disk', 'free'],
                host='trust'
            )
            
            print(f"Sent disk metrics: {usage_percent*100:.1f}% used ({used_gb:.1f}GB / {total_gb:.1f}GB)")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    print("Starting improved disk monitoring...")
    while True:
        get_disk_usage()
        time.sleep(60)  # Check every minute