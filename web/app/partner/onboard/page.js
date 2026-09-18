'use client';

import {useEffect, useState} from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';

async function call(path, token, options = {}) {
  const response = await fetch(API_BASE + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-NahaOS-Onboarding-Token': token,
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || ('Request failed (' + response.status + ')'));
  return data;
}

const empty = {
  provider_key: '', base_url: '', api_spec_url: '', health_endpoint_path: '/health',
  auth_scheme: 'bearer', auth_header_name: 'Authorization', timeout_seconds: 30,
  api_key: '', api_secret: '', extra_headers: '{}', allow_private_network: false,
  request_defaults: '{}', operation_configs: '{}', response_mappings: '{}',
};

export default function PartnerOnboardPage() {
  const [token, setToken] = useState('');
  const [invite, setInvite] = useState(null);
  const [form, setForm] = useState(empty);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [testOperation, setTestOperation] = useState('');

  useEffect(() => {
    const fragment = window.location.hash.replace(/^#/, '');
    const params = new URLSearchParams(fragment);
    const stored = window.sessionStorage.getItem('nahaos_partner_token');
    const value = params.get('token') || stored || '';
    if (value) {
      setToken(value);
      window.sessionStorage.setItem('nahaos_partner_token', value);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const data = await call('/partner/status', token, {method: 'POST', body: '{}'});
        setInvite(data.invite);
        if (data.integration?.configured) {
          setForm(f => ({
            ...f,
            ...data.integration,
            api_key: '',
            api_secret: '',
            extra_headers: '{}',
            operation_configs: JSON.stringify(data.integration.operation_configs || {}, null, 2),
            request_defaults: JSON.stringify(data.integration.request_defaults || {}, null, 2),
            response_mappings: JSON.stringify(data.integration.response_mappings || {}, null, 2),
          }));
          const ops = Object.keys(data.integration.operation_configs || {});
          setTestOperation(ops[0] || '');
        }
      } catch (e) { setError(e.message); }
    })();
  }, [token]);

  function update(key, value) { setForm(f => ({...f, [key]: value})); }

  async function save() {
    setBusy(true); setError(''); setMessage('');
    try {
      const body = {
        ...form,
        timeout_seconds: Number(form.timeout_seconds),
        extra_headers: JSON.parse(form.extra_headers || '{}'),
        request_defaults: JSON.parse(form.request_defaults || '{}'),
        operation_configs: JSON.parse(form.operation_configs || '{}'),
        response_mappings: JSON.parse(form.response_mappings || '{}'),
      };
      const data = await call('/partner/integration', token, {method:'PUT', body: JSON.stringify(body)});
      setMessage('Saved. Next: test the connection.');
      setForm(f => ({...f, ...data, api_key: '', api_secret: ''}));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function discover() {
    setBusy(true); setError('');
    try {
      const data = await call('/partner/discover', token, {method:'POST', body: JSON.stringify({openapi_url: form.api_spec_url})});
      update('operation_configs', JSON.stringify(data.operations || {}, null, 2));
      const ops = Object.keys(data.operations || {});
      setTestOperation(ops[0] || '');
      setMessage(ops.length + ' API operations discovered.');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function test() {
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await call('/partner/integration/test', token, {method:'POST', body:'{}'});
      setMessage('Connection test passed (' + data.kind + ').');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function activate() {
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await call('/partner/integration/activate', token, {method:'POST', body:'{}'});
      setMessage('Production connected: ' + data.active_provider + '.');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  if (!token) return <main className="adminShell"><section className="adminCard adminAuth"><h1>NahaOS Partner Onboarding</h1><p>Open the secure onboarding link supplied by the NahaOS platform administrator.</p></section></main>;

  return <main className="adminShell">
    <header className="adminTopbar"><div><div className="adminBrand">NahaOS</div><div className="adminSub">Partner Integration Hub</div></div></header>
    <section className="adminHero">
      <div className="adminPill">SELF-ONBOARDING</div>
      <h1>{invite?.stakeholder_name || 'Connect your organisation'}</h1>
      <p>Connect your existing API once. NahaOS validates it, maps the contract, tests it, and activates it without requiring a NahaLabs code change or rebuild.</p>
    </section>

    {message && <div className="adminNotice">{message}</div>}
    {error && <div className="adminError">{error}</div>}

    <section className="adminCard" style={{marginTop:16}}>
      <div className="cardHead"><div><h2>1. API connection</h2><p>{invite?.service_domain || 'Service domain'} · {invite?.stakeholder_type || 'stakeholder'}</p></div></div>
      <div className="formGrid">
        <label>Provider key<input value={form.provider_key} onChange={e=>update('provider_key',e.target.value)} placeholder="e.g. ministry-health-v1" /></label>
        <label>Base URL<input value={form.base_url} onChange={e=>update('base_url',e.target.value)} placeholder="https://api.example.org" /></label>
        <label>OpenAPI URL (optional)<input value={form.api_spec_url || ''} onChange={e=>update('api_spec_url',e.target.value)} placeholder="https://api.example.org/openapi.json" /></label>
        <label>Health endpoint<input value={form.health_endpoint_path || ''} onChange={e=>update('health_endpoint_path',e.target.value)} placeholder="/health" /></label>
        <label>Authentication<select value={form.auth_scheme} onChange={e=>update('auth_scheme',e.target.value)}><option value="bearer">Bearer token</option><option value="api-key">API key</option><option value="basic">Basic</option><option value="custom">Custom headers</option><option value="none">None</option></select></label>
        <label>API header<input value={form.auth_header_name} onChange={e=>update('auth_header_name',e.target.value)} /></label>
        <label>API key / username<input type="password" value={form.api_key} onChange={e=>update('api_key',e.target.value)} placeholder="Stored encrypted" /></label>
        {form.auth_scheme === 'basic' && <label>Password / secret<input type="password" value={form.api_secret} onChange={e=>update('api_secret',e.target.value)} /></label>}
        {form.auth_scheme === 'custom' && <label className="wide">Secret headers JSON<textarea rows="3" value={form.extra_headers} onChange={e=>update('extra_headers',e.target.value)} /></label>}
        <label>Timeout (seconds)<input type="number" min="5" max="180" value={form.timeout_seconds} onChange={e=>update('timeout_seconds',e.target.value)} /></label>
      </div>
    </section>

    <section className="adminCard" style={{marginTop:16}}>
      <div className="cardHead"><div><h2>2. API contract</h2><p>Import your OpenAPI file, or paste the operation contract supplied by your team.</p></div><button className="secondaryBtn" disabled={!form.api_spec_url || busy} onClick={discover}>Discover API operations</button></div>
      <label>Operation configuration<textarea rows="12" spellCheck="false" value={form.operation_configs} onChange={e=>update('operation_configs',e.target.value)} /></label>
      <label>Production test operation<select value={testOperation} onChange={e=>setTestOperation(e.target.value)}>
        <option value="">Health check only (cannot activate production)</option>
        {(() => { try { return Object.keys(JSON.parse(form.operation_configs || '{}')).map(name => <option key={name} value={name}>{name}</option>); } catch (_) { return null; } })()}
      </select></label>
      <label>Request defaults<textarea rows="5" spellCheck="false" value={form.request_defaults} onChange={e=>update('request_defaults',e.target.value)} /></label>
      <label>Response mappings<textarea rows="6" spellCheck="false" value={form.response_mappings} onChange={e=>update('response_mappings',e.target.value)} /></label>
    </section>

    <section className="adminCard actionCard" style={{marginTop:16}}>
      <div><h2>3. Save → Test → Activate</h2><p>NahaOS disables changed integrations until a fresh test passes.</p></div>
      <div className="actionRow"><button className="secondaryBtn" onClick={save} disabled={busy}>Save</button><button className="secondaryBtn" onClick={test} disabled={busy}>Test</button><button className="primaryBtn" onClick={activate} disabled={busy}>Activate production</button></div>
    </section>
  </main>;
}
