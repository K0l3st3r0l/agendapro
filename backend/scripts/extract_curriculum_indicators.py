"""Extrae los Indicadores de Evaluación de los Programas de Estudio MINEDUC.

Los indicadores NO están en las Bases Curriculares (que es lo que parsea
`extract_curriculum_oa.py`): están en los Programas de Estudio, un PDF por
asignatura y nivel. La estructura es una tabla de dos columnas que se repite en
cada unidad:

    OBJETIVOS DE APRENDIZAJE                    INDICADORES DE EVALUACIÓN SUGERIDOS
    Se espera que los estudiantes...            Los estudiantes que han alcanzado...

      OA 1
    Contar números naturales                  › Cuentan de 1 en 1 números dados en una secuencia
    del 0 al 100, de 1 en 1...                  numérica hasta 15, partiendo de 0.
                                              › Cuentan números de 2 en 2 y de 5 en 5, por tramos.

Se lee con `pdftotext -bbox-layout` en vez de `-layout` por una razón concreta:
los marcadores de nota al pie son superíndices y `-layout` los pega al texto
("entre 50 y 30" sale como "entre 50 y 302"). Con las cajas de cada palabra el
superíndice se reconoce por altura menor y línea base elevada, y se descarta.
"""

import difflib
import functools
import html
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import extract_curriculum_oa as bases  # noqa: E402

CONTENT_DIR = Path("/root/apps/academia/content")

# (asignatura y nivel tal cual están en la BD, archivo, tanda)
PROGRAMAS = [
    ("Lenguaje y Comunicación", "1° Básico", "programa_lenguaje_1basico.pdf", 1),
    ("Lenguaje y Comunicación", "2° Básico", "programa_lenguaje_2basico.pdf", 1),
    ("Matemática", "1° Básico", "programa_matematica_1basico.pdf", 1),
    ("Matemática", "2° Básico", "programa_matematica_2basico.pdf", 1),
    ("Ciencias Naturales", "1° Básico", "programa_ciencias_1basico.pdf", 2),
    ("Ciencias Naturales", "2° Básico", "programa_ciencias_2basico.pdf", 2),
    ("Historia, Geografía y Cs. Sociales", "1° Básico", "programa_historia_1basico.pdf", 2),
    ("Historia, Geografía y Cs. Sociales", "2° Básico", "programa_historia_2basico.pdf", 2),
    ("Educación Física", "1° Básico", "programa_edfisica_1basico.pdf", 3),
    ("Educación Física", "2° Básico", "programa_edfisica_2basico.pdf", 3),
    ("Orientación", "1° Básico", "programa_orientacion_1basico.pdf", 3),
    ("Orientación", "2° Básico", "programa_orientacion_2basico.pdf", 3),
    ("Música", "1° Básico", "programa_musica_1basico.pdf", 3),
    ("Música", "2° Básico", "programa_musica_2basico.pdf", 3),
    ("Artes Visuales", "1° Básico", "programa_artes_1basico.pdf", 3),
    ("Artes Visuales", "2° Básico", "programa_artes_2basico.pdf", 3),
    ("Tecnología", "1° Básico", "programa_tecnologia_1basico.pdf", 3),
    ("Tecnología", "2° Básico", "programa_tecnologia_2basico.pdf", 3),
]

BULLETS = {"›", "»", "‹", "•", ">", "·"}
# El encabezado de la tabla se repite en cada página, así que sirve de marcador
# de "esta página tiene indicadores" sin tener que seguir el hilo entre páginas.
# Va en VERSALITAS y exige las dos columnas: la sección "Estructura del programa"
# usa los mismos títulos en caja normal sobre una tabla de ejemplo de otro nivel,
# y sin esta distinción se colaban indicadores de 4º básico dentro de 1º.
HEADER_OA = "OBJETIVOS DE APRENDIZAJE"
HEADER_IND_RE = re.compile(r"^INDICADORES DE EVALUACI[ÓO]N")
OA_HEAD_RE = re.compile(r"^OA\s?(\d{1,2})$")
# Pie de página: "54  Programa de Estudio / 1º básico", "Matemática  Unidad 1  53".
FOOTER_RE = re.compile(r"Programa de Estudio\s*/|^\s*Unidad \d+\s*$|Ministerio de Educaci[óo]n")


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", html.unescape(s)).strip()


class Word:
    __slots__ = ("x", "y", "x2", "y2", "text")

    def __init__(self, el):
        self.x = float(el.get("xMin"))
        self.y = float(el.get("yMin"))
        self.x2 = float(el.get("xMax"))
        self.y2 = float(el.get("yMax"))
        self.text = norm(el.text or "")

    @property
    def h(self):
        return self.y2 - self.y


def leer_paginas(pdf: Path) -> list[list[Word]]:
    xml = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    root = ET.fromstring(xml)
    ns = {"p": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    tag = lambda n: f"{{{ns['p']}}}{n}" if ns else n

    paginas = []
    for page in root.iter(tag("page")):
        palabras = [Word(w) for w in page.iter(tag("word")) if norm(w.text or "")]
        paginas.append(palabras)
    return paginas


def agrupar_lineas(palabras: list[Word], tol: float = 3.0) -> list[list[Word]]:
    """Agrupa palabras en renglones por línea base, y ordena por columna."""
    lineas: list[list[Word]] = []
    for w in sorted(palabras, key=lambda w: (round(w.y2, 1), w.x)):
        if lineas and abs(lineas[-1][0].y2 - w.y2) <= tol:
            lineas[-1].append(w)
        else:
            lineas.append([w])
    for ln in lineas:
        ln.sort(key=lambda w: w.x)
    return lineas


def cuerpo_de_pagina(palabras: list[Word]) -> float:
    alturas = sorted(w.h for w in palabras)
    return alturas[len(alturas) // 2]


def sin_cuerpo_menor(palabras: list[Word]) -> list[Word]:
    """Descarta lo que está en cuerpo menor que el texto de la página.

    Se filtra ANTES de agrupar renglones, no después: el superíndice de una nota
    al pie tiene línea base propia, así que al agrupar queda como un renglón
    suelto de una sola palabra y se colaba como continuación del indicador
    anterior ("de 5 en 5 por 2 tramos"). De paso saca el cuerpo de las notas al
    pie y los folios, que también van en cuerpo menor.
    """
    if not palabras:
        return palabras
    mediana = cuerpo_de_pagina(palabras)
    return [w for w in palabras if w.h >= mediana * 0.85]


def texto(linea: list[Word]) -> str:
    return " ".join(w.text for w in linea)


def unir(acumulado: str, fragmento: str) -> str:
    """Concatena renglones deshaciendo el guion de corte de sílaba."""
    if not acumulado:
        return fragmento
    if acumulado.endswith("-") and fragmento[:1].islower():
        return acumulado[:-1] + fragmento
    return f"{acumulado} {fragmento}"


def columna_indicadores(lineas: list[list[Word]]) -> float | None:
    """x donde empieza la columna de indicadores, leída del propio encabezado.

    Se calcula por página en vez de fijarse: el ancho de la columna izquierda
    cambia entre asignaturas y entre unidades del mismo PDF. No sirve mirar las
    viñetas, porque el texto del OA de la columna izquierda también las usa
    para sus sub-ítems.
    """
    tiene_oa = False
    x = None
    for linea in lineas:
        if HEADER_OA in texto(linea):
            tiene_oa = True
        for i, w in enumerate(linea):
            if HEADER_IND_RE.match(texto(linea[i:])):
                x = w.x
    if not tiene_oa or x is None:
        return None
    # La viñeta cuelga unos puntos a la izquierda del encabezado, así que el
    # corte se ancla a las viñetas reales de esa banda: restar un margen fijo
    # dejaba la viñeta en la columna izquierda por menos de un punto.
    colgadas = [w.x for ln in lineas for w in ln if w.text in BULLETS and x - 25 <= w.x <= x + 5]
    return (min(colgadas) if colgadas else x) - 2


def extraer_pdf(pdf: Path, grade: str, subject: str) -> tuple[list[dict], list[str]]:
    """Devuelve los bloques OA→indicadores tal como vienen en el PDF.

    Un bloque guarda además el enunciado del OA que trae el propio Programa,
    porque el rótulo "OA n" no siempre es confiable y hay que contrastarlo
    contra las Bases (ver `resolver_codigos`).
    """
    paginas = leer_paginas(pdf)
    bloques: list[dict] = []
    avisos: list[str] = []
    bloque: dict | None = None

    for num_pagina, palabras in enumerate(paginas, 1):
        if not palabras or cuerpo_de_pagina(palabras) < 7:
            # El capítulo "Estructura del programa" reproduce una tabla de otro
            # nivel como facsímil reducido, con encabezado idéntico. Se descarta
            # por tamaño de letra: el cuerpo real nunca baja de 10 pt.
            continue
        lineas = agrupar_lineas(sin_cuerpo_menor(palabras))
        split = columna_indicadores(lineas)
        if split is None:
            continue

        actual: dict | None = None

        def cerrar():
            nonlocal actual
            if actual and len(actual["text"]) >= 15:
                bloque["indicadores"].append(actual)
            actual = None

        for linea in lineas:
            crudo = texto(linea)
            if HEADER_OA in crudo or HEADER_IND_RE.search(crudo) or FOOTER_RE.search(crudo):
                continue
            if crudo.startswith(("Se espera que", "Los estudiantes que han alcanzado")):
                continue

            izquierda = [w for w in linea if w.x < split]
            derecha = [w for w in linea if w.x >= split]

            if izquierda and OA_HEAD_RE.match(texto(izquierda)):
                if bloque:
                    cerrar()
                bloque = {
                    "grade": grade,
                    "subject": subject,
                    "rotulo": f"OA{int(OA_HEAD_RE.match(texto(izquierda)).group(1))}",
                    "enunciado": "",
                    "indicadores": [],
                    "source_ref": f"{pdf.name}#p{num_pagina}",
                }
                bloques.append(bloque)
                continue

            if bloque is None:
                continue

            if izquierda:
                # En esta tabla la columna izquierda es solo el enunciado del
                # OA, así que se acumula entero hasta el próximo rótulo: se
                # reparte en varios renglones a la par de los indicadores.
                bloque["enunciado"] = unir(bloque["enunciado"], texto(izquierda))

            if not derecha:
                continue

            if derecha[0].text in BULLETS:
                cerrar()
                actual = {
                    "text": texto(derecha[1:]).strip(),
                    "source_ref": f"{pdf.name}#p{num_pagina}",
                }
            elif actual:
                actual["text"] = unir(actual["text"], texto(derecha))

        cerrar()

    return bloques, avisos


# --- Verificación del rótulo contra las Bases Curriculares ------------------


@functools.lru_cache(maxsize=1)
def catalogo_oa() -> dict[tuple[str, str], dict[str, str]]:
    """{(nivel, asignatura): {código: descripción}} leído de las Bases.

    Misma fuente que `curriculum_oa` en la base de datos, así que los códigos
    que salgan de aquí cruzan con la FK sin tabla de mapeo.
    """
    catalogo: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for fila in bases.normalize(bases.extract(bases.PDFS["1a6"])):
        catalogo[(fila["grade"], fila["subject"])][fila["code"]] = fila["desc"]
    return catalogo


def plano(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"\s+", " ", t)).strip()


def resolver_codigos(bloques: list[dict], avisos: list[str]) -> list[dict]:
    """Corrige el rótulo cuando el enunciado del bloque es el de otro OA.

    El Programa de Matemática 1º rotula "OA 12" un bloque cuyo enunciado es
    textualmente el OA14 de las Bases ("identificar en el entorno figuras 3D y
    figuras 2D"). Sin este contraste, cuatro indicadores de geometría quedaban
    colgando del OA de igualdad y desigualdad.
    """
    catalogo = catalogo_oa()
    filas: list[dict] = []

    for b in bloques:
        oficiales = catalogo.get((b["grade"], b["subject"]), {})
        enunciado = plano(b["enunciado"])[:140]
        codigo = b["rotulo"]

        if enunciado and oficiales:
            puntajes = {
                code: difflib.SequenceMatcher(None, enunciado, plano(desc)[:140]).ratio()
                for code, desc in oficiales.items()
            }
            mejor = max(puntajes, key=puntajes.get)
            if puntajes[mejor] >= 0.55 and mejor != b["rotulo"]:
                avisos.append(
                    f"{b['source_ref']}: el PDF rotula {b['rotulo']} pero el enunciado es "
                    f"{mejor} (similitud {puntajes[mejor]:.2f}) — se usa {mejor}"
                )
                codigo = mejor
            elif puntajes[mejor] < 0.55 and b["rotulo"] not in oficiales:
                avisos.append(
                    f"{b['source_ref']}: {b['rotulo']} no existe en las Bases y el enunciado "
                    f"no calza con ninguno (mejor {mejor} {puntajes[mejor]:.2f}) — descartado"
                )
                continue

        if codigo not in oficiales:
            avisos.append(f"{b['source_ref']}: {codigo} sin OA en las Bases — descartado")
            continue

        for ind in b["indicadores"]:
            filas.append({
                "grade": b["grade"],
                "subject": b["subject"],
                "code": codigo,
                "text": ind["text"],
                "source_ref": ind["source_ref"],
            })
    return filas


# --- Limpieza y filtros -----------------------------------------------------

RUIDO_RE = re.compile(r"\s+")


def limpiar(t: str) -> str:
    t = RUIDO_RE.sub(" ", t).strip()
    t = re.sub(r"\s+([,;.:])", r"\1", t)
    t = re.sub(r"“\s+", "“", t)
    t = re.sub(r"\s+”", "”", t)
    if t and not t.endswith((".", ":", "?", "!", ")", "”")):
        t += "."
    return t


def es_valido(t: str) -> tuple[bool, str]:
    if len(t) < 20:
        return False, "muy corto"
    if t.rstrip(".").rstrip().endswith(("-", "…")):
        return False, "truncado"
    # Todo indicador describe qué hace el estudiante: verbo conjugado en plural.
    if not re.match(r"^[A-ZÁÉÍÓÚÑ¿“(]", t):
        return False, "no parte con mayúscula"
    return True, ""


def consolidar(filas: list[dict]) -> list[dict]:
    """Numera los indicadores por OA y descarta repetidos.

    Un mismo OA reaparece en varias unidades del programa con indicadores
    distintos: se acumulan todos en el orden en que salen del documento.
    """
    vistos: dict[tuple, set] = defaultdict(set)
    contador: dict[tuple, int] = defaultdict(int)
    salida = []
    for f in filas:
        f["text"] = limpiar(f["text"])
        ok, motivo = es_valido(f["text"])
        if not ok:
            f["rechazo"] = motivo
            continue
        clave = (f["grade"], f["subject"], f["code"])
        huella = f["text"].lower()
        if huella in vistos[clave]:
            continue
        vistos[clave].add(huella)
        contador[clave] += 1
        f["ordinal"] = contador[clave]
        salida.append(f)
    return salida


def procesar(seleccion: list[tuple]) -> tuple[list[dict], list[str]]:
    bloques: list[dict] = []
    avisos: list[str] = []
    for subject, grade, archivo, _ in seleccion:
        pdf = CONTENT_DIR / archivo
        if not pdf.exists():
            avisos.append(f"FALTA: {archivo} ({grade} {subject})")
            continue
        bs, av = extraer_pdf(pdf, grade, subject)
        bloques.extend(bs)
        avisos.extend(av)
    return consolidar(resolver_codigos(bloques, avisos)), avisos


# --- Salida SQL -------------------------------------------------------------

CABECERA_SQL = """\
-- Indicadores de Evaluación MINEDUC — 1° y 2° Básico
--
-- Fuente: los Programas de Estudio oficiales, un PDF por asignatura y nivel,
-- extraídos con backend/scripts/extract_curriculum_indicators.py. Los
-- indicadores NO están en las Bases Curriculares (de donde salen los OA de la
-- migración 006): están solo en los Programas.
--
-- La procedencia de cada PDF —URL oficial, captura, tamaño y sha256— queda en
-- backend/scripts/programas_descargados.json.
--
-- Los indicadores son oficiales: ninguno se generó con IA. Un OA sin
-- indicadores en su Programa queda con cero filas y la UI lo dice; no se
-- rellena con invención.
--
-- Aditiva: crea su propia tabla y no toca ni borra nada de curriculum_oa.
-- Idempotente: borra sus propias filas de 1° y 2° antes de insertar, así que
-- reejecutarla en cada deploy deja el mismo estado.

CREATE TABLE IF NOT EXISTS curriculum_indicator (
    id SERIAL PRIMARY KEY,
    oa_id INTEGER NOT NULL REFERENCES curriculum_oa(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'mineduc',
    source_ref VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (oa_id, ordinal)
);

CREATE INDEX IF NOT EXISTS ix_curriculum_indicator_oa_id ON curriculum_indicator(oa_id);

DELETE FROM curriculum_indicator WHERE source = 'mineduc' AND oa_id IN (
    SELECT id FROM curriculum_oa WHERE grade_level IN ('1° Básico', '2° Básico')
);

INSERT INTO curriculum_indicator (oa_id, text, ordinal, source, source_ref)
SELECT oa.id, v.text, v.ordinal, 'mineduc', v.source_ref
FROM (VALUES
"""

PIE_SQL = """
) AS v(grade_level, subject, code, ordinal, text, source_ref)
JOIN curriculum_oa oa
  ON oa.grade_level = v.grade_level AND oa.subject = v.subject AND oa.code = v.code
ON CONFLICT (oa_id, ordinal)
DO UPDATE SET text = EXCLUDED.text, source_ref = EXCLUDED.source_ref;
"""


def sq(t: str) -> str:
    return "'" + t.replace("'", "''") + "'"


def generar_sql(filas: list[dict]) -> str:
    valores = ",\n".join(
        f"  ({sq(f['grade'])}, {sq(f['subject'])}, {sq(f['code'])}, {f['ordinal']}, "
        f"{sq(f['text'])}, {sq(f['source_ref'])})"
        for f in filas
    )
    return CABECERA_SQL + valores + PIE_SQL


def informe(filas: list[dict], avisos: list[str]) -> None:
    por_par = defaultdict(list)
    for f in filas:
        por_par[(f["grade"], f["subject"])].append(f)

    catalogo = catalogo_oa()
    print(f"TOTAL: {len(filas)} indicadores\n")
    print(f"{'Nivel':<11} {'Asignatura':<36} {'OA c/ind':>9} {'OA en BD':>9} {'Indic':>6} {'máx/OA':>7}")
    print("-" * 84)
    total_sin = 0
    for (grade, subject), fs in sorted(por_par.items()):
        por_oa = defaultdict(int)
        for f in fs:
            por_oa[f["code"]] += 1
        en_bd = len(catalogo.get((grade, subject), {}))
        total_sin += en_bd - len(por_oa)
        print(
            f"{grade:<11} {subject:<36} {len(por_oa):>9} {en_bd:>9} "
            f"{len(fs):>6} {max(por_oa.values()):>7}"
        )
    print(f"\nOA sin ningún indicador: {total_sin}")

    for (grade, subject), fs in sorted(por_par.items()):
        con = {f["code"] for f in fs}
        faltan = [c for c in catalogo.get((grade, subject), {}) if c not in con]
        if faltan:
            print(f"  {grade} {subject}: {', '.join(sorted(faltan, key=lambda c: int(c[2:])))}")

    if avisos:
        print(f"\nAVISOS ({len(avisos)}):")
        for a in avisos:
            print(f"  {a}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    filtro = args[0] if args else ""
    if filtro.isdigit():
        seleccion = [p for p in PROGRAMAS if p[3] == int(filtro)]
    else:
        seleccion = [p for p in PROGRAMAS if filtro.lower() in p[2].lower()]

    filas, avisos = procesar(seleccion)

    if "--sql" in sys.argv:
        destino = Path(__file__).parents[1] / "migrations" / "008_curriculum_indicators.sql"
        destino.write_text(generar_sql(filas), encoding="utf-8")
        print(f"{len(filas)} indicadores → {destino}")
    else:
        informe(filas, avisos)
        print("\n=== MUESTRA ===")
        for f in filas[:6]:
            print(f"[{f['grade']} / {f['subject']} / {f['code']} #{f['ordinal']}] {f['source_ref']}")
            print(f"   {f['text']}\n")
