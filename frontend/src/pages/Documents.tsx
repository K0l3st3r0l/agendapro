import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { constructorAPI } from '../services/api';
import { DOC_TYPE_CONFIG } from '../types';
import type { DocType, Document } from '../types';
import toast from 'react-hot-toast';
import { TrashIcon, EyeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import PageHeader from '../components/ui/PageHeader';
import AppDialog from '../components/ui/AppDialog';
import { Button, IconButton } from '../components/ui/Button';
import { EmptyPanel, ErrorPanel } from '../components/ui/StatePanel';
import DocumentPreview from '../components/DocumentPreview';

interface DocSummary {
  id: number;
  title: string;
  doc_type: DocType;
  subject?: string;
  grade_level?: string;
  created_at: string;
}

function DocumentCardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="w-8 h-8 bg-gray-200 dark:bg-gray-700 rounded" />
        <div className="w-16 h-6 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2" />
      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-1" />
      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
    </div>
  );
}

export default function Documents() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'error' | 'ready'>('loading');
  const [filter, setFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Document | null>(null);

  useEffect(() => {
    fetchDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const fetchDocs = async () => {
    setLoadState('loading');
    try {
      const res = await constructorAPI.getDocuments(filter || undefined);
      setDocs(res.data);
      setLoadState('ready');
    } catch {
      setLoadState('error');
    }
  };

  const handleView = async (id: number) => {
    try {
      const res = await constructorAPI.getDocument(id);
      setSelected(res.data);
    } catch {
      toast.error('Error al cargar documento');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar este documento?')) return;
    try {
      await constructorAPI.deleteDocument(id);
      toast.success('Documento eliminado');
      setDocs(d => d.filter(doc => doc.id !== id));
    } catch {
      toast.error('Error al eliminar');
    }
  };

  const filtered = docs.filter(d =>
    d.title.toLowerCase().includes(search.toLowerCase()) ||
    d.subject?.toLowerCase().includes(search.toLowerCase()) ||
    d.grade_level?.toLowerCase().includes(search.toLowerCase())
  );

  const hasActiveFilters = !!filter || !!search;

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      <PageHeader title="Mis Documentos" description="Documentos generados y guardados" />

      {/* Filters */}
      <div className="px-4 sm:px-6 py-3 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative w-full sm:w-56">
          <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <label htmlFor="doc-search" className="sr-only">Buscar documentos</label>
          <input
            id="doc-search"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar documentos..."
            className="pl-9 pr-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none w-full bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500"
          />
        </div>

        {/* Mobile: select */}
        <div className="sm:hidden">
          <label htmlFor="doc-type-filter" className="sr-only">Filtrar por tipo</label>
          <select
            id="doc-type-filter"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Todos los tipos</option>
            {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(type => (
              <option key={type} value={type}>{DOC_TYPE_CONFIG[type].icon} {DOC_TYPE_CONFIG[type].label}</option>
            ))}
          </select>
        </div>

        {/* Desktop: chips */}
        <div className="hidden sm:flex gap-2 flex-wrap">
          <button
            onClick={() => setFilter('')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${!filter ? 'bg-primary-100 text-primary-700' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
          >
            Todos
          </button>
          {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(type => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 min-h-[36px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${filter === type ? 'bg-primary-100 text-primary-700' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
            >
              {DOC_TYPE_CONFIG[type].icon} {DOC_TYPE_CONFIG[type].label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-auto p-4 sm:p-6 bg-gray-50 dark:bg-gray-900">
        {loadState === 'loading' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <DocumentCardSkeleton key={i} />)}
          </div>
        ) : loadState === 'error' ? (
          <ErrorPanel message="No se pudieron cargar los documentos." onRetry={fetchDocs} />
        ) : filtered.length === 0 ? (
          hasActiveFilters ? (
            <EmptyPanel
              icon="🔍"
              title="Sin resultados para tu búsqueda"
              description="Prueba con otro término o quita los filtros aplicados"
              action={<Button variant="secondary" onClick={() => { setSearch(''); setFilter(''); }}>Limpiar filtros</Button>}
            />
          ) : (
            <EmptyPanel
              icon="📄"
              title="No hay documentos guardados"
              description="Ve al Constructor IA para crear y guardar documentos"
              action={<Button onClick={() => navigate('/constructor')}>Crear documento</Button>}
            />
          )
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(doc => (
              <article key={doc.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-2xl" aria-hidden="true">{DOC_TYPE_CONFIG[doc.doc_type]?.icon}</span>
                  <div className="flex gap-1">
                    <IconButton label={`Ver ${doc.title}`} onClick={() => handleView(doc.id)} className="text-gray-400 hover:text-primary-600">
                      <EyeIcon className="w-4 h-4" />
                    </IconButton>
                    <IconButton label={`Eliminar ${doc.title}`} onClick={() => handleDelete(doc.id)} className="text-gray-400 hover:text-red-500">
                      <TrashIcon className="w-4 h-4" />
                    </IconButton>
                  </div>
                </div>
                <h4 className="font-medium text-gray-900 dark:text-white text-sm line-clamp-2 mb-2 break-words">{doc.title}</h4>
                <div className="space-y-1">
                  {doc.subject && <p className="text-xs text-gray-500 dark:text-gray-400">📚 {doc.subject}</p>}
                  {doc.grade_level && <p className="text-xs text-gray-500 dark:text-gray-400">🎓 {doc.grade_level}</p>}
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {format(new Date(doc.created_at), "d MMM yyyy", { locale: es })}
                  </p>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      {/* Document Modal */}
      <AppDialog
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.title || 'Documento'}
        maxWidth="3xl"
        footer={
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <Button variant="secondary" onClick={() => setSelected(null)}>Cerrar</Button>
            <Button variant="secondary" className="bg-gray-700 text-white hover:bg-gray-800 border-gray-700" onClick={() => window.print()}>
              Imprimir
            </Button>
          </div>
        }
      >
        {selected?.content && (
          <DocumentPreview
            content={selected.content}
            imageUrl={selected.images?.[0]}
            showStudentRow
            bare
          />
        )}
      </AppDialog>
    </div>
  );
}
