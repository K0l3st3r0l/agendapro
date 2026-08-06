# agent-bridge — imágenes con Codex desde el backend

Servicio HTTP mínimo que corre **en el host** y expone la herramienta `image_gen`
de Codex al backend, que vive en un contenedor.

## Por qué existe

Codex 0.146.0 trae una herramienta interna `image_gen` que **no aparece en
`codex --help`** — está en el binario (`image_generation_begin`,
`ExtensionItemImageGeneration`) y tiene su skill en
`~/.codex/skills/.system/imagegen/`. Su documentación dice textual:

> Does not require `OPENAI_API_KEY`

Es decir, genera contra la **suscripción de ChatGPT**, no contra la API de
plataforma. No cuesta dólares; cuesta cuota del plan y ~35 s por imagen.

Meter la CLI dentro del contenedor obligaría a instalar ahí el runtime de Node y
a copiar el `auth.json` de la suscripción. Por eso el host expone este puente.

## Lugar en la cascada

`app/services/images.py` resuelve cada palabra así:

1. **Caché en disco** — costo cero, latencia cero
2. **ARASAAC** — costo cero, ~0,3 s (resuelve casi todo el vocabulario de básica)
3. **Codex por este puente** — cero dólares, ~35 s, gasta cuota del plan
4. **OpenRouter `gpt-image-2`** — ~$0,018, ~22 s, siempre disponible

Si el puente está caído, apagado o sin `AGENT_BRIDGE_URL`, la capa 3 se salta
sola y todo sigue funcionando por OpenRouter.

## Seguridad

Las palabras llegan desde un documento generado por IA a partir del texto que
escribe la profesora: **entrada no confiable**. Las defensas:

- Escucha **solo en la IP del bridge de Docker** (`172.22.0.1`), nunca en `0.0.0.0`
- Token compartido en la cabecera `X-Bridge-Token`
- **El cliente no manda el prompt.** Manda palabra + estilo; la plantilla vive
  en el puente
- La palabra pasa por lista blanca (letras, espacios y guiones) y tope de 3
  palabras — sin eso, una frase de puras letras como *"ignora lo anterior y…"*
  pasa el filtro y quema 30 s de cuota
- `codex exec --sandbox read-only`, verificado que igual genera
- Una generación a la vez: cada invocación levanta un agente completo

## Instalación

```bash
sudo systemctl enable --now agendapro-agent-bridge
systemctl status agendapro-agent-bridge
curl http://172.22.0.1:8765/health
```

La unidad está en `/etc/systemd/system/agendapro-agent-bridge.service` y lleva el
`BRIDGE_TOKEN`, que debe coincidir con `AGENT_BRIDGE_TOKEN` del `.env` de
AgendaPro.

## Límite conocido

Esto funciona porque es **una persona usando su propia suscripción en su propio
VPS**. Cuando AgendaPro atienda a más profesores, servir sus peticiones por una
cuenta personal deja de ser viable —por cuota, concurrencia y términos de
servicio— y hay que apagar la capa 3 dejando `AGENT_BRIDGE_URL` vacío. El resto
de la cascada sigue igual.
