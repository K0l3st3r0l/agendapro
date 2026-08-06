"""Ilustraciones para las actividades, en tres capas.

    1. Caché en disco       — costo cero, latencia cero
    2. ARASAAC              — costo cero, ~0,3 s, pictogramas educativos
    3. IA, en cascada       — para lo que ARASAAC no cubre:
       a) Codex (puente)       — $0 en dólares, ~35 s, cuota del plan ChatGPT
       b) Qwen Image 3 Pro     — ~$0,04/img, ~45 s, si el puente falla o no está
       c) OpenRouter (default) — ~$0,0115/img, ~22 s, red de seguridad final

**ARASAAC va primero a propósito.** Es el set de pictogramas del Gobierno de
Aragón, estándar en escuelas hispanohablantes: búsqueda en español, versión en
color y versión de línea negra para colorear. Para el vocabulario concreto de
1º a 4º básico —"sol", "gato", "abeja", "pato"— es mejor que la IA en todo lo
que importa: es gratis, es instantáneo, acierta siempre (la IA a veces dibuja
algo ambiguo) y mantiene un único lenguaje visual en toda la guía, mientras que
la IA entrega un estilo distinto en cada imagen.

La IA queda para lo que ARASAAC no cubre: conceptos abstractos o específicos
("fotosíntesis", "sistema circulatorio") y vocabulario de cursos superiores.

Elección del modelo de respaldo, medida el 2026-08-06 con `usage.cost`:

    openai/gpt-image-2                   $0.0115/img   22 s   ← default
    black-forest-labs/flux.2-klein-4b    $0.0140/img    3 s
    black-forest-labs/flux.2-pro         $0.0300/img   13 s
    google/gemini-3.1-flash-lite-image   $0.0338/img    4 s
    openai/gpt-5-image-mini              $0.0397/img   40 s

El costo por sí solo elegía mal. El primer benchmark se corrió con "abeja" y
"pato" —palabras que ARASAAC ya cubre, o sea justamente las que la IA nunca va
a ver— y coronó a FLUX.2 klein por ser barato y rápido. Al repetirlo con el
caso real de la capa 3 ("sistema circulatorio", "fotosíntesis"), klein devolvió
un borrón amarillo con el texto inventado "Circulluarri", pese a que el prompt
pide explícitamente sin texto: un modelo de 4B no sostiene la instrucción
negativa. gpt-image-2 entregó un diagrama anatómicamente correcto y sin texto,
además de ser el más barato. La latencia de 22 s se tolera porque este camino
es excepcional y corre con concurrencia 4.

`openai/gpt-5-image-mini` merece una nota: cuesta $0.000008 por token contra
$0.00003 de Nano Banana Lite —parecía 4× más barato— y terminó siendo el más
caro de todos, porque genera muchísimos más tokens por imagen. Los precios de
lista por token no predicen el costo por imagen.

⚠️ Licencia: los pictogramas de ARASAAC son CC BY-NC-SA. Sirven para material
de aula (uso educativo no comercial) citando la fuente, que es lo que hacen los
exportadores. Si AgendaPro pasa a ser un producto pago hay que revisar esto:
la cláusula NC no lo permitiría y habría que caer a la IA o licenciar otro set.

Qwen Image 3 Pro se agregó el 2026-08-06 como respaldo intermedio del puente,
no como reemplazo del fallback final: cubre las caídas de Codex (offline, sin
cuota) sin gastar el modelo ya benchmarkeado arriba como red de seguridad. Se
pide a 1024x1024 porque a su tamaño por defecto, 2048x2048, el costo real
medido casi se duplica ($0,075 vs $0,04) sin ganancia para una tarjeta de
vocabulario chica. Comparado lado a lado con el puente en la misma palabra,
tiende a elegir paletas poco fieles al objeto real (araña azul, cuerpo
morado); por eso queda después del puente y no lo reemplaza. Detalle en
wiki/projects/agendapro/decisions/.
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

# Costo medido de openai/gpt-image-2, solo para reportar el gasto en los logs.
COSTO_ESTIMADO_IA = 0.018

# Respaldo intermedio cuando el puente de Codex falla o no está configurado.
# Tamaño fijo en 1024x1024: a 2048x2048 (su default) el costo real medido casi
# se duplica ($0,075 vs $0,04) sin ganancia para una tarjeta de vocabulario.
QWEN_MODEL = "qwen/qwen-image-3-pro"
QWEN_SIZE = "1024x1024"
COSTO_ESTIMADO_QWEN = 0.04


ARASAAC_SEARCH = "https://api.arasaac.org/v1/pictograms/es/search/{palabra}"
ARASAAC_IMAGE = "https://api.arasaac.org/v1/pictograms/{pid}"
ARASAAC_TIMEOUT = 20.0

# Puente en el host hacia la herramienta `image_gen` de Codex. Genera contra la
# suscripción de ChatGPT, así que no gasta créditos en dólares — pero sí cuota
# del plan y ~35 s por imagen. Ver agent-bridge/bridge.py.
BRIDGE_URL = os.getenv("AGENT_BRIDGE_URL", "")
BRIDGE_TOKEN = os.getenv("AGENT_BRIDGE_TOKEN", "")
BRIDGE_TIMEOUT = 300.0

FUENTE_ARASAAC = "ARASAAC"
FUENTE_CODEX = "codex"
FUENTE_QWEN = "qwen"
FUENTE_IA = "ia"


class ImageGenerationError(Exception):
    """Fallo al generar una imagen concreta. No aborta el lote completo."""


async def _from_arasaac(client: httpx.AsyncClient, word: str, style: str) -> bytes | None:
    """Descarga el pictograma de ARASAAC, o None si no existe la palabra."""
    try:
        search = await client.get(ARASAAC_SEARCH.format(palabra=word), timeout=ARASAAC_TIMEOUT)
        if search.status_code != 200:
            return None
        resultados = search.json()
        if not isinstance(resultados, list) or not resultados:
            return None

        pid = resultados[0].get("_id")
        if not pid:
            return None

        # `color=false` entrega la versión de línea negra, que es justo lo que
        # necesita una actividad de colorear. La IA acierta eso a medias.
        params = {"resolution": "500"}
        if style == "coloring":
            params["color"] = "false"

        imagen = await client.get(ARASAAC_IMAGE.format(pid=pid), params=params, timeout=ARASAAC_TIMEOUT)
        if imagen.status_code != 200 or not imagen.content.startswith(b"\x89PNG"):
            return None
        return imagen.content
    except Exception as exc:
        logger.debug("ARASAAC no resolvió '%s': %s", word, exc)
        return None


async def _from_codex(client: httpx.AsyncClient, word: str, style: str) -> bytes | None:
    """Genera con Codex a través del puente del host, o None si no está o falla.

    El puente valida la palabra y arma el prompt: acá solo se le pasan la palabra
    y el estilo, nunca texto libre.
    """
    if not BRIDGE_URL or not BRIDGE_TOKEN:
        return None
    try:
        response = await client.post(
            f"{BRIDGE_URL.rstrip('/')}/image",
            headers={"X-Bridge-Token": BRIDGE_TOKEN},
            json={"word": word, "style": style},
            timeout=BRIDGE_TIMEOUT,
        )
        if response.status_code != 200:
            logger.info("El puente de Codex no pudo con '%s': %s", word, response.text[:120])
            return None
        raw = base64.b64decode((response.json() or {}).get("b64") or "")
        return raw if raw.startswith(b"\x89PNG") else None
    except Exception as exc:
        logger.info("Puente de Codex no disponible para '%s': %s", word, exc)
        return None


async def _from_qwen(client: httpx.AsyncClient, api_key: str, word: str, style: str) -> bytes | None:
    """Genera con Qwen Image 3 Pro, o None si falla. Ver nota del módulo.

    Respaldo intermedio: cubre las caídas del puente de Codex sin gastar el
    modelo por defecto (`_request_image`), que quedó elegido por benchmark
    real como red de seguridad final.
    """
    if not api_key:
        return None
    try:
        response = await client.post(
            IMAGES_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://agendapro.laravas.com",
                "X-Title": "AgendaPro",
            },
            json={
                "model": QWEN_MODEL,
                "prompt": build_prompt(word, style),
                "n": 1,
                "size": QWEN_SIZE,
            },
        )
        if response.status_code != 200:
            logger.info("Qwen Image 3 Pro no pudo con '%s': HTTP %s", word, response.status_code)
            return None

        payload = response.json()
        data = payload.get("data") or []
        if not data:
            return None
        encoded = data[0].get("b64_json")
        if not encoded:
            return None

        cost = (payload.get("usage") or {}).get("cost")
        if cost is not None:
            logger.info("Imagen generada con %s — costo real $%.5f", QWEN_MODEL, float(cost))
        return base64.b64decode(encoded)
    except Exception as exc:
        logger.info("Qwen Image 3 Pro no disponible para '%s': %s", word, exc)
        return None


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

    if not pending:
        logger.info("Caché completo: %d/%d imágenes servidas sin costo", len(results), len(words))
        return results

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    origen: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:

        async def one(word: str, style: str) -> tuple[str, str | None]:
            async with semaphore:
                path, url = cache_path(word, style, model)

                # 1) ARASAAC: gratis e instantáneo. Cubre casi todo el
                #    vocabulario concreto de básica.
                raw = await _from_arasaac(client, word, style)
                fuente = FUENTE_ARASAAC

                # 2) Codex: gratis en dólares (va contra la suscripción), pero
                #    ~35 s por imagen. Solo para lo que ARASAAC no tiene.
                if raw is None:
                    raw = await _from_codex(client, word, style)
                    fuente = FUENTE_CODEX

                # 3) Qwen Image 3 Pro: respaldo intermedio cuando el puente no
                #    está, se cayó o se agotó la cuota. ~$0,04, ~45 s.
                if raw is None:
                    raw = await _from_qwen(client, settings.openrouter_key, word, style)
                    fuente = FUENTE_QWEN

                # 4) OpenRouter (modelo por defecto): red de seguridad final,
                #    siempre responde. Cuesta ~$0,018 pero siempre responde.
                if raw is None:
                    if not settings.openrouter_key:
                        logger.info("'%s' no salió de ARASAAC ni de Codex, y no hay clave de OpenRouter", word)
                        return word, None
                    try:
                        raw = await _request_image(
                            client, settings.openrouter_key, model, build_prompt(word, style)
                        )
                        fuente = FUENTE_IA
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

                origen[word] = fuente
                return word, url

        done = await asyncio.gather(*(one(w, s) for w, s in pending.items()))

    for word, url in done:
        if url:
            results[word] = url

    de_cache = len(words) - len(pending)
    de_arasaac = sum(1 for f in origen.values() if f == FUENTE_ARASAAC)
    de_codex = sum(1 for f in origen.values() if f == FUENTE_CODEX)
    de_qwen = sum(1 for f in origen.values() if f == FUENTE_QWEN)
    de_ia = sum(1 for f in origen.values() if f == FUENTE_IA)
    logger.info(
        "Imágenes: %d de caché, %d de ARASAAC, %d por Codex, %d por Qwen (~$%.3f), "
        "%d por OpenRouter (~$%.3f), %d fallidas",
        de_cache,
        de_arasaac,
        de_codex,
        de_qwen,
        de_qwen * COSTO_ESTIMADO_QWEN,
        de_ia,
        de_ia * COSTO_ESTIMADO_IA,
        len(pending) - len(origen),
    )
    return results
