# Luồng Hoạt Động của Analysis Agent

## Tổng Quan

Analysis Agent là một agent chuyên biệt trong hệ thống OASM Assistant, có nhiệm vụ phân tích dữ liệu bảo mật từ workspace thông qua MCP (Model Context Protocol) và trả về kết quả phân tích với **LLM streaming real-time** (như ChatGPT/Claude).

## Kiến Trúc Tổng Thể

```
User Input (gRPC Streaming)
    ↓
MessageService.CreateMessage() [Streaming]
    ↓
SecurityCoordinator.process_message_question_streaming() [Async]
    ↓
LangGraph Workflow (Router)
    ↓
AnalysisAgent.execute_task_streaming() [Async]
    ↓
MCP Tools (Dynamic Discovery)
    ↓
LLM.astream() [Real-time Streaming]
    ↓
Stream to User (Buffered Chunks)
```

---

## Các Thay Đổi Quan Trọng

### 🆕 **Streaming Architecture**
- **LLM Streaming**: Text được stream từ LLM như ChatGPT/Claude
- **Async/Await**: Toàn bộ pipeline sử dụng async generators
- **Buffered Chunks**: Gom nhỏ chunks để giảm số responses (configurable)
- **No Manual Chunking**: Không còn DELTA_CHUNK_SIZE thủ công

### 🔧 **Cấu hình Streaming**
```bash
# config/.env
LLM_MIN_CHUNK_SIZE=20  # Minimum chars before sending (default: 20)
```

---

## Chi Tiết Luồng Hoạt Động

### 1. Entry Point: MessageService (app/services/message.py)

**File:** `app/services/message.py`
**Method:** `CreateMessage()` - gRPC Streaming

#### Luồng Streaming:

```python
def CreateMessage(self, request, context):
    # Step 1: Setup
    question = request.question.strip()
    workspace_id = context.workspace_id
    user_id = context.user_id
    message_id = str(uuid.uuid4())

    # Step 2: Initialize coordinator
    coordinator = SecurityCoordinator(
        db_session=session,
        workspace_id=workspace_id,
        user_id=user_id
    )

    # Step 3: Create async streaming generator
    streaming_events = coordinator.process_message_question_streaming(question)

    # Step 4: Build async response stream
    async_stream = StreamingResponseBuilder.build_response_stream(
        message_id=message_id,
        conversation_id=conversation_id,
        question=question,
        response_generator=streaming_events
    )

    # Step 5: Convert async → sync for gRPC compatibility
    for stream_message in async_generator_to_sync(async_stream):
        # Accumulate delta text for DB storage
        if stream_message.type == "delta":
            accumulated_answer.append(stream_message.text)

        # Yield streaming message to client
        yield assistant_pb2.CreateMessageResponse(message=stream_message)

    # Step 6: Save to database after streaming completes
    answer = "".join(accumulated_answer)
    save_to_database(question, answer)
```

#### Event Types được Stream:

| Event Type | Description | Example |
|------------|-------------|---------|
| `message_start` | Bắt đầu message | `{"message_id": "xxx", "timestamp": "..."}` |
| `thinking` | Agent đang suy nghĩ | `{"thought": "Analyzing security data..."}` |
| `tool_start` | Bắt đầu dùng tool | `{"tool_name": "mcp_data_fetch"}` |
| `tool_output` | Kết quả tool | `{"status": "success", "output": {...}}` |
| `tool_end` | Hoàn thành tool | `{"summary": "Completed data fetch"}` |
| `delta` ⭐ | **LLM text chunk** | `{"text": "Based on the scan data..."}` |
| `message_end` | Kết thúc message | `{"total_time_ms": 5000, "success": true}` |
| `done` | Hoàn tất | `{"final_status": "success"}` |

---

### 2. SecurityCoordinator (agents/workflows/security_coordinator.py)

**File:** `agents/workflows/security_coordinator.py`
**Class:** `SecurityCoordinator`

#### 2.1. Process Message Question Streaming

```python
async def process_message_question_streaming(
    self,
    question: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process question with real-time streaming

    Yields:
        Streaming events from agents
    """
    try:
        # Yield thinking event
        yield {
            "type": "thinking",
            "agent": "SecurityCoordinator",
            "thought": "Analyzing security question and determining workflow",
            "roadmap": [
                {"step": "1", "description": "Route to appropriate security agent"},
                {"step": "2", "description": "Execute security analysis with LLM"},
                {"step": "3", "description": "Stream response to user"}
            ]
        }

        # Create agent
        agent = AnalysisAgent(
            db_session=self.db_session,
            workspace_id=self.workspace_id,
            user_id=self.user_id
        )

        # Prepare task
        task = {
            "action": "analyze_vulnerabilities",
            "question": question
        }

        # Stream agent execution (async for)
        async for event in agent.execute_task_streaming(task):
            yield event

    except Exception as e:
        yield {
            "type": "error",
            "error_message": str(e),
            "agent": "SecurityCoordinator"
        }
```

**Key Points:**
- ✅ **Async Generator**: Sử dụng `async def` với `AsyncGenerator` return type
- ✅ **Direct Streaming**: Không qua LangGraph cho đơn giản
- ✅ **Error Handling**: Yield error events thay vì raise exceptions

---

### 3. AnalysisAgent (agents/specialized/analysis_agent.py)

**File:** `agents/specialized/analysis_agent.py`
**Class:** `AnalysisAgent`

#### 3.1. Execute Task Streaming

```python
async def execute_task_streaming(
    self,
    task: Dict[str, Any]
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute task with streaming support

    Yields streaming events like ChatGPT/Claude
    """
    try:
        action = task.get("action", "analyze_vulnerabilities")
        question = task.get("question")

        # Yield thinking event
        yield {
            "type": "thinking",
            "thought": "Analyzing security data and preparing response",
            "agent": self.name
        }

        if action == "analyze_vulnerabilities":
            async for event in self.analyze_vulnerabilities_streaming(question):
                yield event
        else:
            yield {
                "type": "error",
                "error": f"Unknown action: {action}",
                "agent": self.name
            }

    except Exception as e:
        yield {
            "type": "error",
            "error": str(e),
            "agent": self.name
        }
```

#### 3.2. Analyze Vulnerabilities Streaming

```python
async def analyze_vulnerabilities_streaming(
    self,
    question: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streaming vulnerability analysis - like ChatGPT/Claude

    Yields:
        Streaming events with LLM text chunks as they are generated
    """
    # Step 1: Yield tool start - fetching MCP data
    yield {
        "type": "tool_start",
        "tool_name": "mcp_data_fetch",
        "tool_description": "Fetching security scan data from MCP",
        "agent": self.name
    }

    # Step 2: Fetch MCP data
    scan_data = await self._fetch_mcp_data(question)

    # Step 3: Yield tool output
    yield {
        "type": "tool_output",
        "tool_name": "mcp_data_fetch",
        "status": "success" if scan_data else "no_data",
        "output": {
            "has_data": bool(scan_data),
            "source": scan_data.get("source") if scan_data else None
        },
        "agent": self.name
    }

    # Step 4: Yield tool_end
    yield {
        "type": "tool_end",
        "tool_name": "mcp_data_fetch",
        "agent": self.name
    }

    # Step 5: Stream LLM analysis (REAL-TIME STREAMING)
    async for event in self._generate_analysis_streaming(question, scan_data):
        yield event

    # Step 6: Yield final result
    yield {
        "type": "result",
        "data": {
            "success": bool(scan_data),
            "has_data": bool(scan_data)
        },
        "agent": self.name
    }
```

#### 3.3. Generate Analysis Streaming (⭐ Key Method)

```python
async def _generate_analysis_streaming(
    self,
    question: str,
    scan_data: Optional[Dict]
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Generate analysis response with LLM streaming (like ChatGPT/Claude)

    Yields delta events as LLM generates text (buffered to reduce responses)
    """
    # Get min chunk size from config
    min_chunk_size = configs.llm.min_chunk_size  # Default: 20

    # Select appropriate prompt
    if not scan_data:
        prompt = AnalysisAgentPrompts.get_no_data_response_prompt(question)
    else:
        stats = scan_data.get("stats", {})
        tool = scan_data.get("tool", "unknown")

        if "statistics" in tool or "score" in str(stats):
            prompt = AnalysisAgentPrompts.get_statistics_analysis_prompt(question, stats)
        elif "vulnerabilities" in tool:
            prompt = AnalysisAgentPrompts.get_vulnerabilities_analysis_prompt(question, stats)
        elif "assets" in tool:
            prompt = AnalysisAgentPrompts.get_assets_analysis_prompt(question, stats)
        else:
            prompt = AnalysisAgentPrompts.get_generic_analysis_prompt(question, stats)

    # ⭐ Stream LLM response with buffering
    async for buffered_text in self._buffer_llm_chunks(
        self.llm.astream(prompt),
        min_chunk_size
    ):
        yield {
            "type": "delta",
            "text": buffered_text,
            "agent": self.name
        }
```

#### 3.4. Buffer LLM Chunks (⭐ Performance Optimization)

```python
async def _buffer_llm_chunks(
    self,
    llm_stream: AsyncGenerator,
    min_chunk_size: int
) -> AsyncGenerator[str, None]:
    """
    Buffer LLM chunks to reduce number of responses sent

    Args:
        llm_stream: Async generator from LLM (self.llm.astream())
        min_chunk_size: Minimum characters before yielding (from config)

    Yields:
        Buffered text chunks

    Example:
        LLM generates: "Based" → Buffer (5 chars)
        LLM generates: " on" → Buffer (8 chars)
        LLM generates: " the" → Buffer (12 chars)
        LLM generates: " scan" → Buffer (17 chars)
        LLM generates: " data" → Buffer (22 chars) → YIELD "Based on the scan data" ✅
    """
    buffer = ""

    async for chunk in llm_stream:
        # Extract text from chunk
        if isinstance(chunk, BaseMessage) and chunk.content:
            text = chunk.content
        elif isinstance(chunk, str):
            text = chunk
        else:
            continue

        buffer += text

        # Yield when buffer reaches min size
        if len(buffer) >= min_chunk_size:
            yield buffer
            buffer = ""

    # Yield remaining buffer
    if buffer:
        yield buffer
```

**Benefits of Buffering:**
- ✅ Reduces number of gRPC responses (less overhead)
- ✅ More natural text flow for users
- ✅ Configurable via `LLM_MIN_CHUNK_SIZE` env var
- ✅ Still maintains real-time streaming feel

---

### 4. Streaming Response Builder (app/services/streaming_handler.py)

**File:** `app/services/streaming_handler.py`
**Class:** `StreamingResponseBuilder`

#### Build Response Stream

```python
@staticmethod
async def build_response_stream(
    message_id: str,
    conversation_id: str,
    question: str,
    response_generator: AsyncGenerator[Dict[str, Any], None]
) -> AsyncGenerator[assistant_pb2.Message, None]:
    """
    Build a complete streaming response from an async generator

    Converts agent events to gRPC Message protobuf objects
    """
    handler = StreamingMessageHandler(message_id, conversation_id, question)

    try:
        # Send message_start
        yield handler.message_start()

        # Process events from async generator
        async for event in response_generator:
            event_type = event.get("type")

            if event_type == "thinking":
                yield handler.thinking(
                    agent=event.get("agent", ""),
                    thought=event.get("thought", ""),
                    roadmap=event.get("roadmap"),
                    context=event.get("context")
                )

            elif event_type == "tool_start":
                yield handler.tool_start(
                    tool_name=event.get("tool_name", ""),
                    tool_description=event.get("tool_description", ""),
                    parameters=event.get("parameters", {}),
                    agent=event.get("agent", "")
                )

            elif event_type == "tool_output":
                yield handler.tool_output(
                    tool_name=event.get("tool_name", ""),
                    status=event.get("status", "success"),
                    agent=event.get("agent", ""),
                    output=event.get("output")
                )

            elif event_type == "tool_end":
                yield handler.tool_end(
                    tool_name=event.get("tool_name", ""),
                    agent=event.get("agent", ""),
                    summary=event.get("summary", "")
                )

            elif event_type == "delta":  # ⭐ LLM text streaming
                yield handler.delta(
                    text=event.get("text", ""),
                    agent=event.get("agent", "")
                )

            elif event_type == "error":
                yield handler.error(
                    error_type=event.get("error_type", ""),
                    error_message=event.get("error_message", ""),
                    agent=event.get("agent", "")
                )

        # Send message_end
        yield handler.message_end(success=True)

        # Send done
        yield handler.done(final_status="success")

    except Exception as e:
        logger.error(f"Error in streaming response: {e}", exc_info=True)
        yield handler.error(
            error_type="StreamingError",
            error_message=str(e),
            agent="StreamingResponseBuilder"
        )
        yield handler.done(final_status="error")
```

---

### 5. Async to Sync Conversion (app/services/message.py)

**Helper Function:** `async_generator_to_sync()`

```python
def async_generator_to_sync(async_gen):
    """
    Convert async generator to sync generator for gRPC compatibility

    Why needed:
    - gRPC servicer methods must be sync generators
    - Our agents use async generators for streaming
    - This bridges the gap

    Args:
        async_gen: Async generator to convert

    Yields:
        Items from the async generator (synchronously)
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        while True:
            try:
                # Run async __anext__() in event loop
                yield loop.run_until_complete(async_gen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        loop.close()
```

**Why Needed:**
- gRPC servicer methods must return **sync generators** (not async)
- Our agent pipeline uses **async generators** for performance
- This helper bridges the gap between async and sync worlds

---

## Sơ Đồ Streaming Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER REQUEST (gRPC)                                          │
│    - Question: "Workspace có lỗ hổng gì nghiêm trọng?"          │
│    - workspace_id, user_id                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. MESSAGE SERVICE                                              │
│    CreateMessage() - gRPC Streaming Generator                   │
│                                                                  │
│    for msg in async_generator_to_sync(async_stream):            │
│        yield CreateMessageResponse(message=msg)                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. STREAMING RESPONSE BUILDER (Async)                          │
│    async for event in response_generator:                       │
│        - Convert events to protobuf Messages                    │
│        - Track agents used, tools used                          │
│        - Accumulate past actions                                │
│        yield Message(type=event_type, content=json)             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SECURITY COORDINATOR (Async)                                │
│    async def process_message_question_streaming():              │
│        yield {"type": "thinking", ...}                          │
│        async for event in agent.execute_task_streaming():       │
│            yield event                                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. ANALYSIS AGENT (Async)                                      │
│    async def execute_task_streaming():                          │
│        yield {"type": "tool_start", ...}                        │
│        scan_data = await _fetch_mcp_data()                      │
│        yield {"type": "tool_output", ...}                       │
│                                                                  │
│        # ⭐ Stream LLM response                                  │
│        async for event in _generate_analysis_streaming():       │
│            yield event  # {"type": "delta", "text": "..."}      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. GENERATE ANALYSIS STREAMING                                 │
│    async def _generate_analysis_streaming():                    │
│                                                                  │
│        # Buffer LLM chunks                                      │
│        async for buffered_text in _buffer_llm_chunks(           │
│            self.llm.astream(prompt),                            │
│            min_chunk_size=20                                    │
│        ):                                                        │
│            yield {"type": "delta", "text": buffered_text}       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. BUFFER LLM CHUNKS                                            │
│    async def _buffer_llm_chunks():                              │
│        buffer = ""                                              │
│        async for chunk in self.llm.astream(prompt):             │
│            # Extract text from chunk                            │
│            text = chunk.content if BaseMessage else chunk       │
│            buffer += text                                       │
│                                                                  │
│            # Yield when buffer reaches min size                 │
│            if len(buffer) >= min_chunk_size:                    │
│                yield buffer                                     │
│                buffer = ""                                      │
│                                                                  │
│        # Yield remaining                                        │
│        if buffer:                                               │
│            yield buffer                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. LLM (Ollama/OpenAI/Anthropic)                               │
│    async for chunk in llm.astream(prompt):                      │
│        # Generate text token by token                           │
│        yield "Based"                                            │
│        yield " on"                                              │
│        yield " the"                                             │
│        yield " scan"                                            │
│        yield " data"                                            │
│        ...                                                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. BACK TO USER (Streaming)                                    │
│                                                                  │
│    Stream 1: {"type": "message_start", ...}                     │
│    Stream 2: {"type": "thinking", "thought": "Analyzing..."}    │
│    Stream 3: {"type": "tool_start", "tool_name": "mcp_fetch"}  │
│    Stream 4: {"type": "tool_output", "status": "success"}      │
│    Stream 5: {"type": "tool_end", ...}                         │
│    Stream 6: {"type": "delta", "text": "Based on the scan "}   │
│    Stream 7: {"type": "delta", "text": "data, your workspace"} │
│    Stream 8: {"type": "delta", "text": " has 45 vulnerabilit"} │
│    Stream 9: {"type": "delta", "text": "ies: 3 Critical, "}    │
│    ...                                                           │
│    Stream N: {"type": "message_end", "success": true}          │
│    Stream N+1: {"type": "done", "final_status": "success"}     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Environment Variables (.env)

```bash
# LLM Configuration
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
LLM_MODEL_NAME=llama3
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4000

# ⭐ Streaming Configuration
LLM_MIN_CHUNK_SIZE=20  # Min chars before sending chunk (default: 20)
# Lower (5-10): More responsive, more frequent updates
# Higher (30-50): Fewer updates, more text per chunk

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=9432
POSTGRES_DB=oasm-assistant
```

---

## Performance Considerations

### 1. Buffering Strategy

**Without Buffering (BAD ❌):**
```
LLM: "B" → Send to user
LLM: "a" → Send to user
LLM: "s" → Send to user
LLM: "e" → Send to user
LLM: "d" → Send to user
→ 5 responses for 5 characters! Too many!
```

**With Buffering (GOOD ✅):**
```
LLM: "B" → Buffer (1 char)
LLM: "a" → Buffer (2 chars)
LLM: "s" → Buffer (3 chars)
LLM: "e" → Buffer (4 chars)
LLM: "d" → Buffer (5 chars)
...
LLM: " " → Buffer (20 chars) → SEND "Based on the scan d"
→ 1 response for 20 characters! Much better!
```

### 2. Async/Await Benefits

- **Non-blocking I/O**: Không block khi chờ LLM response
- **Concurrent Processing**: Multiple users được serve đồng thời
- **Memory Efficient**: Generators không load toàn bộ response vào memory
- **Scalable**: Dễ scale với nhiều concurrent connections

### 3. gRPC Streaming Benefits

- **Low Latency**: User thấy text ngay khi LLM generate
- **Better UX**: Giống ChatGPT/Claude, không phải chờ full response
- **Progressive Rendering**: Frontend có thể render từng phần
- **Cancellable**: User có thể cancel request giữa chừng

---

## Error Handling

### 1. Async Generator Errors

```python
async def execute_task_streaming(self, task):
    try:
        # Normal flow
        async for event in self.analyze_vulnerabilities_streaming(question):
            yield event
    except Exception as e:
        # Yield error event instead of raising
        yield {
            "type": "error",
            "error_message": str(e),
            "agent": self.name,
            "recoverable": False
        }
```

### 2. LLM Streaming Errors

```python
async def _generate_analysis_streaming(self, question, scan_data):
    try:
        async for chunk in self.llm.astream(prompt):
            # Process chunk
            yield {"type": "delta", "text": chunk.content}
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        # Send fallback response
        yield {
            "type": "delta",
            "text": "I apologize, but I encountered an error generating the response."
        }
```

### 3. MCP Errors

```python
async def _fetch_mcp_data(self, question):
    try:
        await self.mcp_manager.initialize()
        result = await self.mcp_manager.call_tool(server, tool, args)
        return result
    except Exception as e:
        logger.error(f"MCP fetch error: {e}")
        return None  # Will trigger "no data" flow
```

---

## Files & Locations

```
oasm-assistant/
├── app/
│   └── services/
│       ├── message.py                    # Entry point, async_generator_to_sync()
│       └── streaming_handler.py          # StreamingResponseBuilder (async)
│
├── agents/
│   ├── core/
│   │   └── base_agent.py                # BaseAgent with streaming support
│   │
│   ├── specialized/
│   │   └── analysis_agent.py            # AnalysisAgent (async streaming)
│   │
│   └── workflows/
│       └── security_coordinator.py       # SecurityCoordinator (async streaming)
│
├── common/
│   └── config/
│       └── configs.py                    # LlmConfigs.min_chunk_size
│
└── llms/
    ├── llm_manager.py                    # LLM provider management
    └── prompts/
        └── analysis_agent_prompts.py     # Prompt templates
```

---

## Kết Luận

Analysis Agent hiện tại là một hệ thống **streaming-first** với:

### ✅ **Streaming Architecture**
- LLM streaming real-time (như ChatGPT/Claude)
- Async/await throughout
- Buffered chunks để tối ưu performance

### ✅ **Performance Optimized**
- Configurable `LLM_MIN_CHUNK_SIZE`
- Non-blocking I/O
- Memory efficient generators

### ✅ **User Experience**
- Text xuất hiện ngay khi LLM generate
- Smooth, natural flow
- Progressive rendering support

### ✅ **Developer Friendly**
- Clear separation: async agents, sync gRPC
- Easy to debug with event-based architecture
- Configurable for different use cases

**Total Latency Breakdown:**
- Time to first token: ~100-500ms (LLM dependent)
- Streaming overhead: ~5-20ms per chunk (buffered)
- Total response time: Same as before, but user sees results immediately!