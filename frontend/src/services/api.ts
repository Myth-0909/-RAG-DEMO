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

export const getVisibleMenuTree = () => api.get('/roles/permissions/menus');

export const createPermission = (data: any) => api.post('/roles/permissions', data);

export const updatePermission = (id: number, data: any) => api.put(`/roles/permissions/${id}`, data);

export const deletePermission = (id: number) => api.delete(`/roles/permissions/${id}`);

export const reorderPermissions = (data: Array<{ id: number; parent_id?: number | null; sort_order: number }>) =>
  api.put('/roles/permissions/reorder', data);

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

export const getConvertedText = (kbId: number, docId: number) =>
  api.get(`/knowledge/${kbId}/documents/${docId}/converted`);

// Chat
export const chatQuery = (data: any) => api.post('/chat/query', data, { timeout: 120000 });

export const chatStream = (data: any) =>
  api.post('/chat/stream', data, { responseType: 'stream' });

// Conversations
export const getConversations = () => api.get('/conversations/');

export const createConversation = (data: { title: string; knowledge_base_ids: number[]; domain_id?: number }) =>
  api.post('/conversations/', data);

export const getConversation = (id: number) => api.get(`/conversations/${id}`);

export const getConversationMessages = (id: number) => api.get(`/conversations/${id}/messages`);

export const deleteConversation = (id: number) => api.delete(`/conversations/${id}`);

// Domains
// Document processing SSE stream
export const connectProcessStream = (
  kbId: number,
  docId: number,
  onEvent: (event: { step: string; status: string; data: any }) => void,
  onError?: (error: any) => void,
  onDone?: () => void,
): (() => void) => {
  const token = localStorage.getItem('token');
  const url = `/api/v1/knowledge/${kbId}/documents/${docId}/process-stream`;

  // Use fetch + ReadableStream for SSE with auth header
  const controller = new AbortController();

  fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream',
    },
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        onError?.(response);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError?.(new Error('No response body'));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            const dataStr = line.slice(5).trim();
            if (dataStr) {
              try {
                const data = JSON.parse(dataStr);
                onEvent(data);
              } catch {
                // skip malformed data
              }
            }
          }
        }
      }

      onDone?.();
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError?.(err);
      }
    });

  // Return cancel function
  return () => controller.abort();
};

export const getDomains = () => api.get('/domains/');

export const createDomain = (data: any) => api.post('/domains/', data);

export const updateDomain = (id: number, data: any) => api.put(`/domains/${id}`, data);

export const deleteDomain = (id: number) => api.delete(`/domains/${id}`);

// Model Configs
export const getModelConfigs = () => api.get('/model-configs/');

export const createModelConfig = (data: any) => api.post('/model-configs/', data);

export const updateModelConfig = (id: number, data: any) => api.put(`/model-configs/${id}`, data);

export const deleteModelConfig = (id: number) => api.delete(`/model-configs/${id}`);

export const getModelConfigHistory = (configId: number) =>
  api.get(`/model-configs/${configId}/history`);

export const getAllModelConfigHistory = (limit = 50) =>
  api.get('/model-configs/history/all', { params: { limit } });

export const restoreModelConfig = (historyId: number) =>
  api.post(`/model-configs/restore/${historyId}`);

export const setModelConfigAsCurrent = (configId: number) =>
  api.post(`/model-configs/${configId}/set-current`);

// Processing Tasks
export const getProcessingTasks = (params?: { status?: string; skip?: number; limit?: number }) =>
  api.get('/processing-tasks/', { params });

export const getProcessingTask = (taskId: number) =>
  api.get(`/processing-tasks/${taskId}`);

export const retryProcessingTask = (taskId: number) =>
  api.post(`/processing-tasks/${taskId}/retry`);
