import os
from typing import Dict, List

import streamlit as st

from st_app.graph.router import build_graph
from st_app.utils.state import GraphState


def _bootstrap_api_keys_from_secrets() -> None:
    # Streamlit Cloud 권장: st.secrets 사용. 로컬에서 secrets.toml 없으면 무시하고 env만 사용
    upstage_key = None
    openai_key = None
    base_url = None
    try:
        _secrets = st.secrets  # 접근 시 파일 없으면 FileNotFoundError 발생 가능
        upstage_key = _secrets.get("UPSTAGE_API_KEY")
        openai_key = _secrets.get("OPENAI_API_KEY")
        base_url = _secrets.get("UPSTAGE_BASE_URL") or _secrets.get("OPENAI_BASE_URL")
    except FileNotFoundError:
        pass

    if upstage_key and not os.environ.get("UPSTAGE_API_KEY"):
        os.environ["UPSTAGE_API_KEY"] = upstage_key

    if openai_key and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = openai_key

    if base_url and not os.environ.get("UPSTAGE_BASE_URL") and not os.environ.get("OPENAI_BASE_URL"):
        # Upstage 우선 적용
        os.environ["UPSTAGE_BASE_URL"] = base_url


def init_session() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages: List[Dict[str, str]] = []
    if "graph" not in st.session_state:
        st.session_state.graph = build_graph()
    if "thread_id" not in st.session_state:
        import uuid
        st.session_state.thread_id = uuid.uuid4().hex


def main() -> None:
    st.set_page_config(page_title="RAG + Agent LangGraph 데모", page_icon="🤖")
    st.title("RAG + Agent LangGraph 데모")

    with st.sidebar:
        st.markdown("**환경 설정**")
        st.info(
            "Upstage 또는 OpenAI 키를 Streamlit Secrets에 설정하거나 환경변수로 설정하세요.\\n"
            "- Secrets/Env 키: `UPSTAGE_API_KEY` (권장) 또는 `OPENAI_API_KEY`\\n"
            "- (옵션) 베이스 URL: `UPSTAGE_BASE_URL` 또는 `OPENAI_BASE_URL`"
        )
        if st.button("대화 초기화"):
            st.session_state.messages = []
            st.rerun()

    _bootstrap_api_keys_from_secrets()
    init_session()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("메시지를 입력하세요…")
    if not user_input:
        return

    # 사용자 메시지 표시/저장
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # LangGraph 실행
    initial_state: GraphState = {
        "history": st.session_state.messages,
        "user_input": user_input,
        "route": "router",
        "subject": None,
        "citations": [],
        "response": "",
    }

    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    result_state: GraphState = st.session_state.graph.invoke(initial_state, config=config)
    answer = result_state.get("response", "")
    citations = result_state.get("citations", [])

    with st.chat_message("assistant"):
        st.markdown(answer if answer else "(응답이 비어 있습니다)")
        # 디버그 정보: 사용된 라우트/노드/주제
        debug_route = result_state.get("route")
        debug_node = result_state.get("last_node")
        debug_subject = result_state.get("subject")
        with st.expander("디버그: 라우팅 정보"):
            st.write({
                "route": debug_route,
                "last_node": debug_node,
                "subject": debug_subject,
            })
        if citations:
            with st.expander("참고 문서"):
                for c in citations:
                    st.markdown(f"- 출처: {c.get('source', 'unknown')} | id: {c.get('id', '')}")

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()

