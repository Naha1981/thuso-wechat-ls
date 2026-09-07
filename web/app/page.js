'use client';

import {useEffect, useMemo, useState} from 'react';
import {api} from '../lib/api';

const money = value => `${Number(value || 0).toFixed(2)} LSL`;

export default function Home() {
  const [feed, setFeed] = useState([]);
  const [location, setLocation] = useState(null);
  const [selected, setSelected] = useState(null);
  const [menu, setMenu] = useState([]);
  const [cart, setCart] = useState(null);
  const [orders, setOrders] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    setBusy(true); setMessage('');
    try {
      const [food, loc] = await Promise.all([api('/food/feed'), api('/food/location')]);
      setFeed(food.merchants || []); setLocation(loc.location || null);
    } catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  }

  useEffect(() => { load(); }, []);

  async function openMerchant(merchant) {
    setSelected(merchant); setMessage('');
    try { const data = await api(`/food/merchants/${merchant.id}/menu`); setMenu(data.items || []); }
    catch (e) { setMessage(e.message); }
  }

  async function add(item) {
    setBusy(true); setMessage('');
    try {
      const data = await api('/commerce/cart/items', {method:'POST', body: JSON.stringify({merchant_id:selected.id, product_id:item.id, quantity:1})});
      setCart(data); setMessage(`${item.name} added to your cart.`);
    } catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  }

  async function checkout() {
    if (!cart) return;
    if (!location) { setMessage('Share or save a delivery location before checkout.'); return; }
    setBusy(true); setMessage('Creating your order…');
    try {
      const data = await api('/food/checkout', {method:'POST', body: JSON.stringify({cart_id:cart.cart.id})});
      setMessage(`Order ${data.order.id} created. Continue to payment.`);
      setCart(null); await loadOrders();
    } catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  }

  async function loadOrders() {
    try { const data = await api('/food/orders'); setOrders(data.orders || []); } catch (_) {}
  }

  const activeOrders = useMemo(() => orders.filter(o => !['completed','cancelled'].includes(o.status)), [orders]);

  return <main className="shell">
    <header className="topbar">
      <div><div className="brand">THUSO</div><div className="tagline">Ask THUSO. Get it done.</div></div>
      <button className="ghost" onClick={load} disabled={busy}>Refresh</button>
    </header>

    <section className="hero">
      <div><p className="eyebrow">FOOD + DELIVERY</p><h1>Good food, without the complicated app.</h1><p>Built for everyday Lesotho connectivity: fast pages, LSL pricing, WhatsApp-first ordering and a simple delivery flow.</p></div>
      <div className="locationCard"><span>Delivery location</span><strong>{location?.label || 'Not set'}</strong><small>{location ? `${Number(location.latitude).toFixed(4)}, ${Number(location.longitude).toFixed(4)}` : 'Share your location in WhatsApp or save it in your account.'}</small></div>
    </section>

    {message && <div className="notice" role="status">{message}</div>}

    <section className="section"><div className="sectionHead"><h2>Food near you</h2><span>{feed.length} merchants</span></div>
      {busy && !feed.length ? <div className="empty">Loading food…</div> : <div className="merchantGrid">{feed.map(m => <button className="merchant" key={m.id} onClick={() => openMerchant(m)}><div className="merchantMark">{(m.business_name || 'F').slice(0,1).toUpperCase()}</div><div className="merchantBody"><strong>{m.business_name}</strong><span>{m.category}</span>{m.distance_m != null && <small>{Math.round(m.distance_m)} m away</small>}<p>{(m.menu_preview || []).slice(0,3).map(x => x.name).join(' · ') || 'View menu'}</p></div></button>)}</div>}
    </section>

    {selected && <section className="section menuPanel"><div className="sectionHead"><div><button className="back" onClick={() => setSelected(null)}>← Food</button><h2>{selected.business_name}</h2></div><span>Available now</span></div><div className="menuList">{menu.map(item => <div className="menuItem" key={item.id}><div><strong>{item.name}</strong><small>{item.stock_quantity} available</small></div><div className="priceAction"><b>{money(item.price)}</b><button onClick={() => add(item)} disabled={busy}>Add</button></div></div>)}</div></section>}

    {cart && <section className="cartBar"><div><strong>Your cart</strong><span>{cart.items?.length || 0} item types · {money(cart.subtotal)}</span></div><button onClick={checkout} disabled={busy || !location}>Checkout</button></section>}

    <section className="section orders"><div className="sectionHead"><h2>Your orders</h2><button className="ghost" onClick={loadOrders}>Load orders</button></div>{activeOrders.length ? activeOrders.map(o => <div className="order" key={o.id}><div><strong>{o.merchant_name}</strong><span>{o.status.replaceAll('_',' ')}</span></div><b>{money(o.total)}</b></div>) : <div className="empty">Your active orders will appear here.</div>}</section>

    <footer><strong>THUSO</strong><span>WhatsApp-first services for everyday life.</span></footer>
  </main>;
}
