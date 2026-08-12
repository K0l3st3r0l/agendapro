"""Capa única de proveedores de IA para texto.

Antes existían tres cadenas de selección de proveedor distintas —una en
`/generate`, otra en `/improve` y una tercera en `/optimize-instructions`—
que daban tres respuestas diferentes a la misma pregunta. Aquí hay una sola.

Todos los clientes son asíncronos. Los anteriores eran `async def` que por
dentro llamaban clientes bloqueantes, con dos efectos medibles: el
`asyncio.gather` de la generación de imágenes corría en serie, y con un solo
worker una generación congelaba el servidor entero — ni `/health` respondía.
"""

import json
import logging
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.api.settings import AISettings
from app.schemas.document import gemini_schema as documento_gemini_schema
from app.schemas.document import openai_schema as documento_openai_schema

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
XAI_BASE_URL = "https://api.x.ai/v1"

# Cabeceras de atribución que OpenRouter usa en su ranking público.
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://agendapro.laravas.com",
    "X-Title": "AgendaPro",
}

class InvalidJSONError(HTTPException):
    """El proveedor devolvió algo que no parsea como JSON.

    Es una `HTTPException` 502 —así el Constructor la sigue propagando igual que
    antes— pero con tipo propio para que quien quiera reintentar pueda
    distinguirla de un 402 sin créditos o un 401 de clave inválida, donde
    reintentar solo gasta tiempo y plata.
    """

    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=detail)


PROVIDER_LABELS = {
    "openrouter": "OpenRouter",
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "xai": "xAI (Grok)",
}


@dataclass
class GenerationResult:
    content: dict = field(default_factory=dict)
    text: str = ""
    provider: str = ""
    model: str = ""
    cost: float = 0.0
    # 'length' significa que se acabó `max_tokens` a mitad de la respuesta: el
    # JSON queda cortado y no parsea. Sin este dato, ese caso es indistinguible
    # de un modelo que devolvió basura, y se diagnostica mal.
    finish_reason: str = ""


# ---------------------------------------------------------------------------
# Selección de proveedor
# ---------------------------------------------------------------------------

def resolve_provider(settings: AISettings, requested: str | None = None) -> str:
    """Devuelve el proveedor a usar, o falla con un mensaje accionable.

    Orden: lo que pidió el usuario → su preferido → el primero con clave.
    """
    available = settings.available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail=(
                "No hay ninguna API key configurada. Ve a Configuración y agrega "
                "tu clave de OpenRouter para generar documentos e imágenes."
            ),
        )

    for candidate in (requested if requested and requested != "auto" else None, settings.preferred):
        if candidate in available:
            return candidate

    # El pedido o el preferido no tienen clave: se usa el primero disponible.
    return available[0]


def _fail(provider: str, model: str, exc: Exception) -> HTTPException:
    """Traduce el error del proveedor a algo que la profesora pueda accionar."""
    label = PROVIDER_LABELS.get(provider, provider)
    message = str(exc)
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)

    if status in (401, 403) or "API_KEY_INVALID" in message or "api key not valid" in message.lower():
        return HTTPException(
            status_code=400,
            detail=f"La API Key de {label} es inválida o caducó. Revísala en Configuración.",
        )
    if status == 402 or "insufficient" in message.lower() or "credit" in message.lower():
        return HTTPException(
            status_code=402,
            detail=f"{label} se quedó sin créditos. Recarga saldo para seguir generando.",
        )
    if status == 429 or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
        return HTTPException(
            status_code=429,
            detail=f"{label} alcanzó su límite de uso. Espera unos minutos o cambia de proveedor en Configuración.",
        )

    logger.exception("Fallo de %s con el modelo %s", provider, model)
    return HTTPException(status_code=502, detail=f"Error de {label} ({model}): {message}")


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

def _openai_compatible_client(api_key: str, base_url: str | None):
    from openai import AsyncOpenAI

    kwargs = {"api_key": api_key, "timeout": 180.0}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)


async def _chat_completion(
    *,
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str,
    system: str,
    prompt: str,
    schema: dict | None,
    max_tokens: int,
    temperature: float,
    schema_name: str = "documento_educativo",
) -> GenerationResult:
    client = _openai_compatible_client(api_key, base_url)

    request: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if schema is not None:
        request["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        }

    extra_headers = OPENROUTER_HEADERS if provider == "openrouter" else None
    # OpenRouter devuelve el costo real de la llamada si se lo pide.
    extra_body = {"usage": {"include": True}} if provider == "openrouter" else None

    try:
        response = await client.chat.completions.create(
            **request,
            extra_headers=extra_headers,
            extra_body=extra_body,
        )
    except Exception as exc:
        raise _fail(provider, model, exc) from exc

    choice = response.choices[0]
    text = (choice.message.content or "").strip()
    usage = getattr(response, "usage", None)
    cost = float(getattr(usage, "cost", 0.0) or 0.0) if usage else 0.0

    return GenerationResult(
        text=text,
        provider=provider,
        model=model,
        cost=cost,
        finish_reason=getattr(choice, "finish_reason", "") or "",
    )


async def _gemini_generate(
    *,
    api_key: str,
    model: str,
    system: str,
    prompt: str,
    schema: dict | None,
    max_tokens: int,
    temperature: float,
) -> GenerationResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config: dict = {
        "system_instruction": system,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_schema"] = schema

    try:
        # `client.aio` es el cliente asíncrono; el síncrono bloqueaba el event loop.
        response = await client.aio.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(**config),
        )
    except Exception as exc:
        raise _fail("gemini", model, exc) from exc

    return GenerationResult(text=(response.text or "").strip(), provider="gemini", model=model)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def generate_json(
    settings: AISettings,
    *,
    prompt: str,
    system: str,
    provider: str | None = None,
    max_tokens: int = 8000,
    temperature: float = 0.7,
    gemini_schema=documento_gemini_schema,
    openai_schema=documento_openai_schema,
    schema_name: str = "documento_educativo",
    openrouter_model: str = "",
) -> GenerationResult:
    """Genera JSON estructurado validado contra un esquema.

    El esquema llega por parámetro desde que las clases visuales necesitan uno
    propio; los defaults son los del Constructor para no tocar su llamada.

    `openrouter_model` fuerza un modelo distinto al configurado, y solo cuando
    la llamada sale por OpenRouter. Existe porque las clases visuales tienen un
    presupuesto de latencia que el modelo por defecto no cumple; si la profesora
    usa un proveedor directo, manda su configuración.
    """
    chosen = resolve_provider(settings, provider)
    model = settings.model_for(chosen)
    if openrouter_model and chosen == "openrouter":
        model = openrouter_model
    key = settings.key_for(chosen)

    if chosen == "gemini":
        result = await _gemini_generate(
            api_key=key,
            model=model,
            system=system,
            prompt=prompt,
            schema=gemini_schema(),
            max_tokens=max_tokens,
            temperature=temperature,
        )
    else:
        base_url = {"openrouter": OPENROUTER_BASE_URL, "xai": XAI_BASE_URL}.get(chosen)
        result = await _chat_completion(
            provider=chosen,
            api_key=key,
            base_url=base_url,
            model=model,
            system=system,
            prompt=prompt,
            schema=openai_schema(),
            schema_name=schema_name,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    try:
        result.content = json.loads(result.text)
    except json.JSONDecodeError as exc:
        label = PROVIDER_LABELS.get(chosen, chosen)
        if result.finish_reason == "length":
            detalle = (
                f"{label} se quedó sin espacio a mitad de la respuesta (max_tokens={max_tokens}) "
                f"y el JSON quedó cortado. Pide un contenido más corto o sube el límite."
            )
        else:
            detalle = f"{label} devolvió una respuesta que no es JSON válido."
        raise InvalidJSONError(detalle) from exc

    return result


async def generate_text(
    settings: AISettings,
    *,
    prompt: str,
    system: str = "",
    provider: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.5,
) -> GenerationResult:
    """Genera texto plano. Una sola llamada al proveedor, sin descartes."""
    chosen = resolve_provider(settings, provider)
    model = settings.model_for(chosen)
    key = settings.key_for(chosen)

    if chosen == "gemini":
        return await _gemini_generate(
            api_key=key,
            model=model,
            system=system,
            prompt=prompt,
            schema=None,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    base_url = {"openrouter": OPENROUTER_BASE_URL, "xai": XAI_BASE_URL}.get(chosen)
    return await _chat_completion(
        provider=chosen,
        api_key=key,
        base_url=base_url,
        model=model,
        system=system or "Eres un asistente experto en pedagogía chilena.",
        prompt=prompt,
        schema=None,
        max_tokens=max_tokens,
        temperature=temperature,
    )
