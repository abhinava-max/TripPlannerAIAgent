from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..groq_client import get_llm
from ..ingest_policies import ingest_policy_documents
from ..policy_vector_store import get_policy_retriever


router = APIRouter(
    prefix="/policy",
    tags=["Policy RAG"]
)


class PolicyQuery(BaseModel):
    question: str


@router.post("/ingest")
def ingest_policies():
    try:
        return ingest_policy_documents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask")
def ask_policy_question(request: PolicyQuery):
    try:
        retriever = get_policy_retriever(k=4)
        docs = retriever.invoke(request.question)

        if not docs:
            return {
                "answer": "No relevant policy information found.",
                "sources": []
            }

        context = ""

        sources = []

        for doc in docs:
            source = doc.metadata.get("source", "Unknown source")
            page = doc.metadata.get("page", "Unknown page")

            context += f"""
Source: {source}
Page: {page}

Content:
{doc.page_content}

---
"""

            sources.append({
                "source": source,
                "page": page
            })

        prompt = f"""
You are a travel policy assistant.

Answer the user's question using ONLY the context below.
If the answer is not found in the context, say:
"I could not find this information in the uploaded policy documents."

Question:
{request.question}

Context:
{context}

Give a clear and concise answer.
Also mention important warnings if any.
"""

        response = get_llm().invoke(prompt)

        return {
            "question": request.question,
            "answer": response.content,
            "sources": sources
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
