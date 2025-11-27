from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HealthCheckRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthCheckResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: str
    def __init__(self, message: _Optional[str] = ...) -> None: ...

class DomainClassifyRequest(_message.Message):
    __slots__ = ("domain",)
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    domain: str
    def __init__(self, domain: _Optional[str] = ...) -> None: ...

class DomainClassifyResponse(_message.Message):
    __slots__ = ("labels",)
    LABELS_FIELD_NUMBER: _ClassVar[int]
    labels: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, labels: _Optional[_Iterable[str]] = ...) -> None: ...

class CreateTemplateRequest(_message.Message):
    __slots__ = ("question",)
    QUESTION_FIELD_NUMBER: _ClassVar[int]
    question: str
    def __init__(self, question: _Optional[str] = ...) -> None: ...

class CreateTemplateResponse(_message.Message):
    __slots__ = ("answer",)
    ANSWER_FIELD_NUMBER: _ClassVar[int]
    answer: str
    def __init__(self, answer: _Optional[str] = ...) -> None: ...

class Conversation(_message.Message):
    __slots__ = ("conversation_id", "title", "description", "created_at", "updated_at")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    title: str
    description: str
    created_at: str
    updated_at: str
    def __init__(self, conversation_id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class GetConversationsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetConversationsResponse(_message.Message):
    __slots__ = ("conversations",)
    CONVERSATIONS_FIELD_NUMBER: _ClassVar[int]
    conversations: _containers.RepeatedCompositeFieldContainer[Conversation]
    def __init__(self, conversations: _Optional[_Iterable[_Union[Conversation, _Mapping]]] = ...) -> None: ...

class UpdateConversationRequest(_message.Message):
    __slots__ = ("conversation_id", "title", "description")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    title: str
    description: str
    def __init__(self, conversation_id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class UpdateConversationResponse(_message.Message):
    __slots__ = ("conversation",)
    CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    conversation: Conversation
    def __init__(self, conversation: _Optional[_Union[Conversation, _Mapping]] = ...) -> None: ...

class DeleteConversationRequest(_message.Message):
    __slots__ = ("conversation_id",)
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    def __init__(self, conversation_id: _Optional[str] = ...) -> None: ...

class DeleteConversationResponse(_message.Message):
    __slots__ = ("message", "success")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    message: str
    success: bool
    def __init__(self, message: _Optional[str] = ..., success: bool = ...) -> None: ...

class DeleteConversationsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeleteConversationsResponse(_message.Message):
    __slots__ = ("message", "success")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    message: str
    success: bool
    def __init__(self, message: _Optional[str] = ..., success: bool = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("message_id", "question", "type", "content", "conversation_id", "created_at", "updated_at")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    QUESTION_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    question: str
    type: str
    content: str
    conversation_id: str
    created_at: str
    updated_at: str
    def __init__(self, message_id: _Optional[str] = ..., question: _Optional[str] = ..., type: _Optional[str] = ..., content: _Optional[str] = ..., conversation_id: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class GetMessagesRequest(_message.Message):
    __slots__ = ("conversation_id",)
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    def __init__(self, conversation_id: _Optional[str] = ...) -> None: ...

class GetMessagesResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    def __init__(self, messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ...) -> None: ...

class CreateMessageRequest(_message.Message):
    __slots__ = ("question", "conversation_id", "is_create_conversation")
    QUESTION_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    IS_CREATE_CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    question: str
    conversation_id: str
    is_create_conversation: bool
    def __init__(self, question: _Optional[str] = ..., conversation_id: _Optional[str] = ..., is_create_conversation: bool = ...) -> None: ...

class CreateMessageResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: Message
    def __init__(self, message: _Optional[_Union[Message, _Mapping]] = ...) -> None: ...

class UpdateMessageRequest(_message.Message):
    __slots__ = ("conversation_id", "message_id", "question")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    QUESTION_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    message_id: str
    question: str
    def __init__(self, conversation_id: _Optional[str] = ..., message_id: _Optional[str] = ..., question: _Optional[str] = ...) -> None: ...

class UpdateMessageResponse(_message.Message):
    __slots__ = ("message",)
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    message: Message
    def __init__(self, message: _Optional[_Union[Message, _Mapping]] = ...) -> None: ...

class DeleteMessageRequest(_message.Message):
    __slots__ = ("conversation_id", "message_id")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    conversation_id: str
    message_id: str
    def __init__(self, conversation_id: _Optional[str] = ..., message_id: _Optional[str] = ...) -> None: ...

class DeleteMessageResponse(_message.Message):
    __slots__ = ("message", "success")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    message: str
    success: bool
    def __init__(self, message: _Optional[str] = ..., success: bool = ...) -> None: ...

class MCPServer(_message.Message):
    __slots__ = ("config", "active", "error")
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    config: _struct_pb2.Struct
    active: bool
    error: str
    def __init__(self, config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., active: bool = ..., error: _Optional[str] = ...) -> None: ...

class GetMCPServersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMCPServersResponse(_message.Message):
    __slots__ = ("servers", "mcp_config_json")
    SERVERS_FIELD_NUMBER: _ClassVar[int]
    MCP_CONFIG_JSON_FIELD_NUMBER: _ClassVar[int]
    servers: _containers.RepeatedCompositeFieldContainer[MCPServer]
    mcp_config_json: str
    def __init__(self, servers: _Optional[_Iterable[_Union[MCPServer, _Mapping]]] = ..., mcp_config_json: _Optional[str] = ...) -> None: ...

class AddMCPServersRequest(_message.Message):
    __slots__ = ("mcp_config",)
    MCP_CONFIG_FIELD_NUMBER: _ClassVar[int]
    mcp_config: _struct_pb2.Struct
    def __init__(self, mcp_config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class AddMCPServersResponse(_message.Message):
    __slots__ = ("servers", "success", "error", "mcp_config_json")
    SERVERS_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    MCP_CONFIG_JSON_FIELD_NUMBER: _ClassVar[int]
    servers: _containers.RepeatedCompositeFieldContainer[MCPServer]
    success: bool
    error: str
    mcp_config_json: str
    def __init__(self, servers: _Optional[_Iterable[_Union[MCPServer, _Mapping]]] = ..., success: bool = ..., error: _Optional[str] = ..., mcp_config_json: _Optional[str] = ...) -> None: ...

class UpdateMCPServersRequest(_message.Message):
    __slots__ = ("mcp_config",)
    MCP_CONFIG_FIELD_NUMBER: _ClassVar[int]
    mcp_config: _struct_pb2.Struct
    def __init__(self, mcp_config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class UpdateMCPServersResponse(_message.Message):
    __slots__ = ("servers", "success", "mcp_config_json")
    SERVERS_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MCP_CONFIG_JSON_FIELD_NUMBER: _ClassVar[int]
    servers: _containers.RepeatedCompositeFieldContainer[MCPServer]
    success: bool
    mcp_config_json: str
    def __init__(self, servers: _Optional[_Iterable[_Union[MCPServer, _Mapping]]] = ..., success: bool = ..., mcp_config_json: _Optional[str] = ...) -> None: ...

class DeleteMCPServersRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class DeleteMCPServersResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...
