import {API_BASE} from './api';

function csrfToken() {
  if (typeof window === 'undefined') return '';
  return window.sessionStorage.getItem('nahaos_admin_csrf') || '';
}

export function storeAdminCsrf(token) {
  if (typeof window !== 'undefined' && token) window.sessionStorage.setItem('nahaos_admin_csrf', token);
}

export function clearAdminCsrf() {
  if (typeof window !== 'undefined') window.sessionStorage.removeItem('nahaos_admin_csrf');
}

export async function adminApi(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  if (!['GET','HEAD','OPTIONS'].includes(method)) {
    const token = csrfToken();
    if (token) headers['X-CSRF-Token'] = token;
  }

  const response = await fetch(`${API_BASE}/admin${path}`, {
    ...options,
    method,
    headers,
    credentials: 'include',
    cache: 'no-store',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || data.message || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}
