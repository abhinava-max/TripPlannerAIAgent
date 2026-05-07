from functools import lru_cache

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from .config import settings


@lru_cache
def get_embedding_model():
    return HuggingFaceEmbeddings(
        model_name=settings.HF_EMBEDDING_MODEL,
        model_kwargs={
            "token": settings.HF_TOKEN,
            "device": "cpu"
        },
        encode_kwargs={
            "normalize_embeddings": True
        }
    )


@lru_cache
def get_policy_vector_store():
    embeddings = get_embedding_model()

    return Chroma(
        collection_name=settings.POLICY_COLLECTION_NAME,
        persist_directory=settings.CHROMA_DB_PATH,
        embedding_function=embeddings
    )


def get_policy_retriever(k: int = 4):
    vector_store = get_policy_vector_store()

    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": k
        }
    )
