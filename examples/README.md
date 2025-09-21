# OASM Assistant Examples

This folder contains example client code demonstrating how to interact with the OASM Assistant gRPC services.

## Prerequisites

1. Make sure the OASM Assistant server is running:
   ```bash
   task dev
   ```

2. The server should be accessible at `localhost:8000` (default configuration).

## Available Examples

### 1. Health Check Client (`health_check_client.py`)

A simple example that demonstrates how to call the HealthCheck service to verify the server is running.

**Usage:**
```bash
cd examples
python health_check_client.py
```

**Expected Output:**
```
=== Health Check Client Example ===
Connecting to gRPC server at localhost:8000
Health Check Response: ok
✓ Health check successful!
```

### 2. Domain Classification Client (`domain_classification_client.py`)

Demonstrates how to use the DomainClassify service to categorize website domains.

**Usage:**

Classify multiple example domains:
```bash
cd examples
python domain_classification_client.py
```

Classify a specific domain:
```bash
cd examples
python domain_classification_client.py google.com
```

**Expected Output:**
```
=== Domain Classification Examples ===

Classifying: google.com
Domain: google.com
Classification Labels: ['technology', 'search_engine']
--------------------------------------------------

Classifying: amazon.com
Domain: amazon.com
Classification Labels: ['ecommerce', 'technology']
--------------------------------------------------
...
```

## gRPC Service Details

### HealthCheck Service
- **Method:** `HealthCheck(HealthCheckRequest) returns (HealthCheckResponse)`
- **Purpose:** Verify server health and availability
- **Request:** Empty request message
- **Response:** Contains a status message

### DomainClassify Service
- **Method:** `DomainClassify(DomainClassifyRequest) returns (DomainClassifyResponse)`
- **Purpose:** Classify website domains into categories
- **Request:** Contains the domain string to classify
- **Response:** Contains a list of classification labels

## Customization

You can modify the server connection details in the examples:

```python
SERVER_HOST = "localhost"  # Change to your server host
SERVER_PORT = 8000         # Change to your server port
```

## Error Handling

The examples include proper error handling for common gRPC errors:

- Connection failures
- Server unavailable
- Invalid requests
- Timeout errors

## Protocol Buffers

The examples use the generated protocol buffer files from `app/protos/`:
- `assistant_pb2.py` - Generated message classes
- `assistant_pb2_grpc.py` - Generated service stubs

## Troubleshooting

1. **Connection refused:** Make sure the server is running with `task dev`
2. **Import errors:** Run the examples from the `examples/` directory
3. **gRPC errors:** Check the server logs for detailed error information

## Development

To add new examples:

1. Create a new Python file in the `examples/` folder
2. Import the required protobuf modules
3. Follow the pattern of creating a gRPC channel and stub
4. Add proper error handling and documentation