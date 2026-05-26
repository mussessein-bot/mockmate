import io
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.api.schemas import ParsePDFResponse

router = APIRouter()


@router.post("/parse-pdf", response_model=ParsePDFResponse)
async def parse_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB guard
        raise HTTPException(status_code=413, detail="PDF too large (max 10 MB)")

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n".join(pages).strip()
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber not installed on server")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse PDF: {e}")

    if not text:
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    return ParsePDFResponse(text=text)
