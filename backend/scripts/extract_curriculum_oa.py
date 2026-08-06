"""Extrae los OA directamente de los PDF oficiales de Bases Curriculares MINEDUC.

Se re-extrae desde el PDF en vez de reutilizar `curriculum_reference.md` porque
esa fuente arrastra 51 descripciones truncadas de 281 (18%), OA fusionados,
duplicados y hasta un "OA0" inexistente: anclar la IA a objetivos cortados a
media frase es peor que no anclarla.

Estructura del PDF (modo -layout), muy regular:

      Objetivos de Aprendizaje
      Ejes
      Los estudiantes serán capaces de:

      Lectura                       1     Reconocer que los textos escritos ...
                                          alguien para cumplir un propósito.

El número del OA cae siempre en la misma banda de columnas y las líneas de
continuación quedan indentadas bajo el texto.
"""

import re
import subprocess
import sys
import unicodedata
from collections import defaultdict

PDFS = {
    "1a6": "/root/apps/academia/content/articles-22394_bases.pdf",
    "7a2m": "/root/apps/academia/content/articles-37136_bases.pdf",
}

ORDINALES = {
    "primero": 1, "segundo": 2, "tercero": 3, "cuarto": 4,
    "quinto": 5, "sexto": 6, "séptimo": 7, "septimo": 7, "octavo": 8,
}

SUBJECT_CANON = {
    "lenguaje y comunicación": "Lenguaje y Comunicación",
    "lengua y literatura": "Lenguaje y Comunicación",
    "matemática": "Matemática",
    "ciencias naturales": "Ciencias Naturales",
    "historia, geografía y ciencias sociales": "Historia, Geografía y Cs. Sociales",
    "artes visuales": "Artes Visuales",
    "música": "Música",
    "tecnología": "Tecnología",
    "educación física y salud": "Educación Física",
    "orientación": "Orientación",
    "idioma extranjero: inglés": "Inglés",
}

# El layout no es fijo: en las páginas que repiten la columna "Ejes" el número
# cae cerca de la columna 32, y en las que no, cerca de la 6. Por eso la
# columna donde empieza el texto se calcula por ítem en vez de fijarse.
# El texto de un OA siempre arranca con verbo en mayúscula, lo que descarta
# los números sueltos de la prosa y los pies de página.
# El PDF de 7º a 2º medio numera con punto ("1. Leer...") y el de 1º a 6º sin
# él ("1 Leer..."), así que el punto es opcional.
ITEM_RE = re.compile(
    r"^(?P<lead>\s*)(?:(?P<eje>\S[^\d]{0,32}?)\s{2,})?(?P<num>\d{1,2})\.?\s+(?P<text>[A-ZÁÉÍÓÚÑ¿¡].*)$"
)
MAX_OA_NUM = 40

GRADE_LINE = re.compile(r"^\s*(Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|Séptimo|Octavo)\s*$", re.IGNORECASE)
BASICO_LINE = re.compile(r"^\s*[Bb]ásico\s*$")
# El PDF de 7º a 2º medio usa "Se espera que los y las estudiantes...".
START_MARKER = re.compile(
    r"^\s*(?:Los estudiantes ser[áa]n|Se espera que los y las estudiantes sean)\s+capaces de\s*:?\s*$"
)
FOOTER = re.compile(r"Bases Curriculares|Ministerio de Educación|Unidad de Curr[íi]culum")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def detect_subject(line: str) -> str | None:
    """Lee la asignatura del encabezado de página.

    Los dos PDF la ubican distinto: el de 1º a 6º la pone al inicio del
    encabezado, y el de 7º a 2º medio al final de
    "Bases Curriculares 2015 | 7° básico a 2° medio | <Asignatura>".
    Sin la segunda forma se perdía Ciencias Naturales entera en 7º y 8º.
    """
    head = line.strip()
    if not head or len(head) > 160:
        return None

    candidates = [head]
    if "|" in head:
        candidates.append(head.rsplit("|", 1)[-1].strip())

    for candidate in candidates:
        flat = strip_accents(candidate.lower())
        for raw, canon in SUBJECT_CANON.items():
            if flat.startswith(strip_accents(raw)):
                return canon
    return None


def extract(path: str) -> list[dict]:
    text = subprocess.run(
        ["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True
    ).stdout
    lines = text.split("\n")

    entries: list[dict] = []
    grade: str | None = None
    subject: str | None = None
    collecting = False
    current: dict | None = None

    def flush():
        nonlocal current
        if current and len(current["desc"]) > 20:
            current.pop("text_col", None)
            entries.append(current)
        current = None

    for index, line in enumerate(lines):
        # Página divisoria de nivel: "Primero" seguido de "Básico".
        m = GRADE_LINE.match(line)
        if m and index + 1 < len(lines) and BASICO_LINE.match(lines[index + 1]):
            flush()
            grade = f"{ORDINALES[strip_accents(m.group(1).lower())]}° Básico"
            collecting = False
            continue

        found = detect_subject(line)
        if found:
            if found != subject:
                flush()
            subject = found

        if START_MARKER.match(line):
            flush()
            collecting = True
            continue

        if not collecting or not grade or not subject:
            continue

        if FOOTER.search(line):
            # Pie de página: no corta la tabla, que continúa en la página siguiente.
            continue

        stripped = line.strip()
        if not stripped:
            continue

        m = ITEM_RE.match(line)
        if m and int(m.group("num")) <= MAX_OA_NUM:
            flush()
            current = {
                "grade": grade,
                "subject": subject,
                "num": int(m.group("num")),
                "desc": m.group("text").strip(),
                # Columna donde arranca el texto: las líneas de continuación
                # quedan alineadas ahí o más a la derecha.
                "text_col": m.start("text"),
            }
            continue

        if current:
            # La continuación se lee por COLUMNA, no por indentación: el nombre
            # del eje ocupa el margen izquierdo de la segunda línea
            # ("saludable      ten la condición física..."), así que mirar la
            # indentación del renglón descartaba la mitad de esos objetivos.
            col = max(current["text_col"] - 3, 0)
            right = line[col:].strip()
            left = line[:col].strip()
            # A la izquierda solo puede quedar el nombre del eje, nunca prosa.
            if right and len(left) <= 34 and not left.endswith((".", ":")):
                fragment = right.replace("»", "·")
                if current["desc"].endswith("-"):
                    current["desc"] = current["desc"][:-1] + fragment
                else:
                    current["desc"] += " " + fragment
        # Nada más corta la recolección: la tabla de OA sigue a través de los
        # saltos de página, y tanto el encabezado como el pie vuelven al
        # margen izquierdo. Terminarla ahí perdía todo salvo el primer OA.
        # La tabla se cierra sola al llegar al siguiente nivel, a la siguiente
        # asignatura o al siguiente "Los estudiantes serán capaces de:".

    flush()
    return entries


# --- Filtros de calidad -----------------------------------------------------
#
# El parser sigue la tabla a través de los saltos de página, y en algunas
# asignaturas (6º Lenguaje, 6º Ciencias, 8º Inglés) eso lo lleva a la sección
# de bibliografía, cuyas entradas también empiezan con un número. Estos tres
# filtros descartan 26 de 1026 filas.

# Una referencia bibliográfica siempre parte con el autor, así que va anclada.
BIBLIO_RE = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ.]*,?\s+){0,4}[A-Z]\.\s*[A-Z]?\.?\s*"
    r"(?:y|&|et al\.|,)?[^()]{0,60}\(\d{4}\)|^The\s|^Programme\s"
)
# Todo OA del currículum chileno empieza con un verbo en infinitivo.
VERBO_RE = re.compile(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]*(ar|er|ir)(se)?\b")
# Los títulos del PDF llevan tracking y salen como "O b s er var y p regun tar".
LETRAS_VALIDAS = {"a", "y", "o", "e", "u"}


def es_valido(desc: str) -> tuple[bool, str]:
    if len(desc) < 30:
        return False, "muy corta"
    if desc.rstrip().endswith(("-", "…", "...")):
        return False, "truncada"
    if BIBLIO_RE.match(desc):
        return False, "bibliografía"
    primeras = desc.split()[:8]
    sueltas = sum(1 for w in primeras if len(w) == 1 and w.isalpha() and w.lower() not in LETRAS_VALIDAS)
    if sueltas >= 3:
        return False, "texto con tracking"
    if not VERBO_RE.match(desc):
        return False, "no parte con infinitivo"
    return True, ""


def normalize(entries: list[dict]) -> list[dict]:
    """Deduplica por (nivel, asignatura, número) conservando la versión más larga."""
    best: dict[tuple, dict] = {}
    for e in entries:
        desc = e["desc"]
        # pdftotext decodifica la viñeta "»" del PDF como una "ú" suelta.
        # Una "ú" aislada no existe como palabra en español, así que es segura
        # de reemplazar por un separador legible.
        desc = re.sub(r"(?:^|\s)ú(?=\s)", " ·", desc)
        # A veces la viñeta queda pegada a la palabra siguiente ("úorganizando").
        # Se excluyen las pocas palabras españolas que sí empiezan con "ú".
        desc = re.sub(r"(?:^|\s)ú(?!nic|ltim|til|lcer|ter|vul)(?=[a-záéíóúñ])", " · ", desc)
        desc = re.sub(r"·\s*·+", "·", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        desc = re.sub(r"[\s·]+$", "", desc)
        e["desc"] = desc
        e["code"] = f"OA{e['num']}"
        ok, motivo = es_valido(e["desc"])
        if not ok:
            e["rechazo"] = motivo
            continue
        key = (e["grade"], e["subject"], e["code"])
        if key not in best or len(e["desc"]) > len(best[key]["desc"]):
            best[key] = e
    return sorted(best.values(), key=lambda e: (e["grade"], e["subject"], e["num"]))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "1a6"
    rows = normalize(extract(PDFS[which]))

    counts = defaultdict(int)
    for r in rows:
        counts[(r["grade"], r["subject"])] += 1

    print(f"TOTAL: {len(rows)} OA\n")
    print(f"{'Nivel':<12} {'Asignatura':<36} {'OA':>4}  {'máx':>4}")
    print("-" * 62)
    for (grade, subject), n in sorted(counts.items()):
        nums = [r["num"] for r in rows if r["grade"] == grade and r["subject"] == subject]
        print(f"{grade:<12} {subject:<36} {n:>4}  {max(nums):>4}")

    truncadas = [r for r in rows if r["desc"].rstrip().endswith(("…", "...", "-"))]
    cortas = [r for r in rows if len(r["desc"]) < 30]
    bleed = [r for r in rows if FOOTER.search(r["desc"])]
    print(f"\ntruncadas: {len(truncadas)}   muy cortas: {len(cortas)}   con bleed: {len(bleed)}")
    for r in (truncadas + cortas + bleed)[:8]:
        print(f"   {r['grade']} {r['subject'][:22]} {r['code']}: {r['desc'][:80]!r}")

    print("\n=== MUESTRA ===")
    for r in rows[:3]:
        print(f"[{r['grade']} / {r['subject']} / {r['code']}]\n   {r['desc'][:220]}\n")
