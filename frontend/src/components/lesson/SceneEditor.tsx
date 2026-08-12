import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { IconButton } from '../ui/Button';
import type { Question, Scene } from '../../types/lesson';

const ETIQUETA: Record<string, string> = {
  concept: 'Idea central',
  example: 'Ejemplo cotidiano',
  process: 'Paso a paso',
  quiz: 'Pregunta',
  recap: 'Cierre',
};

/** Cuenta caracteres y avisa antes de que el servidor rechace.
 *
 * El límite no es un capricho: es lo que cabe legible proyectado. Ver DESIGN.md.
 */
function Contador({ valor, max }: { valor: string; max: number }) {
  const excedido = valor.length > max;
  return (
    <span className={`text-xs tabular-nums ${excedido ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-400'}`}>
      {valor.length}/{max}
      {excedido && ' — no cabe proyectado'}
    </span>
  );
}

const campo =
  'w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 ' +
  'px-3 py-2 text-sm text-gray-900 dark:text-gray-100 ' +
  'focus:outline-none focus:ring-2 focus:ring-primary-500';

interface Props {
  scene: Scene;
  indice: number;
  total: number;
  question?: Question;
  limites: { title: number; body: number };
  onChange: (parcial: Partial<Scene>) => void;
  onMover: (direccion: -1 | 1) => void;
  onCambiarRespuesta: (optionId: string) => void;
}

export default function SceneEditor({
  scene, indice, total, question, limites, onChange, onMover, onCambiarRespuesta,
}: Props) {
  return (
    <section className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
      <header className="flex items-center justify-between gap-3 mb-4">
        <h3 className="font-semibold text-gray-900 dark:text-white">
          <span className="text-gray-400 tabular-nums mr-2">{indice + 1}.</span>
          {ETIQUETA[scene.type] ?? scene.type}
        </h3>
        <div className="flex gap-1">
          <IconButton label="Subir escena" onClick={() => onMover(-1)} disabled={indice === 0}>
            <ChevronUpIcon className="w-5 h-5" />
          </IconButton>
          <IconButton label="Bajar escena" onClick={() => onMover(1)} disabled={indice === total - 1}>
            <ChevronDownIcon className="w-5 h-5" />
          </IconButton>
        </div>
      </header>

      <div className="space-y-4">
        <label className="block">
          <span className="flex items-center justify-between text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Título <Contador valor={scene.title} max={limites.title} />
          </span>
          <input className={campo} value={scene.title} onChange={(e) => onChange({ title: e.target.value })} />
        </label>

        <label className="block">
          <span className="flex items-center justify-between text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Lo que se proyecta <Contador valor={scene.body} max={limites.body} />
          </span>
          <textarea className={campo} rows={2} value={scene.body} onChange={(e) => onChange({ body: e.target.value })} />
        </label>

        <label className="block">
          <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Lo que dices en voz alta
            <span className="ml-2 font-normal text-gray-500">no se proyecta</span>
          </span>
          <textarea className={campo} rows={4} value={scene.narration} onChange={(e) => onChange({ narration: e.target.value })} />
        </label>

        <label className="block">
          <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Nota para ti
            <span className="ml-2 font-normal text-gray-500">material, cuándo esperar respuestas</span>
          </span>
          <textarea className={campo} rows={2} value={scene.teacher_note} onChange={(e) => onChange({ teacher_note: e.target.value })} />
        </label>

        {/* La respuesta correcta se corrige acá: es lo que más importa revisar
            antes de proyectar, porque un error se muestra al curso entero. */}
        {scene.type === 'quiz' && question && (
          <fieldset className="rounded-lg bg-gray-50 dark:bg-gray-900/50 p-4">
            <legend className="text-sm font-medium text-gray-700 dark:text-gray-300 px-1">
              {question.prompt}
            </legend>
            <div className="space-y-2 mt-2">
              {question.options.map((op) => (
                <label key={op.id} className="flex items-center gap-3 text-sm text-gray-800 dark:text-gray-200 cursor-pointer">
                  <input
                    type="radio"
                    name={`correcta-${question.id}`}
                    className="w-5 h-5 text-primary-600 focus:ring-primary-500"
                    checked={question.correct_option_ids.includes(op.id)}
                    onChange={() => onCambiarRespuesta(op.id)}
                  />
                  <span>{op.label}</span>
                  {!op.asset_id && (
                    <span className="text-xs text-amber-700 dark:text-amber-400">sin imagen</span>
                  )}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {scene.type === 'recap' && scene.data.key_points.length > 0 && (
          <div>
            <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ideas de cierre</span>
            <ul className="space-y-2">
              {scene.data.key_points.map((punto, i) => (
                <li key={i}>
                  <input
                    className={campo}
                    value={punto}
                    onChange={(e) => {
                      const puntos = [...scene.data.key_points];
                      puntos[i] = e.target.value;
                      onChange({ data: { ...scene.data, key_points: puntos } });
                    }}
                  />
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
