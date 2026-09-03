from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    pages: int
    ocr_pages: int = 0
    chunks: int


class SourceChunk(BaseModel):
    document_id: str
    document_name: str
    page: int
    text: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    pages: int
    ocr_pages: int = 0
    chunks: int
    uploaded_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]


class DeleteResponse(BaseModel):
    deleted: bool
    document_id: str
