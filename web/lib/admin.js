import {API_BASE} from './api';

function csrfToken() {
  if (typeof document === 'undefined') return '';
  const match = document.cookie.match(/(?:^|; )nahaos_admin_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
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
