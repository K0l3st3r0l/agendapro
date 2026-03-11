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
        parts.append("""REGLAS IMPORTANTES PARA ACTIVIDADES CON IMÁGENES:
1. Cuando una actividad necesite que el alumno observe imágenes/dibujos, incluye un campo "image_words" con la lista COMPLETA de palabras cuyas imágenes se mostrarán.
2. Las image_words deben ser sustantivos concretos y visuales (animales, objetos, frutas, etc.) que se puedan encontrar fácilmente como imagen.
3. El texto de la actividad NO debe listar las palabras con asteriscos (*), viñetas, ni comas. Solo describe la instrucción.
4. Si la actividad pide "pinta" o "colorea", agrega "image_style": "coloring" al item.
5. Cada item de content que sea un objeto DEBE tener un campo "number" con su número secuencial (1, 2, 3...). NO incluyas el número dentro del campo "text".
6. NUNCA uses una sola letra como palabra en image_words (como "P" o "M"). Usa siempre la palabra completa.
7. Asegúrate de que TODAS las palabras en image_words estén coherentemente relacionadas con la instrucción de la actividad.

Ejemplo correcto:
{"number": 1, "text": "Pinta la imagen que empieza con el sonido de la letra A.", "image_words": ["abeja", "sol", "araña", "mesa"], "image_style": "coloring"}
{"number": 2, "text": "Une cada imagen con la letra de su sonido inicial.", "image_words": ["pato", "mesa", "luna"]}""")
    elif req.doc_type == "planificacion":
        parts.append("Incluye: objetivos de aprendizaje, habilidades, actitudes, inicio-desarrollo-cierre, evaluación.")
    elif req.doc_type == "ficha":
        parts.append("Incluye datos del estudiante, sección de contenidos y actividades prácticas.")
    if req.instructions:
        parts.append(f"Instrucciones adicionales: {req.instructions}")
    parts.append("""
REGLAS GLOBALES DE FORMATO:
- Cada item de contenido que sea un objeto DEBE tener "number" con su número secuencial.
- NO incluyas el número dentro del texto (no "1. Actividad 1", solo "Actividad 1" y number: 1).
- Asegúrate de que el documento sea coherente: si mencionas "mira el dibujo de X", entonces X DEBE estar en image_words.

Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{
  "title": "título del documento",
  "instructions": "instrucciones para el alumno",
  "sections": [
    {
      "type": "header|text|questions|activities|answers",
      "title": "título de sección (opcional)",
      "content": "texto o lista de objetos con campos: number, text, image_words (opcional), image_style (opcional), options (opcional), answer (opcional), points (opcional)"
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

async def generate_with_gemini(prompt: str, google_key: str, model: str = "gemini-2.0-flash") -> dict:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=google_key)
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.7,
                max_output_tokens=8000,
            )
        )
        return json.loads(response.text)
    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "INVALID_ARGUMENT" in err:
            raise HTTPException(status_code=400, detail="Google API Key inválida o sin permisos. Verifica tu clave en Configuración.")
        if "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            raise HTTPException(status_code=429, detail="Cuota de Google Gemini agotada. Intenta más tarde o usa otro proveedor.")
        raise HTTPException(status_code=500, detail=f"Error con Google Gemini ({model}): {err}")


async def generate_image_with_gemini(prompt: str, google_key: str, model: str = "gemini-2.0-flash-preview-image-generation") -> List[str]:
    try:
        from google import genai
        from google.genai import types
        import logging
        logger = logging.getLogger(__name__)
        client = genai.Client(api_key=google_key)
        response = client.models.generate_content(
            model=model,
            contents=[f"Crea una ilustración educativa colorida y clara para niños sobre: {prompt}"],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            )
        )
        images = []
        parts = response.candidates[0].content.parts
        logger.warning(f"IMAGE PARTS COUNT: {len(parts)}")
        for i, part in enumerate(parts):
            logger.warning(f"PART {i}: type={type(part)}, attrs={[a for a in dir(part) if not a.startswith('_')]}")
            logger.warning(f"PART {i}: has inline_data={hasattr(part, 'inline_data')}, inline_data={getattr(part, 'inline_data', None) is not None}")
            if hasattr(part, 'inline_data') and part.inline_data:
                logger.warning(f"PART {i}: mime_type={getattr(part.inline_data, 'mime_type', 'NONE')}, data_len={len(part.inline_data.data) if part.inline_data.data else 0}")
                if part.inline_data.data:
                    raw = part.inline_data.data
                    # google-genai may return data as base64-encoded bytes or raw binary
                    if isinstance(raw, bytes) and not raw[:4].startswith(b'\x89PNG') and not raw[:2].startswith(b'\xff\xd8'):
                        # Likely already base64-encoded bytes — try to decode first
                        try:
                            decoded = base64.b64decode(raw)
                            if decoded[:4].startswith(b'\x89PNG') or decoded[:2].startswith(b'\xff\xd8'):
                                b64 = raw.decode() if isinstance(raw, bytes) else raw
                            else:
                                b64 = base64.b64encode(raw).decode()
                        except Exception:
                            b64 = base64.b64encode(raw).decode()
                    else:
                        b64 = base64.b64encode(raw).decode()
                    images.append(f"data:{part.inline_data.mime_type};base64,{b64}")
        logger.warning(f"IMAGES FOUND: {len(images)}")
        return images
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"IMAGE GENERATION ERROR: {type(e).__name__}: {e}")
        return []


async def generate_with_openai(prompt: str, openai_key: str, model: str = "gpt-4o") -> dict:
    try:
        import openai as openai_lib
        client = openai_lib.OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except openai_lib.AuthenticationError:
        raise HTTPException(status_code=400, detail="OpenAI API Key inválida. Verifica tu clave en Configuración.")
    except openai_lib.RateLimitError:
        raise HTTPException(status_code=429, detail="Límite de OpenAI alcanzado. Intenta más tarde o usa Google Gemini.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error con OpenAI ({model}): {str(e)}")


async def generate_with_xai(prompt: str, xai_key: str, model: str = "grok-3-mini") -> dict:
    try:
        import openai as openai_lib
        client = openai_lib.OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=8000,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except openai_lib.AuthenticationError:
        raise HTTPException(status_code=400, detail="xAI API Key inválida. Verifica tu clave de Grok en Configuración.")
    except openai_lib.RateLimitError:
        raise HTTPException(status_code=429, detail="Límite de xAI/Grok alcanzado. Intenta más tarde.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error con Grok ({model}): {str(e)}")


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
# Post-generation validation & cleanup
# ---------------------------------------------------------------------------

def _validate_and_fix_content(content: dict) -> dict:
    """Fix common AI generation issues before sending to frontend."""
    import re

    sections = content.get("sections", [])
    global_counter = 0

    for sec in sections:
        items = sec.get("content")
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            global_counter += 1
            text = item.get("text") or item.get("question") or item.get("activity") or ""

            # Fix 1: Remove leading number from text if item has "number" field
            # e.g. "1. Actividad 1: ..." -> "Actividad 1: ..."
            cleaned = re.sub(r'^\d+[\.\)\-]\s*', '', text).strip()
            if item.get("text"):
                item["text"] = cleaned
            elif item.get("question"):
                item["question"] = cleaned
            elif item.get("activity"):
                item["activity"] = cleaned

            # Fix 2: Ensure sequential numbering
            item["number"] = global_counter

            # Fix 3: Filter out single-letter image_words
            if "image_words" in item and isinstance(item["image_words"], list):
                item["image_words"] = [w for w in item["image_words"] if len(w.strip()) > 1]

            # Fix 4: Extract image_words from text if missing but text has inline lists
            if "image_words" not in item or not item.get("image_words"):
                extracted = []
                # Pattern: "* Word1 * Word2"
                asterisk_match = re.findall(r'\*\s+([A-ZÁÉÍÓÚÑa-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+)?)', text)
                if len(asterisk_match) >= 2:
                    extracted = [w.strip().lower() for w in asterisk_match]
                # Pattern: "Dibujos: word1, word2"
                dibujos_match = re.search(r'(?:dibujos|figuras|imágenes?\s+sugeridas?)\s*[:\-]\s*(.+)', text, re.IGNORECASE)
                if dibujos_match:
                    extracted = [w.strip().lower() for w in re.split(r'[,;]', dibujos_match.group(1)) if len(w.strip()) > 1]
                if extracted:
                    item["image_words"] = extracted
                    # Clean the text
                    cleaned_text = item.get("text") or item.get("question") or item.get("activity") or ""
                    cleaned_text = re.sub(r'(?:\s*\*\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+)?)+\s*$', '', cleaned_text).strip()
                    cleaned_text = re.sub(r'\(\s*(?:dibujos|figuras|imágenes?\s+sugeridas?)\s*[:\-][^)]+\)', '', cleaned_text, flags=re.IGNORECASE).strip()
                    cleaned_text = re.sub(r'(?:dibujos|figuras|imágenes?\s+sugeridas?)\s*[:\-]\s*.+$', '', cleaned_text, flags=re.IGNORECASE).strip()
                    if item.get("text"):
                        item["text"] = cleaned_text
                    elif item.get("question"):
                        item["question"] = cleaned_text
                    elif item.get("activity"):
                        item["activity"] = cleaned_text

            # Fix 5: Detect coloring style from text
            if not item.get("image_style"):
                lower_text = text.lower()
                if any(kw in lower_text for kw in ["pinta", "colorea", "colorear", "pintar", "color"]):
                    item["image_style"] = "coloring"

    return content


# ---------------------------------------------------------------------------
# Main generate endpoint
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_document(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    openai_key, google_key, preferred, xai_key, gemini_model, openai_model, xai_model, gemini_image_model = get_user_settings(current_user.id, db)
    requested = req.provider if req.provider and req.provider != "auto" else None
    provider = requested or preferred

    if not openai_key and not google_key and not xai_key:
        raise HTTPException(
            status_code=503,
            detail="No hay API keys configuradas. Ve a Configuración para agregar tu clave de Google Gemini, xAI (Grok) u OpenAI."
        )

    # Fallback: if chosen provider has no key, switch to another available one
    if provider == "gemini" and not google_key:
        provider = "xai" if xai_key else ("openai" if openai_key else None)
    elif provider == "xai" and not xai_key:
        provider = "gemini" if google_key else ("openai" if openai_key else None)
    elif provider == "openai" and not openai_key:
        provider = "gemini" if google_key else ("xai" if xai_key else None)

    if not provider:
        raise HTTPException(status_code=503, detail="Configura al menos una API Key en Configuración")

    prompt = build_prompt(req)
    image_prompt = f"{req.subject}, nivel {req.grade_level}, tema: {req.topic}"

    if provider == "gemini":
        content = await generate_with_gemini(prompt, google_key, gemini_model)
    elif provider == "xai":
        content = await generate_with_xai(prompt, xai_key, xai_model)
    else:
        content = await generate_with_openai(prompt, openai_key, openai_model)

    # ── Post-generation validation & cleanup ──────────────────────────────
    content = _validate_and_fix_content(content)
    # ──────────────────────────────────────────────────────────────────────

    images = []
    should_generate_image = req.include_images or req.doc_type in ["guia", "ficha"]
    if should_generate_image:
        if provider == "gemini" and google_key:
            images = await generate_image_with_gemini(image_prompt, google_key, gemini_image_model)
        elif openai_key:
            images = await generate_image_with_openai(image_prompt, openai_key)

    return {"content": content, "prompt": prompt, "images": images, "provider_used": provider, "model_used": gemini_model if provider == "gemini" else (xai_model if provider == "xai" else openai_model)}

# ---------------------------------------------------------------------------
# Improve endpoint
# ---------------------------------------------------------------------------

@router.post("/improve")
async def improve_content(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    openai_key, google_key, preferred, xai_key, gemini_model, openai_model, xai_model, gemini_image_model = get_user_settings(current_user.id, db)
    provider = data.get("provider") or preferred
    original = data.get("content", "")
    instruction = data.get("instruction", "Mejora este contenido educativo")
    improve_prompt = f"{instruction}:\n\n{original}\n\nResponde en JSON con la misma estructura."

    if provider == "gemini" and google_key:
        return await generate_with_gemini(improve_prompt, google_key, gemini_model)
    elif provider == "xai" and xai_key:
        return await generate_with_xai(improve_prompt, xai_key, xai_model)
    elif openai_key:
        return await generate_with_openai(improve_prompt, openai_key, openai_model)
    elif xai_key:
        return await generate_with_xai(improve_prompt, xai_key, xai_model)
    else:
        raise HTTPException(status_code=503, detail="Configura al menos una API Key en Configuración")

# ---------------------------------------------------------------------------
# Optimize instructions endpoint
# ---------------------------------------------------------------------------

@router.post("/optimize-instructions")
async def optimize_instructions(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    openai_key, google_key, preferred, xai_key, gemini_model, openai_model, xai_model, gemini_image_model = get_user_settings(current_user.id, db)
    provider = preferred

    raw = data.get("instructions", "").strip()
    doc_type = data.get("doc_type", "")
    subject = data.get("subject", "")
    grade_level = data.get("grade_level", "")
    topic = data.get("topic", "")

    if not raw:
        raise HTTPException(status_code=400, detail="Escribe algo en las instrucciones primero")

    optimize_prompt = f"""Eres un experto en ingeniería de prompts y diseño instruccional para modelos de lenguaje.

CONTEXTO DEL DOCUMENTO A GENERAR:
- Tipo: {doc_type}
- Asignatura: {subject}
- Nivel escolar: {grade_level}
- Tema: {topic}

INSTRUCCIONES SIMPLES DEL USUARIO:
\"\"\"{raw}\"\"\"

TU TAREA:
Transforma esas instrucciones simples en un prompt técnico detallado y específico que extraiga el máximo potencial del modelo de IA al generar el documento educativo. No te limites a parafrasear — EXPANDE y ENRIQUECE con:
- Nivel cognitivo explícito según Taxonomía de Bloom (recordar, comprender, aplicar, analizar, evaluar, crear)
- Especificaciones pedagógicas concretas: tipo de preguntas (abiertas, cerradas, de análisis, situacionales), enfoque didáctico, habilidades a desarrollar
- Restricciones o requisitos de formato que mejoren la calidad (longitud, tono, complejidad léxica apropiada al nivel)
- Criterios de calidad específicos para ese tipo de documento
- Cualquier consideración disciplinar relevante para {subject}

FORMATO DE RESPUESTA: Un bloque de texto continuo de 2 a 4 oraciones, en español, sin títulos, sin viñetas, sin comillas. Directo y técnico, listo para usarse como instrucción adicional."""

    try:
        if provider == "gemini" and google_key:
            result = await generate_with_gemini(optimize_prompt, google_key, gemini_model)
            # generate_with_gemini returns dict (JSON), but here we want plain text
            # So we call the API directly for plain text response
            raise ValueError("use_plain")
        raise ValueError("use_plain")
    except (ValueError, Exception):
        # Call directly for plain text
        try:
            if google_key:
                from google import genai
                from google.genai import types as gtypes
                client = genai.Client(api_key=google_key)
                response = client.models.generate_content(
                    model=gemini_model,
                    contents=[optimize_prompt],
                    config=gtypes.GenerateContentConfig(
                        temperature=0.5,
                        max_output_tokens=2000,
                    )
                )
                return {"optimized": response.text.strip()}
            elif openai_key:
                import openai as openai_lib
                client = openai_lib.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model=openai_model,
                    messages=[{"role": "user", "content": optimize_prompt}],
                    temperature=0.5,
                    max_tokens=2000,
                )
                return {"optimized": response.choices[0].message.content.strip()}
            elif xai_key:
                import openai as openai_lib
                client = openai_lib.OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
                response = client.chat.completions.create(
                    model=xai_model,
                    messages=[{"role": "user", "content": optimize_prompt}],
                    temperature=0.5,
                    max_tokens=2000,
                )
                return {"optimized": response.choices[0].message.content.strip()}
            else:
                raise HTTPException(status_code=503, detail="Configura al menos una API Key en Configuración")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al optimizar: {str(e)}")

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

class SaveToCalendarRequest(BaseModel):
    title: Optional[str] = None
    doc_type: str
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    content: Optional[dict] = None
    ai_prompt: Optional[str] = None
    images: Optional[list] = None
    event_date: str  # ISO date string e.g. "2026-03-15"

@router.post("/save-to-calendar", response_model=dict)
async def save_to_calendar(
    data: SaveToCalendarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.event import Event
    from datetime import datetime

    # 1. Save document
    db_doc = Document(
        user_id=current_user.id,
        title=data.title or f"{data.doc_type} - {data.subject}",
        doc_type=data.doc_type,
        subject=data.subject,
        grade_level=data.grade_level,
        content=data.content,
        ai_prompt=data.ai_prompt,
        images=data.images or [],
    )
    db.add(db_doc)
    db.flush()  # get id without commit

    # 2. Map doc_type to event category and color
    category_map = {
        "prueba": "evaluacion",
        "evaluacion": "evaluacion",
        "planificacion": "planificacion",
        "guia": "general",
        "ficha": "general",
    }
    color_map = {
        "evaluacion": "#EF4444",
        "planificacion": "#10B981",
        "general": "#6B7280",
    }
    category = category_map.get(data.doc_type, "general")
    color = color_map.get(category, "#6B7280")

    # 3. Create calendar event for that day (all_day)
    try:
        event_dt = datetime.fromisoformat(data.event_date)
    except Exception:
        event_dt = datetime.utcnow()

    db_event = Event(
        user_id=current_user.id,
        title=db_doc.title,
        description=f"[doc_id:{db_doc.id}] {data.subject or ''} - {data.grade_level or ''}".strip(" -"),
        start_datetime=event_dt,
        end_datetime=event_dt,
        all_day=True,
        color=color,
        category=category,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_doc)
    db.refresh(db_event)

    return {"doc_id": db_doc.id, "event_id": db_event.id, "message": "Documento guardado y agregado al calendario"}


@router.post("/search-images")
async def search_images_endpoint(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate images for a small batch of words using Gemini.
    Accepts max 3 words per request to avoid timeouts.
    Frontend calls this repeatedly in batches with progress tracking.
    Returns {word: url} mapping.
    """
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    words = data.get("words", [])
    style = data.get("style", "photo")
    results = {}

    # Accept max 3 words per request to stay well under timeout limits
    words = [w for w in words[:3] if isinstance(w, str) and len(w.strip()) > 1]
    if not words:
        return {"images": results}

    openai_key, google_key, preferred, xai_key, gemini_model, openai_model, xai_model, gemini_image_model = get_user_settings(current_user.id, db)
    if not google_key:
        return {"images": results}

    import uuid, os
    import base64 as b64mod
    os.makedirs("/app/static/images", exist_ok=True)

    async def generate_one(word: str):
        try:
            if style == "coloring":
                prompt = (f"Genera un dibujo para colorear de: {word}. "
                         f"Líneas negras simples sobre fondo blanco puro. "
                         f"Solo el objeto '{word}', sin texto, sin fondo decorativo. "
                         f"Estilo libro de colorear infantil.")
            else:
                prompt = (f"Genera una ilustración educativa simple y clara de: {word}. "
                         f"Estilo clipart infantil colorido. Solo el objeto '{word}' centrado, "
                         f"fondo blanco puro. Sin texto, sin otros objetos. "
                         f"La imagen debe representar EXACTAMENTE '{word}' y nada más.")
            imgs = await generate_image_with_gemini(prompt, google_key, gemini_image_model)
            if imgs:
                data_uri = imgs[0]
                hdr, b64data = data_uri.split(",", 1)
                mime = hdr.split(";")[0].replace("data:", "")
                ext = mime.split("/")[-1] if "/" in mime else "png"
                filename = f"activity_{uuid.uuid4().hex[:12]}.{ext}"
                filepath = f"/app/static/images/{filename}"
                with open(filepath, "wb") as f:
                    f.write(b64mod.b64decode(b64data))
                logger.info(f"SEARCH-IMAGES: Generated image for '{word}' -> {filename}")
                return (word, f"/static/images/{filename}")
        except Exception as e:
            logger.warning(f"SEARCH-IMAGES: Failed to generate '{word}': {e}")
        return (word, None)

    # Generate all words in this batch concurrently (max 3)
    tasks = [generate_one(w) for w in words]
    done = await asyncio.gather(*tasks, return_exceptions=True)
    for item in done:
        if isinstance(item, tuple) and item[1]:
            results[item[0]] = item[1]

    logger.info(f"SEARCH-IMAGES: Batch done {len(results)}/{len(words)}")
    return {"images": results}


@router.post("/generate-image")
async def generate_image_endpoint(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Genera una imagen ilustrativa y la guarda en disco, retorna su URL."""
    import uuid, os
    openai_key, google_key, preferred, xai_key, gemini_model, openai_model, xai_model, gemini_image_model = get_user_settings(current_user.id, db)

    subject = data.get("subject", "")
    grade_level = data.get("grade_level", "")
    topic = data.get("topic", "")
    prompt = f"{subject}, nivel {grade_level}, tema: {topic}"

    if not google_key:
        raise HTTPException(status_code=503, detail="Se requiere API Key de Google para generar imágenes")

    images_b64 = await generate_image_with_gemini(prompt, google_key, gemini_image_model)
    if not images_b64:
        raise HTTPException(status_code=500, detail="No se pudo generar la imagen")

    # Parse data URI and save to disk
    data_uri = images_b64[0]
    # format: data:image/png;base64,<data>
    header, b64data = data_uri.split(",", 1)
    mime = header.split(";")[0].replace("data:", "")
    ext = mime.split("/")[-1] if "/" in mime else "png"

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = f"/app/static/images/{filename}"
    os.makedirs("/app/static/images", exist_ok=True)

    import base64 as b64mod
    with open(filepath, "wb") as f:
        f.write(b64mod.b64decode(b64data))

    return {"image_url": f"/static/images/{filename}"}


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


# ---------------------------------------------------------------------------
# Export endpoints (PDF / DOCX)
# ---------------------------------------------------------------------------

def _strip_md(text) -> str:
    """Remove common markdown markers for plain-text export."""
    import re
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    return text.strip()


@router.post("/export-pdf")
async def export_pdf(
    data: dict,
    current_user: User = Depends(get_current_user)
):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from fastapi.responses import StreamingResponse
    import io, os

    content = data.get("content", {})
    activity_images: dict = data.get("activity_images", {})  # {word: "/static/images/xxx.png"}
    title = _strip_md(content.get("title", "Documento"))
    metadata = content.get("metadata", {})
    instructions = content.get("instructions", "")
    sections = content.get("sections", [])

    def get_image_flowable(word: str, size_mm: float = 28):
        """Return a ReportLab Image flowable for a word, or None if not found."""
        url = activity_images.get(word.lower().strip(), "")
        if not url:
            return None
        # Convert /static/images/foo.png -> /app/static/images/foo.png
        filepath = "/app" + url if url.startswith("/static/") else None
        if filepath and os.path.exists(filepath):
            try:
                img = RLImage(filepath, width=size_mm*mm, height=size_mm*mm)
                return img
            except Exception:
                pass
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, alignment=TA_CENTER, spaceAfter=4)
    story.append(Paragraph(title.upper(), title_style))

    # Metadata row
    if metadata:
        meta_parts = []
        if metadata.get("subject"): meta_parts.append(f"<b>Asignatura:</b> {metadata['subject']}")
        if metadata.get("grade"):   meta_parts.append(f"<b>Nivel:</b> {metadata['grade']}")
        if metadata.get("total_points"): meta_parts.append(f"<b>Puntaje:</b> {metadata['total_points']} pts")
        meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=6)
        story.append(Paragraph("   |   ".join(meta_parts), meta_style))

    # Student data row
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=6))
    student_data = [["Nombre: ________________________", "Curso: ______________", "Fecha: ______________"]]
    t = Table(student_data, colWidths=[90*mm, 50*mm, 50*mm])
    t.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # Instructions
    if instructions:
        inst_style = ParagraphStyle('Inst', parent=styles['Normal'], fontSize=10,
                                    backColor=colors.HexColor('#f9f9f9'),
                                    borderPadding=6, spaceAfter=8)
        story.append(Paragraph(f"<b>Instrucciones:</b> {_strip_md(instructions)}", inst_style))

    # Sections
    for sec in sections:
        sec_title = _strip_md(sec.get("title", ""))
        if sec_title:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=2))
            h_style = ParagraphStyle('SecH', parent=styles['Heading2'], fontSize=11, spaceAfter=4)
            story.append(Paragraph(sec_title, h_style))
        sec_content = sec.get("content", "")
        body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, spaceAfter=4, leading=14)
        if isinstance(sec_content, str):
            story.append(Paragraph(_strip_md(sec_content), body_style))
        elif isinstance(sec_content, list):
            for i, item in enumerate(sec_content):
                if isinstance(item, str):
                    story.append(Paragraph(f"{i+1}. {_strip_md(item)}", body_style))
                elif isinstance(item, dict):
                    q_text = item.get("text") or item.get("question") or item.get("activity") or item.get("description") or ""
                    pts = item.get("points") or ""
                    num = item.get("number", i+1)
                    line = f"{num}. {_strip_md(q_text)}"
                    if pts: line += f"  <font size='8' color='grey'>({pts} pts)</font>"
                    story.append(Paragraph(line, ParagraphStyle('Q', parent=body_style, backColor=colors.HexColor('#f5f5f5'), borderPadding=5)))
                    # Embed activity images if present
                    img_words = item.get("image_words", [])
                    if img_words:
                        img_cells = []
                        label_cells = []
                        for w in img_words:
                            img_fl = get_image_flowable(w, size_mm=24)
                            img_cells.append(img_fl if img_fl else Paragraph("", body_style))
                            label_cells.append(Paragraph(f"<para align='center'><font size='8'>{w.capitalize()}</font></para>", body_style))
                        if img_cells:
                            col_w = 28 * mm
                            img_table = Table([img_cells, label_cells],
                                             colWidths=[col_w] * len(img_cells))
                            img_table.setStyle(TableStyle([
                                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                ('TOPPADDING', (0,0), (-1,-1), 3),
                                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                            ]))
                            story.append(img_table)
                            story.append(Spacer(1, 3*mm))
                    if item.get("options"):
                        for j, opt in enumerate(item["options"]):
                            ltr = chr(65 + j)
                            story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{ltr}) {_strip_md(opt)}", body_style))
                    if item.get("answer"):
                        story.append(Paragraph(f"<font color='green'>✓ {_strip_md(item['answer'])}</font>",
                                                ParagraphStyle('Ans', parent=body_style, fontSize=9)))
        story.append(Spacer(1, 4*mm))

    doc.build(story)
    buf.seek(0)
    safe_title = title.replace(" ", "_")[:50]
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'})


@router.post("/export-docx")
async def export_docx(
    data: dict,
    current_user: User = Depends(get_current_user)
):
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from fastapi.responses import StreamingResponse
    import io, os

    content = data.get("content", {})
    activity_images: dict = data.get("activity_images", {})
    title = _strip_md(content.get("title", "Documento"))
    metadata = content.get("metadata", {})
    instructions = content.get("instructions", "")
    sections = content.get("sections", [])

    docx = DocxDocument()

    # Page margins
    for section in docx.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)

    # Title
    h = docx.add_heading(title.upper(), level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Metadata
    if metadata:
        parts = []
        if metadata.get("subject"): parts.append(f"Asignatura: {metadata['subject']}")
        if metadata.get("grade"):   parts.append(f"Nivel: {metadata['grade']}")
        if metadata.get("total_points"): parts.append(f"Puntaje: {metadata['total_points']} pts")
        p = docx.add_paragraph("   |   ".join(parts))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs: run.font.size = Pt(10)

    docx.add_paragraph("─" * 80)

    # Student data table
    table = docx.add_table(rows=1, cols=3)
    cells = table.rows[0].cells
    cells[0].text = "Nombre: _______________________"
    cells[1].text = "Curso: _______________"
    cells[2].text = "Fecha: _______________"
    for cell in cells:
        for run in cell.paragraphs[0].runs:
            run.font.size = Pt(10)
    docx.add_paragraph("")

    # Instructions
    if instructions:
        p = docx.add_paragraph()
        r = p.add_run("Instrucciones: ")
        r.bold = True; r.font.size = Pt(10)
        r2 = p.add_run(_strip_md(instructions))
        r2.font.size = Pt(10)

    # Sections
    for sec in sections:
        sec_title = _strip_md(sec.get("title", ""))
        if sec_title:
            docx.add_heading(sec_title, level=2)
        sec_content = sec.get("content", "")
        if isinstance(sec_content, str):
            docx.add_paragraph(_strip_md(sec_content)).style.font.size = Pt(10)
        elif isinstance(sec_content, list):
            for i, item in enumerate(sec_content):
                if isinstance(item, str):
                    docx.add_paragraph(f"{i+1}. {_strip_md(item)}")
                elif isinstance(item, dict):
                    q_text = item.get("text") or item.get("question") or item.get("activity") or item.get("description") or ""
                    pts = item.get("points") or ""
                    num = item.get("number", i+1)
                    label = f"({pts} pts)" if pts else ""
                    p = docx.add_paragraph()
                    r = p.add_run(f"{num}. {_strip_md(q_text)} {label}")
                    r.font.size = Pt(10)
                    # Embed activity images
                    img_words = item.get("image_words", [])
                    if img_words:
                        img_table = docx.add_table(rows=2, cols=len(img_words))
                        for col_idx, w in enumerate(img_words):
                            url = activity_images.get(w.lower().strip(), "")
                            filepath = "/app" + url if url.startswith("/static/") else None
                            cell = img_table.cell(0, col_idx)
                            if filepath and os.path.exists(filepath):
                                try:
                                    p_img = cell.paragraphs[0]
                                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                    run_img = p_img.add_run()
                                    run_img.add_picture(filepath, width=Inches(0.9))
                                except Exception:
                                    cell.text = f"[{w}]"
                            else:
                                cell.text = f"[{w}]"
                            label_cell = img_table.cell(1, col_idx)
                            lp = label_cell.paragraphs[0]
                            lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            lr = lp.add_run(w.capitalize())
                            lr.font.size = Pt(8)
                        docx.add_paragraph("")
                    if item.get("options"):
                        for j, opt in enumerate(item["options"]):
                            op = docx.add_paragraph(f"    {chr(65+j)}) {_strip_md(opt)}")
                            op.paragraph_format.left_indent = Inches(0.3)
                    if item.get("answer"):
                        ap = docx.add_paragraph(f"✓ {_strip_md(item['answer'])}")
                        ap.runs[0].font.color.rgb = RGBColor(0x05, 0x96, 0x69)
                        ap.runs[0].font.size = Pt(9)

    buf = io.BytesIO()
    docx.save(buf)
    buf.seek(0)
    safe_title = title.replace(" ", "_")[:50]
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             headers={"Content-Disposition": f'attachment; filename="{safe_title}.docx"'})
