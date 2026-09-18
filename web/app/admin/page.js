'use client';

import {useEffect, useMemo, useState} from 'react';
import {adminApi, clearAdminCsrf, storeAdminCsrf} from '../../lib/admin';

const DEFAULT_REQUEST = {
  model: '{{model}}',
  messages: '{{messages}}',
  metadata: '{{metadata}}',
};

const DEFAULT_RESPONSE = {
  content_path: 'choices.0.message.content',
  model_path: 'model',
  input_units_path: 'usage.prompt_tokens',
  output_units_path: 'usage.completion_tokens',
};

const emptyForm = {
  base_url: '',
  chat_endpoint_path: '/chat/completions',
  health_endpoint_path: '/health',
  auth_scheme: 'bearer',
  auth_header_name: 'Authorization',
  model: 'default',
  timeout_seconds: 60,
  api_key: '',
  api_secret: '',
  extra_headers: '{}',
  allow_private_network: false,
  request_template: JSON.stringify(DEFAULT_REQUEST, null, 2),
  response_mapping: JSON.stringify(DEFAULT_RESPONSE, null, 2),
};

export default function AdminPage() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [checking, setChecking] = useState(true);
  const [authMode, setAuthMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [bootstrapToken, setBootstrapToken] = useState('');
  const [form, setForm] = useState(emptyForm);
  const [meta, setMeta] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    setChecking(true);
    try {
      await adminApi('/auth/me');
      if (!window.sessionStorage.getItem('nahaos_admin_csrf')) { setLoggedIn(false); return; }
      setLoggedIn(true);
      await loadConfig();
    } catch (_) {
      setLoggedIn(false);
    } finally {
      setChecking(false);
    }
  }

  async function loadConfig() {
    const data = await adminApi('/integrations/econet');
    setMeta(data);
    if (data.configured) {
      setForm(current => ({
        ...current,
        base_url: data.base_url || '',
        chat_endpoint_path: data.chat_endpoint_path || '/chat/completions',
        health_endpoint_path: data.health_endpoint_path || '',
        auth_scheme: data.auth_scheme || 'bearer',
        auth_header_name: data.auth_header_name || 'Authorization',
        model: data.model || 'default',
        timeout_seconds: data.timeout_seconds || 60,
        allow_private_network: !!data.allow_private_network,
        request_template: JSON.stringify(data.request_template || DEFAULT_REQUEST, null, 2),
        response_mapping: JSON.stringify(data.response_mapping || DEFAULT_RESPONSE, null, 2),
      }));
    }
  }

  useEffect(() => { refresh(); }, []);

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      const path = authMode === 'login' ? '/auth/login' : '/auth/bootstrap';
      const body = authMode === 'login'
        ? {email, password}
        : {bootstrap_token: bootstrapToken, email, password};
      const authResult = await adminApi(path, {method:'POST', body:JSON.stringify(body)});
      storeAdminCsrf(authResult.csrf_token);
      setLoggedIn(true);
      setMessage(authMode === 'login' ? 'Signed in.' : 'Administrator account created.');
      await loadConfig();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function update(key, value) {
    setForm(current => ({...current, [key]: value}));
  }

  function parsedJson(text, label) {
    try { return JSON.parse(text); }
    catch (_) { throw new Error(`${label} contains invalid JSON.`); }
  }

  async function save() {
    setBusy(true); setError(''); setMessage('');
    try {
      const payload = {
        base_url: form.base_url,
        chat_endpoint_path: form.chat_endpoint_path,
        health_endpoint_path: form.health_endpoint_path || null,
        auth_scheme: form.auth_scheme,
        auth_header_name: form.auth_header_name || 'Authorization',
        model: form.model || 'default',
        timeout_seconds: Number(form.timeout_seconds),
        api_key: form.api_key || null,
        api_secret: form.api_secret || null,
        extra_headers: form.auth_scheme === 'custom' ? parsedJson(form.extra_headers, 'Custom headers') : null,
        allow_private_network: !!form.allow_private_network,
        request_template: parsedJson(form.request_template, 'Request template'),
        response_mapping: parsedJson(form.response_mapping, 'Response mapping'),
      };
      await adminApi('/integrations/econet', {method:'PUT', body:JSON.stringify(payload)});
      update('api_key',''); update('api_secret',''); update('extra_headers','{}');
      setMessage('Configuration saved. Run Test AI request and then activate production.');
      await loadConfig();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function test(smokeChat) {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await adminApi('/integrations/econet/test', {method:'POST', body:JSON.stringify({smoke_chat: smokeChat})});
      setMessage(`Connectivity test passed (${result.kind}).`);
      await loadConfig();
    } catch (e) {
      setError(e.message);
      await loadConfig().catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  async function activate() {
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await adminApi('/integrations/econet/activate', {method:'POST'});
      setMessage(`${result.active_provider} is now the live AI provider. No rebuild is required.`);
      await loadConfig();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivate() {
    setBusy(true); setError(''); setMessage('');
    try {
      await adminApi('/integrations/econet/deactivate', {method:'POST'});
      setMessage('Econet production integration is off. NahaOS is back on sandbox/runtime fallback.');
      await loadConfig();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    try { await adminApi('/auth/logout', {method:'POST'}); } catch (_) {}
    clearAdminCsrf();
    setLoggedIn(false);
  }

  const status = useMemo(() => {
    if (!meta?.configured) return {label:'Not configured', tone:'neutral'};
    if (meta.enabled) return {label:'LIVE — Econet AI', tone:'good'};
    if (meta.last_test_status === 'passed' && meta.last_test_kind === 'chat') return {label:'AI test passed — ready to activate', tone:'good'};
    if (meta.last_test_status === 'passed') return {label:'Health test passed — run AI test before activation', tone:'neutral'};
    if (meta.last_test_status === 'failed') return {label:'Test failed', tone:'bad'};
    return {label:'Saved — needs connectivity test', tone:'neutral'};
  }, [meta]);

  if (checking) return <main className="adminShell"><div className="adminCard"><p>Checking administrator session…</p></div></main>;

  if (!loggedIn) return <main className="adminShell">
    <section className="adminHero">
      <div className="adminBrand">NAHAOS</div>
      <div className="adminPill">Secure integration control plane</div>
      <h1>Econet AI production integration</h1>
      <p>Connect the approved Econet API without touching source code. Credentials are encrypted server-side and never returned to the browser.</p>
    </section>
    <form className="adminCard adminAuth" onSubmit={submitAuth}>
      <div className="authTabs">
        <button type="button" className={authMode === 'login' ? 'active' : ''} onClick={() => setAuthMode('login')}>Sign in</button>
        <button type="button" className={authMode === 'bootstrap' ? 'active' : ''} onClick={() => setAuthMode('bootstrap')}>First-time setup</button>
      </div>
      {authMode === 'bootstrap' && <label>Bootstrap token<input value={bootstrapToken} onChange={e => setBootstrapToken(e.target.value)} type="password" required /></label>}
      <label>Administrator email<input value={email} onChange={e => setEmail(e.target.value)} type="email" autoComplete="email" required /></label>
      <label>Password<input value={password} onChange={e => setPassword(e.target.value)} type="password" autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} minLength={12} required /></label>
      {error && <div className="adminError">{error}</div>}
      <button className="primaryBtn" disabled={busy}>{busy ? 'Working…' : authMode === 'login' ? 'Sign in' : 'Create administrator'}</button>
      {authMode === 'bootstrap' && <small>The deployment owner must provide the one-time bootstrap token. After the first administrator is created, bootstrap is permanently closed.</small>}
    </form>
  </main>;

  return <main className="adminShell">
    <header className="adminTopbar">
      <div><div className="adminBrand">NAHAOS</div><div className="adminSub">Production control plane</div></div>
      <button className="ghostBtn" onClick={logout}>Sign out</button>
    </header>

    <section className="adminHero compact">
      <div className="adminPill">ECONET AI</div>
      <h1>Production integration</h1>
      <p>Econet can complete the integration independently from this portal. Save, test, then activate. Activation changes runtime selection without rebuilding NahaOS.</p>
      <div className={`statusBadge ${status.tone}`}>{status.label}</div>
    </section>

    {message && <div className="adminNotice">{message}</div>}
    {error && <div className="adminError">{error}</div>}

    <section className="adminGrid">
      <div className="adminCard">
        <div className="cardHead"><div><h2>Connection</h2><p>Use the exact API contract issued by Econet.</p></div></div>
        <div className="formGrid">
          <label className="wide">Base URL<input value={form.base_url} onChange={e => update('base_url',e.target.value)} placeholder="https://..." /></label>
          <label>Chat endpoint<input value={form.chat_endpoint_path} onChange={e => update('chat_endpoint_path',e.target.value)} /></label>
          <label>Health endpoint<input value={form.health_endpoint_path} onChange={e => update('health_endpoint_path',e.target.value)} placeholder="/health (optional)" /></label>
          <label>Authentication<select value={form.auth_scheme} onChange={e => update('auth_scheme',e.target.value)}><option value="bearer">Bearer token</option><option value="api-key">API key header</option><option value="basic">Basic auth</option><option value="custom">Custom headers</option><option value="none">None</option></select></label>
          <label>API header name<input value={form.auth_header_name} onChange={e => update('auth_header_name',e.target.value)} disabled={!['api-key'].includes(form.auth_scheme)} /></label>
          <label>Model / service ID<input value={form.model} onChange={e => update('model',e.target.value)} /></label>
          <label>Timeout (seconds)<input value={form.timeout_seconds} onChange={e => update('timeout_seconds',e.target.value)} type="number" min="5" max="180" /></label>
          <label>API key / username<input value={form.api_key} onChange={e => update('api_key',e.target.value)} type="password" placeholder={meta?.secret_configured ? 'Stored — leave blank to keep' : 'Enter secret'} /></label>
          {form.auth_scheme === 'basic' && <label>Password / secret<input value={form.api_secret} onChange={e => update('api_secret',e.target.value)} type="password" /></label>}
          {form.auth_scheme === 'custom' && <label className="wide">Custom secret headers (JSON)<textarea value={form.extra_headers} onChange={e => update('extra_headers',e.target.value)} rows="4" /></label>}
          <label className="checkRow wide"><input type="checkbox" checked={form.allow_private_network} onChange={e => update('allow_private_network',e.target.checked)} /><span><strong>Allow private network endpoint</strong><small>Only enable this when Econet explicitly provides an internal/private endpoint.</small></span></label>
        </div>
      </div>

      <div className="adminCard">
        <div className="cardHead"><div><h2>Contract mapping</h2><p>Lets Econet adapt its exact JSON schema without changing NahaOS code.</p></div></div>
        <label>Request template<textarea value={form.request_template} onChange={e => update('request_template',e.target.value)} rows="10" spellCheck="false" /></label>
        <label>Response mapping<textarea value={form.response_mapping} onChange={e => update('response_mapping',e.target.value)} rows="8" spellCheck="false" /></label>
      </div>
    </section>

    <section className="adminCard actionCard">
      <div><h2>Deployment sequence</h2><p>1. Save → 2. Test → 3. Activate. Activation is reversible.</p></div>
      <div className="actionRow">
        <button className="secondaryBtn" onClick={save} disabled={busy}>Save configuration</button>
        <button className="secondaryBtn" onClick={() => test(false)} disabled={busy || !meta?.configured}>Test health</button>
        <button className="secondaryBtn" onClick={() => test(true)} disabled={busy || !meta?.configured}>Test AI request</button>
        {!meta?.enabled
          ? <button className="primaryBtn" onClick={activate} disabled={busy || meta?.last_test_status !== 'passed' || meta?.last_test_kind !== 'chat'}>Activate production</button>
          : <button className="dangerBtn" onClick={deactivate} disabled={busy}>Deactivate production</button>}
      </div>
    </section>

    <section className="adminGrid">
      <div className="adminCard sandboxCard">
        <div className="cardHead"><div><h2>NahaOS Sandbox</h2><p>Always available for demonstrations. It never uses Econet credentials and never becomes the production provider unless explicitly selected as fallback.</p></div><div className="statusBadge good">ISOLATED</div></div>
        <div className="sandboxFlow">Demo user → NahaOS → DemoAIProvider → simulated response</div>
      </div>
      <div className="adminCard">
        <div className="cardHead"><div><h2>Security</h2><p>Production integration secrets are encrypted with the deployment's <code>SECRETS_ENCRYPTION_KEY</code>. The browser only receives masked state.</p></div></div>
        <p className="muted">Every save, test, activation and deactivation is written to the administrator audit log.</p>
      </div>
    </section>
  </main>;
}
