import { useState, useEffect } from 'react';
import { constructorAPI } from '../services/api';
import { DOC_TYPE_CONFIG } from '../types';
import type { DocType } from '../types';
import toast from 'react-hot-toast';
import { TrashIcon, EyeIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';

interface DocSummary {
  id: number;
  title: string;
  doc_type: DocType;
  subject?: string;
  grade_level?: string;
  created_at: string;
}

export default function Documents() {
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<any | null>(null);

  useEffect(() => {
    fetchDocs();
  }, [filter]);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await constructorAPI.getDocuments(filter || undefined);
      setDocs(res.data);
    } catch {
      toast.error('Error al cargar documentos');
    } finally {
      setLoading(false);
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

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      <div className="px-6 py-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Mis Documentos</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">Documentos generados y guardados</p>
      </div>

      {/* Filters */}
      <div className="px-6 py-3 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 flex items-center gap-3 flex-wrap">
        <div className="relative">
          <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar documentos..."
            className="pl-9 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none w-56 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium ${!filter ? 'bg-primary-100 text-primary-700' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
          >
            Todos
          </button>
          {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(type => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 ${filter === type ? 'bg-primary-100 text-primary-700' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
            >
              {DOC_TYPE_CONFIG[type].icon} {DOC_TYPE_CONFIG[type].label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-auto p-6 bg-gray-50 dark:bg-gray-900">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400 dark:text-gray-500">
            <p className="text-4xl mb-3">📄</p>
            <p className="font-medium text-gray-500 dark:text-gray-400">No hay documentos guardados</p>
            <p className="text-sm mt-1">Ve al Constructor IA para crear y guardar documentos</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(doc => (
              <div key={doc.id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-2xl">{DOC_TYPE_CONFIG[doc.doc_type]?.icon}</span>
                  <div className="flex gap-1">
                    <button onClick={() => handleView(doc.id)} className="p-1.5 text-gray-400 hover:text-primary-600 rounded">
                      <EyeIcon className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDelete(doc.id)} className="p-1.5 text-gray-400 hover:text-red-500 rounded">
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <h4 className="font-medium text-gray-900 dark:text-white text-sm line-clamp-2 mb-2">{doc.title}</h4>
                <div className="space-y-1">
                  {doc.subject && <p className="text-xs text-gray-500 dark:text-gray-400">📚 {doc.subject}</p>}
                  {doc.grade_level && <p className="text-xs text-gray-500 dark:text-gray-400">🎓 {doc.grade_level}</p>}
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {format(new Date(doc.created_at), "d MMM yyyy", { locale: es })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Document Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700 sticky top-0 bg-white dark:bg-gray-800">
              <h3 className="font-semibold text-gray-900 dark:text-white">{selected.title}</h3>
              <div className="flex gap-2">
                <button onClick={() => window.print()} className="text-sm px-3 py-1.5 bg-gray-700 text-white rounded-lg">
                  Imprimir
                </button>
                <button onClick={() => setSelected(null)} className="text-gray-400 dark:text-gray-300 hover:text-gray-600 dark:hover:text-white text-sm px-3 py-1.5 border border-gray-200 dark:border-gray-600 rounded-lg">
                  Cerrar
                </button>
              </div>
            </div>
            <div className="p-6">
              {selected.content?.sections?.map((section: any, idx: number) => (
                <div key={idx} className="mb-4">
                  {section.title && <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{section.title}</h4>}
                  {typeof section.content === 'string' && (
                    <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">{section.content}</p>
                  )}
                  {Array.isArray(section.content) && section.content.map((item: any, i: number) => (
                    <div key={i} className="mb-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded text-sm dark:text-gray-300">
                      {typeof item === 'string' ? `${i + 1}. ${item}` : (
                        <div>
                          <p>{item.number || i + 1}. {item.text}</p>
                          {item.options && <ul className="ml-4 mt-1">{item.options.map((o: string, j: number) => <li key={j}>{String.fromCharCode(65+j)}) {o}</li>)}</ul>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
