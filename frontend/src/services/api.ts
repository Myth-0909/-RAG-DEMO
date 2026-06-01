import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;

// Auth
export const login = (data: { username: string; password: string }) =>
  api.post('/auth/login', data);

export const getMe = () => api.get('/auth/me');

// Users
export const getUsers = (params?: { skip?: number; limit?: number }) =>
  api.get('/auth/users', { params });

export const createUser = (data: any) => api.post('/auth/users', data);

export const updateUser = (id: number, data: any) => api.put(`/auth/users/${id}`, data);

export const deleteUser = (id: number) => api.delete(`/auth/users/${id}`);

// Roles
export const getRoles = () => api.get('/roles/');

export const createRole = (data: any) => api.post('/roles/', data);

export const updateRole = (id: number, data: any) => api.put(`/roles/${id}`, data);

export const deleteRole = (id: number) => api.delete(`/roles/${id}`);

// Permissions
export const getPermissionTree = () => api.get('/roles/permissions/tree');

export const createPermission = (data: any) => api.post('/roles/permissions', data);

export const updatePermission = (id: number, data: any) => api.put(`/roles/permissions/${id}`, data);

export const deletePermission = (id: number) => api.delete(`/roles/permissions/${id}`);

// Knowledge Bases
export const getKnowledgeBases = () => api.get('/knowledge/');

export const createKnowledgeBase = (data: any) => api.post('/knowledge/', data);

export const updateKnowledgeBase = (id: number, data: any) => api.put(`/knowledge/${id}`, data);

export const deleteKnowledgeBase = (id: number) => api.delete(`/knowledge/${id}`);

export const getDocuments = (kbId: number) => api.get(`/knowledge/${kbId}/documents`);

export const uploadDocument = (kbId: number, formData: FormData) =>
  api.post(`/knowledge/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const deleteDocument = (kbId: number, docId: number) =>
  api.delete(`/knowledge/${kbId}/documents/${docId}`);

export const getChunks = (kbId: number, docId: number) =>
  api.get(`/knowledge/${kbId}/documents/${docId}/chunks`);

// Chat
export const chatQuery = (data: any) => api.post('/chat/query', data);

export const chatStream = (data: any) =>
  api.post('/chat/stream', data, { responseType: 'stream' });

// Domains
export const getDomains = () => api.get('/domains/');

export const createDomain = (data: any) => api.post('/domains/', data);

export const updateDomain = (id: number, data: any) => api.put(`/domains/${id}`, data);

export const deleteDomain = (id: number) => api.delete(`/domains/${id}`);
