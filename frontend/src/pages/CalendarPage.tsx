import { useState, useEffect, useRef } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import esLocale from '@fullcalendar/core/locales/es';
import { eventsAPI } from '../services/api';
import type { CalendarEvent, EventFormData } from '../types';
import { CATEGORY_CONFIG } from '../types';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';
import PageHeader from '../components/ui/PageHeader';
import AppDialog from '../components/ui/AppDialog';
import { Button } from '../components/ui/Button';
import { ErrorPanel, LoadingPanel } from '../components/ui/StatePanel';
import { useMediaQuery } from '../hooks/useMediaQuery';

const emptyForm: EventFormData = {
  title: '',
  description: '',
  start_datetime: '',
  end_datetime: '',
  all_day: false,
  category: 'general',
  location: '',
  alert_minutes: undefined,
  recurrence: 'none',
};

const inputClass =
  'mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100';

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'error' | 'ready'>('loading');
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<EventFormData>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [mobileView, setMobileView] = useState<'listWeek' | 'dayGridMonth'>('listWeek');
  const calendarRef = useRef<FullCalendar>(null);
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const wasDesktop = useRef(isDesktop);

  useEffect(() => {
    fetchEvents();
  }, []);

  useEffect(() => {
    if (wasDesktop.current === isDesktop) return;
    wasDesktop.current = isDesktop;
    const api = calendarRef.current?.getApi();
    if (!api) return;
    api.changeView(isDesktop ? 'dayGridMonth' : mobileView);
  }, [isDesktop]);

  const fetchEvents = async () => {
    setLoadState('loading');
    try {
      const res = await eventsAPI.getAll();
      setEvents(res.data);
      setLoadState('ready');
    } catch {
      setLoadState('error');
    }
  };

  const toFCEvent = (ev: CalendarEvent) => ({
    id: String(ev.id),
    title: ev.title,
    start: ev.start_datetime,
    end: ev.end_datetime || undefined,
    allDay: ev.all_day,
    backgroundColor: ev.color,
    borderColor: ev.color,
    extendedProps: { ...ev },
  });

  const handleDateSelect = (selectInfo: any) => {
    const start = selectInfo.startStr;
    const end = selectInfo.endStr;
    setForm({
      ...emptyForm,
      start_datetime: start.length > 10 ? start.slice(0, 16) : `${start}T08:00`,
      end_datetime: end.length > 10 ? end.slice(0, 16) : `${start}T09:00`,
      all_day: selectInfo.allDay,
    });
    setEditingId(null);
    setShowModal(true);
  };

  const handleEventClick = (clickInfo: any) => {
    const ev: CalendarEvent = clickInfo.event.extendedProps;
    setForm({
      title: ev.title,
      description: ev.description || '',
      start_datetime: ev.start_datetime.slice(0, 16),
      end_datetime: ev.end_datetime?.slice(0, 16) || '',
      all_day: ev.all_day,
      color: ev.color,
      category: ev.category,
      location: ev.location || '',
      alert_minutes: ev.alert_minutes,
      recurrence: ev.recurrence || 'none',
    });
    setEditingId(ev.id);
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) { toast.error('El título es requerido'); return; }
    if (!form.start_datetime) { toast.error('La fecha de inicio es requerida'); return; }
    if (form.end_datetime && form.end_datetime < form.start_datetime) {
      toast.error('La fecha de fin debe ser posterior al inicio');
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await eventsAPI.update(editingId, form);
        toast.success('Evento actualizado');
      } else {
        await eventsAPI.create(form);
        toast.success('Evento creado');
      }
      await fetchEvents();
      setShowModal(false);
      setForm(emptyForm);
      setEditingId(null);
    } catch {
      toast.error('Error al guardar evento');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!editingId) return;
    if (!confirm('¿Eliminar este evento?')) return;
    setDeleting(true);
    try {
      await eventsAPI.delete(editingId);
      toast.success('Evento eliminado');
      await fetchEvents();
      setShowModal(false);
    } catch {
      toast.error('Error al eliminar');
    } finally {
      setDeleting(false);
    }
  };

  const set = (field: keyof EventFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const value = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
    setForm(f => ({ ...f, [field]: value }));
  };

  const openNewEventModal = () => { setForm(emptyForm); setEditingId(null); setShowModal(true); };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Calendario"
        description="Gestiona tus eventos y actividades pedagógicas"
        actions={
          <Button onClick={openNewEventModal}>
            <PlusIcon className="w-4 h-4" />
            Nuevo Evento
          </Button>
        }
      />

      {/* Category Legend */}
      <div className="px-4 sm:px-6 py-2 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 flex flex-nowrap sm:flex-wrap gap-3 overflow-x-auto">
        {Object.entries(CATEGORY_CONFIG).map(([key, { label, color }]) => (
          <div key={key} className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap flex-shrink-0">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Mobile view toggle */}
      <div className="lg:hidden px-4 sm:px-6 py-2 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 flex gap-2">
        {([
          { id: 'listWeek', label: 'Agenda' },
          { id: 'dayGridMonth', label: 'Mes' },
        ] as const).map(v => (
          <button
            key={v.id}
            onClick={() => { setMobileView(v.id); calendarRef.current?.getApi()?.changeView(v.id); }}
            className={`flex-1 min-h-[40px] px-3 py-1.5 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
              mobileView === v.id
                ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-400'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Calendar */}
      <div className="flex-1 p-2 sm:p-4 overflow-auto">
        {loadState === 'loading' ? (
          <LoadingPanel label="Cargando calendario..." />
        ) : loadState === 'error' ? (
          <ErrorPanel message="No se pudieron cargar los eventos." onRetry={fetchEvents} />
        ) : (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 h-full p-2 sm:p-4">
            <FullCalendar
              ref={calendarRef}
              plugins={[dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin]}
              initialView={isDesktop ? 'dayGridMonth' : mobileView}
              locale={esLocale}
              headerToolbar={isDesktop ? {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
              } : {
                left: 'prev,next',
                center: 'title',
                right: 'today',
              }}
              buttonText={{ today: 'Hoy', month: 'Mes', week: 'Semana', day: 'Día', list: 'Lista' }}
              events={events.map(toFCEvent)}
              selectable={true}
              selectMirror={true}
              dayMaxEvents={3}
              weekends={true}
              select={handleDateSelect}
              eventClick={handleEventClick}
              datesSet={(arg) => {
                if (arg.view.type === 'listWeek' || arg.view.type === 'dayGridMonth') {
                  setMobileView(arg.view.type as 'listWeek' | 'dayGridMonth');
                }
              }}
              height="100%"
              eventDisplay="block"
            />
          </div>
        )}
      </div>

      <AppDialog
        open={showModal}
        onClose={() => setShowModal(false)}
        title={editingId ? 'Editar Evento' : 'Nuevo Evento'}
        maxWidth="lg"
        footer={
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            {editingId && (
              <Button variant="danger" type="button" onClick={handleDelete} busy={deleting} className="w-full sm:w-auto">
                <TrashIcon className="w-4 h-4" /> {deleting ? 'Eliminando...' : 'Eliminar'}
              </Button>
            )}
            <div className="flex flex-col sm:flex-row gap-2 sm:ml-auto">
              <Button variant="secondary" type="button" onClick={() => setShowModal(false)} className="w-full sm:w-auto">
                Cancelar
              </Button>
              <Button type="submit" form="event-form" busy={saving} className="w-full sm:w-auto">
                {saving ? 'Guardando...' : editingId ? 'Actualizar' : 'Crear Evento'}
              </Button>
            </div>
          </div>
        }
      >
        <form id="event-form" onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="ev-title" className="text-sm font-medium text-gray-700 dark:text-gray-300">Título *</label>
            <input
              id="ev-title"
              value={form.title}
              onChange={set('title')}
              className={inputClass}
              placeholder="Reunión de apoderados, Evaluación, etc."
            />
          </div>

          <div>
            <label htmlFor="ev-category" className="text-sm font-medium text-gray-700 dark:text-gray-300">Categoría</label>
            <select id="ev-category" value={form.category} onChange={set('category')} className={inputClass}>
              {Object.entries(CATEGORY_CONFIG).map(([k, { label }]) => (
                <option key={k} value={k}>{label}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input type="checkbox" id="ev-allday" checked={form.all_day} onChange={set('all_day')} className="w-4 h-4 rounded" />
            <label htmlFor="ev-allday" className="text-sm text-gray-700 dark:text-gray-300">Todo el día</label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="ev-start" className="text-sm font-medium text-gray-700 dark:text-gray-300">Inicio *</label>
              <input
                id="ev-start"
                type={form.all_day ? 'date' : 'datetime-local'}
                value={form.start_datetime}
                onChange={set('start_datetime')}
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="ev-end" className="text-sm font-medium text-gray-700 dark:text-gray-300">Fin</label>
              <input
                id="ev-end"
                type={form.all_day ? 'date' : 'datetime-local'}
                value={form.end_datetime}
                onChange={set('end_datetime')}
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label htmlFor="ev-description" className="text-sm font-medium text-gray-700 dark:text-gray-300">Descripción</label>
            <textarea
              id="ev-description"
              value={form.description}
              onChange={set('description')}
              rows={3}
              className={`${inputClass} resize-none`}
              placeholder="Detalles del evento..."
            />
          </div>

          <div>
            <label htmlFor="ev-location" className="text-sm font-medium text-gray-700 dark:text-gray-300">Lugar</label>
            <input
              id="ev-location"
              value={form.location}
              onChange={set('location')}
              className={inputClass}
              placeholder="Sala 3B, Biblioteca, Zoom..."
            />
          </div>

          <div>
            <label htmlFor="ev-alert" className="text-sm font-medium text-gray-700 dark:text-gray-300">Alerta (minutos antes)</label>
            <select id="ev-alert" value={form.alert_minutes || ''} onChange={set('alert_minutes')} className={inputClass}>
              <option value="">Sin alerta</option>
              <option value={5}>5 minutos</option>
              <option value={15}>15 minutos</option>
              <option value={30}>30 minutos</option>
              <option value={60}>1 hora</option>
              <option value={1440}>1 día antes</option>
            </select>
          </div>
        </form>
      </AppDialog>
    </div>
  );
}
