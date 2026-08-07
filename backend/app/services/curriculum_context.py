"""Contexto curricular MINEDUC para anclar la generación.

La tabla `curriculum_oa` existía desde julio pero nunca se usó en los prompts:
la IA inventaba objetivos de aprendizaje sin ninguna relación con el nivel.

El patrón sigue lo que funcionó en el RAG del Reglamento Interno de Anahuac
(ver wiki: anahuac/bugs/reglamento-ia-alucinaciones): **el contexto va en el
mensaje del usuario, no en el system prompt**. Ponerlo en el system hacía que
el modelo lo tratara como un rol a interpretar en vez de datos a citar.

Los OA se cargan siempre desde la base de datos. Nunca se confía en el texto
que manda el cliente: si el frontend pudiera inyectar descripciones de OA, la
"validación curricular" no validaría nada.
"""

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from app.models.curriculum_indicator import CurriculumIndicator
from app.models.curriculum_oa import CurriculumOA

logger = logging.getLogger(__name__)

MAX_OA_EN_CONTEXTO = 12
# Los Programas de Estudio traen hasta 31 indicadores para un mismo OA. Volcarlos
# todos repite el problema que ya obligó a acotar los OA: el modelo reparte la
# atención y el documento termina rozando decenas de desempeños en vez de evaluar
# unos pocos. Seis alcanzan para cubrir el rango de dificultad del OA, que es
# como el propio Programa los ordena (de habilidades básicas a superiores).
# Este tope solo rige el llenado AUTOMÁTICO (sin selección explícita de la
# profesora); ver MAX_INDICADORES_SELECCION para la selección manual.
MAX_INDICADORES_POR_OA = 6
# Tope duro cuando la profesora elige indicadores a mano. Más alto que el
# automático porque aquí la elección es intencional, no un relleno del
# backend — pero sigue habiendo un techo para no diluir la atención del
# modelo si marca los 31 de Educación Física. Nunca se trunca en silencio:
# el frontend avisa cuando la selección de un OA supera este número.
MAX_INDICADORES_SELECCION = 12

_REF_PATTERN = re.compile(r"^([A-ZÑ]+\d+):(\d+)$")


def _parse_indicator_refs(refs: list[str] | None) -> dict[str, set[int]]:
    """Agrupa referencias 'OA11:3' por código de OA. Mal formadas se descartan con log."""
    agrupados: dict[str, set[int]] = {}
    for raw in refs or []:
        match = _REF_PATTERN.match(raw.strip().upper())
        if not match:
            logger.warning("Referencia de indicador mal formada, descartada: %r", raw)
            continue
        codigo, ordinal = match.group(1), int(match.group(2))
        agrupados.setdefault(codigo, set()).add(ordinal)
    return agrupados


@dataclass
class CurriculumContext:
    block: str
    oa_codes: list[str] = field(default_factory=list)
    # Referencias "CODIGO:ordinal" de los indicadores efectivamente incluidos en
    # el bloque, en mayúsculas. Sirve para validar el indicator_ref que devuelva
    # el modelo: solo puede citar lo que realmente se le entregó.
    indicator_refs: set[str] = field(default_factory=set)


def fetch_oa(
    db: Session,
    grade_level: str,
    subject: str,
    codes: list[str] | None = None,
) -> list[CurriculumOA]:
    query = db.query(CurriculumOA).filter(
        CurriculumOA.grade_level == grade_level,
        CurriculumOA.subject == subject,
    )
    if codes:
        query = query.filter(CurriculumOA.code.in_([c.strip().upper() for c in codes if c.strip()]))
    # El código es siempre "OA" + número (ver normalize() en extract_curriculum_oa.py):
    # se ordena por ese número, no por id ni lexicográficamente, para que OA21 no
    # caiga después de OA9 ni al final del selector por haberse insertado tarde.
    orden_numerico = cast(func.substr(CurriculumOA.code, 3), Integer)
    return query.order_by(orden_numerico).all()


def fetch_indicators(db: Session, oa_ids: list[int]) -> dict[int, list[CurriculumIndicator]]:
    """{oa_id: [indicadores en orden]}. Una sola consulta para todos los OA."""
    if not oa_ids:
        return {}
    rows = (
        db.query(CurriculumIndicator)
        .filter(CurriculumIndicator.oa_id.in_(oa_ids))
        .order_by(CurriculumIndicator.oa_id, CurriculumIndicator.ordinal)
        .all()
    )
    agrupados: dict[int, list[CurriculumIndicator]] = {}
    for row in rows:
        agrupados.setdefault(row.oa_id, []).append(row)
    return agrupados


def build_context(
    db: Session,
    grade_level: str,
    subject: str,
    codes: list[str] | None = None,
    indicator_refs: list[str] | None = None,
) -> CurriculumContext:
    """Bloque de texto para inyectar en el prompt. Vacío si no hay OA cargados.

    Si la profesora marcó indicadores a mano para un OA (`indicator_refs`), esos
    mandan sobre el llenado automático para ESE OA — un OA sin selección propia
    sigue usando el tope automático de `MAX_INDICADORES_POR_OA`.
    """
    rows = fetch_oa(db, grade_level, subject, codes)
    if not rows:
        return CurriculumContext(block="")

    # Sin selección explícita de OA se acota el contexto: volcar 40 OA diluye la
    # atención del modelo y encarece la llamada sin mejorar el documento.
    if not codes:
        rows = rows[:MAX_OA_EN_CONTEXTO]

    # Los indicadores se cargan de la BD igual que los OA. El cliente no manda
    # texto, solo referencias que se resuelven aquí: si pudiera mandar texto,
    # el anclaje curricular dejaría de anclar nada.
    indicadores = fetch_indicators(db, [row.id for row in rows])
    refs_por_oa = _parse_indicator_refs(indicator_refs)

    bloques = []
    hay_indicadores = False
    refs_usados: set[str] = set()
    for row in rows:
        bloques.append(f"- {row.code}: {row.description}")
        propios = indicadores.get(row.id, [])
        ordinales_elegidos = refs_por_oa.get(row.code.upper())

        if ordinales_elegidos:
            seleccionados = [ind for ind in propios if ind.ordinal in ordinales_elegidos]
            faltantes = ordinales_elegidos - {ind.ordinal for ind in seleccionados}
            if faltantes:
                logger.warning(
                    "Referencias de indicador inexistentes para %s, descartadas: %s",
                    row.code, sorted(faltantes),
                )
            if len(seleccionados) > MAX_INDICADORES_SELECCION:
                logger.warning(
                    "%s: %d indicadores marcados a mano, se truncan a %d",
                    row.code, len(seleccionados), MAX_INDICADORES_SELECCION,
                )
                seleccionados = seleccionados[:MAX_INDICADORES_SELECCION]
        else:
            seleccionados = propios[:MAX_INDICADORES_POR_OA]

        if seleccionados:
            hay_indicadores = True
            bloques.append(f"  Indicadores de evaluación oficiales de {row.code}:")
            for ind in seleccionados:
                bloques.append(f"    · [{row.code}:{ind.ordinal}] {ind.text}")
                refs_usados.add(f"{row.code.upper()}:{ind.ordinal}")

    listado = "\n".join(bloques)
    disponibles = ", ".join(row.code for row in rows)

    reglas = [
        "- El contenido debe apuntar a los OA listados arriba.",
        f"- En metadata.oa_codes incluye únicamente códigos de esta lista: {disponibles}.",
        "- No inventes códigos OA ni cites objetivos que no aparezcan arriba.",
        "- Si un OA no calza con el tema pedido, simplemente no lo incluyas.",
    ]
    if hay_indicadores:
        reglas.append(
            "- Cada pregunta o actividad debe evaluar alguno de los indicadores listados "
            "para su OA. No inventes indicadores ni evalúes desempeños que no estén ahí; "
            "si un OA no trae indicadores, guíate solo por su enunciado."
        )
        reglas.append(
            "- Cada indicador va precedido de su referencia entre corchetes, ej. '[OA11:3]'. "
            "Cuando el campo del ítem lo pida, copia esa referencia SIN corchetes (ej. 'OA11:3'); "
            "nunca inventes una referencia que no aparezca arriba."
        )

    block = (
        "\n\nCURRÍCULUM OFICIAL MINEDUC — Objetivos de Aprendizaje de "
        f"{subject}, {grade_level}:\n{listado}\n\n"
        "REGLAS SOBRE EL CURRÍCULUM:\n" + "\n".join(reglas) + "\n"
    )
    return CurriculumContext(
        block=block,
        oa_codes=[row.code for row in rows],
        indicator_refs=refs_usados,
    )


def valid_codes(db: Session, grade_level: str, subject: str) -> set[str]:
    """Códigos realmente existentes, para descartar los que el modelo invente."""
    rows = (
        db.query(CurriculumOA.code)
        .filter(CurriculumOA.grade_level == grade_level, CurriculumOA.subject == subject)
        .all()
    )
    return {row[0] for row in rows}
