#!/usr/bin/env python3
"""
UDPRIP - Virtual Topology Router Implementation
Implements a distance vector routing protocol over UDP sockets
"""

import socket
import threading
import time
import json
import sys
import argparse
from typing import Dict, Set, Optional, Tuple
import ipaddress
import os

class Router:
    def __init__(self, router_ip: str, period: float, startup_file: Optional[str] = None):
        self.router_ip = router_ip
        self.period = period
        self.port = 55151  # Fixed port as per specification
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        
        # Bind to the router's IP address
        try:
            self.socket.bind((router_ip, self.port))
            print(f"Router bound to {router_ip}:{self.port}")
        except OSError as e:
            print(f"Error binding to {router_ip}:{self.port}: {e}")
            print("Make sure the IP address exists on your system")
            sys.exit(1)
        
        # Routing data structures
        self.neighbors: Dict[str, int] = {}  # neighbor_ip -> weight
        self.routing_table: Dict[str, Tuple[int, str]] = {}  # dest_ip -> (distance, next_hop)
        self.last_update_received: Dict[str, float] = {}  # neighbor_ip -> timestamp
        
        # Initialize routing table with self
        self.routing_table[router_ip] = (0, router_ip)
        
        # Threading control
        self.running = True
        self.lock = threading.Lock()
        
        # Start background threads
        self.listen_thread = threading.Thread(target=self._listen_for_messages, daemon=True)
        self.listen_thread.start()
        
        self.update_thread = threading.Thread(target=self._periodic_updates, daemon=True)
        self.update_thread.start()
        
        self.timeout_thread = threading.Thread(target=self._check_neighbor_timeouts, daemon=True)
        self.timeout_thread.start()
        
        # Process startup file if provided
        if startup_file:
            self._process_startup_file(startup_file)
        
        print(f"Router {router_ip} started successfully (period={period}s)")
    
    def _process_startup_file(self, filename: str):
        """Process startup commands from file"""
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self._process_command(line.split())
        except FileNotFoundError:
            print(f"Startup file {filename} not found")
        except Exception as e:
            print(f"Error processing startup file: {e}")
    
    def add_link(self, neighbor_ip: str, weight: int):
        """Add a virtual link to a neighbor"""
        with self.lock:
            self.neighbors[neighbor_ip] = weight
            print(f"Added link to {neighbor_ip} with weight {weight}")
            
            # Update routing table if this provides a better route
            if neighbor_ip not in self.routing_table or self.routing_table[neighbor_ip][0] > weight:
                self.routing_table[neighbor_ip] = (weight, neighbor_ip)
            
            # Send immediate update to new neighbor
            # self._send_update_message(neighbor_ip)
            # let periodic updates handle this instead
    
    def remove_link(self, neighbor_ip: str):
        """Remove a virtual link to a neighbor"""
        with self.lock:
            if neighbor_ip in self.neighbors:
                del self.neighbors[neighbor_ip]
                if neighbor_ip in self.last_update_received:
                    del self.last_update_received[neighbor_ip]
                print(f"Removed link to {neighbor_ip}")
                
                # Remove routes that go through this neighbor
                routes_to_remove = []
                for dest, (dist, next_hop) in self.routing_table.items():
                    if next_hop == neighbor_ip and dest != self.router_ip:
                        routes_to_remove.append(dest)
                
                for dest in routes_to_remove:
                    del self.routing_table[dest]
                    print(f"Removed route to {dest} (was through {neighbor_ip})")
            else:
                print(f"No link to {neighbor_ip} exists")
    
    def send_trace(self, destination_ip: str):
        """Send a trace message to destination"""
        trace_message = {
            'type': 'trace',
            'source': self.router_ip,
            'destination': destination_ip,
            'routers': [self.router_ip]
        }
        
        self._forward_message(trace_message)
    
    def _listen_for_messages(self):
        """Listen for incoming messages"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                self._process_message(message)
            except json.JSONDecodeError:
                print(f"Received invalid JSON from {addr}")
            except Exception as e:
                if self.running:
                    print(f"Error receiving message: {e}")
    
    def _process_message(self, message: dict):
        """Process incoming messages based on type"""
        msg_type = message.get('type')
        
        if msg_type == 'update':
            self._process_update_message(message)
        elif msg_type == 'data':
            self._process_data_message(message)
        elif msg_type == 'trace':
            self._process_trace_message(message)
    
    def _process_update_message(self, message: dict):
        """Process incoming route update messages"""
        source_ip = message.get('source')
        distances = message.get('distances', {})
        
        with self.lock:
            # Only process if sender is a neighbor
            if source_ip not in self.neighbors:
                return
            
            # Update last received timestamp
            self.last_update_received[source_ip] = time.time()
            
            sender_weight = self.neighbors[source_ip]
            changed = False
            
            # Process each route in the update
            for dest_ip, distance in distances.items():
                if dest_ip == self.router_ip:
                    continue  # Skip routes to ourselves
                
                new_distance = distance + sender_weight
                
                # Update routing table if we found a better route
                if (dest_ip not in self.routing_table or 
                    self.routing_table[dest_ip][0] > new_distance or
                    self.routing_table[dest_ip][1] == source_ip):  # Update if route came from same neighbor
                    
                    old_distance = self.routing_table.get(dest_ip, (float('inf'), None))[0]
                    self.routing_table[dest_ip] = (new_distance, source_ip)
                    
                    if old_distance != new_distance:
                        changed = True
        
        # If routes changed, send updates to neighbors
        if changed:
            self._send_updates_to_neighbors()
    
    def _process_data_message(self, message: dict):
        """Process data messages"""
        destination = message.get('destination')
        
        if destination == self.router_ip:
            # Message is for us - print the payload
            payload = message.get('payload', '')
            print(payload)
        else:
            # Forward the message
            self._forward_message(message)
    
    def _process_trace_message(self, message: dict):
        """Process trace messages"""
        destination = message.get('destination')
        routers = message.get('routers', [])
        
        # Add ourselves to the routers list
        routers = routers + [self.router_ip]
        message['routers'] = routers
        
        if destination == self.router_ip:
            # We are the destination - send response back to source
            source = message.get('source')
            response = {
                'type': 'data',
                'source': self.router_ip,
                'destination': source,
                'payload': json.dumps(message)
            }
            self._forward_message(response)
        else:
            # Forward the trace message
            self._forward_message(message)
    
    def _forward_message(self, message: dict):
        """Forward a message towards its destination"""
        destination = message.get('destination')
        
        with self.lock:
            if destination in self.routing_table:
                next_hop = self.routing_table[destination][1]
                
                try:
                    self.socket.sendto(json.dumps(message).encode(), (next_hop, self.port))
                except Exception as e:
                    print(f"Error forwarding message to {next_hop}: {e}")
            else:
                # No route to destination - drop the message
                pass
    
    def _send_update_message(self, neighbor_ip: str):
        """Send update message to a specific neighbor"""
        distances = {}
        
        with self.lock:
            # Implement split horizon - don't send routes learned from this neighbor
            for dest_ip, (distance, next_hop) in self.routing_table.items():
                if next_hop != neighbor_ip:  # Split horizon
                    distances[dest_ip] = distance
        
        message = {
            'type': 'update',
            'source': self.router_ip,
            'destination': neighbor_ip,
            'distances': distances
        }
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (neighbor_ip, self.port))
        except Exception as e:
            print(f"Error sending update to {neighbor_ip}: {e}")
    
    def _send_updates_to_neighbors(self):
        """Send update messages to all neighbors"""
        with self.lock:
            neighbors = list(self.neighbors.keys())
        
        for neighbor_ip in neighbors:
            self._send_update_message(neighbor_ip)
    
    def _periodic_updates(self):
        """Periodically send updates to neighbors"""
        while self.running:
            time.sleep(self.period)
            if self.neighbors:  # Only send if we have neighbors
                self._send_updates_to_neighbors()
    
    def _check_neighbor_timeouts(self):
        """Check for neighbor timeouts and remove stale routes"""
        while self.running:
            time.sleep(self.period)  # Check every period
            current_time = time.time()
            timeout_threshold = 4 * self.period
            
            with self.lock:
                # Find neighbors that haven't sent updates recently
                timed_out_neighbors = []
                for neighbor_ip, last_update in self.last_update_received.items():
                    if current_time - last_update > timeout_threshold:
                        timed_out_neighbors.append(neighbor_ip)
                
                # Remove routes learned from timed out neighbors
                for neighbor_ip in timed_out_neighbors:
                    routes_to_remove = []
                    for dest, (dist, next_hop) in self.routing_table.items():
                        if next_hop == neighbor_ip and dest != self.router_ip:
                            routes_to_remove.append(dest)
                    
                    for dest in routes_to_remove:
                        del self.routing_table[dest]
                        print(f"Removed route to {dest} (neighbor {neighbor_ip} timed out)")
                    
                    # Remove from last_update_received
                    if neighbor_ip in self.last_update_received:
                        del self.last_update_received[neighbor_ip]
    
    def _process_command(self, command):
        """Process a command (from CLI or startup file)"""
        if not command:
            return
        
        if command[0] == 'add':
            if len(command) != 3:
                print("Usage: add <ip> <weight>")
                return
            
            try:
                neighbor_ip = command[1]
                weight = int(command[2])
                
                # Validate neighbor IP
                ipaddress.IPv4Address(neighbor_ip)
                
                if weight <= 0:
                    print("Weight must be positive")
                    return
                
                self.add_link(neighbor_ip, weight)
            except ValueError as e:
                print(f"Error: {e}")
        
        elif command[0] == 'del':
            if len(command) != 2:
                print("Usage: del <ip>")
                return
            
            neighbor_ip = command[1]
            self.remove_link(neighbor_ip)
        
        elif command[0] == 'trace':
            if len(command) != 2:
                print("Usage: trace <ip>")
                return
            
            
            try:
                destination_ip = command[1]
                ipaddress.IPv4Address(destination_ip)
                self.send_trace(destination_ip)
            except ValueError:
                print("Invalid IP address")
        
        else:
            print("Unknown command. Available: add, del, trace")
    
    def show_routing_table(self):
        """Display the current routing table"""
        print(f"\nRouting table for {self.router_ip}:")
        print("Destination\t\tDistance\tNext Hop")
        print("-" * 50)
        
        with self.lock:
            for dest_ip, (distance, next_hop) in sorted(self.routing_table.items()):
                print(f"{dest_ip:<15}\t{distance}\t\t{next_hop}")
        print()
    
    def show_neighbors(self):
        """Display current neighbors"""
        print(f"\nNeighbors of {self.router_ip}:")
        print("IP Address\t\tWeight")
        print("-" * 30)
        
        with self.lock:
            for neighbor_ip, weight in sorted(self.neighbors.items()):
                print(f"{neighbor_ip:<15}\t{weight}")
        print()
    
    def shutdown(self):
        """Shutdown the router"""
        self.running = False
        self.socket.close()
        print(f"Router {self.router_ip} shutdown")

def main():
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: ./router.py <address> <period> [startup]")
        sys.exit(1)
    
    router_ip = sys.argv[1]
    try:
        period = float(sys.argv[2])
    except ValueError:
        print("Period must be a number")
        sys.exit(1)
    
    startup_file = sys.argv[3] if len(sys.argv) == 4 else None
    
    # Validate IP address is in correct range
    try:
        ip = ipaddress.IPv4Address(router_ip)
        if not str(ip).startswith('127.0.1.'):
            print("Error: IP address must be in 127.0.1.0/24 range")
            sys.exit(1)
    except ipaddress.AddressValueError:
        print("Error: Invalid IP address format")
        sys.exit(1)
    
    # Create router instance
    router = Router(router_ip, period, startup_file)
    
    try:
        while True:
            try:
                command_line = input().strip()
                
                if command_line == 'quit':
                    break
                
                command = command_line.split()
                router._process_command(command)
            
            except KeyboardInterrupt:
                break
            except EOFError:
                break
    
    finally:
        router.shutdown()

if __name__ == "__main__":
    main()
