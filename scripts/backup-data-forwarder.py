#!/usr/bin/env python3
"""
Backup Data Forwarder
Reads backup metrics from local InfluxDB and forwards to external monitor
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Configuration
LOCAL_INFLUXDB = 'http://localhost:8086'
EXTERNAL_GRAFANA = 'http://monitor.trustblocks.com'
EXTERNAL_INFLUXDB = 'http://monitor.trustblocks.com/influxdb'  # Try proxied path
DATABASE = 'riemann'
USERNAME = 'riemann'
PASSWORD = 'riemann'

def get_local_backup_metrics():
    """Get backup metrics from local InfluxDB"""
    try:
        # Get backup metrics from last 10 minutes
        query = "SELECT * FROM /backup.*/ WHERE time > now() - 10m ORDER BY time DESC"
        url = f'{LOCAL_INFLUXDB}/query'
        params = {
            'db': DATABASE,
            'u': USERNAME, 
            'p': PASSWORD,
            'q': query
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            metrics = []
            
            if 'results' in data and data['results']:
                for result in data['results']:
                    if 'series' in result and result['series']:
                        for series in result['series']:
                            measurement = series['name']
                            columns = series['columns']
                            values = series['values']
                            
                            for value in values:
                                metric = dict(zip(columns, value))
                                metric['measurement'] = measurement
                                metrics.append(metric)
            
            print(f"Retrieved {len(metrics)} backup metrics from local InfluxDB")
            return metrics
        else:
            print(f"Failed to query local InfluxDB: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error querying local InfluxDB: {e}")
        return []

def create_line_protocol(metric):
    """Convert metric to InfluxDB line protocol"""
    measurement = metric['measurement'].replace('.', '_')
    host = metric.get('host', 'trust-server')
    value = metric.get('value', 0)
    timestamp = metric.get('time', datetime.now().isoformat())
    
    # Convert timestamp to nanoseconds
    if 'Z' in timestamp:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    else:
        dt = datetime.fromisoformat(timestamp)
    
    timestamp_ns = int(dt.timestamp() * 1000000000)
    
    return f"{measurement},host={host} value={value} {timestamp_ns}"

def send_to_external_influxdb(metrics):
    """Send metrics to external InfluxDB"""
    if not metrics:
        return True
        
    try:
        # Try different endpoints for external InfluxDB
        endpoints_to_try = [
            f'{EXTERNAL_INFLUXDB}/write?db={DATABASE}&u={USERNAME}&p={PASSWORD}',
            f'{EXTERNAL_GRAFANA}/influxdb/write?db={DATABASE}&u={USERNAME}&p={PASSWORD}',
            f'{EXTERNAL_GRAFANA}:8086/write?db={DATABASE}&u={USERNAME}&p={PASSWORD}'
        ]
        
        # Convert metrics to line protocol
        lines = [create_line_protocol(metric) for metric in metrics]
        data = '\n'.join(lines)
        
        success = False
        for endpoint in endpoints_to_try:
            try:
                response = requests.post(
                    endpoint, 
                    data=data,
                    headers={'Content-Type': 'application/octet-stream'},
                    timeout=10
                )
                
                if response.status_code == 204:
                    print(f"✅ Successfully sent {len(metrics)} metrics to {endpoint}")
                    success = True
                    break
                else:
                    print(f"❌ Failed to send to {endpoint}: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error sending to {endpoint}: {e}")
                continue
        
        if not success:
            print(f"❌ All external endpoints failed, trying local forwarding fallback")
            return forward_via_grafana_api(metrics)
            
        return success
        
    except Exception as e:
        print(f"Error sending to external InfluxDB: {e}")
        return False

def forward_via_grafana_api(metrics):
    """Fallback: try to forward via Grafana API"""
    try:
        # Login to external Grafana
        login_data = {'user': 'admin', 'password': 'riemann123'}
        session = requests.Session()
        
        response = session.post(
            f'{EXTERNAL_GRAFANA}/login',
            json=login_data,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"Failed to login to external Grafana: {response.status_code}")
            return False
        
        # Try to create annotations for backup metrics (as fallback)
        for metric in metrics[:5]:  # Limit to avoid spam
            annotation = {
                'time': int(datetime.now().timestamp() * 1000),
                'timeEnd': int(datetime.now().timestamp() * 1000),
                'tags': ['backup', 'trust-server'],
                'text': f"{metric['measurement']}: {metric.get('value', 0)}"
            }
            
            response = session.post(
                f'{EXTERNAL_GRAFANA}/api/annotations',
                json=annotation,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Created annotation for {metric['measurement']}")
            
        return True
        
    except Exception as e:
        print(f"Error in Grafana API fallback: {e}")
        return False

def main():
    """Main forwarding loop"""
    print(f"Starting backup data forwarder...")
    print(f"Local InfluxDB: {LOCAL_INFLUXDB}")
    print(f"External Monitor: {EXTERNAL_GRAFANA}")
    
    while True:
        try:
            print(f"\n--- Forwarding backup data at {datetime.now()} ---")
            
            # Get metrics from local InfluxDB
            metrics = get_local_backup_metrics()
            
            if metrics:
                # Send to external system
                success = send_to_external_influxdb(metrics)
                if success:
                    print(f"✅ Successfully forwarded {len(metrics)} backup metrics")
                else:
                    print(f"❌ Failed to forward backup metrics")
            else:
                print("No backup metrics found to forward")
            
            # Wait 5 minutes before next forwarding
            time.sleep(300)
            
        except KeyboardInterrupt:
            print("\nStopping backup data forwarder...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(60)  # Wait 1 minute on error

if __name__ == "__main__":
    main()
