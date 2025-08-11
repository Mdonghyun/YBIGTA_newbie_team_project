from typing import Dict, List, Literal, Optional, TypedDict, Any


class Message(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


class Citation(TypedDict, total=False):
    id: str
    source: str
    score: float
    snippet: str


class GraphState(TypedDict):
    history: List[Message]
    user_input: str
    route: Literal["router", "chat", "subject_info", "rag_review"]
    subject: Optional[str]
    citations: List[Citation]
    response: str
    last_node: Optional[Literal["chat", "subject_info", "rag_review"]]


def get_last_user_message(history: List[Message]) -> Optional[str]:
    for msg in reversed(history):
        if msg["role"] == "user":
            return msg["content"]
    return None

