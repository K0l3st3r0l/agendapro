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
  generate: (data: object) => api.post('/constructor/generate', data),
  save: (data: object) => api.post('/constructor/save', data),
  getDocuments: (doc_type?: string) => api.get('/constructor/documents', { params: { doc_type } }),
  getDocument: (id: number) => api.get(`/constructor/documents/${id}`),
  deleteDocument: (id: number) => api.delete(`/constructor/documents/${id}`),
  improve: (content: string, instruction: string) =>
    api.post('/constructor/improve', { content, instruction }),
};

export default api;
