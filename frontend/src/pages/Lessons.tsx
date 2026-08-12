import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { PresentationChartLineIcon, PlusIcon } from '@heroicons/react/24/outline';
import { lessonsAPI } from '../services/api';
import PageHeader from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import AppDialog from '../components/ui/AppDialog';
import { LoadingPanel, ErrorPanel, EmptyPanel } from '../components/ui/StatePanel';
import type { LessonSummary } from '../types/lesson';

export default function Lessons() {
  const navigate = useNavigate();
  const [clases, setClases] = useState<LessonSummary[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [porBorrar, setPorBorrar] = useState<LessonSummary | null>(null);

  const cargar = () => {
    setCargando(true);
    setError('');
    lessonsAPI
      .list()
      .then((r) => setClases(r.data.lessons))
      .catch(() => setError('No se pudieron cargar tus clases.'))
      .finally(() => setCargando(false));
  };

  useEffect(cargar, []);

  const borrar = async () => {
    if (!porBorrar) return;
    try {
      await lessonsAPI.remove(porBorrar.id);
      setClases((c) => c.filter((x) => x.id !== porBorrar.id));
      toast.success('Clase eliminada');
    } catch {
      toast.error('No se pudo eliminar la clase');
    } finally {
      setPorBorrar(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Clases visuales"
        description="Presentaciones para proyectar en la sala, alineadas al currículum."
        actions={
          <Button onClick={() => navigate('/clases/nueva')}>
            <PlusIcon className="w-5 h-5" />
            Nueva clase
          </Button>
        }
      />

      {cargando && <LoadingPanel label="Cargando tus clases..." />}
      {!cargando && error && <ErrorPanel message={error} onRetry={cargar} />}

      {!cargando && !error && clases.length === 0 && (
        <EmptyPanel
          icon={<PresentationChartLineIcon className="w-8 h-8" />}
          title="Todavía no tienes clases"
          description="Elige un objetivo de aprendizaje y la IA propone la clase; tú la revisas antes de proyectarla."
          action={<Button onClick={() => navigate('/clases/nueva')}>Crear mi primera clase</Button>}
        />
      )}

      {!cargando && !error && clases.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clases.map((c) => (
            <li
              key={c.id}
              className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 flex flex-col gap-3"
            >
              <div>
                <h2 className="font-semibold text-gray-900 dark:text-white leading-snug">{c.title}</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {c.grade_level} · {c.subject}
                </p>
              </div>

              <p className="text-sm text-gray-600 dark:text-gray-400">
                {c.scenes} escenas
                {c.status === 'draft' && (
                  <span className="ml-2 rounded px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                    borrador
                  </span>
                )}
              </p>

              <div className="flex flex-wrap gap-2 mt-auto pt-2">
                <Link to={`/clases/${c.id}/presentar`} className="flex-1">
                  <Button className="w-full">Presentar</Button>
                </Link>
                <Link to={`/clases/${c.id}/editar`}>
                  <Button variant="secondary">Editar</Button>
                </Link>
                <Button variant="ghost" onClick={() => setPorBorrar(c)} aria-label={`Eliminar ${c.title}`}>
                  Eliminar
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <AppDialog
        open={porBorrar !== null}
        onClose={() => setPorBorrar(null)}
        title="Eliminar clase"
        description={`"${porBorrar?.title}" se elimina definitivamente. Esta acción no se puede deshacer.`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPorBorrar(null)}>Cancelar</Button>
            <Button variant="danger" onClick={borrar}>Eliminar</Button>
          </>
        }
      >
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Si solo quieres dejar de usarla por ahora, puedes conservarla: no molesta en el listado.
        </p>
      </AppDialog>
    </div>
  );
}
