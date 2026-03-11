import { useState, useEffect, useRef } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import esLocale from '@fullcalendar/core/locales/es';
import { eventsAPI } from '../services/api';
import type { CalendarEvent, EventCategory, EventFormData } from '../types';
import { CATEGORY_CONFIG } from '../types';
import toast from 'react-hot-toast';
import { PlusIcon, XMarkIcon, TrashIcon } from '@heroicons/react/24/outline';
import { format } from 'date-fns';

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

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<EventFormData>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const calendarRef = useRef<FullCalendar>(null);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    try {
      const res = await eventsAPI.getAll();
      setEvents(res.data);
    } catch {
      toast.error('Error al cargar eventos');
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

  const handleSave = async () => {
    if (!form.title.trim()) { toast.error('El título es requerido'); return; }
    setLoading(true);
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
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!editingId) return;
    if (!confirm('¿Eliminar este evento?')) return;
    try {
      await eventsAPI.delete(editingId);
      toast.success('Evento eliminado');
      await fetchEvents();
      setShowModal(false);
    } catch {
      toast.error('Error al eliminar');
    }
  };

  const set = (field: keyof EventFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const value = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
    setForm(f => ({ ...f, [field]: value }));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Calendario</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Gestiona tus eventos y actividades pedagógicas</p>
        </div>
        <button
          onClick={() => { setForm(emptyForm); setEditingId(null); setShowModal(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          Nuevo Evento
        </button>
      </div>

      {/* Category Legend */}
      <div className="px-6 py-2 bg-white dark:bg-gray-800 border-b border-gray-100 dark:border-gray-700 flex flex-wrap gap-3">
        {Object.entries(CATEGORY_CONFIG).map(([key, { label, color }]) => (
          <div key={key} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Calendar */}
      <div className="flex-1 p-4 overflow-auto">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 h-full p-4">
          <FullCalendar
            ref={calendarRef}
            plugins={[dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin]}
            initialView="dayGridMonth"
            locale={esLocale}
            headerToolbar={{
              left: 'prev,next today',
              center: 'title',
              right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
            }}
            buttonText={{ today: 'Hoy', month: 'Mes', week: 'Semana', day: 'Día', list: 'Lista' }}
            events={events.map(toFCEvent)}
            selectable={true}
            selectMirror={true}
            dayMaxEvents={3}
            weekends={true}
            select={handleDateSelect}
            eventClick={handleEventClick}
            height="100%"
            eventDisplay="block"
          />
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {editingId ? 'Editar Evento' : 'Nuevo Evento'}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              {/* Title */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Título *</label>
                <input
                  value={form.title}
                  onChange={set('title')}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder="Reunión de apoderados, Evaluación, etc."
                />
              </div>

              {/* Category */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Categoría</label>
                <select value={form.category} onChange={set('category')}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                  {Object.entries(CATEGORY_CONFIG).map(([k, { label }]) => (
                    <option key={k} value={k}>{label}</option>
                  ))}
                </select>
              </div>

              {/* All day */}
              <div className="flex items-center gap-2">
                <input type="checkbox" id="allday" checked={form.all_day} onChange={set('all_day')} className="rounded" />
                <label htmlFor="allday" className="text-sm text-gray-700 dark:text-gray-300">Todo el día</label>
              </div>

              {/* Dates */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Inicio *</label>
                  <input
                    type={form.all_day ? 'date' : 'datetime-local'}
                    value={form.start_datetime}
                    onChange={set('start_datetime')}
                    className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Fin</label>
                  <input
                    type={form.all_day ? 'date' : 'datetime-local'}
                    value={form.end_datetime}
                    onChange={set('end_datetime')}
                    className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Descripción</label>
                <textarea
                  value={form.description}
                  onChange={set('description')}
                  rows={3}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none resize-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder="Detalles del evento..."
                />
              </div>

              {/* Location */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Lugar</label>
                <input
                  value={form.location}
                  onChange={set('location')}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder="Sala 3B, Biblioteca, Zoom..."
                />
              </div>

              {/* Alert */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Alerta (minutos antes)</label>
                <select value={form.alert_minutes || ''} onChange={set('alert_minutes')}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                  <option value="">Sin alerta</option>
                  <option value={5}>5 minutos</option>
                  <option value={15}>15 minutos</option>
                  <option value={30}>30 minutos</option>
                  <option value={60}>1 hora</option>
                  <option value={1440}>1 día antes</option>
                </select>
              </div>
            </div>

            {/* Actions */}
            <div className="px-6 py-4 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
              <div>
                {editingId && (
                  <button onClick={handleDelete} className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700">
                    <TrashIcon className="w-4 h-4" /> Eliminar
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <button onClick={() => setShowModal(false)} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-transparent">
                  Cancelar
                </button>
                <button onClick={handleSave} disabled={loading}
                  className="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-60 font-medium">
                  {loading ? 'Guardando...' : editingId ? 'Actualizar' : 'Crear Evento'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
