import os
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider


def get_llm_model(use_capable: bool = False) -> OpenAIModel:
    """
    use_capable=False → mini model (routing, extraction, validation)
    use_capable=True  → capable model (detection, synthesis, report)
    Cost tiering per Agent Master Guide §4.6
    """
    model_name = (
        os.getenv("LLM_CHOICE_CAPABLE", "gpt-4o")
        if use_capable
        else os.getenv("LLM_CHOICE", "gpt-4o-mini")
    )
    return OpenAIModel(
        model_name,
        provider=OpenAIProvider(
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        ),
    )