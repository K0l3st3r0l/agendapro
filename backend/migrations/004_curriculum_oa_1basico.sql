-- Objetivos de Aprendizaje (OA) MINEDUC — 1° Básico
-- Fuente: Bases Curriculares MINEDUC (Decreto 433/2012 y 614/2013),
-- vía /root/apps/academia/content/curriculum_reference.md
--
-- Nota de calidad: el texto fuente viene de una extracción automática de PDF.
-- Se limpiaron restos de OCR (encabezados/números de página mezclados en el texto),
-- pero dos OA quedan truncados en el original (marcados con "…"):
-- Lenguaje OA18 y Historia OA13. OA1-OA9 no están: según la nota de uso del
-- documento fuente, se omitieron a propósito los OA actitudinales/procedimentales
-- por no ser aptos para generar contenido de evaluación tipo quiz.

CREATE TABLE IF NOT EXISTS curriculum_oa (
    id SERIAL PRIMARY KEY,
    grade_level VARCHAR(50) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    code VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(grade_level, subject, code)
);

INSERT INTO curriculum_oa (grade_level, subject, code, description) VALUES
('1° Básico', 'Lenguaje y Comunicación', 'OA10', 'Leer independientemente y comprender textos no literarios escritos con oraciones simples (cartas, notas, instrucciones y artículos informativos) para entretenerse y ampliar su conocimiento del mundo: extrayendo información explícita e implícita formulando una opinión sobre algún aspecto de la lectura'),
('1° Básico', 'Lenguaje y Comunicación', 'OA11', 'Desarrollar el gusto por la lectura, explorando libros y sus ilustraciones.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA12', 'Asistir habitualmente a la biblioteca para elegir, escuchar, leer y explorar textos de su interés.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA13', 'Experimentar con la escritura para comunicar hechos, ideas y sentimientos, entre otros.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA14', 'Escribir oraciones completas para transmitir mensajes.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA15', 'Escribir con letra clara, separando las palabras con un espacio para que puedan ser leídas por otros con facilidad.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA16', 'Incorporar de manera pertinente en la escritura el vocabulario nuevo extraído de textos escuchados o leídos.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA17', 'Comprender y disfrutar versiones completas de obras de la literatura, narradas o leídas por un adulto, como: cuentos folclóricos y de autor poemas fábulas leyendas'),
('1° Básico', 'Lenguaje y Comunicación', 'OA18', 'Comprender textos orales (explicaciones, instrucciones, relatos, anécdotas, etc.) para obtener información y desarrollar su curiosidad por el mundo: estableciendo conexiones con sus propias experiencias visualizando lo que se describe en el texto formulando preguntas para obtener información adicional y aclarar dudas respondiendo preguntas abiertas…'),
('1° Básico', 'Lenguaje y Comunicación', 'OA19', 'Desarrollar la curiosidad por las palabras o expresiones que desconocen y adquirir el hábito de averiguar su significado.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA20', 'Disfrutar de la experiencia de asistir a obras de teatro infantiles o representaciones para ampliar sus posibilidades de expresión, desarrollar su creatividad y familiarizarse con el género.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA21', 'Participar activamente en conversaciones grupales sobre textos leídos o escuchados en clases o temas de su interés: expresando sus ideas u opiniones demostrando interés ante lo escuchado respetando turnos'),
('1° Básico', 'Lenguaje y Comunicación', 'OA22', 'Interactuar de acuerdo con las convenciones sociales en diferentes situaciones: presentarse a sí mismo y a otros saludar preguntar expresar opiniones, sentimientos e ideas situaciones que requieren el uso de fórmulas de cortesía, como por favor, gracias, perdón, permiso'),
('1° Básico', 'Lenguaje y Comunicación', 'OA23', 'Expresarse de manera coherente y articulada sobre temas de su interés: presentando información o narrando un evento relacionado con el tema incorporando frases descriptivas que ilustren lo dicho utilizando un vocabulario variado pronunciando adecuadamente y usando un volumen audible manteniendo una postura adecuada'),
('1° Básico', 'Lenguaje y Comunicación', 'OA24', 'Incorporar de manera pertinente en sus intervenciones orales el vocabulario nuevo extraído de textos escuchados o leídos.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA25', 'Desempeñar diferentes roles para desarrollar su lenguaje y autoestima, y aprender a trabajar en equipo.'),
('1° Básico', 'Lenguaje y Comunicación', 'OA26', 'Recitar con entonación y expresión poemas, rimas, canciones, trabalenguas y adivinanzas para fortalecer la confianza en sí mismos, aumentar el vocabulario y desarrollar su capacidad expresiva.'),

('1° Básico', 'Matemática', 'OA10', 'Demostrar que la adición y la sustracción son operaciones inversas, de manera concreta, pictórica y simbólica.'),
('1° Básico', 'Matemática', 'OA11', 'Reconocer, describir, crear y continuar patrones repetitivos (sonidos, figuras, ritmos...) y patrones numéricos hasta el 20, crecientes y decrecientes, usando material concreto, pictórico y simbólico, de manera manual y/o por medio de software educativo.'),
('1° Básico', 'Matemática', 'OA12', 'Describir y registrar la igualdad y la desigualdad como equilibrio y desequilibrio, usando una balanza en forma concreta, pictórica y simbólica del 0 al 20, usando el símbolo igual (=).'),
('1° Básico', 'Matemática', 'OA13', 'Describir la posición de objetos y personas con relación a sí mismos y a otros objetos y personas, usando un lenguaje común (como derecha e izquierda).'),
('1° Básico', 'Matemática', 'OA14', 'Identificar en el entorno figuras 3D y figuras 2D y relacionarlas, usando material concreto.'),
('1° Básico', 'Matemática', 'OA15', 'Identificar y dibujar líneas rectas y curvas.'),
('1° Básico', 'Matemática', 'OA16', 'Usar unidades no estandarizadas de tiempo para comparar la duración de eventos cotidianos.'),
('1° Básico', 'Matemática', 'OA17', 'Usar un lenguaje cotidiano para secuenciar eventos en el tiempo: días de la semana, meses del año y algunas fechas significativas.'),
('1° Básico', 'Matemática', 'OA18', 'Identificar y comparar la longitud de objetos, usando palabras como largo y corto.'),
('1° Básico', 'Matemática', 'OA19', 'Recolectar y registrar datos para responder preguntas estadísticas sobre sí mismo y el entorno, usando bloques, tablas de conteo y pictogramas.'),
('1° Básico', 'Matemática', 'OA20', 'Construir, leer e interpretar pictogramas.'),

('1° Básico', 'Ciencias Naturales', 'OA10', 'Diseñar instrumentos tecnológicos simples, considerando diversos materiales y sus propiedades para resolver problemas cotidianos.'),
('1° Básico', 'Ciencias Naturales', 'OA11', 'Describir y registrar el ciclo diario y las diferencias entre el día y la noche, a partir de la observación del Sol, la Luna, las estrellas y la luminosidad del cielo, entre otras, y sus efectos en los seres vivos y el ambiente.'),
('1° Básico', 'Ciencias Naturales', 'OA12', 'Describir y comunicar los cambios del ciclo de las estaciones y sus efectos en los seres vivos y el ambiente.'),

('1° Básico', 'Historia, Geografía y Cs. Sociales', 'OA10', 'Observar y describir paisajes de su entorno local, utilizando vocabulario geográfico adecuado (país, ciudad, camino, pueblo, construcciones, cordillera, mar, vegetación y desierto) y categorías de ubicación relativa (derecha, izquierda, delante, detrás, entre otros).'),
('1° Básico', 'Historia, Geografía y Cs. Sociales', 'OA11', 'Identificar trabajos y productos de su familia y su localidad y cómo estos aportan a su vida diaria, reconociendo la importancia de todos los trabajos, tanto remunerados como no remunerados.'),
('1° Básico', 'Historia, Geografía y Cs. Sociales', 'OA12', 'Conocer cómo viven otros niños en diferentes partes del mundo por medio de imágenes y relatos, ubicando en un globo terráqueo o mapamundi los países donde habitan y comparando su idioma, vestimenta, comida, fiestas, costumbres y principales tareas con las de niños chilenos.'),
('1° Básico', 'Historia, Geografía y Cs. Sociales', 'OA13', 'Mostrar actitudes y realizar acciones concretas en su entorno cercano (familia, escuela y comunidad) que reflejen: respeto al otro (ejemplos: escuchar atentamente al otro, tratar con cortesía a los demás, etc.) empatía (ejemplos: ayudar a los demás cuando sea necesario, no discriminar a otros por su aspecto o costumbres, etc.) responsabilidad (ejem…'),
('1° Básico', 'Historia, Geografía y Cs. Sociales', 'OA14', 'Explicar y aplicar algunas normas para la buena convivencia y para la seguridad y el autocuidado en su familia, en la escuela y en la vía pública.'),
('1° Básico', 'Historia, Geografía y Cs. Sociales', 'OA15', 'Identificar la labor que cumplen, en beneficio de la comunidad, instituciones como la escuela, la municipalidad, el hospital o la posta, Carabineros de Chile, y las personas que trabajan en ellas.')

ON CONFLICT (grade_level, subject, code) DO NOTHING;
