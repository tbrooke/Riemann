#!/usr/bin/env python3
import socket
import time

def send_test_event():
    try:
        # Create a test event
        message = "test-host cpu 0.75 ok\n"
        
        # Send via UDP to Riemann
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message.encode(), ('localhost', 5555))
        sock.close()
        
        print(f"Sent test event: {message.strip()}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Riemann connection...")
    if send_test_event():
        print("Success! Check Riemann logs for the event.")
    else:
        print("Failed to send test event.")
