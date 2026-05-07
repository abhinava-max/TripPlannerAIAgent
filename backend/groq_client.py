from functools import lru_cache

from langchain_groq import ChatGroq

from .config import settings


@lru_cache
def get_llm():
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in the environment")

    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0.3
    )
