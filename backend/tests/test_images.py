"""Pruebas de la resolución de imágenes: figuras dibujadas y elección en ARASAAC.

No tocan la red: prueban las dos decisiones que antes fallaban en silencio.

Corre con:
    docker exec agendapro-backend python /app/tests/test_images.py
"""

import sys

sys.path.insert(0, "/app")

from app.services.images import _elegir_pictograma, _normaliza  # noqa: E402
from app.services.shapes import COLORES, render  # noqa: E402


def fill_de(svg: bytes) -> str:
    return svg.decode("utf-8").split('fill="')[1].split('"')[0]


# ---------------------------------------------------------------------------
# Figuras dibujadas por código
# ---------------------------------------------------------------------------

def test_figura_con_color_sale_del_color_pedido():
    """ARASAAC devolvía un círculo amarillo rayado para 'círculo rojo'. En una
    clase de patrones el color ES el contenido."""
    assert fill_de(render("círculo rojo")) == COLORES["rojo"]
    assert fill_de(render("cuadrado azul")) == COLORES["azul"]
    assert fill_de(render("triángulo verde")) == COLORES["verde"]


def test_el_adjetivo_en_femenino_tambien_es_color():
    """El modelo concuerda el adjetivo con la figura: 'estrella amarilla'.
    Sin esto la estrella salía del color por defecto."""
    assert fill_de(render("estrella amarilla")) == COLORES["amarillo"]
    assert fill_de(render("estrella amarilla")) == fill_de(render("estrella amarillo"))
    assert fill_de(render("luna roja") or render("círculo roja")) == COLORES["rojo"]


def test_plural_de_la_figura_se_reconoce():
    assert render("círculos") is not None
    assert render("triángulos verdes") is not None


def test_sin_color_usa_uno_neutro_pero_dibuja():
    svg = render("rombo")
    assert svg is not None
    assert fill_de(svg) == COLORES["azul"]


def test_un_patron_dibuja_la_secuencia_repetida():
    svg = render("patrón rojo azul")
    assert svg is not None
    contenido = svg.decode("utf-8")
    # La unidad se repite: ambos colores aparecen más de una vez.
    assert contenido.count(COLORES["rojo"]) >= 2
    assert contenido.count(COLORES["azul"]) >= 2


def test_un_patron_de_un_solo_color_no_es_patron():
    """Sin al menos dos colores no hay unidad que repetir; sigue a ARASAAC."""
    assert render("patrón rojo") is None or "circle" in render("patrón rojo").decode()


def test_lo_que_no_es_figura_sigue_de_largo():
    """Devolver None no es un fallo: es 'no sé dibujar esto con certeza'."""
    for palabra in ("manzana", "collar de cuentas", "fotosíntesis", "perro", ""):
        assert render(palabra) is None, f"{palabra!r} no debería resolverse como figura"


def test_el_svg_es_valido_y_liviano():
    svg = render("círculo rojo").decode("utf-8")
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert len(svg) < 1024, "una figura no debería pesar más de 1 KB"


def test_la_figura_lleva_trazo_para_sobrevivir_al_proyector():
    """El relleno se lava cuando el proyector pierde contraste; el contorno
    oscuro es lo que sostiene la forma. Y sin él, el blanco desaparece."""
    for consulta in ("círculo blanco", "cuadrado amarillo"):
        assert 'stroke="#111827"' in render(consulta).decode("utf-8")


def test_la_misma_consulta_da_siempre_la_misma_figura():
    """Reproducibilidad: el círculo de la escena 1 y el de la escena 4 tienen
    que ser idénticos, que es justo lo que un generativo no garantiza."""
    assert render("círculo rojo") == render("círculo rojo")


# ---------------------------------------------------------------------------
# Elección del pictograma en ARASAAC
# ---------------------------------------------------------------------------

def picto(pid: int, *keywords: str) -> dict:
    return {"_id": pid, "keywords": [{"keyword": k} for k in keywords]}


def test_se_elige_la_coincidencia_exacta_aunque_no_sea_la_primera():
    """El bug original: se tomaba resultados[0] sin mirar, y para 'círculo rojo'
    ARASAAC devolvía primero el pictograma de semáforo rojo."""
    resultados = [picto(36223, "semáforo rojo"), picto(999, "círculo rojo")]
    assert _elegir_pictograma(resultados, "círculo rojo") == 999


def test_sin_coincidencia_no_se_inventa():
    """Antes devolvía el primero igual, y la profesora proyectaba un semáforo
    frente al curso creyendo que el sistema había acertado."""
    resultados = [picto(36223, "semáforo rojo"), picto(1, "coche")]
    assert _elegir_pictograma(resultados, "collar de perlas") is None


def test_se_acepta_por_el_nucleo_del_termino():
    """En español el sustantivo va primero: 'collar de cuentas' se resuelve con
    el pictograma de 'collar'."""
    resultados = [picto(5, "collar")]
    assert _elegir_pictograma(resultados, "collar de cuentas") == 5


def test_la_comparacion_ignora_tildes_y_mayusculas():
    assert _elegir_pictograma([picto(7, "PLÁTANO")], "platano") == 7
    assert _normaliza("¿Cuál es tu Nombre?") == "cual es tu nombre"


def test_lista_vacia_no_revienta():
    assert _elegir_pictograma([], "manzana") is None


if __name__ == "__main__":
    fallos = 0
    pruebas = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for nombre, fn in pruebas:
        try:
            fn()
            print(f"  ok    {nombre}")
        except AssertionError as e:
            fallos += 1
            print(f"  FALLA {nombre}: {e}")
        except Exception as e:
            fallos += 1
            print(f"  ERROR {nombre}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas OK")
    sys.exit(1 if fallos else 0)
