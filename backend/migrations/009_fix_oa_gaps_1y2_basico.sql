-- Cierra los 3 huecos de curriculum_oa (migración 006) que dejaban 17
-- indicadores sin fila donde colgar en 1° y 2° básico. Ver
-- wiki/projects/agendapro/decisions/indicadores-evaluacion-1y2-basico.md
-- ("Brechas conocidas").
--
-- a) Matemática 2° OA21 no existía: el extractor de 006 usa `pdftotext
--    -layout`, que pega los superíndices de nota al pie al texto (mismo
--    defecto documentado para los indicadores). En la página 234 de
--    articles-22394_bases.pdf, el marcador "²¹" que sigue a "sobre juegos"
--    quedó leído como el número "21" y se fusionó dentro de OA20, comiéndose
--    el OA21 real. Verificado filtrando por altura de fuente con
--    `pdftotext -bbox-layout` (extract_curriculum_indicators.sin_cuerpo_menor):
--    sin el superíndice, la tabla lee limpio "20 Recolectar... pictogramas."
--    / "21 Registrar en tablas... monedas." — dos OA, no uno.
--
-- b) Tecnología 1° y 2°, eje TIC (OA5 y OA6): nunca se extrajeron. El mismo
--    defecto de layout hizo que sus dos primeras palabras y el número de
--    ítem se perdieran contra el nombre del eje ("Tecnologías de la
--    Información y la Comunicación", que ocupa 2-3 líneas), y el resto del
--    texto de OA5+OA6 quedó pegado como cola de OA4. Se limpia también la
--    descripción de OA4 en ambos niveles (mismo origen, mismas filas que ya
--    hay que tocar para insertar OA5/OA6) — no estaba en el pedido original
--    pero es el mismo bug, confirmado con la misma técnica de bbox.
--
-- Fuente de los 8 enunciados: páginas 232-234 (Matemática) y 191, 195
-- (Tecnología) de academia/content/articles-22394_bases.pdf, leídas con
-- pdftotext -bbox-layout y sin_cuerpo_menor() para descartar superíndices —
-- misma técnica que extract_curriculum_indicators.py, no un nuevo script.
--
-- Convergente: solo INSERT ... ON CONFLICT DO UPDATE sobre la tripleta
-- (grade_level, subject, code) de uq_curriculum_oa. Re-ejecutar el
-- directorio completo en cada deploy deja el mismo estado.

INSERT INTO curriculum_oa (grade_level, subject, code, description) VALUES
  ('2° Básico', 'Matemática', 'OA20', 'Recolectar y registrar datos para responder preguntas estadísticas sobre juegos con monedas y dados, usando bloques y tablas de conteo y pictogramas.'),
  ('2° Básico', 'Matemática', 'OA21', 'Registrar en tablas y gráficos de barra simple, resultados de juegos aleatorios con dados y monedas.'),
  ('1° Básico', 'Tecnología', 'OA4', 'Probar y explicar los resultados de los trabajos propios y de otros, de forma individual o en equipos, dialogando sobre sus ideas e identificando lo que podría hacerse de otra manera.'),
  ('1° Básico', 'Tecnología', 'OA5', 'Usar software de dibujo para crear y representar ideas por medio de imágenes, guiados por el docente.'),
  ('1° Básico', 'Tecnología', 'OA6', 'Explorar y usar una variedad de software educativos (simuladores, libros digitales, interactivos y creativos, entre otros) para lograr aprendizajes significativos y una interacción apropiada con las TIC.'),
  ('2° Básico', 'Tecnología', 'OA4', 'Probar y explicar los resultados de los trabajos propios y de otros, de forma individual o en equipos, dialogando sobre sus ideas y señalando cómo podría mejorar el trabajo en el futuro.'),
  ('2° Básico', 'Tecnología', 'OA5', 'Usar software de dibujo para crear y representar diferentes ideas por medio de imágenes.'),
  ('2° Básico', 'Tecnología', 'OA6', 'Usar procesador de textos para crear, editar y guardar información.')
ON CONFLICT (grade_level, subject, code)
DO UPDATE SET description = EXCLUDED.description;

-- Los 17 indicadores que estos OA destrababan. Misma fuente y mismo parser
-- que 008 (Programas de Estudio), solo que resolver_codigos() los descartaba
-- porque el catálogo de Bases —construido con el mismo extractor buggy de
-- 006— tampoco tenía OA21 ni el eje TIC contra qué resolver el rótulo.
-- Sin DELETE: son filas nuevas sobre OA que 008 nunca pudo insertar, así que
-- no hay basura previa que limpiar. ON CONFLICT (oa_id, ordinal) basta.

INSERT INTO curriculum_indicator (oa_id, text, ordinal, source, source_ref)
SELECT oa.id, v.text, v.ordinal, 'mineduc', v.source_ref
FROM (VALUES
  ('2° Básico', 'Matemática', 'OA21', 1, 'Registran resultados de juegos aleatorios con dados y monedas en tablas.', 'programa_matematica_2basico.pdf#p138'),
  ('2° Básico', 'Matemática', 'OA21', 2, 'Registran resultados de juegos aleatorios con dados y monedas en gráficos de barra simple.', 'programa_matematica_2basico.pdf#p138'),

  ('1° Básico', 'Tecnología', 'OA5', 1, 'Usan software de dibujo en funciones como abrir, cerrar, guardar, arrastrar el mouse y cliquear.', 'programa_tecnologia_1basico.pdf#p54'),
  ('1° Básico', 'Tecnología', 'OA5', 2, 'Dibujan ideas, usando líneas rectas y curvas, triángulos, cuadrados y círculos.', 'programa_tecnologia_1basico.pdf#p54'),
  ('1° Básico', 'Tecnología', 'OA5', 3, 'Crean imágenes guiados por el docente, usando pincel, lápiz, brocha, goma y relleno.', 'programa_tecnologia_1basico.pdf#p54'),
  ('1° Básico', 'Tecnología', 'OA6', 1, 'Juegan y avanza en distintos niveles de complejidad.', 'programa_tecnologia_1basico.pdf#p54'),
  ('1° Básico', 'Tecnología', 'OA6', 2, 'Reconocen los iconos para entrar, salir y avanzar en las aplicaciones (libros digitales y software interactivos).', 'programa_tecnologia_1basico.pdf#p54'),
  ('1° Básico', 'Tecnología', 'OA6', 3, 'Siguen las instrucciones de los juegos interactivos y explican lo aprendido a un par o a un adulto.', 'programa_tecnologia_1basico.pdf#p54'),
  ('1° Básico', 'Tecnología', 'OA6', 4, 'Leen textos simples en la pantalla.', 'programa_tecnologia_1basico.pdf#p54'),

  ('2° Básico', 'Tecnología', 'OA5', 1, 'Dibujan y pintan líneas rectas y curvas, flechas, rombos y polígonos.', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA5', 2, 'Dibujan ideas, combinando líneas y formas predeterminadas (como estrellas, cruces, globos).', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA5', 3, 'Crean imágenes cambiando color y tamaño de pinceles, lápices, brochas y formas.', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA6', 1, 'Abren, cierran y guardan archivos de texto.', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA6', 2, 'Usan las características básicas de un procesador de textos (por ejemplo: tipo y tamaño de fuente, tamaño de papel, vista de página).', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA6', 3, 'Usan opciones de edición para cortar y pegar texto en un documento.', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA6', 4, 'Insertan y ajustan imágenes o autoformas en documentos.', 'programa_tecnologia_2basico.pdf#p54'),
  ('2° Básico', 'Tecnología', 'OA6', 5, 'Crean documentos, combinan textos y formas en un archivo.', 'programa_tecnologia_2basico.pdf#p54')
) AS v(grade_level, subject, code, ordinal, text, source_ref)
JOIN curriculum_oa oa
  ON oa.grade_level = v.grade_level AND oa.subject = v.subject AND oa.code = v.code
ON CONFLICT (oa_id, ordinal)
DO UPDATE SET text = EXCLUDED.text, source_ref = EXCLUDED.source_ref;
