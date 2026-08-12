import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import type { RefObject } from 'react';
import type { MotionPreset, SceneType } from '../../types/lesson';

gsap.registerPlugin(useGSAP);

/** Qué anima cada preset, expresado como selectores dentro de la escena.
 *
 * El movimiento explica una progresión o revela información; nunca compensa una
 * jerarquía débil. Si al desactivarlo la escena pierde algo, la escena está mal
 * diseñada (ver DESIGN.md §5.5).
 */
const COREOGRAFIA: Record<MotionPreset, string[]> = {
  'gentle-reveal': ['.lp-titulo', '.lp-cuerpo', '.lp-figura', '.lp-example-item', '.lp-clave'],
  'step-by-step': ['.lp-titulo', '.lp-cuerpo'],
  'answer-reveal': ['.lp-titulo', '.lp-alternativa'],
  none: [],
  static: [],
};

/**
 * Entrada de la escena actual.
 *
 * Deliberadamente pobre: una sola entrada escalonada por escena. La progresión
 * de un `process` y la revelación del `quiz` ya las maneja React con el estado
 * de la escena —GSAP no debe ser una segunda fuente de verdad sobre qué se ve.
 *
 * `useGSAP` con `scope` acota los selectores a la escena y revierte todo al
 * desmontar o al cambiar de escena: sin eso, cambiar rápido de lámina dejaría
 * tweens vivos peleando por los mismos nodos.
 */
export function useSceneMotion(
  scope: RefObject<HTMLElement>,
  sceneId: string,
  tipo: SceneType,
  preset: MotionPreset,
  duracionMs: number,
  staggerMs: number,
) {
  useGSAP(
    () => {
      // El propio GSAP respeta la preferencia del sistema: con movimiento
      // reducido se salta al estado final en vez de animar. No hay rama
      // aparte que mantener ni estado final distinto que se pueda desincronizar.
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

      const objetivos = COREOGRAFIA[preset] ?? [];
      if (objetivos.length === 0) return;

      const existentes = objetivos.filter((sel) => scope.current?.querySelector(sel));
      if (existentes.length === 0) return;

      gsap.from(existentes.join(', '), {
        y: 24,
        autoAlpha: 0,
        duration: Math.max(duracionMs, 200) / 1000,
        stagger: Math.max(staggerMs, 60) / 1000,
        ease: 'power2.out',
        // Si algo interrumpe la animación, el estado final es el correcto:
        // nunca una escena a medio aparecer frente al curso.
        clearProps: 'transform,opacity,visibility',
      });
    },
    // La escena es la unidad: al cambiar de lámina se revierte y se rearma.
    { scope, dependencies: [sceneId, tipo, preset], revertOnUpdate: true },
  );
}
