from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import settings
from .policy_vector_store import get_policy_vector_store


def load_policy_documents():
    docs_path = Path(settings.POLICY_DOCS_PATH)
    if not docs_path.is_absolute():
        docs_path = Path(__file__).resolve().parent / docs_path

    docs_path.mkdir(parents=True, exist_ok=True)

    documents = []

    for file_path in docs_path.iterdir():
        if file_path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(file_path))
            loaded_docs = loader.load()

            for doc in loaded_docs:
                doc.metadata["source"] = file_path.name

            documents.extend(loaded_docs)

        elif file_path.suffix.lower() == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
            loaded_docs = loader.load()

            for doc in loaded_docs:
                doc.metadata["source"] = file_path.name

            documents.extend(loaded_docs)

    return documents


def ingest_policy_documents():
    documents = load_policy_documents()

    if not documents:
        return {
            "status": "no_documents",
            "message": "No PDF or TXT files found inside policy_docs folder."
        }

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )

    chunks = text_splitter.split_documents(documents)

    vector_store = get_policy_vector_store()
    vector_store.add_documents(chunks)

    return {
        "status": "success",
        "documents_loaded": len(documents),
        "chunks_created": len(chunks),
        "collection_name": settings.POLICY_COLLECTION_NAME,
        "chroma_path": settings.CHROMA_DB_PATH
    }


if __name__ == "__main__":
    result = ingest_policy_documents()
    print(result)
