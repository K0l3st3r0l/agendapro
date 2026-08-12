"""Revisión de las ilustraciones antes de que lleguen a la sala.

Idea del flujo: generar rápido con FLUX.2 Pro —13 s las cuatro, en paralelo— y
mandar a regenerar con gpt-image solo las que no se entienden. gpt-image produce
ilustraciones educativas mejores pero el puente las serializa: nueve imágenes
tomaron 576 s medidos. Revisar primero y regenerar solo lo necesario aprovecha
lo bueno de cada uno.

El juez es un modelo con visión barato mirando la imagen ya generada. Se le pide
una sola cosa, la que de verdad importa en una sala de clases:

    ¿un niño de seis años, sin leer nada, diría que esto es un/una X?

No se le pregunta si es bonita. Una ilustración preciosa pero ambigua —la hoja
de FLUX que parecía un árbol dentro de una hoja— es peor que una simple y
correcta, porque el contenido de la clase depende de que el objeto se reconozca.

Sesgo deliberado hacia dejar pasar: ante la duda se acepta. Un falso rechazo
cuesta 50 s de regeneración y cuota; un falso positivo cuesta una imagen
mediocre que la profesora igual puede cambiar a mano.
"""

import asyncio
import base64
import json
import logging
import os
import unicodedata

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_CHAT = "https://openrouter.ai/api/v1/chat/completions"

# Barato y con visión: revisar no puede costar más que generar.
REVIEW_MODEL = os.getenv("IMAGE_REVIEW_MODEL", "google/gemini-2.5-flash-lite")
REVIEW_TIMEOUT = 60.0

# Tope de regeneraciones por clase. Si el juez rechaza casi todo, el problema es
# el juez o el prompt de generación —no se arregla gastando diez minutos de
# puente y cuota de ChatGPT en rehacer una clase entera.
MAX_REGENERACIONES = 4

# Primero nombrar, después juzgar.
#
# La primera versión preguntaba directo "¿es claro que esto es X?" y el juez
# aprobó una ilustración ambigua describiéndola, en la misma respuesta, como
# "un árbol con hojas verdes y un tronco marrón" —cuando la palabra era "hoja"—.
# Veía bien; lo que no hacía era comparar lo que veía con lo que se pedía.
#
# Ahora se le pide que nombre el objeto sin decirle la respuesta esperada, y la
# comparación la hace el código. Un modelo de visión nombrando un dibujo simple
# es una tarea fácil; juzgar coincidencia con sesgo a aceptar, no.
_PROMPT = (
    "¿Qué objeto muestra esta ilustración infantil?\n\n"
    "Responde SOLO con este JSON:\n"
    "{{\"objeto\": \"<el objeto principal, 1 o 2 palabras, en singular>\", "
    "\"tiene_texto\": true|false, "
    "\"ambigua\": true|false}}\n\n"
    "\"objeto\": qué diría un niño de 6 años que es, mirando sin leer nada.\n"
    "\"tiene_texto\": si hay letras, números o palabras dibujadas encima.\n"
    "\"ambigua\": true solo si de verdad no se distingue qué es, o si mezcla "
    "varias cosas distintas sin que ninguna domine."
)


def _normaliza(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").lower().strip())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _coinciden(visto: str, esperado: str) -> bool:
    """Compara con manga ancha: el juez describe libremente.

    "hoja verde" contra "hoja" coincide; "arbol" contra "hoja" no. Basta con que
    alguna palabra significativa se comparta —el objetivo es cazar el caso en que
    el modelo dibujó otra cosa, no corregirle el vocabulario.
    """
    if not visto or not esperado:
        return True
    palabras_vistas = {p for p in visto.split() if len(p) > 2}
    palabras_esperadas = {p for p in esperado.split() if len(p) > 2}
    if not palabras_esperadas:
        return True
    # Singular/plural simple: "hojas" cubre "hoja".
    def raices(ps):
        return {p.rstrip("es") if len(p) > 4 else p for p in ps}
    return bool(raices(palabras_vistas) & raices(palabras_esperadas))


async def revisar(
    client: httpx.AsyncClient, api_key: str, png: bytes, palabra: str
) -> tuple[bool, str]:
    """(sirve, razón). Ante cualquier fallo devuelve True: no bloquear por el juez."""
    if not api_key or not png:
        return True, "sin revisión"
    try:
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode()
        r = await client.post(
            OPENROUTER_CHAT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": REVIEW_MODEL,
                "max_tokens": 100,
                "temperature": 0,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT.format(palabra=palabra)},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }],
            },
            timeout=REVIEW_TIMEOUT,
        )
        if r.status_code != 200:
            logger.info("El revisor no respondió para '%s': %s", palabra, r.status_code)
            return True, "revisor no disponible"

        texto = (r.json()["choices"][0]["message"]["content"] or "").strip()
        texto = texto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        veredicto = json.loads(texto)

        visto = _normaliza(str(veredicto.get("objeto", "")))
        esperado = _normaliza(palabra)

        if veredicto.get("tiene_texto"):
            return False, f"tiene texto encima (vio: {visto})"
        if veredicto.get("ambigua"):
            return False, f"ambigua (vio: {visto})"
        if _coinciden(visto, esperado):
            return True, visto

        # El nombre no calza, pero eso no basta para descartar: una ilustración
        # de raíz la nombra "planta" y sirve igual, porque la raíz es lo que
        # domina el cuadro. Recién acá se le dice qué se pedía y se pregunta si
        # está presente como protagonista. Solo cuesta una llamada extra en los
        # casos dudosos, y evita gastar 50 s del puente regenerando una imagen
        # que servía.
        return await _segunda_opinion(client, api_key, data_uri, palabra, visto)
    except Exception as exc:
        # El juez es una mejora, no un requisito: si falla, la imagen pasa.
        logger.info("Revisión de '%s' no concluyó: %s", palabra, exc)
        return True, "revisión fallida"


_PROMPT_2 = (
    "En esta ilustración infantil, ¿aparece \"{palabra}\" de forma clara y como "
    "elemento principal del dibujo?\n\n"
    "Responde SOLO con este JSON: {{\"aparece\": true|false}}\n\n"
    "true si un niño de 6 años podría señalar \"{palabra}\" en la imagen sin dudar, "
    "aunque haya otros elementos acompañando.\n"
    "false si \"{palabra}\" no está, es un detalle secundario, o el dibujo muestra "
    "principalmente otra cosa."
)


async def _segunda_opinion(
    client: httpx.AsyncClient, api_key: str, data_uri: str, palabra: str, visto: str
) -> tuple[bool, str]:
    try:
        r = await client.post(
            OPENROUTER_CHAT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": REVIEW_MODEL,
                "max_tokens": 40,
                "temperature": 0,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT_2.format(palabra=palabra)},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }],
            },
            timeout=REVIEW_TIMEOUT,
        )
        texto = (r.json()["choices"][0]["message"]["content"] or "").strip()
        texto = texto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        if json.loads(texto).get("aparece"):
            return True, f"{visto} (contiene lo pedido)"
        return False, f"muestra '{visto}', se pidió '{palabra}'"
    except Exception:
        return True, "segunda opinión fallida"


async def revisar_lote(
    api_key: str, imagenes: dict[str, bytes]
) -> dict[str, tuple[bool, str]]:
    """Revisa todas en paralelo: el juez sí paraleliza, a diferencia del puente."""
    if not imagenes:
        return {}
    async with httpx.AsyncClient(timeout=REVIEW_TIMEOUT) as client:
        palabras = list(imagenes)
        resultados = await asyncio.gather(
            *[revisar(client, api_key, imagenes[p], p) for p in palabras]
        )
    return dict(zip(palabras, resultados))
