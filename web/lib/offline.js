const DB_NAME = 'nahaos-offline';
const STORE = 'outbox';
const VERSION = 1;

async function fingerprintToken(token) {
  if (!token || !globalThis.crypto?.subtle) return '';
  const bytes = new TextEncoder().encode(token);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, {keyPath: 'id'});
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function queueOfflineRequest({url, method = 'POST', body, headers = {}, idempotencyKey, sessionToken}) {
  const sessionFingerprint = await fingerprintToken(sessionToken);
  const db = await openDb();
  const safeHeaders = {...headers};
  delete safeHeaders.Authorization;
  delete safeHeaders.authorization;
  const item = {
    id: crypto.randomUUID(),
    url,
    method,
    body,
    headers: safeHeaders,
    idempotencyKey: idempotencyKey || crypto.randomUUID(),
    sessionFingerprint,
    queuedAt: new Date().toISOString(),
  };
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(item);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  return item;
}

export async function flushOfflineQueue() {
  if (!navigator.onLine) return {sent: 0, remaining: await countQueued()};
  const db = await openDb();
  const items = await allQueued(db);
  const currentToken = typeof window !== 'undefined' ? window.localStorage.getItem('thuso_session') : null;
  const currentFingerprint = await fingerprintToken(currentToken);
  let sent = 0;

  for (const item of items) {
    if (item.sessionFingerprint && item.sessionFingerprint !== currentFingerprint) continue;
    try {
      const currentToken = typeof window !== 'undefined' ? window.localStorage.getItem('thuso_session') : null;
      const headers = {
        'Content-Type': 'application/json',
        ...item.headers,
        'Idempotency-Key': item.idempotencyKey,
        ...(currentToken ? {Authorization: 'Bearer ' + currentToken} : {}),
      };
      const response = await fetch(item.url, {
        method: item.method,
        headers,
        body: item.method === 'GET' ? undefined : JSON.stringify(item.body),
        credentials: 'include',
      });
      if (!response.ok && response.status >= 400 && response.status < 500 && response.status !== 408 && response.status !== 429) {
        await deleteQueued(db, item.id);
        continue;
      }
      if (!response.ok) break;
      await deleteQueued(db, item.id);
      sent += 1;
    } catch (_) {
      break;
    }
  }

  return {sent, remaining: await countQueued()};
}

export async function countQueued() {
  const db = await openDb();
  return allQueued(db).then(items => items.length);
}

function allQueued(db) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const request = tx.objectStore(STORE).getAll();
    request.onsuccess = () => resolve(request.result || []);
    request.onerror = () => reject(request.error);
  });
}

function deleteQueued(db, id) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}
