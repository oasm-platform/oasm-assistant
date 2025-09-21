#!/usr/bin/env python3
"""
Domain Classification Client Example

This example demonstrates how to call the DomainClassify gRPC service
to classify website domains into categories.
"""

import grpc
import sys
import os

# Add the parent directory to the path to import the protobuf files
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.protos import assistant_pb2, assistant_pb2_grpc


def classify_domain(domain, host='localhost', port=8000):
    """
    Send a domain classification request to the gRPC server.
    
    Args:
        domain (str): The domain to classify (e.g., 'google.com')
        host (str): Server host (default: localhost)
        port (int): Server port (default: 8000)
    
    Returns:
        list: List of classification labels
    """
    # Create a gRPC channel
    channel = grpc.insecure_channel(f'{host}:{port}')
    
    # Create a stub (client)
    stub = assistant_pb2_grpc.DomainClassifyStub(channel)
    
    try:
        # Create the request
        request = assistant_pb2.DomainClassifyRequest(domain=domain)
        
        # Make the gRPC call
        response = stub.DomainClassify(request)
        
        print(f"Domain: {domain}")
        print(f"Classification Labels: {list(response.label)}")
        
        return list(response.label)
        
    except grpc.RpcError as e:
        print(f"gRPC Error: {e.code()} - {e.details()}")
        return []
        
    finally:
        # Close the channel
        channel.close()


def run_classification_examples():
    """Run multiple domain classification examples."""
    
    # Example domains to classify
    test_domains = [
        "google.com",
        "amazon.com", 
        "github.com",
        "facebook.com",
        "stackoverflow.com",
        "wikipedia.org",
        "cnn.com",
        "shopify.com",
        "netflix.com",
        "university.edu"
    ]
    
    print("=== Domain Classification Examples ===\n")
    
    results = {}
    
    for domain in test_domains:
        print(f"Classifying: {domain}")
        labels = classify_domain(domain)
        results[domain] = labels
        print("-" * 50)
        print()
    
    # Summary
    print("=== Classification Summary ===")
    for domain, labels in results.items():
        if labels:
            labels_str = ", ".join(labels)
            print(f"• {domain}: {labels_str}")
        else:
            print(f"• {domain}: No classification")


if __name__ == "__main__":
    SERVER_HOST = "localhost"
    SERVER_PORT = 8000
    
    print(f"Connecting to gRPC server at {SERVER_HOST}:{SERVER_PORT}\n")
    
    # Check if a specific domain was provided as command line argument
    if len(sys.argv) > 1:
        domain = sys.argv[1]
        print(f"Classifying single domain: {domain}")
        classify_domain(domain, SERVER_HOST, SERVER_PORT)
    else:
        # Run multiple examples
        run_classification_examples()