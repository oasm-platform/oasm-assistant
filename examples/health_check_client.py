#!/usr/bin/env python3
"""
Health Check Client Example

This example demonstrates how to call the HealthCheck gRPC service.
"""

import grpc
import sys
import os

# Add the parent directory to the path to import the protobuf files
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.protos import assistant_pb2, assistant_pb2_grpc


def run_health_check(host='localhost', port=8000):
    """
    Send a health check request to the gRPC server.
    
    Args:
        host (str): Server host (default: localhost)
        port (int): Server port (default: 8000)
    
    Returns:
        str: Health check response message
    """
    # Create a gRPC channel
    channel = grpc.insecure_channel(f'{host}:{port}')
    
    # Create a stub (client)
    stub = assistant_pb2_grpc.HealthCheckStub(channel)
    
    try:
        # Create the request
        request = assistant_pb2.HealthCheckRequest()
        
        # Make the gRPC call
        response = stub.HealthCheck(request)
        
        print(f"Health Check Response: {response.message}")
        return response.message
        
    except grpc.RpcError as e:
        print(f"gRPC Error: {e.code()} - {e.details()}")
        return None
        
    finally:
        # Close the channel
        channel.close()


if __name__ == "__main__":
    print("=== Health Check Client Example ===")
    
    # You can modify these values or pass them as command line arguments
    SERVER_HOST = "localhost"
    SERVER_PORT = 8000
    
    print(f"Connecting to gRPC server at {SERVER_HOST}:{SERVER_PORT}")
    
    # Run the health check
    result = run_health_check(SERVER_HOST, SERVER_PORT)
    
    if result:
        print("✓ Health check successful!")
    else:
        print("✗ Health check failed!")
        sys.exit(1)