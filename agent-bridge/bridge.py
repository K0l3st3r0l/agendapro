#!/usr/bin/env python3
"""Puente HTTP para generar imágenes con Codex desde el backend en Docker.

El backend corre en un contenedor; Codex y sus credenciales viven en el host.
Montar la CLI dentro del contenedor obligaría a meter ahí el runtime de Node y
el `auth.json` de la suscripción, así que en vez de eso el host expone este
servicio mínimo.

Por qué existe: la herramienta `image_gen` de Codex genera contra la suscripción
de ChatGPT y no consume créditos en dólares. Es más lenta que la API (~35 s
contra 22 s) y gasta cuota del plan, así que en la cascada de `images.py` va
después de ARASAAC y antes de FLUX.2 por OpenRouter.

Superficie de ataque y cómo se cierra:

- **Solo escucha en la IP del bridge de Docker**, nunca en 0.0.0.0.
- **Token compartido** en la cabecera `X-Bridge-Token`.
- **El cliente NO manda el prompt.** Manda una palabra y un estilo; la plantilla
  del prompt vive acá. Eso corta de raíz la inyección: las palabras vienen de un
  documento generado por IA a partir del texto que escribe la profesora, así que
  son entrada no confiable.
- **La palabra se valida contra una lista blanca** de letras y espacios. Nada de
  comillas, backticks, saltos de línea ni metacaracteres de shell.
- `codex exec` corre con `--sandbox read-only`, verificado que igual genera.
- Una sola generación a la vez: cada invocación levanta un agente completo.

Se instala como servicio systemd; ver agent-bridge/README.md.
"""

from __future__ import annotations

import base64
import glob
import json
import logging
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-bridge")

HOST = os.getenv("BRIDGE_HOST", "172.22.0.1")
PORT = int(os.getenv("BRIDGE_PORT", "8765"))
TOKEN = os.getenv("BRIDGE_TOKEN", "")
CODEX_HOME = os.getenv("CODEX_HOME", os.path.expanduser("~/.codex"))
CODEX_BIN = os.getenv("CODEX_BIN", "/root/.local/bin/codex")
TIMEOUT_S = int(os.getenv("BRIDGE_TIMEOUT", "240"))
MAX_BODY = 8 * 1024

# Lista blanca: letras (con tildes y ñ), espacios y guiones. Sin comillas,
# backticks, saltos de línea ni nada que pueda escaparse del prompt.
PALABRA_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ \-]{1,39}$")

# Un `image_words` legítimo es un sustantivo concreto: "abeja", "sistema
# circulatorio". Nunca una oración. Sin este tope, una frase de puras letras
# ("ignora lo anterior y ...") pasa la lista blanca y gasta 30 s de cuota antes
# de devolver una imagen inútil. El sandbox read-only ya impide daño real; esto
# evita el desperdicio.
MAX_PALABRAS = 3

_una_a_la_vez = threading.Semaphore(1)


def construir_prompt(palabra: str, estilo: str) -> str:
    """La plantilla vive acá, no en el cliente. Espeja build_prompt() del backend."""
    if estilo == "coloring":
        return (
            f"Genera una imagen: dibujo para colorear de {palabra}. "
            "Solo líneas negras de contorno sobre fondo blanco puro, sin relleno de color. "
            f"Un único objeto centrado, sin texto, sin fondo decorativo, sin marco. "
            "Estilo libro de colorear infantil, trazo grueso y simple, apto para imprimir. "
            "Solo genera la imagen, no expliques nada."
        )
    return (
        f"Genera una imagen: ilustración educativa simple y clara de {palabra}. "
        "Estilo clipart infantil colorido. Un único objeto centrado sobre fondo blanco puro. "
        "Sin texto, sin letras, sin otros objetos. "
        "Solo genera la imagen, no expliques nada."
    )


def _pngs_conocidos() -> dict[str, float]:
    patron = os.path.join(CODEX_HOME, "generated_images", "*", "*.png")
    return {ruta: os.path.getmtime(ruta) for ruta in glob.glob(patron)}


def generar(palabra: str, estilo: str) -> tuple[bytes | None, float, str]:
    """Devuelve (png, segundos, error). El semáforo serializa las corridas."""
    inicio = time.time()
    with _una_a_la_vez:
        previos = _pngs_conocidos()
        try:
            proceso = subprocess.run(
                [
                    CODEX_BIN, "exec",
                    "--skip-git-repo-check",
                    "--sandbox", "read-only",
                    construir_prompt(palabra, estilo),
                ],
                capture_output=True,
                timeout=TIMEOUT_S,
                cwd="/tmp",
                env={**os.environ, "CODEX_HOME": CODEX_HOME},
            )
        except subprocess.TimeoutExpired:
            return None, time.time() - inicio, f"codex superó los {TIMEOUT_S}s"
        except Exception as exc:
            return None, time.time() - inicio, f"{type(exc).__name__}: {exc}"

        nuevos = [r for r in _pngs_conocidos() if r not in previos]
        if not nuevos:
            cola = (proceso.stderr or b"")[-300:].decode(errors="replace")
            return None, time.time() - inicio, f"no se generó ninguna imagen. {cola}"

        # El semáforo garantiza una corrida a la vez, así que el más reciente es el nuestro.
        ruta = max(nuevos, key=os.path.getmtime)
        with open(ruta, "rb") as handle:
            datos = handle.read()

    if not datos.startswith(b"\x89PNG"):
        return None, time.time() - inicio, "el archivo generado no es un PNG"
    return datos, time.time() - inicio, ""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):  # noqa: N802 - firma de la stdlib
        logger.info("%s %s", self.address_string(), formato % args)

    def _responder(self, codigo: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._responder(200, {"status": "ok", "codex": os.path.exists(CODEX_BIN)})
        else:
            self._responder(404, {"error": "ruta desconocida"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/image":
            self._responder(404, {"error": "ruta desconocida"})
            return

        if not TOKEN or self.headers.get("X-Bridge-Token") != TOKEN:
            self._responder(401, {"error": "token inválido"})
            return

        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            largo = 0
        if largo <= 0 or largo > MAX_BODY:
            self._responder(400, {"error": "cuerpo ausente o demasiado grande"})
            return

        try:
            datos = json.loads(self.rfile.read(largo))
        except Exception:
            self._responder(400, {"error": "JSON inválido"})
            return

        palabra = str(datos.get("word", "")).strip()
        estilo = str(datos.get("style", "photo"))

        if not PALABRA_RE.match(palabra) or len(palabra.split()) > MAX_PALABRAS:
            # Se rechaza sin generar: la palabra viene de contenido producido por
            # un modelo a partir de texto del usuario, o sea entrada no confiable.
            self._responder(400, {"error": "palabra no permitida"})
            return
        if estilo not in ("photo", "coloring"):
            self._responder(400, {"error": "estilo no permitido"})
            return

        png, segundos, error = generar(palabra, estilo)
        if png is None:
            logger.warning("falló '%s' (%s): %s", palabra, estilo, error)
            self._responder(502, {"error": error, "seconds": round(segundos, 1)})
            return

        logger.info("generada '%s' (%s) en %.1fs, %d bytes", palabra, estilo, segundos, len(png))
        self._responder(200, {
            "b64": base64.b64encode(png).decode(),
            "seconds": round(segundos, 1),
        })


def main() -> None:
    if not TOKEN:
        raise SystemExit("Falta BRIDGE_TOKEN. El servicio no arranca sin autenticación.")
    if not os.path.exists(CODEX_BIN):
        raise SystemExit(f"No se encontró el binario de Codex en {CODEX_BIN}")

    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info("agent-bridge escuchando en %s:%s (timeout %ss)", HOST, PORT, TIMEOUT_S)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
