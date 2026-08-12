import type { VisualTheme } from '../../types/lesson';

/** Formas de fondo por mundo visual.
 *
 * Cada clase se ve distinta según su contenido, sin que la IA genere nada
 * gráfico: elige el mundo (`metadata.visual_theme`) y estas formas están
 * dibujadas acá. Son grandes, planas y tenues —ancladas a las esquinas— para
 * dar carácter sin competir con el texto ni invadir la zona de lectura.
 *
 * Planas y sin degradados a propósito: un gradiente proyectado produce banding.
 */
const FORMAS: Record<VisualTheme, [string, string]> = {
  // Círculos y cuadrados: el vocabulario visual de las cantidades y patrones.
  numeros: [
    '<circle cx="60" cy="40" r="38" /><rect x="8" y="62" width="30" height="30" rx="4" />',
    '<circle cx="30" cy="70" r="26" /><circle cx="72" cy="34" r="16" />',
  ],
  // Hojas.
  naturaleza: [
    '<path d="M78 12C40 16 14 44 16 84c40 2 68-24 62-72z" /><path d="M18 84C34 66 52 44 74 20" fill="none" stroke="currentColor" stroke-width="3" />',
    '<path d="M22 92C58 88 86 58 82 16 44 20 16 50 22 92z" />',
  ],
  // Astros y órbitas: día, noche y el paso del tiempo.
  universo: [
    '<circle cx="62" cy="38" r="30" /><circle cx="20" cy="76" r="8" /><circle cx="86" cy="82" r="5" />',
    '<circle cx="40" cy="52" r="34" fill="none" stroke="currentColor" stroke-width="4" /><circle cx="40" cy="52" r="12" />',
  ],
  // Ondas de lectura, líneas de texto.
  palabras: [
    '<path d="M4 30h84M4 52h60M4 74h72" stroke="currentColor" stroke-width="9" stroke-linecap="round" fill="none" />',
    '<path d="M8 76c18-40 44-52 84-46" fill="none" stroke="currentColor" stroke-width="10" stroke-linecap="round" />',
  ],
  // Techos: casa, barrio, comunidad.
  comunidad: [
    '<path d="M50 10 92 46H8z" /><rect x="24" y="46" width="52" height="42" rx="3" />',
    '<path d="M28 34 52 54H4z" /><path d="M72 22 96 44H48z" />',
  ],
  // Formas orgánicas: cuerpo, emociones.
  cuerpo: [
    '<path d="M50 88C22 66 8 48 16 30 24 12 44 14 50 30 56 14 76 12 84 30c8 18-6 36-34 58z" />',
    '<circle cx="50" cy="50" r="34" fill="none" stroke="currentColor" stroke-width="12" />',
  ],
  // Ondas de agua y gotas.
  agua: [
    '<path d="M0 40c16-14 32-14 48 0s32 14 48 0v20c-16 14-32 14-48 0s-32-14-48 0z" />',
    '<path d="M50 12c18 24 28 38 28 50a28 28 0 1 1-56 0c0-12 10-26 28-50z" />',
  ],
  // Manchas de color.
  arte: [
    '<circle cx="36" cy="38" r="28" /><circle cx="68" cy="66" r="22" />',
    '<path d="M20 24c30-14 60 4 58 34-2 28-40 40-58 22S-4 38 20 24z" />',
  ],
};

/* `dangerouslySetInnerHTML` con contenido constante de este archivo: no viene
 * de la IA ni del usuario. El contrato prohíbe explícitamente que el modelo
 * genere SVG o marcado (ver `LessonSpec`); acá solo elige el NOMBRE del mundo. */
export default function SceneBackdrop({ theme }: { theme: VisualTheme }) {
  const [a, b] = FORMAS[theme] ?? FORMAS.numeros;
  return (
    <div className="lp-deco" aria-hidden="true">
      <svg className="lp-deco-a" viewBox="0 0 100 100" fill="currentColor" dangerouslySetInnerHTML={{ __html: a }} />
      <svg className="lp-deco-b" viewBox="0 0 100 100" fill="currentColor" dangerouslySetInnerHTML={{ __html: b }} />
    </div>
  );
}
