import os
from typing import Optional

from langchain_openai import ChatOpenAI


def get_llm(model: Optional[str] = None, temperature: float = 0.3) -> ChatOpenAI:
    """
    기본 LLM 팩토리. OpenAI 호환 엔드포인트를 사용하며, 우선순위는 다음과 같습니다.
    1) UPSTAGE_API_KEY 가 설정되어 있으면 Upstage OpenAI-호환 엔드포인트 사용 (기본 base_url은 https://api.upstage.ai/v1)
    2) 아니면 OPENAI_API_KEY 가 있으면 해당 키/엔드포인트 사용

    모델 이름은 다음 우선순위를 따릅니다.
    - 인자 model → OPENAI_MODEL → UPSTAGE_MODEL → (기본) solar-1-mini-chat
    """
    upstage_key = os.getenv("UPSTAGE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # base_url 우선순위: 사용자가 지정한 값 우선
    base_url = (
        os.getenv("UPSTAGE_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or None
    )

    # Upstage 우선 사용
    api_key_to_use = upstage_key or openai_key
    if not api_key_to_use:
        raise RuntimeError(
            "OPENAI_API_KEY 또는 UPSTAGE_API_KEY 중 하나는 반드시 설정해야 합니다."
        )

    # Provider 별 기본 모델 설정
    if model:
        model_name = model
    else:
        model_name = (
            os.getenv("UPSTAGE_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "solar-1-mini-chat"
        )

    # Upstage 전용 기본 base_url
    if (not base_url) and (api_key_to_use == upstage_key):
        base_url = "https://api.upstage.ai/v1"

    return ChatOpenAI(api_key=api_key_to_use, base_url=base_url, model=model_name, temperature=temperature)

