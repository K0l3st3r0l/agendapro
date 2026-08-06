"""Generación de ilustraciones por la Image API de OpenRouter.

Reemplaza las rutas de imágenes de Gemini y DALL·E, que quedaron inutilizables:
Gemini devuelve 429 por cuota agotada y el modelo configurado por defecto
(`gemini-2.0-flash-preview-image-generation`) ya no existe en la API.

El caché por hash de contenido es la palanca de costo más importante del
módulo. Antes había 108 imágenes en disco (83 MB) contra un solo documento
guardado, sin ninguna deduplicación: cada guía regeneraba "sol", "gato" y
"casa" desde cero. En 1° a 4° básico ese vocabulario se repite constantemente,
así que la tasa de acierto del caché es alta y un acierto cuesta cero.
"""

import asyncio
import base64
import hashlib
import logging
import os

import httpx

from app.api.settings import AISettings

logger = logging.getLogger(__name__)

IMAGES_ENDPOINT = "https://openrouter.ai/api/v1/images"
IMAGES_DIR = "/app/static/images"
PUBLIC_PREFIX = "/static/images"

# Cada imagen es un proceso aparte en el proveedor; más de 4 en paralelo no
# acelera y sí aumenta la probabilidad de rate limit.
MAX_CONCURRENT = 4
REQUEST_TIMEOUT = 120.0


class ImageGenerationError(Exception):
    """Fallo al generar una imagen concreta. No aborta el lote completo."""


def build_prompt(word: str, style: str) -> str:
    if style == "coloring":
        return (
            f"Dibujo para colorear de: {word}. "
            f"Solo líneas negras de contorno sobre fondo blanco puro, sin relleno de color. "
            f"Un único objeto '{word}' centrado, sin texto, sin fondo decorativo, sin marco. "
            f"Estilo libro de colorear infantil, trazo grueso y simple, apto para imprimir."
        )
    return (
        f"Ilustración educativa simple y clara de: {word}. "
        f"Estilo clipart infantil colorido. Un único objeto '{word}' centrado sobre fondo blanco puro. "
        f"Sin texto, sin letras, sin otros objetos. La imagen debe representar exactamente '{word}'."
    )


def cache_path(word: str, style: str, model: str) -> tuple[str, str]:
    """Ruta en disco y URL pública, derivadas del contenido.

    El nombre depende de palabra + estilo + modelo, así que cambiar de modelo
    invalida el caché automáticamente en vez de servir mezclas de estilos.
    """
    digest = hashlib.sha256(f"{word}|{style}|{model}".encode()).hexdigest()[:16]
    filename = f"{digest}.png"
    return os.path.join(IMAGES_DIR, filename), f"{PUBLIC_PREFIX}/{filename}"


async def _request_image(client: httpx.AsyncClient, api_key: str, model: str, prompt: str) -> bytes:
    response = await client.post(
        IMAGES_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://agendapro.laravas.com",
            "X-Title": "AgendaPro",
        },
        json={"model": model, "prompt": prompt, "n": 1},
    )

    if response.status_code != 200:
        detail = response.text[:200]
        raise ImageGenerationError(f"HTTP {response.status_code}: {detail}")

    payload = response.json()
    data = (payload.get("data") or [])
    if not data:
        raise ImageGenerationError("La respuesta no trae ninguna imagen")

    encoded = data[0].get("b64_json")
    if not encoded:
        raise ImageGenerationError("La respuesta no trae b64_json")

    cost = (payload.get("usage") or {}).get("cost")
    if cost is not None:
        logger.info("Imagen generada con %s — costo real $%.5f", model, float(cost))

    return base64.b64decode(encoded)


async def generate_cover(settings: AISettings, subject: str, grade_level: str, topic: str) -> str | None:
    """Ilustración de cabecera del documento. Devuelve la URL o None.

    Se genera solo cuando la profesora marca la casilla. Antes se forzaba para
    toda guía o ficha, sumando ~10 s y costo a documentos que no la pedían.
    """
    if not settings.openrouter_key:
        return None

    descriptor = f"{topic} ({subject}, {grade_level})"
    prompt = (
        f"Ilustración educativa de portada sobre: {descriptor}. "
        f"Estilo alegre y colorido para material escolar infantil, composición horizontal, "
        f"fondo claro y limpio, sin texto ni letras."
    )
    path, url = cache_path(descriptor, "cover", settings.image_model)
    if os.path.exists(path):
        return url

    os.makedirs(IMAGES_DIR, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            raw = await _request_image(client, settings.openrouter_key, settings.image_model, prompt)
    except Exception as exc:
        logger.warning("No se pudo generar la portada de '%s': %s", descriptor, exc)
        return None

    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "wb") as handle:
            handle.write(raw)
        os.replace(tmp, path)
    except Exception as exc:
        logger.warning("No se pudo guardar la portada: %s", exc)
        if os.path.exists(tmp):
            os.unlink(tmp)
        return None
    return url


async def generate_images(settings: AISettings, words: dict[str, str]) -> dict[str, str]:
    """Genera las imágenes que falten y devuelve {palabra: url}.

    `words` mapea cada palabra a su estilo ('photo' | 'coloring'). Las palabras
    que fallan simplemente no aparecen en el resultado: el documento se sigue
    mostrando con el placeholder, en vez de romper la generación completa.
    """
    if not words:
        return {}

    model = settings.image_model
    os.makedirs(IMAGES_DIR, exist_ok=True)

    results: dict[str, str] = {}
    pending: dict[str, str] = {}

    for word, style in words.items():
        path, url = cache_path(word, style, model)
        if os.path.exists(path):
            results[word] = url  # acierto de caché: sin llamada, sin costo
        else:
            pending[word] = style

    if pending and not settings.openrouter_key:
        logger.warning("Sin OPENROUTER_API_KEY: %d imágenes quedan sin generar", len(pending))
        return results

    if not pending:
        logger.info("Caché completo: %d/%d imágenes servidas sin costo", len(results), len(words))
        return results

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:

        async def one(word: str, style: str) -> tuple[str, str | None]:
            async with semaphore:
                path, url = cache_path(word, style, model)
                try:
                    raw = await _request_image(client, settings.openrouter_key, model, build_prompt(word, style))
                except Exception as exc:
                    logger.warning("No se pudo generar la imagen de '%s': %s", word, exc)
                    return word, None

                # Escritura atómica: un archivo a medio escribir quedaría en el
                # caché para siempre, servido como imagen corrupta.
                tmp = f"{path}.{os.getpid()}.tmp"
                try:
                    with open(tmp, "wb") as handle:
                        handle.write(raw)
                    os.replace(tmp, path)
                except Exception as exc:
                    logger.warning("No se pudo guardar la imagen de '%s': %s", word, exc)
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                    return word, None
                return word, url

        done = await asyncio.gather(*(one(w, s) for w, s in pending.items()))

    for word, url in done:
        if url:
            results[word] = url

    logger.info(
        "Imágenes: %d de caché, %d generadas, %d fallidas",
        len(words) - len(pending),
        len(results) - (len(words) - len(pending)),
        len(pending) - (len(results) - (len(words) - len(pending))),
    )
    return results
