---
colors:
  projector:
    bg: "#FFFFFF"
    surface: "#F4F6FA"
    ink: "#111827"
    ink-soft: "#374151"
    accent: "#1D4ED8"
    accent-ink: "#FFFFFF"
    correct: "#065F46"
    correct-bg: "#D1FAE5"
    rule: "#111827"
  app:
    primary: "#2563EB"
    ink: "#111827"
    muted: "#6B7280"
typography:
  projector-title:
    size: "clamp(2.2rem, 7vh, 5rem)"
    weight: "800"
    leading: "1.05"
  projector-body:
    size: "clamp(1.4rem, 5vh, 3.2rem)"
    weight: "600"
    leading: "1.25"
  projector-min:
    size: "clamp(1rem, 3vh, 1.8rem)"
    weight: "600"
  app-base:
    family: "Inter, system-ui, sans-serif"
    size: "1rem"
rounded:
  card: "1.5rem"
  control: "0.75rem"
spacing:
  scene-pad: "6vh"
  stack: "3vh"
components:
  scene-card:
    background: "{colors.projector.bg}"
    color: "{colors.projector.ink}"
    padding: "{spacing.scene-pad}"
  quiz-option:
    background: "{colors.projector.surface}"
    color: "{colors.projector.ink}"
    rounded: "{rounded.card}"
    border: "{colors.projector.rule}"
  quiz-option-correct:
    background: "{colors.projector.correct-bg}"
    color: "{colors.projector.correct}"
  player-control:
    background: "{colors.projector.ink}"
    color: "{colors.projector.bg}"
    rounded: "{rounded.control}"
---

# Sistema visual — AgendaPro

Dos superficies con reglas distintas. No comparten componentes de presentación.

| Superficie | Modo | Medio |
|---|---|---|
| App (calendario, constructor, documentos, editor de clases) | Operate | Monitor, a 50 cm |
| Player de clases (`/clases/:id/presentar`) | Experience | Proyector de sala, a 8 metros |

## Overview

La app hereda el lenguaje existente: Tailwind, `primary` azul, Inter, `darkMode: class`.
No se toca.

El **player** es un medio distinto y por eso tiene tokens propios. Está diseñado
para el peor proyector de una sala de colegio y para niños de 6 a 7 años que
recién decodifican.

Supuesto declarado: **la pantalla está duplicada**, no extendida. En una sala con
un cable HDMI, la profesora ve exactamente lo mismo que se proyecta. De ahí sale
la regla más importante del player: *nada que la profesora necesite leer puede
estar permanentemente en pantalla*, porque también lo verían los niños.

## Colors

El player usa **fondo claro por defecto**, que es contraintuitivo y deliberado.
El negro de un proyector con luz ambiente no es negro: es gris claro. Un tema
oscuro se lava y el contraste real colapsa. El blanco es la máxima luz que el
equipo puede entregar, así que el texto oscuro sobre fondo claro es lo que mejor
se lee en una sala con las cortinas abiertas.

- Contraste mínimo **7:1**, no el 4.5:1 de WCAG AA: el medio degrada lo que se
  mide en el monitor.
- Prohibido el gris claro sobre blanco para texto.
- El color nunca es el único portador de significado: la alternativa correcta se
  marca con color **y** con un ícono **y** con un cambio de peso tipográfico.
- `TV o pantalla LED` podrá activar un tema oscuro más adelante; no es el default
  porque no es el caso mayoritario.

## Typography

Tamaños en `vh`, nunca en `px`: hay salas con proyectores de 1024×768 y otras con
1920×1080, y el texto tiene que ocupar la misma proporción de pantalla en ambas.

- Título de escena: 7vh
- Cuerpo proyectado: 5vh
- **Mínimo absoluto: 3vh.** Si un texto no merece 3vh, no va en la proyección.

Referencia que justifica los límites de contenido del `LessonSpec`: a 5vh en
1024×768 entran unos 40–45 caracteres por línea. Un `body` de 90 caracteres son
dos líneas; una viñeta de recap de 80, dos líneas.

## Layout

Cada tipo de escena tiene una **composición distinta**, no el mismo molde con
otro color. Cinco escenas que se ven iguales hacen una clase monótona.

| Escena | Composición |
|---|---|
| `concept` | Idea grande arriba, imagen de apoyo al costado, mucho aire |
| `example` | La imagen domina (≥50% del alto); el texto la subtitula |
| `process` | Pasos en progresión horizontal, numerados, revelados de a uno |
| `quiz` | Pregunta fija arriba; alternativas como tarjetas grandes con imagen |
| `recap` | Cierre visualmente distinto a todo lo anterior: se nota que terminó |

En 1° y 2° básico la imagen ocupa al menos la mitad de la pantalla en las escenas
que la tienen. La imagen es el contenido; el texto la acompaña.

## Shapes

Radios amplios (`1.5rem` en tarjetas). Nada de bordes de 1px: a 8 metros
desaparecen. Las separaciones se hacen con espacio y contraste de fondo, no con
líneas finas.

## Components

### `scene-card`
Contenedor de escena a pantalla completa. Padding de 6vh. Nunca scrollea: si el
contenido no cabe, el contenido está mal, no el contenedor.

### `quiz-option`
Objetivo táctil grande —muy por encima de los 44px, porque se toca en un pizarrón
o se apunta desde 8 metros—. Lleva imagen arriba y etiqueta abajo. En 1°–2° la
imagen es obligatoria: una alternativa de solo texto convierte la pregunta en una
prueba de lectura.

Estados: reposo, foco (anillo grueso, no sutil), correcta revelada, incorrecta
descartada.

### `player-control`
Barra de control que **se auto-oculta a los 3 segundos** sin actividad del mouse
y reaparece al moverlo. En pantalla duplicada, todo control visible se proyecta.

### `narration-panel`
Guion hablado y nota operativa de la profesora. **Oculto por defecto**, se abre
con la tecla `N`. No puede quedar fijo: se proyectaría.

## Do's and Don'ts

**Do**
- Medir el contraste asumiendo que el proyector lo va a degradar.
- Dar a cada tipo de escena una composición propia.
- Dejar que la imagen mande en 1° y 2° básico.
- Mantener el foco visible y grueso: la clase se maneja con teclado.

**Don't**
- Tema oscuro por defecto en proyección.
- Líneas de 1px, texto gris, gradientes sutiles (producen banding).
- Tamaños en `px` para contenido proyectado.
- Dejar la narración o las notas del docente permanentemente en pantalla.
- Animar para compensar una jerarquía débil.
