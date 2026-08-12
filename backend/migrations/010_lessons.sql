-- Clases visuales proyectables.
--
-- Tabla propia y no una extensión de `documents`: ese modelo está hecho para
-- imprimibles (raw_html, exportación PDF/DOCX, vínculo textual [doc_id:N] con el
-- calendario) y una clase necesita escenas ordenadas, preguntas referenciadas,
-- assets con estado y notas privadas que nunca se proyectan. Mezclarlos obligaría
-- a ramificar exportadores, preview y filtros por un tipo que no comparte nada.
--
-- El spec completo va en un solo JSONB: se guarda y se lee atómicamente, y su
-- forma la valida Pydantic (`app/schemas/lesson.py`) antes de llegar acá.
--
-- Idempotente: deploy.sh corre todos los .sql en orden y en cada deploy.

CREATE TABLE IF NOT EXISTS lessons (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title          VARCHAR NOT NULL,
    subject        VARCHAR NOT NULL,
    grade_level    VARCHAR NOT NULL,
    status         VARCHAR NOT NULL DEFAULT 'draft',
    schema_version VARCHAR NOT NULL DEFAULT '1.0',
    spec           JSONB   NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW(),
    updated_at     TIMESTAMP DEFAULT NOW()
);

-- La biblioteca lista las clases de una profesora por fecha de edición, que es
-- la única consulta del listado.
CREATE INDEX IF NOT EXISTS ix_lessons_user_updated ON lessons(user_id, updated_at DESC);
