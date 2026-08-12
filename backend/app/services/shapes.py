"""Figuras geométricas dibujadas por código, antes de buscar o generar.

Motivo medido: para el vocabulario de 1° y 2° Básico en Matemática —"círculo
rojo", "cuadrado azul", patrones de figuras— ni ARASAAC ni un modelo generativo
sirven.

- ARASAAC tiene la forma pero no el color: pedir "círculo rojo" devolvía el
  pictograma de *semáforo rojo* y, ya corregida la búsqueda, un círculo
  **amarillo con rayas**. En una clase cuyo contenido es la secuencia
  "rojo, azul, rojo", proyectar el color equivocado destruye la clase.
- Un generativo cuesta, tarda y —lo peor— no es reproducible: el círculo rojo de
  la escena 1 no sale idéntico al de la escena 4, que es exactamente lo que una
  clase de patrones necesita comparar.

Un SVG dibujado por código es exacto, idéntico entre escenas, instantáneo,
gratis, pesa menos de 1 KB y se ve nítido en cualquier proyector.

Cubre solo lo que puede dibujar con certeza. Lo que no reconoce sigue de largo
hacia ARASAAC y la cascada de IA.
"""

import re
import unicodedata

# Paleta de alto contraste para proyección. Los colores "de escuela" saturados
# se lavan menos que los pasteles cuando el proyector pierde contraste; ver
# DESIGN.md.
COLORES = {
    "rojo": "#DC2626",
    "azul": "#2563EB",
    "verde": "#16A34A",
    "amarillo": "#EAB308",
    "naranjo": "#EA580C",
    "naranja": "#EA580C",
    "morado": "#7C3AED",
    "violeta": "#7C3AED",
    "rosado": "#DB2777",
    "rosa": "#DB2777",
    "cafe": "#92400E",
    "negro": "#111827",
    "blanco": "#FFFFFF",
    "gris": "#6B7280",
    "celeste": "#0EA5E9",
}

# El modelo escribe el adjetivo concordado con la figura: "estrella amarilla",
# "cuadrado rojo". Sin las formas femeninas, "amarilla" no era un color y la
# estrella salía del color por defecto —azul— en una clase donde el color es
# justamente el contenido.
COLORES.update({
    f"{raiz}a": COLORES[f"{raiz}o"]
    for raiz in ("roj", "amarill", "morad", "rosad", "blanc", "negr")
    if f"{raiz}o" in COLORES
})

# Trazo oscuro siempre: sostiene la figura cuando el proyector lava el relleno,
# y hace visible el blanco sobre fondo blanco.
TRAZO = "#111827"
GROSOR = 8


def _svg(contenido: str, ancho: int = 512, alto: int = 512) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
        f'width="{ancho}" height="{alto}" role="img">{contenido}</svg>'
    ).encode("utf-8")


def _circulo(color: str, cx=256, cy=256, r=200) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}"/>'


def _cuadrado(color: str, x=66, y=66, lado=380) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{lado}" height="{lado}" rx="12" '
        f'fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}"/>'
    )


def _triangulo(color: str) -> str:
    return f'<polygon points="256,56 456,436 56,436" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}" stroke-linejoin="round"/>'


def _rectangulo(color: str) -> str:
    return f'<rect x="46" y="146" width="420" height="220" rx="12" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}"/>'


def _rombo(color: str) -> str:
    return f'<polygon points="256,46 466,256 256,466 46,256" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}" stroke-linejoin="round"/>'


def _estrella(color: str) -> str:
    puntos = "256,40 315,196 480,196 347,296 397,456 256,358 115,456 165,296 32,196 197,196"
    return f'<polygon points="{puntos}" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}" stroke-linejoin="round"/>'


def _corazon(color: str) -> str:
    d = ("M256 452 L106 302 A86 86 0 0 1 256 186 A86 86 0 0 1 406 302 Z")
    return f'<path d="{d}" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}" stroke-linejoin="round"/>'


def _ovalo(color: str) -> str:
    return f'<ellipse cx="256" cy="256" rx="210" ry="150" fill="{color}" stroke="{TRAZO}" stroke-width="{GROSOR}"/>'


FORMAS = {
    "circulo": _circulo,
    "circunferencia": _circulo,
    "cuadrado": _cuadrado,
    "triangulo": _triangulo,
    "rectangulo": _rectangulo,
    "rombo": _rombo,
    "estrella": _estrella,
    "corazon": _corazon,
    "ovalo": _ovalo,
    "elipse": _ovalo,
}

# Plurales simples: el modelo escribe tanto "círculo" como "círculos".
_PLURALES = {f"{nombre}s": nombre for nombre in FORMAS}
FORMAS.update({plural: FORMAS[base] for plural, base in _PLURALES.items()})

PALABRAS_PATRON = {"patron", "patrones", "secuencia", "serie"}


def _normaliza(texto: str) -> str:
    base = unicodedata.normalize("NFD", (texto or "").lower())
    limpio = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", limpio)


def _patron(forma_fn, colores: list[str]) -> bytes:
    """Secuencia repetida de la unidad de colores, para enseñar patrones.

    Dibuja la unidad dos veces y deja la tercera repetición incompleta, que es
    como se presenta un patrón en el aula: "¿qué figura sigue?".
    """
    unidad = len(colores)
    total = min(unidad * 2 + 1, 6)
    paso = 512 // total
    radio = int(paso * 0.38)
    piezas = []
    for i in range(total):
        cx = paso // 2 + paso * i
        color = COLORES[colores[i % unidad]]
        piezas.append(f'<circle cx="{cx}" cy="128" r="{radio}" fill="{color}" stroke="{TRAZO}" stroke-width="6"/>')
    return _svg("".join(piezas), ancho=512, alto=256)


def render(query: str) -> bytes | None:
    """SVG de la figura pedida, o None si no es una figura reconocible.

    Devolver None no es un fallo: significa "esto no lo sé dibujar con certeza",
    y la cadena de imágenes sigue a ARASAAC.
    """
    palabras = _normaliza(query).split()
    if not palabras:
        return None

    colores = [p for p in palabras if p in COLORES]
    formas = [p for p in palabras if p in FORMAS]

    # "patrón rojo azul" → secuencia alternada; necesita al menos dos colores
    # para que haya algo que repetir.
    if any(p in PALABRAS_PATRON for p in palabras) and len(colores) >= 2:
        return _patron(FORMAS.get(formas[0], _circulo) if formas else _circulo, colores)

    if not formas:
        return None

    # Sin color explícito se usa un azul neutro: la figura es el contenido y el
    # color no aporta significado en ese caso.
    color = COLORES[colores[0]] if colores else COLORES["azul"]
    return _svg(FORMAS[formas[0]](color))
