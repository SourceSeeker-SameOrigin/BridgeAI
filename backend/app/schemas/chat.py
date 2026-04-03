from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    message: Optional[str] = None  # Simple string format (auto-converted to messages)
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = True
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def ensure_messages(self) -> "ChatRequest":
        """Accept both `messages` array and `message` string. Normalize to `messages`."""
        if not self.messages and self.message:
            self.messages = [ChatMessage(role="user", content=self.message)]
        if not self.messages:
            raise ValueError("Either 'messages' or 'message' must be provided")
        return self


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    id: str
    conversation_id: Optional[str] = None
    choices: List[ChatChoice]
    usage: Optional[ChatUsage] = None
    model: Optional[str] = None


class MessageSchema(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    model_used: Optional[str] = None
    token_input: int = 0
    token_output: int = 0
    created_at: str

    class Config:
        from_attributes = True
