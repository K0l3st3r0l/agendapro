from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.document import Document
from app.models.user import User
from app.utils.auth import get_current_user
from app.api.settings import get_user_settings
import json
import base64

router = APIRouter(prefix="/api/constructor", tags=["constructor"])

SYSTEM_PROMPT = """Eres un experto en educación chilena y pedagogía.
Tu tarea es generar contenido educativo de alta calidad, adaptado al currículo chileno.
Siempre responde en español chileno, con lenguaje claro y adecuado al nivel educativo indicado.
Responde SIEMPRE con un JSON válido siguiendo exactamente la estructura que se te pide."""

DOC_TYPE_MAPPING = {
    "prueba":        "prueba de conocimientos",
    "evaluacion":    "evaluación sumativa",
    "guia":          "guía de trabajo",
    "planificacion": "planificación de clases",
    "ficha":         "ficha de actividades",
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    doc_type: str
    subject: str
    grade_level: str
    topic: str
    instructions: Optional[str] = None
    num_questions: Optional[int] = 10
    difficulty: Optional[str] = "medio"
    include_images: bool = False
    include_answers: bool = True
    provider: Optional[str] = None  # gemini | openai | None = use preferred

class DocumentSave(BaseModel):
    title: str
    doc_type: str
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    content: Optional[dict] = None
    raw_html: Optional[str] = None
    ai_prompt: Optional[str] = None
    images: Optional[list] = None

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(req: GenerateRequest) -> str:
    doc_name = DOC_TYPE_MAPPING.get(req.doc_type, req.doc_type)
    parts = [
        f"Crea una {doc_name} completa para la asignatura de {req.subject},",
        f"nivel {req.grade_level}, sobre el tema: '{req.topic}'.",
        f"Dificultad: {req.difficulty}.",
    ]
    if req.doc_type in ["prueba", "evaluacion"]:
        parts.append(f"Incluye {req.num_questions} preguntas variadas (selección múltiple, verdadero/falso, desarrollo).")
        if req.include_answers:
            parts.append("Incluye la pauta de corrección con las respuestas correctas y puntajes.")
    elif req.doc_type == "guia":
        parts.append(f"Incluye {req.num_questions} actividades o ejercicios.")
        parts.append("Incluye instrucciones claras para el estudiante.")
    elif req.doc_type == "planificacion":
        parts.append("Incluye: objetivos de aprendizaje, habilidades, actitudes, inicio-desarrollo-cierre, evaluación.")
    elif req.doc_type == "ficha":
        parts.append("Incluye datos del estudiante, sección de contenidos y actividades prácticas.")
    if req.instructions:
        parts.append(f"Instrucciones adicionales: {req.instructions}")
    parts.append("""
Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{
  "title": "título del documento",
  "instructions": "instrucciones para el alumno",
  "sections": [
    {
      "type": "header|text|questions|activities|answers",
      "title": "título de sección (opcional)",
      "content": "texto o lista de preguntas/actividades"
    }
  ],
  "metadata": {
    "subject": "asignatura",
    "grade": "nivel",
    "topic": "tema",
    "total_points": 100
  }
}""")
    return " ".join(parts)

# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

async def generate_with_gemini(prompt: str, google_key: str) -> dict:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=google_key)
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.7,
                max_output_tokens=4000,
            )
        )
        return json.loads(response.text)
    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "INVALID_ARGUMENT" in err:
            raise HTTPException(status_code=401, detail="Google API Key inválida o sin permisos")
        if "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            raise HTTPException(status_code=429, detail="Cuota de Google Gemini agotada. Intenta más tarde o usa OpenAI.")
        raise HTTPException(status_code=500, detail=f"Error con Google Gemini: {err}")


async def generate_image_with_gemini(prompt: str, google_key: str) -> List[str]:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=google_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[f"Generate an educational illustration: {prompt}"],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="1:1"),
            )
        )
        images = []
        for part in response.parts:
            if part.inline_data:
                b64 = base64.b64encode(part.inline_data.data).decode()
                images.append(f"data:{part.inline_data.mime_type};base64,{b64}")
        return images
    except Exception:
        return []


async def generate_with_openai(prompt: str, openai_key: str) -> dict:
    try:
        import openai as openai_lib
        client = openai_lib.OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except openai_lib.AuthenticationError:
        raise HTTPException(status_code=401, detail="OpenAI API Key inválida")
    except openai_lib.RateLimitError:
        raise HTTPException(status_code=429, detail="Límite de OpenAI alcanzado. Intenta más tarde o usa Google Gemini.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error con OpenAI: {str(e)}")


async def generate_image_with_openai(prompt: str, openai_key: str) -> List[str]:
    try:
        import openai as openai_lib
        client = openai_lib.OpenAI(api_key=openai_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Educational illustration for: {prompt}. Clean, colorful, child-friendly style.",
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return [response.data[0].url]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Main generate endpoint
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_document(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    openai_key, google_key, preferred = get_user_settings(current_user.id, db)
    provider = req.provider or preferred

    if not openai_key and not google_key:
        raise HTTPException(
            status_code=503,
            detail="No hay API keys configuradas. Ve a Configuración para agregar tu clave de Google Gemini u OpenAI."
        )

    # Fallback: if chosen provider has no key, switch to the other
    if provider == "gemini" and not google_key:
        provider = "openai" if openai_key else None
    elif provider == "openai" and not openai_key:
        provider = "gemini" if google_key else None

    if not provider:
        raise HTTPException(status_code=503, detail="Configura al menos una API Key en Configuración")

    prompt = build_prompt(req)
    image_prompt = f"{req.subject}, nivel {req.grade_level}, tema: {req.topic}"

    if provider == "gemini":
        content = await generate_with_gemini(prompt, google_key)
    else:
        content = await generate_with_openai(prompt, openai_key)

    images = []
    if req.include_images:
        if provider == "gemini" and google_key:
            images = await generate_image_with_gemini(image_prompt, google_key)
        elif openai_key:
            images = await generate_image_with_openai(image_prompt, openai_key)

    return {"content": content, "prompt": prompt, "images": images, "provider_used": provider}

# ---------------------------------------------------------------------------
# Improve endpoint
# ---------------------------------------------------------------------------

@router.post("/improve")
async def improve_content(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    openai_key, google_key, preferred = get_user_settings(current_user.id, db)
    provider = data.get("provider") or preferred
    original = data.get("content", "")
    instruction = data.get("instruction", "Mejora este contenido educativo")
    improve_prompt = f"{instruction}:\n\n{original}\n\nResponde en JSON con la misma estructura."

    if provider == "gemini" and google_key:
        return await generate_with_gemini(improve_prompt, google_key)
    elif openai_key:
        return await generate_with_openai(improve_prompt, openai_key)
    else:
        raise HTTPException(status_code=503, detail="Configura al menos una API Key en Configuración")

# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------

@router.post("/save", response_model=dict)
async def save_document(
    doc: DocumentSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_doc = Document(
        user_id=current_user.id,
        title=doc.title,
        doc_type=doc.doc_type,
        subject=doc.subject,
        grade_level=doc.grade_level,
        content=doc.content,
        raw_html=doc.raw_html,
        ai_prompt=doc.ai_prompt,
        images=doc.images or [],
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return {"id": db_doc.id, "message": "Documento guardado"}

@router.get("/documents")
def get_documents(
    doc_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Document).filter(Document.user_id == current_user.id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    docs = query.order_by(Document.created_at.desc()).all()
    return [
        {
            "id": d.id, "title": d.title, "doc_type": d.doc_type,
            "subject": d.subject, "grade_level": d.grade_level,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]

@router.get("/documents/{doc_id}")
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {
        "id": doc.id, "title": doc.title, "doc_type": doc.doc_type,
        "subject": doc.subject, "grade_level": doc.grade_level,
        "content": doc.content, "raw_html": doc.raw_html,
        "images": doc.images, "ai_prompt": doc.ai_prompt,
        "created_at": doc.created_at.isoformat(),
    }

@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    db.delete(doc)
    db.commit()
    return {"message": "Documento eliminado"}
