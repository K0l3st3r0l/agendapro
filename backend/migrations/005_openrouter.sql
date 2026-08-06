-- OpenRouter como pasarela única para texto e imágenes.
--
-- Contexto (2026-08-06): la generación de imágenes por Gemini quedó inutilizable
-- (429 por cuota agotada tras desactivar billing) y tres model IDs configurados
-- ya no existen en la API de Google:
--   gemini-2.0-flash-preview-image-generation  ← era el default de imágenes
--   gemini-2.0-flash-exp
--   gemini-2.5-pro-preview-03-25
--
-- Nota sobre gemini_image_model: la columna NO se elimina a propósito. Un DROP
-- COLUMN es irreversible sin restaurar respaldo y no gana nada — el código deja
-- de leerla y queda inerte. Ver /root/apps/CLAUDE.md, regla de base de datos.

ALTER TABLE settings ADD COLUMN IF NOT EXISTS openrouter_api_key VARCHAR;
ALTER TABLE settings ADD COLUMN IF NOT EXISTS text_model  VARCHAR DEFAULT 'deepseek/deepseek-v4-flash';
ALTER TABLE settings ADD COLUMN IF NOT EXISTS image_model VARCHAR DEFAULT 'google/gemini-3.1-flash-lite-image';

-- Sanear los model IDs muertos para que Configuración no ofrezca opciones rotas.
UPDATE settings
   SET gemini_model = 'gemini-2.5-flash'
 WHERE gemini_model IS NULL
    OR gemini_model IN (
        'gemini-2.5-pro-preview-03-25',
        'gemini-2.0-flash',
        'gemini-2.0-flash-exp',
        'gemini-2.0-flash-preview-image-generation'
    );

-- Rellenar los defaults en filas que ya existían antes de esta migración.
UPDATE settings SET text_model  = 'deepseek/deepseek-v4-flash'          WHERE text_model  IS NULL;
UPDATE settings SET image_model = 'google/gemini-3.1-flash-lite-image'  WHERE image_model IS NULL;
