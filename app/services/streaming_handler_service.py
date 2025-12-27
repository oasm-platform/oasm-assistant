"""
Streaming Message Handler for gRPC streaming responses
"""
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
from app.protos import assistant_pb2
from common.logger import logger


class StreamingMessageHandler:
    """
    Handles the creation and streaming of Message objects with JSON content
    following the defined schema in MESSAGE_SCHEMA.md
    """

    def __init__(self, message_id: str, conversation_id: str, question: str):
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.question = question
        self.start_time = datetime.utcnow()
        self.agents_used = []
        self.tools_used = []
        self.past_actions = []

    def _create_message(self, msg_type: str, content_dict: Dict[str, Any]) -> assistant_pb2.Message:
        """Create a Message protobuf with JSON content"""
        try:
            content_json = json.dumps(content_dict, ensure_ascii=False)
            return assistant_pb2.Message(
                message_id=self.message_id,
                question=self.question,
                type=msg_type,
                content=content_json,
                conversation_id=self.conversation_id,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.error("Error creating message: {}", e)
            raise

    def message_start(self) -> assistant_pb2.Message:
        """Create message_start event"""
        content = {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "question": self.question,
            "timestamp": datetime.utcnow().isoformat()
        }
        return self._create_message("message_start", content)

    def thinking(
        self,
        agent: str,
        thought: str,
        roadmap: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> assistant_pb2.Message:
        """Create thinking event"""
        content = {
            "agent": agent,
            "thought": thought,
            "roadmap": roadmap or [],
            "context": context or {}
        }

        # Track agent usage
        if agent not in self.agents_used:
            self.agents_used.append(agent)

        return self._create_message("thinking", content)

    def tool_start(
        self,
        tool_name: str,
        tool_description: str,
        parameters: Dict[str, Any],
        agent: str
    ) -> assistant_pb2.Message:
        """Create tool_start event"""
        content = {
            "tool_name": tool_name,
            "tool_description": tool_description,
            "parameters": parameters,
            "agent": agent,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Track tool usage
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)

        return self._create_message("tool_start", content)

    def tool_output(
        self,
        tool_name: str,
        status: str,
        agent: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ) -> assistant_pb2.Message:
        """Create tool_output event"""
        content = {
            "tool_name": tool_name,
            "status": status,
            "agent": agent
        }

        if output is not None:
            content["output"] = output
        if error is not None:
            content["error"] = error
        if execution_time_ms is not None:
            content["execution_time_ms"] = execution_time_ms

        return self._create_message("tool_output", content)

    def tool_end(
        self,
        tool_name: str,
        agent: str,
        summary: str,
        next_action: Optional[str] = None
    ) -> assistant_pb2.Message:
        """Create tool_end event"""
        content = {
            "tool_name": tool_name,
            "agent": agent,
            "summary": summary,
            "next_action": next_action or ""
        }

        # Track past action
        self.past_actions.append({
            "agent": agent,
            "action": f"Executed {tool_name}",
            "result": summary
        })

        return self._create_message("tool_end", content)

    def delta(self, text: str, agent: str) -> assistant_pb2.Message:
        """Create delta event for streaming text"""
        content = {
            "text": text,
            "agent": agent
        }
        return self._create_message("delta", content)

    def state(
        self,
        state_type: str,
        agent: str,
        status: str,
        details: Dict[str, Any]
    ) -> assistant_pb2.Message:
        """Create state event"""
        content = {
            "state_type": state_type,
            "agent": agent,
            "status": status,
            "details": details
        }
        return self._create_message("state", content)

    def error(
        self,
        error_type: str,
        error_message: str,
        agent: str,
        recoverable: bool = False,
        retry_suggested: bool = False,
        stack_trace: Optional[str] = None
    ) -> assistant_pb2.Message:
        """Create error event"""
        content = {
            "error_type": error_type,
            "error_message": error_message,
            "agent": agent,
            "recoverable": recoverable,
            "retry_suggested": retry_suggested
        }

        if stack_trace:
            content["stack_trace"] = stack_trace

        return self._create_message("error", content)

    def message_end(
        self,
        total_tokens: Optional[int] = None,
        success: bool = True,
        key_findings: Optional[List[str]] = None
    ) -> assistant_pb2.Message:
        """Create message_end event"""
        elapsed_time_ms = int((datetime.utcnow() - self.start_time).total_seconds() * 1000)

        content = {
            "message_id": self.message_id,
            "total_time_ms": elapsed_time_ms,
            "agents_used": self.agents_used,
            "tools_used": self.tools_used,
            "success": success,
            "summary": {
                "past_actions": self.past_actions,
                "key_findings": key_findings or []
            }
        }

        if total_tokens is not None:
            content["total_tokens"] = total_tokens

        return self._create_message("message_end", content)

    def done(self, final_status: str = "success") -> assistant_pb2.Message:
        """Create done event"""
        content = {
            "message_id": self.message_id,
            "final_status": final_status
        }
        return self._create_message("done", content)

    def system_message(
        self,
        level: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> assistant_pb2.Message:
        """Create system event"""
        content = {
            "level": level,
            "message": message
        }

        if details:
            content["details"] = details

        return self._create_message("system", content)

    def event(
        self,
        event_name: str,
        event_data: Dict[str, Any]
    ) -> assistant_pb2.Message:
        """Create custom event"""
        content = {
            "event_name": event_name,
            "event_data": event_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        return self._create_message("event", content)


class StreamingResponseBuilder:
    """
    Builder pattern for creating streaming responses
    """

    @staticmethod
    async def build_response_stream(
        message_id: str,
        conversation_id: str,
        question: str,
        response_generator: AsyncGenerator[Dict[str, Any], None]
    ) -> AsyncGenerator[assistant_pb2.Message, None]:
        """
        Build a complete streaming response from an async generator

        Args:
            message_id: Unique message ID
            conversation_id: Conversation ID
            question: User's question
            response_generator: Async generator yielding streaming events

        Yields:
            assistant_pb2.Message: Streaming message chunks
        """
        handler = StreamingMessageHandler(message_id, conversation_id, question)

        try:
            # Send message_start
            yield handler.message_start()

            # Mapping for event handlers
            event_mapping = {
                "thinking": lambda e: handler.thinking(
                    agent=e.get("agent", ""),
                    thought=e.get("thought", ""),
                    roadmap=e.get("roadmap"),
                    context=e.get("context")
                ),
                "tool_start": lambda e: handler.tool_start(
                    tool_name=e.get("tool_name", ""),
                    tool_description=e.get("tool_description", ""),
                    parameters=e.get("parameters", {}),
                    agent=e.get("agent", "")
                ),
                "tool_output": lambda e: handler.tool_output(
                    tool_name=e.get("tool_name", ""),
                    status=e.get("status", "success"),
                    agent=e.get("agent", ""),
                    output=e.get("output"),
                    error=e.get("error"),
                    execution_time_ms=e.get("execution_time_ms")
                ),
                "tool_end": lambda e: handler.tool_end(
                    tool_name=e.get("tool_name", ""),
                    agent=e.get("agent", ""),
                    summary=e.get("summary", ""),
                    next_action=e.get("next_action")
                ),
                "delta": lambda e: handler.delta(
                    text=e.get("text", ""),
                    agent=e.get("agent", "")
                ),
                "state": lambda e: handler.state(
                    state_type=e.get("state_type", ""),
                    agent=e.get("agent", ""),
                    status=e.get("status", ""),
                    details=e.get("details", {})
                ),
                "error": lambda e: handler.error(
                    error_type=e.get("error_type", ""),
                    error_message=e.get("error_message", ""),
                    agent=e.get("agent", ""),
                    recoverable=e.get("recoverable", False),
                    retry_suggested=e.get("retry_suggested", False),
                    stack_trace=e.get("stack_trace")
                ),
                "event": lambda e: handler.event(
                    event_name=e.get("event_name", ""),
                    event_data=e.get("event_data", {})
                )
            }

            # Process events from async generator
            async for event in response_generator:
                event_type = event.get("type")
                
                if event_type in event_mapping:
                    yield event_mapping[event_type](event)
                
                elif event_type == "result":
                    data = event.get("data", {})
                    response_text = ""
                    
                    if isinstance(data, dict):
                        # Extract prioritized content fields
                        for key in ["response", "answer", "message"]:
                            if key in data:
                                response_text = str(data[key])
                                break
                    else:
                        response_text = str(data)
                        
                    if response_text:
                        yield handler.delta(
                            text=response_text,
                            agent=event.get("agent", "")
                        )

            # Send message_end
            yield handler.message_end(
                success=True,
                key_findings=[]
            )

            # Send done
            yield handler.done(final_status="success")

        except Exception as e:
            logger.error("Error in streaming response: {}", e)
            # Send error message
            yield handler.error(
                error_type="StreamingError",
                error_message=str(e),
                agent="StreamingResponseBuilder",
                recoverable=False,
                retry_suggested=True
            )
            # Send done with error status
            yield handler.done(final_status="error")
