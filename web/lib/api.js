import {queueOfflineRequest} from './offline';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';

function cacheKey(path) { return 'nahaos_cache:' + path; }

function saveCache(path, data) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(cacheKey(path), JSON.stringify({data, cachedAt: new Date().toISOString()}));
  } catch (_) {}
}

function loadCache(path) {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(cacheKey(path));
    return raw ? JSON.parse(raw).data : null;
  } catch (_) { return null; }
}

export async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  const token = typeof window !== 'undefined' ? window.localStorage.getItem('thuso_session') : null;
  if (token) headers.Authorization = 'Bearer ' + token;

  if (typeof window !== 'undefined' && !navigator.onLine) {
    if (method === 'GET') {
      const cached = loadCache(path);
      if (cached !== null) return {...cached, _offline: true};
    }
    if (options.queueWhenOffline && method !== 'GET') {
      await queueOfflineRequest({
        url: API_BASE + path,
        method,
        body: options.body ? JSON.parse(options.body) : undefined,
        headers,
        idempotencyKey: options.idempotencyKey,
      });
      return {_queued: true, _offline: true};
    }
    throw new Error('You are offline. This action will be available when connectivity returns.');
  }

  try {
    const response = await fetch(API_BASE + path, {
      ...options,
      method,
      headers,
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || 'Request failed (' + response.status + ')');
    if (method === 'GET') saveCache(path, data);
    return data;
  } catch (error) {
    if (method === 'GET') {
      const cached = loadCache(path);
      if (cached !== null) return {...cached, _offline: true};
    }
    if (options.queueWhenOffline && method !== 'GET' && typeof window !== 'undefined') {
      await queueOfflineRequest({
        url: API_BASE + path,
        method,
        body: options.body ? JSON.parse(options.body) : undefined,
        headers,
        idempotencyKey: options.idempotencyKey,
      });
      return {_queued: true, _offline: true};
    }
    throw error;
  }
}

export { API_BASE };
