#!/usr/bin/env python3
"""
Simple Python gRPC streaming client to test CreateMessage streaming
"""
import grpc
import sys
import json
from app.protos import assistant_pb2, assistant_pb2_grpc


def test_streaming():
    # Connect to server
    channel = grpc.insecure_channel('localhost:8000')
    stub = assistant_pb2_grpc.MessageServiceStub(channel)

    # Create request
    request = assistant_pb2.CreateMessageRequest(
        question="Trong workspace Scan INT2 tôi đang có lỗ hổng nào nghiêm trọng nhất?",
        conversation_id="1533842f-880b-46e4-bf85-27c8a4e1eac7",
        is_create_conversation=False
    )

    # Add metadata (headers) - gRPC metadata keys should be lowercase
    metadata = [
        ('x-workspace-id', '0362872e-0b57-4e10-a331-c336aff99261'),
        ('x-user-id', '5f96d327-27b1-4218-98e1-768879b7e80d')
    ]

    print(f"📤 Request:")
    print(f"  Question: {request.question}")
    print(f"  Conversation ID: {request.conversation_id}")
    print(f"  Metadata: {dict(metadata)}")
    print()

    print("=" * 80)
    print("Testing gRPC Streaming CreateMessage")
    print("=" * 80)
    print()

    try:
        # Stream responses
        response_count = 0
        accumulated_answer = []  # Tổng hợp các delta chunks

        for response in stub.CreateMessage(request, metadata=metadata):
            response_count += 1
            message = response.message

            print(f"\n[Message #{response_count}] Type: {message.type}")
            print(f"Message ID: {message.message_id}")
            print(f"Conversation ID: {message.conversation_id}")

            # Parse and pretty-print JSON content
            try:
                content_data = json.loads(message.content)
                print(f"Content: {json.dumps(content_data, indent=2, ensure_ascii=False)}")

                # Tích lũy text từ delta messages
                if message.type == "delta" and "text" in content_data:
                    accumulated_answer.append(content_data["text"])

            except json.JSONDecodeError:
                print(f"Content (raw): {message.content}")

            print("-" * 80)

            # For state messages, show real-time updates
            if message.type == "state":
                try:
                    content_data = json.loads(message.content)
                    state_type = content_data.get("state_type", "")
                    if state_type == "heartbeat":
                        print(f"  ⏳ {content_data.get('details', {}).get('message', 'Processing...')}")
                        print(f"  ⏱️  Elapsed: {content_data.get('details', {}).get('elapsed_seconds', 0)}s")
                    elif state_type == "workflow_node":
                        print(f"  🔄 Node: {content_data.get('details', {}).get('node', 'unknown')}")
                except:
                    pass

        print(f"\n✅ Streaming completed! Received {response_count} messages")

        # In ra kết quả tổng hợp
        if accumulated_answer:
            final_answer = "".join(accumulated_answer)
            print("\n" + "=" * 80)
            print("📝 FINAL ANSWER (Tổng hợp từ các delta chunks):")
            print("=" * 80)
            print(final_answer)
            print("=" * 80)

    except grpc.RpcError as e:
        print(f"\n❌ gRPC Error: {e.code()}")
        print(f"Details: {e.details()}")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    test_streaming()

# python test_streaming_client.py
