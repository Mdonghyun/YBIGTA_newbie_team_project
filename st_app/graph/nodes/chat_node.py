from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.runnables import RunnableLambda

from st_app.rag.llm import get_llm
from st_app.rag.prompt import CHAT_SYSTEM_PROMPT
from st_app.utils.state import GraphState


def chat_node() -> RunnableLambda:
    prompt = ChatPromptTemplate.from_messages([
        ("system", CHAT_SYSTEM_PROMPT),
        MessagesPlaceholder("history"),
        ("human", "{user_input}"),
    ])
    llm = get_llm()
    chain = prompt | llm

    def _invoke(state: GraphState) -> GraphState:
        # 이전 노드가 이미 응답을 생성했으면 그대로 전달
        if state.get("response"):
            # route/last_node 보존
            return state
        def _to_messages() -> list[BaseMessage]:
            msgs = []
            for m in state.get("history", []):
                role = m.get("role")
                content = m.get("content", "")
                if not content:
                    continue
                if role == "user":
                    msgs.append(HumanMessage(content=content))
                elif role == "assistant":
                    msgs.append(AIMessage(content=content))
                elif role == "system":
                    msgs.append(SystemMessage(content=content))
            return msgs

        response = chain.invoke({
            "history": _to_messages(),
            "user_input": state.get("user_input", ""),
        })
        text = response.content if hasattr(response, "content") else str(response)
        state["response"] = text
        state["route"] = "chat"
        state["last_node"] = "chat"
        return state

    return RunnableLambda(_invoke)

