'use client';

import {useEffect, useState} from 'react';
import {countQueued, flushOfflineQueue} from '../lib/offline';

export default function OfflineStatus() {
  const [online, setOnline] = useState(true);
  const [queued, setQueued] = useState(0);

  async function refresh() {
    setOnline(navigator.onLine);
    try { setQueued(await countQueued()); } catch (_) {}
  }

  useEffect(() => {
    refresh();
    const onOnline = async () => { await flushOfflineQueue(); refresh(); };
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', refresh);
    const timer = setInterval(refresh, 15000);
    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', refresh);
      clearInterval(timer);
    };
  }, []);

  return <div className="offlineStatus" role="status">
    <span className={online ? 'onlineDot' : 'offlineDot'}></span>
    <span>{online ? 'Online' : 'Offline — saved actions will sync when connected'}</span>
    {queued > 0 && <strong>{queued} queued</strong>}
  </div>;
}
