-- La migración 005 agregó las columnas de OpenRouter (openrouter_api_key,
-- text_model, image_model) y saneó los model IDs muertos, pero se olvidó de
-- preferred_provider. Las filas que ya existían quedaron apuntando a 'gemini',
-- que era el default viejo de la columna.
--
-- Efecto visible: el botón "Automático" del constructor anunciaba "Usa Google
-- Gemini" y toda generación en modo auto se iba a Gemini en vez de a OpenRouter,
-- que es más barato (un documento por $0,00033) y no arrastra los ~900 tokens de
-- "thinking" que gemini-2.5-flash gasta hasta en un prompt trivial.
--
-- Solo se mueven las filas que están en el default histórico: si alguien eligió
-- xAI u OpenAI a propósito, esa decisión se respeta.

UPDATE settings
   SET preferred_provider = 'openrouter'
 WHERE preferred_provider IS NULL
    OR preferred_provider = 'gemini';
