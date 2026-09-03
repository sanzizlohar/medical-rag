"""RAG query pipeline: retrieve relevant chunks, generate grounded answer with Gemini."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from . import config, ingest
from .schemas import SourceChunk

SYSTEM_PROMPT = """You are a careful medical information assistant. You answer questions \
using ONLY the context provided from the user's uploaded medical documents.

Rules:
1. Base your answer strictly on the provided context. If the context does not contain \
the answer, say: "I could not find this information in the uploaded documents."
2. Never invent facts, drug doses, or diagnoses.
3. If the question calls for it, structure the answer with short bullet points.
4. Cite the source in the format [Document Name, page N] when you use a specific chunk.
5. You provide general information only — always end with: \
"⚠️ This is general information from your documents, not medical advice. \
Please consult a qualified medical professional."
"""


def answer_question(question: str) -> dict:
    """Retrieve top chunks for the question and generate a grounded Gemini answer."""
    hits = ingest.search_all(question, k=config.TOP_K)

    if not hits:
        return {
            "answer": "No documents have been uploaded yet. Please upload a medical "
            "PDF first, then ask your question.",
            "sources": [],
        }

    context_blocks = []
    sources: list[SourceChunk] = []
    seen = set()
    for doc, _score in hits:
        meta = doc.metadata
        key = (meta["document_id"], meta["page"], doc.page_content[:80])
        if key in seen:
            continue
        seen.add(key)
        context_blocks.append(
            f"[Source: {meta['document_name']}, page {meta['page']}]\n{doc.page_content}"
        )
        sources.append(
            SourceChunk(
                document_id=meta["document_id"],
                document_name=meta["document_name"],
                page=meta["page"],
                text=doc.page_content,
            )
        )
    context = "\n\n---\n\n".join(context_blocks)

    llm = ChatGoogleGenerativeAI(
        model=config.GEMINI_MODEL,
        google_api_key=config.GOOGLE_API_KEY,
        temperature=0.2,
        max_retries=3,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                "Context from uploaded documents:\n\n{context}\n\n"
                "Question: {question}",
            ),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"context": context, "question": question})

    return {"answer": response.content, "sources": sources}
