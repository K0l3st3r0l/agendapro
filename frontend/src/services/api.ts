import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('agendapro_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('agendapro_token');
      localStorage.removeItem('agendapro_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// Auth
export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  register: (name: string, email: string, password: string) =>
    api.post('/auth/register', { name, email, password }),
  me: () => api.get('/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    api.put('/auth/change-password', { current_password, new_password }),
};

// Events
export const eventsAPI = {
  getAll: (start?: string, end?: string, category?: string) =>
    api.get('/events/', { params: { start, end, category } }),
  create: (data: object) => api.post('/events/', data),
  update: (id: number, data: object) => api.put(`/events/${id}`, data),
  delete: (id: number) => api.delete(`/events/${id}`),
  getUpcoming: (days?: number) => api.get('/events/upcoming', { params: { days } }),
};

// AI Constructor
export const constructorAPI = {
  // nginx corta a 300 s; sin timeout propio, axios esperaba indefinidamente
  // y el spinner quedaba girando para siempre si algo se colgaba.
  generate: (data: object) => api.post('/constructor/generate', data, { timeout: 180000 }),
  optimizeInstructions: (data: object) => api.post('/constructor/optimize-instructions', data, { timeout: 60000 }),
  save: (data: object) => api.post('/constructor/save', data),
  saveToCalendar: (data: object) => api.post('/constructor/save-to-calendar', data),
  generateImage: (data: object) => api.post('/constructor/generate-image', data, { timeout: 120000 }),
  searchImages: (data: object) => api.post('/constructor/search-images', data, { timeout: 180000 }),
  exportPdf: (data: object) => api.post('/constructor/export-pdf', data, { responseType: 'blob' }),
  exportDocx: (data: object) => api.post('/constructor/export-docx', data, { responseType: 'blob' }),
  getDocuments: (doc_type?: string) => api.get('/constructor/documents', { params: { doc_type } }),
  getDocument: (id: number) => api.get(`/constructor/documents/${id}`),
  deleteDocument: (id: number) => api.delete(`/constructor/documents/${id}`),
};

// Clases visuales
export const lessonsAPI = {
  // La generación tarda entre 15 y 40 s según el proveedor; el techo de nginx
  // son 300 s y no conviene cortar antes de tiempo un storyboard que va a llegar.
  storyboard: (data: object) => api.post('/lessons/storyboard', data, { timeout: 180000 }),
  create: (data: object) => api.post('/lessons', data),
  list: () => api.get('/lessons'),
  get: (id: number) => api.get(`/lessons/${id}`),
  present: (id: number) => api.get(`/lessons/${id}/present`),
  update: (id: number, data: object) => api.put(`/lessons/${id}`, data),
  remove: (id: number) => api.delete(`/lessons/${id}`),
  // Resolver imágenes va aparte de guardar: la mayoría se dibuja o sale de
  // ARASAAC en menos de un segundo, pero una que caiga a la IA puede tardar.
  // Genera de nuevo con los mismos parámetros curriculares; `instructions`
  // permite dirigir el segundo intento en vez de repetir el dado.
  regenerate: (id: number, instructions = '') =>
    api.post(`/lessons/${id}/regenerate`, { instructions }, { timeout: 300000 }),
  resolveAssets: (id: number) => api.post(`/lessons/${id}/assets`, {}, { timeout: 180000 }),
};

// Currículum MINEDUC
export const curriculumAPI = {
  getLevels: () => api.get('/curriculum/levels'),
  getOA: (grade_level: string, subject: string) =>
    api.get('/curriculum/oa', { params: { grade_level, subject } }),
};

// Settings
export const settingsAPI = {
  get: () => api.get('/settings/'),
  update: (data: object) => api.put('/settings/', data),
  health: () => api.get('/settings/health', { timeout: 30000 }),
  deleteKey: (provider: 'openrouter' | 'openai' | 'google' | 'xai' | 'all') =>
    api.delete(`/settings/keys?provider=${provider}`),
};

export default api;
