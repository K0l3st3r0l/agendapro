"""Compara los modelos de imagen candidatos con costo y latencia reales.

Existe porque las estimaciones no sirven para decidir: Gemini y GPT cobran por
tokens de imagen, así que el costo por ilustración depende de cuántos genere
cada modelo. La respuesta de OpenRouter trae `usage.cost` con el costo exacto
de cada llamada, de modo que este script mide en vez de estimar.

Genera el mismo set de palabras reales de 1º básico con cada candidato, en los
dos estilos que usa el constructor, y escribe una página HTML comparativa.

Uso:
    docker exec agendapro-backend python /app/scripts/bench_images.py
    # y luego, para verla:
    #   /static/bench/index.html
"""

import asyncio
import base64
import os
import sys
import time

import httpx

sys.path.insert(0, "/app")

ENDPOINT = "https://openrouter.ai/api/v1/images"
OUT_DIR = "/app/static/bench"

MODELOS = [
    "google/gemini-3.1-flash-lite-image",
    "google/gemini-3.1-flash-image",
    "black-forest-labs/flux.2-klein-4b",
    "black-forest-labs/flux.2-pro",
    "openai/gpt-image-2",
]

# Vocabulario real de las guías de sonido inicial de 1º básico.
PALABRAS = ["abeja", "araña", "sol", "mesa", "pato", "luna"]
ESTILOS = ["photo", "coloring"]


def prompt_for(word: str, style: str) -> str:
    from app.services.images import build_prompt

    return build_prompt(word, style)


async def generar(client: httpx.AsyncClient, key: str, model: str, word: str, style: str) -> dict:
    inicio = time.time()
    try:
        response = await client.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "prompt": prompt_for(word, style), "n": 1},
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "segundos": time.time() - inicio}

    segundos = time.time() - inicio
    if response.status_code != 200:
        return {"ok": False, "error": f"HTTP {response.status_code}: {response.text[:160]}", "segundos": segundos}

    payload = response.json()
    data = (payload.get("data") or [{}])[0]
    encoded = data.get("b64_json")
    if not encoded:
        return {"ok": False, "error": "sin b64_json", "segundos": segundos}

    nombre = f"{model.replace('/', '_')}__{style}__{word}.png"
    with open(os.path.join(OUT_DIR, nombre), "wb") as handle:
        handle.write(base64.b64decode(encoded))

    return {
        "ok": True,
        "archivo": nombre,
        "segundos": segundos,
        "costo": float((payload.get("usage") or {}).get("cost") or 0.0),
    }


async def main() -> int:
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        print("Falta OPENROUTER_API_KEY en el entorno del contenedor.")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    resultados: dict[str, list[dict]] = {}

    async with httpx.AsyncClient(timeout=180) as client:
        for model in MODELOS:
            filas = []
            print(f"\n=== {model} ===")
            for style in ESTILOS:
                # De a uno para no gatillar rate limits y medir latencia limpia.
                for word in PALABRAS:
                    resultado = await generar(client, key, model, word, style)
                    resultado.update({"palabra": word, "estilo": style})
                    filas.append(resultado)
                    estado = (
                        f"${resultado['costo']:.5f}  {resultado['segundos']:5.1f}s"
                        if resultado["ok"]
                        else f"FALLA {resultado['error'][:70]}"
                    )
                    print(f"  {style:9s} {word:9s} {estado}")
            resultados[model] = filas

    print("\n" + "=" * 76)
    print(f"{'Modelo':<40}{'ok':>4}{'costo/img':>12}{'seg/img':>10}{'20 imgs':>10}")
    print("=" * 76)
    resumen = []
    for model, filas in resultados.items():
        ok = [f for f in filas if f["ok"]]
        if not ok:
            print(f"{model:<40}{0:>4}{'—':>12}{'—':>10}{'—':>10}")
            continue
        costo = sum(f["costo"] for f in ok) / len(ok)
        seg = sum(f["segundos"] for f in ok) / len(ok)
        print(f"{model:<40}{len(ok):>4}{costo:>12.5f}{seg:>10.1f}{costo * 20:>10.3f}")
        resumen.append((model, costo, seg, len(ok)))

    escribir_html(resultados, resumen)
    print(f"\nComparación visual: {OUT_DIR}/index.html  →  https://agendapro.laravas.com/static/bench/index.html")
    return 0


def escribir_html(resultados: dict[str, list[dict]], resumen: list) -> None:
    partes = [
        "<!doctype html><meta charset='utf-8'><title>Benchmark de modelos de imagen</title>",
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;background:#fafafa;color:#111}"
        "h2{margin-top:2.5rem;border-bottom:2px solid #ddd;padding-bottom:.3rem}"
        "table{border-collapse:collapse;margin:1rem 0}td,th{border:1px solid #ddd;padding:.5rem .8rem;text-align:left}"
        ".fila{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}"
        ".celda{text-align:center;font-size:.8rem}"
        ".celda img{width:150px;height:150px;object-fit:contain;background:#fff;border:1px solid #ddd;border-radius:8px}"
        ".falla{width:150px;height:150px;display:flex;align-items:center;justify-content:center;"
        "background:#fee;border:1px dashed #c66;border-radius:8px;color:#c33;font-size:.7rem;padding:.5rem}</style>",
        "<h1>Benchmark de modelos de imagen</h1>",
        "<p>Mismo set de palabras de 1º básico en los dos estilos del constructor. "
        "El costo es el que informa OpenRouter en <code>usage.cost</code>, no una estimación.</p>",
        "<table><tr><th>Modelo</th><th>Imágenes OK</th><th>Costo por imagen</th>"
        "<th>Segundos por imagen</th><th>Documento de 20 imágenes</th></tr>",
    ]
    for model, costo, seg, n in sorted(resumen, key=lambda r: r[1]):
        partes.append(
            f"<tr><td><code>{model}</code></td><td>{n}</td><td>${costo:.5f}</td>"
            f"<td>{seg:.1f}s</td><td><b>${costo * 20:.3f}</b></td></tr>"
        )
    partes.append("</table>")

    for style in ESTILOS:
        partes.append(f"<h2>Estilo: {style}</h2>")
        for model, filas in resultados.items():
            partes.append(f"<h3><code>{model}</code></h3><div class='fila'>")
            for fila in [f for f in filas if f["estilo"] == style]:
                if fila["ok"]:
                    partes.append(
                        f"<div class='celda'><img src='{fila['archivo']}' alt='{fila['palabra']}'>"
                        f"<div>{fila['palabra']}</div></div>"
                    )
                else:
                    partes.append(
                        f"<div class='celda'><div class='falla'>{fila['error'][:90]}</div>"
                        f"<div>{fila['palabra']}</div></div>"
                    )
            partes.append("</div>")

    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(partes))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
