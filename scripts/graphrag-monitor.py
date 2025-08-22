#!/usr/bin/env python3
"""
GraphRAG and LLM services monitoring for Riemann
Monitors Ollama, GraphRAG backend, and related services
"""

import time
import socket
import psutil
import requests
import subprocess
import json
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
        # For now, just log - would use riemann-client in production
        print(f"RIEMANN: {service} = {metric} ({state})")
    except Exception as e:
        print(f"Error sending to Riemann: {e}")

def monitor_ollama():
    """Monitor Ollama service"""
    try:
        # Check if Ollama is responding
        start_time = time.time()
        response = requests.get('http://localhost:11434/api/version', timeout=5)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            send_to_riemann('ollama status', 1, 'ok')
            send_to_riemann('ollama response-time', response_time)
            
            version_info = response.json()
            print(f"Ollama version: {version_info.get('version', 'unknown')}")
            
            # Check Ollama model status
            try:
                models_response = requests.get('http://localhost:11434/api/tags', timeout=5)
                if models_response.status_code == 200:
                    models = models_response.json().get('models', [])
                    send_to_riemann('ollama models-count', len(models))
                    print(f"Ollama models available: {len(models)}")
            except:
                pass
                
        else:
            send_to_riemann('ollama status', 0, 'critical')
            
    except Exception as e:
        print(f"Error monitoring Ollama: {e}")
        send_to_riemann('ollama status', 0, 'critical')

def monitor_graphrag():
    """Monitor GraphRAG backend service"""
    try:
        # Check GraphRAG API health
        start_time = time.time()
        response = requests.get('http://localhost:8000/api/health', timeout=10)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            send_to_riemann('graphrag status', 1, 'ok')
            send_to_riemann('graphrag response-time', response_time)
            print("GraphRAG backend: OK")
        else:
            send_to_riemann('graphrag status', 0, 'warning')
            
    except Exception as e:
        print(f"Error monitoring GraphRAG: {e}")
        send_to_riemann('graphrag status', 0, 'critical')

def monitor_containers():
    """Monitor specific containers for LLM services"""
    try:
        # Get container stats for GraphRAG containers
        result = subprocess.run([
            'docker', 'stats', '--no-stream', '--format', 
            'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        name = parts[0]
                        if 'graphrag' in name.lower() or 'riemann' in name.lower():
                            try:
                                cpu_str = parts[1].replace('%', '')
                                mem_str = parts[3].replace('%', '')
                                
                                cpu_usage = float(cpu_str) / 100.0
                                mem_usage = float(mem_str) / 100.0
                                
                                send_to_riemann(f'container {name} cpu', cpu_usage)
                                send_to_riemann(f'container {name} memory', mem_usage)
                                
                                # Extract memory in bytes from MemUsage (e.g., "1.5GiB / 8GiB")
                                mem_parts = parts[2].split(' / ')
                                if len(mem_parts) >= 1:
                                    used_mem = mem_parts[0].strip()
                                    if 'GiB' in used_mem:
                                        mem_bytes = float(used_mem.replace('GiB', '')) * 1024 * 1024 * 1024
                                        send_to_riemann(f'container {name} memory-bytes', mem_bytes)
                                        
                            except Exception as e:
                                print(f"Error parsing container stats for {name}: {e}")
                                
    except Exception as e:
        print(f"Error monitoring containers: {e}")

def monitor_gpu():
    """Monitor GPU usage if available"""
    try:
        # Check if nvidia-smi is available
        result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu', 
                               '--format=csv,noheader,nounits'], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                parts = line.split(', ')
                if len(parts) >= 4:
                    gpu_util = float(parts[0]) / 100.0
                    mem_used = float(parts[1]) * 1024 * 1024  # Convert MB to bytes
                    mem_total = float(parts[2]) * 1024 * 1024
                    temp = float(parts[3])
                    
                    send_to_riemann(f'gpu {i} utilization', gpu_util)
                    send_to_riemann(f'gpu {i} memory-used', mem_used)
                    send_to_riemann(f'gpu {i} memory-total', mem_total)
                    send_to_riemann(f'gpu {i} temperature', temp)
                    
                    mem_percent = (mem_used / mem_total) if mem_total > 0 else 0
                    send_to_riemann(f'gpu {i} memory-percent', mem_percent)
                    
    except FileNotFoundError:
        # No nvidia-smi available, skip GPU monitoring
        pass
    except Exception as e:
        print(f"Error monitoring GPU: {e}")

def main():
    """Main monitoring loop"""
    print(f"Starting GraphRAG/LLM monitor for {HOSTNAME}")
    
    while True:
        try:
            print(f"\n--- GraphRAG/LLM metrics at {datetime.now()} ---")
            
            monitor_ollama()
            monitor_graphrag()
            monitor_containers()
            monitor_gpu()
            
            print("GraphRAG/LLM metrics collection complete")
            time.sleep(30)  # Check every 30 seconds
            
        except KeyboardInterrupt:
            print("\nShutting down GraphRAG/LLM monitor...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
