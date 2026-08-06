"""Baja los Programas de Estudio MINEDUC y verifica cada archivo por su portada.

curriculumnacional.cl no responde (timeout contra 52.72.21.30; el apex sirve una
página de "sitio temporalmente fuera de servicio"), así que se lee el mirror del
Internet Archive, que conserva la URL oficial y los bytes originales.

Cuidado con las capturas recientes: el crawler las cortó en 1 MiB exacto y el
PDF queda ilegible. Se elige la captura más pesada y se descarta cualquier
descarga de exactamente 1048576 bytes.

Uso: python3 download_programas.py <tanda|slug>
"""

import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

DESTINO = Path("/root/apps/academia/content")
REGISTRO = Path(__file__).parent / "programas_descargados.json"
UA = "AgendaPro-CurriculumBot/1.0 (+contacto: mhrehbein@gmail.com)"
PAUSA = 2.5
TRUNCADO = 1048576

# (archivo destino, article_id, nivel esperado en la portada, asignatura esperada, tanda)
CATALOGO = [
    ("programa_lenguaje_1basico.pdf", 18871, "primer", "lenguaje", 1),
    ("programa_lenguaje_2basico.pdf", 18958, "segundo", "lenguaje", 1),
    ("programa_matematica_1basico.pdf", 18976, "primer", "matematica", 1),
    ("programa_matematica_2basico.pdf", 18977, "segundo", "matematica", 1),
    ("programa_ciencias_1basico.pdf", 20714, "primer", "ciencias naturales", 2),
    ("programa_ciencias_2basico.pdf", 20715, "segundo", "ciencias naturales", 2),
    ("programa_historia_1basico.pdf", 18968, "primer", "historia", 2),
    ("programa_historia_2basico.pdf", 18969, "segundo", "historia", 2),
    ("programa_edfisica_1basico.pdf", 20738, "primer", "educacion fisica", 3),
    ("programa_edfisica_2basico.pdf", 20739, "segundo", "educacion fisica", 3),
    ("programa_orientacion_1basico.pdf", 20722, "primer", "orientacion", 3),
    ("programa_orientacion_2basico.pdf", 20723, "segundo", "orientacion", 3),
    ("programa_musica_1basico.pdf", 20704, "primer", "musica", 3),
    ("programa_musica_2basico.pdf", 20705, "segundo", "musica", 3),
    ("programa_artes_1basico.pdf", 20746, "primer", "artes visuales", 3),
    ("programa_artes_2basico.pdf", 20747, "segundo", "artes visuales", 3),
    ("programa_tecnologia_1basico.pdf", 20730, "primer", "tecnologia", 3),
    ("programa_tecnologia_2basico.pdf", 20731, "segundo", "tecnologia", 3),
]

ORDINAL = {"primer": ["primer", "1º", "1°"], "segundo": ["segundo", "2º", "2°"]}


def plano(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def curl(url: str, destino: Path | None = None, intentos: int = 4) -> tuple[int, str]:
    """GET con backoff exponencial ante 429/5xx."""
    espera = 6
    for _ in range(intentos):
        cmd = ["curl", "-sS", "-L", "--max-time", "300", "-A", UA, "-w", "%{http_code}"]
        if destino:
            cmd += ["-o", str(destino)]
        cmd.append(url)
        r = subprocess.run(cmd, capture_output=True, text=True)
        salida = r.stdout
        codigo = salida[-3:] if destino else salida.rpartition("\n")[2][-3:]
        cuerpo = "" if destino else salida[: -len(codigo)]
        if codigo == "200":
            return 200, cuerpo
        if codigo in ("429", "500", "502", "503", "504"):
            time.sleep(espera)
            espera *= 2
            continue
        return int(codigo) if codigo.isdigit() else 0, cuerpo
    return 0, ""


# El crawler cortó algunas capturas en 1 MiB exacto, y cuál quedó completa no
# sigue un patrón por fecha: el Programa de Orientación 1º solo está entero
# desde 2022 y el resto lo está en 2018. Por eso se listan las capturas reales
# con el CDX y se prueban de la más pesada a la más liviana. Los años sueltos
# son el respaldo para cuando el CDX responde 503, que lo hace seguido.
ANCLAS = ["2018", "2019", "2022", "2024", "2017", "2020", "2016"]


def capturas(article_id: int) -> list[str]:
    """Timestamps con estado 200, de la captura más pesada a la más liviana."""
    codigo, cuerpo = curl(
        "https://web.archive.org/cdx/search/cdx?url=curriculumnacional.cl/614/"
        f"articles-{article_id}_programa.pdf&output=json&filter=statuscode:200&fl=timestamp,length"
    )
    if codigo != 200 or not cuerpo.strip().startswith("["):
        return []
    filas = json.loads(cuerpo)[1:]
    return [ts for ts, _ in sorted(filas, key=lambda f: -int(f[1]))]


def portada(pdf: Path) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", "-f", "1", "-l", "2", str(pdf), "-"],
        capture_output=True, text=True,
    )
    return plano(r.stdout)


def verificar(pdf: Path, nivel: str, asignatura: str) -> str | None:
    if pdf.stat().st_size == TRUNCADO:
        return "captura truncada en 1 MiB"
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    if info.returncode != 0:
        return "PDF ilegible"
    tapa = portada(pdf)
    if plano(asignatura) not in tapa:
        return f"la portada no dice {asignatura!r}: {tapa[:90]!r}"
    if not any(o in tapa for o in ORDINAL[nivel]):
        return f"la portada no dice {nivel!r}: {tapa[:90]!r}"
    return None


def bajar(archivo: str, article_id: int, nivel: str, asignatura: str) -> dict:
    destino = DESTINO / archivo
    oficial = f"https://www.curriculumnacional.cl/614/articles-{article_id}_programa.pdf"
    for ts in (capturas(article_id) or ANCLAS):
        url = f"https://web.archive.org/web/{ts}id_/{oficial}"
        time.sleep(PAUSA)
        codigo, _ = curl(url, destino)
        if codigo != 200 or not destino.exists():
            continue
        problema = verificar(destino, nivel, asignatura)
        if problema:
            print(f"    descartada {ts}: {problema}")
            continue
        datos = destino.read_bytes()
        paginas = subprocess.run(["pdfinfo", str(destino)], capture_output=True, text=True).stdout
        return {
            "archivo": archivo,
            "article_id": article_id,
            "url_oficial": oficial,
            "captura": ts,
            "bytes": len(datos),
            "sha256": hashlib.sha256(datos).hexdigest(),
            "paginas": int(re.search(r"Pages:\s+(\d+)", paginas).group(1)),
        }
    destino.unlink(missing_ok=True)
    return {"archivo": archivo, "article_id": article_id, "error": "sin captura utilizable"}


def main():
    filtro = sys.argv[1] if len(sys.argv) > 1 else "1"
    # Un dígito suelto es el número de tanda; cualquier otra cosa, parte del
    # nombre de archivo. Sin esta distinción "1" también calzaba con todos los
    # `*_1basico.pdf` y la tanda dejaba de acotar nada.
    if filtro.isdigit():
        pendientes = [c for c in CATALOGO if str(c[4]) == filtro]
    else:
        pendientes = [c for c in CATALOGO if filtro in c[0]]
    if not pendientes:
        sys.exit(f"nada que bajar para {filtro!r}")

    registro = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else {}
    fallos_seguidos = 0

    for archivo, article_id, nivel, asignatura, _ in pendientes:
        if archivo in registro and (DESTINO / archivo).exists():
            print(f"✓ {archivo} ya está")
            continue
        print(f"→ {archivo} (articles-{article_id})")
        r = bajar(archivo, article_id, nivel, asignatura)
        if "error" in r:
            fallos_seguidos += 1
            print(f"  ✗ {r['error']}")
            if fallos_seguidos >= 2:
                sys.exit("abortado: dos fallos seguidos")
            continue
        fallos_seguidos = 0
        registro[archivo] = r
        REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=2))
        print(f"  ✓ {r['bytes']:>9} bytes · {r['paginas']} pág · captura {r['captura']}")
        print(f"    sha256 {r['sha256']}")


if __name__ == "__main__":
    main()
