import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { SparklesIcon } from '@heroicons/react/24/outline';
import { curriculumAPI, lessonsAPI } from '../services/api';
import PageHeader from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { ErrorPanel, LoadingPanel } from '../components/ui/StatePanel';
import SceneEditor from '../components/lesson/SceneEditor';
import { limitesDe, type LessonSpec, type Scene } from '../types/lesson';

interface OA {
  id: number;
  code: string;
  description: string;
  indicators: { id: number; text: string; ordinal: number }[];
}

const BORRADOR = 'agendapro_clase_borrador';

const campo =
  'w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 ' +
  'px-3 py-2 text-sm text-gray-900 dark:text-gray-100 ' +
  'focus:outline-none focus:ring-2 focus:ring-primary-500';

export default function LessonBuilder() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const editando = Boolean(id);

  const [niveles, setNiveles] = useState<{ grade_level: string; subjects: { subject: string }[] }[]>([]);
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [oaDisponibles, setOaDisponibles] = useState<OA[]>([]);
  const [oaElegidos, setOaElegidos] = useState<string[]>([]);
  const [topic, setTopic] = useState('');
  const [duracion, setDuracion] = useState(45);
  const [instrucciones, setInstrucciones] = useState('');

  const [spec, setSpec] = useState<LessonSpec | null>(null);
  const [generando, setGenerando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(editando);
  const [error, setError] = useState('');
  const [sucio, setSucio] = useState(false);
  const primeraCarga = useRef(true);

  // --- Carga inicial --------------------------------------------------------

  useEffect(() => {
    curriculumAPI.getLevels().then((r) => setNiveles(r.data.levels)).catch(() => {});
  }, []);

  useEffect(() => {
    if (editando) return;
    // Un storyboard cuesta ~17 s de espera y plata: si la profesora cierra la
    // pestaña sin querer, no debería tener que generarlo de nuevo.
    const guardado = localStorage.getItem(BORRADOR);
    if (guardado) {
      try {
        setSpec(JSON.parse(guardado));
        toast('Recuperamos el borrador que tenías sin guardar', { icon: '📝' });
      } catch {
        localStorage.removeItem(BORRADOR);
      }
    }
  }, [editando]);

  useEffect(() => {
    if (!editando) return;
    lessonsAPI
      .get(Number(id))
      .then((r) => setSpec(r.data.spec))
      .catch(() => setError('No se pudo cargar la clase.'))
      .finally(() => setCargando(false));
  }, [editando, id]);

  useEffect(() => {
    if (!grade || !subject) return;
    curriculumAPI
      .getOA(grade, subject)
      .then((r) => setOaDisponibles(r.data.oa))
      .catch(() => setOaDisponibles([]));
    setOaElegidos([]);
  }, [grade, subject]);

  // El borrador se guarda solo mientras la clase no exista en el servidor.
  useEffect(() => {
    if (primeraCarga.current) {
      primeraCarga.current = false;
      return;
    }
    if (spec && !editando) localStorage.setItem(BORRADOR, JSON.stringify(spec));
  }, [spec, editando]);

  // Avisa antes de perder cambios no guardados.
  useEffect(() => {
    if (!sucio) return;
    const aviso = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', aviso);
    return () => window.removeEventListener('beforeunload', aviso);
  }, [sucio]);

  // --- Acciones -------------------------------------------------------------

  const generar = async () => {
    setGenerando(true);
    setError('');
    try {
      const r = await lessonsAPI.storyboard({
        grade_level: grade,
        subject,
        topic,
        duration_minutes: duracion,
        lesson_kind: 'introduction',
        oa_refs: oaElegidos,
        indicator_refs: [],
        instructions: instrucciones,
      });
      setSpec(r.data.spec);
      setSucio(true);
      toast.success(`Clase propuesta en ${(r.data.elapsed_ms / 1000).toFixed(0)} s. Revísala antes de proyectar.`);
    } catch (e: unknown) {
      const detalle = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detalle || 'No se pudo generar la clase.');
    } finally {
      setGenerando(false);
    }
  };

  const guardar = async () => {
    if (!spec) return;
    setGuardando(true);
    try {
      if (editando) {
        await lessonsAPI.update(Number(id), { spec, status: 'ready' });
        toast.success('Cambios guardados');
        setSucio(false);
      } else {
        const r = await lessonsAPI.create({ spec, status: 'ready' });
        localStorage.removeItem(BORRADOR);
        setSucio(false);
        toast.success('Clase guardada');
        navigate(`/clases/${r.data.id}/editar`, { replace: true });
      }
    } catch (e: unknown) {
      const detalle = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof detalle === 'string' ? detalle : 'No se pudo guardar la clase');
    } finally {
      setGuardando(false);
    }
  };

  const cambiarEscena = useCallback((i: number, parcial: Partial<Scene>) => {
    setSpec((s) => {
      if (!s) return s;
      const scenes = [...s.scenes];
      scenes[i] = { ...scenes[i], ...parcial };
      return { ...s, scenes };
    });
    setSucio(true);
  }, []);

  const moverEscena = useCallback((i: number, direccion: -1 | 1) => {
    setSpec((s) => {
      if (!s) return s;
      const destino = i + direccion;
      if (destino < 0 || destino >= s.scenes.length) return s;
      const scenes = [...s.scenes];
      [scenes[i], scenes[destino]] = [scenes[destino], scenes[i]];
      return { ...s, scenes };
    });
    setSucio(true);
  }, []);

  const cambiarRespuesta = useCallback((questionId: string, optionId: string) => {
    setSpec((s) => {
      if (!s) return s;
      return {
        ...s,
        questions: s.questions.map((q) =>
          q.id === questionId ? { ...q, correct_option_ids: [optionId] } : q,
        ),
      };
    });
    setSucio(true);
  }, []);

  const limites = useMemo(
    () => limitesDe(spec?.curriculum.grade_level || grade),
    [spec, grade],
  );

  // --- Render ---------------------------------------------------------------

  if (cargando) return <LoadingPanel label="Cargando la clase..." />;

  const asignaturas = niveles.find((n) => n.grade_level === grade)?.subjects ?? [];
  const puedeGenerar = Boolean(grade && subject && topic.trim()) && !generando;

  return (
    <div>
      <PageHeader
        title={editando ? 'Editar clase' : 'Nueva clase visual'}
        description={
          editando
            ? 'Revisa el contenido antes de proyectarlo al curso.'
            : 'Elige el objetivo de aprendizaje y la IA propone la clase. Tú decides qué se proyecta.'
        }
        actions={
          spec && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={guardar} busy={guardando} disabled={guardando}>
                {sucio ? 'Guardar cambios' : 'Guardado'}
              </Button>
              {editando && (
                <Button onClick={() => navigate(`/clases/${id}/presentar`)} disabled={sucio}>
                  Presentar
                </Button>
              )}
            </div>
          )
        }
      />

      {error && <ErrorPanel message={error} />}

      {!spec && !editando && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 max-w-2xl space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nivel</span>
              <select className={campo} value={grade} onChange={(e) => { setGrade(e.target.value); setSubject(''); }}>
                <option value="">Elige un nivel</option>
                {niveles.map((n) => <option key={n.grade_level} value={n.grade_level}>{n.grade_level}</option>)}
              </select>
            </label>

            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Asignatura</span>
              <select className={campo} value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!grade}>
                <option value="">Elige una asignatura</option>
                {asignaturas.map((s) => <option key={s.subject} value={s.subject}>{s.subject}</option>)}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Tema de la clase</span>
            <input className={campo} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Patrones repetitivos con figuras" />
          </label>

          {oaDisponibles.length > 0 && (
            <fieldset>
              <legend className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Objetivos de aprendizaje
                <span className="ml-2 font-normal text-gray-500">opcional, pero ancla mejor la clase</span>
              </legend>
              <div className="max-h-56 overflow-y-auto space-y-1 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
                {oaDisponibles.map((oa) => (
                  <label key={oa.id} className="flex gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      className="mt-1 w-4 h-4 shrink-0 text-primary-600 focus:ring-primary-500"
                      checked={oaElegidos.includes(oa.code)}
                      onChange={(e) => setOaElegidos((prev) =>
                        e.target.checked ? [...prev, oa.code] : prev.filter((c) => c !== oa.code))}
                    />
                    <span><strong>{oa.code}</strong> — {oa.description}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Duración (minutos)</span>
              <input type="number" min={10} max={180} className={campo} value={duracion} onChange={(e) => setDuracion(Number(e.target.value))} />
            </label>
          </div>

          <label className="block">
            <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Indicaciones <span className="font-normal text-gray-500">opcional</span>
            </span>
            <textarea className={campo} rows={2} value={instrucciones} onChange={(e) => setInstrucciones(e.target.value)} placeholder="Usar ejemplos con frutas del kiosco." />
          </label>

          <Button onClick={generar} busy={generando} disabled={!puedeGenerar} className="w-full">
            <SparklesIcon className="w-5 h-5" />
            {generando ? 'Preparando la clase…' : 'Proponer clase'}
          </Button>
          {generando && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
              Suele tomar menos de medio minuto.
            </p>
          )}
        </div>
      )}

      {spec && (
        <div className="space-y-4 max-w-3xl">
          <div className="rounded-xl bg-primary-50 dark:bg-primary-900/20 p-4 text-sm text-primary-900 dark:text-primary-100">
            <strong>{spec.metadata.title}</strong> · {spec.curriculum.grade_level} · {spec.curriculum.subject}
            {spec.curriculum.resolved_oas.length > 0 && (
              <> · {spec.curriculum.resolved_oas.map((o) => o.code).join(', ')}</>
            )}
          </div>

          {spec.scenes.map((escena, i) => (
            <SceneEditor
              key={escena.id || i}
              scene={escena}
              indice={i}
              total={spec.scenes.length}
              question={spec.questions.find((q) => q.id === escena.data.question_ref)}
              limites={limites}
              onChange={(parcial) => cambiarEscena(i, parcial)}
              onMover={(d) => moverEscena(i, d)}
              onCambiarRespuesta={(optionId) => cambiarRespuesta(escena.data.question_ref, optionId)}
            />
          ))}

          <div className="flex justify-end gap-2 pb-8">
            <Button variant="secondary" onClick={guardar} busy={guardando} disabled={guardando}>
              Guardar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
