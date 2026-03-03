from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.document import Document
from app.models.user import User
from app.utils.auth import get_current_user
import openai
import os
import json

router = APIRouter(prefix="/api/constructor", tags=["constructor"])

openai.api_key = os.getenv("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """Eres un experto en educación chilena y pedagogía. 
Tu tarea es generar contenido educativo de alta calidad, adaptado al currículo chileno.
Siempre responde en español chileno, con lenguaje claro y adecuado al nivel educativo indicado.
Cuando generes contenido estructurado, hazlo en formato JSON según se te indique."""

class GenerateRequest(BaseModel):
    doc_type: str          # prueba, evaluacion, guia, planificacion, ficha
    subject: str           # Matemáticas, Lenguaje, Ciencias, Historia, etc.
    grade_level: str       # 1°básico, 2°medio, etc.
    topic: str             # tema específico
    instructions: Optional[str] = None
    num_questions: Optional[int] = 10
    difficulty: Optional[str] = "medio"  # fácil, medio, difícil
    include_images: bool = False
    include_answers: bool = True

class DocumentSave(BaseModel):
    title: str
    doc_type: str
    subject: Optional[str]
    grade_level: Optional[str]
    content: Optional[dict]
    raw_html: Optional[str]
    ai_prompt: Optional[str]
    images: Optional[list]

class DocumentResponse(BaseModel):
    id: int
    title: str
    doc_type: str
    subject: Optional[str]
    grade_level: Optional[str]
    content: Optional[dict]
    raw_html: Optional[str]
    images: Optional[list]
    created_at: str
    class Config:
        from_attributes = True

DOC_TYPE_MAPPING = {
    "prueba": "prueba de conocimientos",
    "evaluacion": "evaluación sumativa",
    "guia": "guía de trabajo",
    "planificacion": "planificación de clases",
    "ficha": "ficha de actividades",
}

def build_prompt(req: GenerateRequest) -> str:
    doc_name = DOC_TYPE_MAPPING.get(req.doc_type, req.doc_type)
    prompt_parts = [
        f"Crea una {doc_name} completa para la asignatura de {req.subject},",
        f"nivel {req.grade_level}, sobre el tema: '{req.topic}'.",
        f"Dificultad: {req.difficulty}.",
    ]
    if req.doc_type in ["prueba", "evaluacion"]:
        prompt_parts.append(f"Incluye {req.num_questions} preguntas variadas (selección múltiple, verdadero/falso, desarrollo).")
        if req.include_answers:
            prompt_parts.append("Incluye la pauta de corrección con las respuestas correctas y puntajes.")
    elif req.doc_type == "guia":
        prompt_parts.append(f"Incluye {req.num_questions} actividades o ejercicios.")
        prompt_parts.append("Incluye instrucciones claras para el estudiante.")
    elif req.doc_type == "planificacion":
        prompt_parts.append("Incluye: objetivos de aprendizaje, habilidades, actitudes, inicio-desarrollo-cierre, evaluación.")
    elif req.doc_type == "ficha":
        prompt_parts.append("Incluye datos del estudiante, sección de contenidos y actividades prácticas.")

    if req.instructions:
        prompt_parts.append(f"Instrucciones adicionales: {req.instructions}")

    prompt_parts.append("""
Responde con un JSON con esta estructura:
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
    return " ".join(prompt_parts)

@router.post("/generate")
async def generate_document(
    req: GenerateRequest,
    current_user: User = Depends(get_current_user)
):
    if not openai.api_key:
        raise HTTPException(status_code=503, detail="API de IA no configurada. Agrega OPENAI_API_KEY al .env")

    prompt = build_prompt(req)
    try:
        client = openai.OpenAI(api_key=openai.api_key)
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
        content_str = response.choices[0].message.content
        content = json.loads(content_str)
    except openai.AuthenticationError:
        raise HTTPException(status_code=401, detail="API Key de OpenAI inválida")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar contenido: {str(e)}")

    images = []
    if req.include_images:
        try:
            image_prompt = f"Educational illustration for {req.subject}, grade {req.grade_level}, topic: {req.topic}. Clean, colorful, child-friendly style."
            img_response = client.images.generate(
                model="dall-e-3",
                prompt=image_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            images = [img_response.data[0].url]
        except Exception:
            images = []

    return {
        "content": content,
        "prompt": prompt,
        "images": images
    }

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
            "id": d.id,
            "title": d.title,
            "doc_type": d.doc_type,
            "subject": d.subject,
            "grade_level": d.grade_level,
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
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "subject": doc.subject,
        "grade_level": doc.grade_level,
        "content": doc.content,
        "raw_html": doc.raw_html,
        "images": doc.images,
        "ai_prompt": doc.ai_prompt,
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

@router.post("/improve")
async def improve_content(
    data: dict,
    current_user: User = Depends(get_current_user)
):
    """Improve or modify existing content with AI"""
    if not openai.api_key:
        raise HTTPException(status_code=503, detail="API de IA no configurada")

    original = data.get("content", "")
    instruction = data.get("instruction", "Mejora este contenido educativo")

    client = openai.OpenAI(api_key=openai.api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{instruction}:\n\n{original}\n\nResponde en JSON con la misma estructura."}
        ],
        temperature=0.5,
        max_tokens=3000,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)
