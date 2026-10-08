document.addEventListener('DOMContentLoaded', () => {
    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const api = async (url, opts = {}) => {
        const res = await fetch(url, opts.body ? { method: 'POST', headers: {'Content-Type': 'application/json'}, ...opts, body: JSON.stringify(opts.body) } : opts);
        const ct = res.headers.get('content-type') || '';
        return ct.includes('json') ? res.json() : res;
    };

    const ESTADOS = {
        nuevo: ['Nuevo', 'gray'], en_cola: ['En cola', 'blue'], enviado: ['Enviado', 'green'],
        sin_whatsapp: ['Sin WhatsApp', 'gray'], error: ['Error', 'red'], respondio: ['Respondió', 'gold'],
        no_interesa: ['No le interesa', 'red'],
    };
    const badge = (estado) => { const [t, c] = ESTADOS[estado] || [estado, 'gray']; return `<span class="badge ${c}">${t}</span>`; };

    // ---------------- navegación ----------------
    const views = { 'view-listas': loadSearches, 'view-contactos': loadContacts, 'view-plantillas': loadTemplates, 'view-envios': loadEnvios };
    function showView(id) {
        document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.target === id));
        document.querySelectorAll('.view-section').forEach(v => v.style.display = v.id === id ? 'block' : 'none');
        if (views[id]) views[id]();
    }
    document.querySelectorAll('.nav-item').forEach(item => item.addEventListener('click', e => { e.preventDefault(); showView(item.dataset.target); }));

    // ---------------- resultados (tabla principal) ----------------
    let places = [];           // locales cargados en la tabla
    let currentTitle = 'Resultados';
    const selected = new Set();

    function visiblePlaces() {
        const f = {
            sinweb: $('f-sinweb').checked, sinfudo: $('f-sinfudo').checked, nocturno: $('f-nocturno').checked,
            tel: $('f-tel').checked, celular: $('f-celular').checked, nuevos: $('f-nuevos').checked,
            resenas: parseInt($('f-resenas').value) || 0, texto: $('f-texto').value.trim().toLowerCase(),
        };
        return places.filter(p => {
            if (f.sinweb && p.web_tipo === 'Web propia') return false;
            if (f.sinfudo && (p.web_tipo === 'FUDO' || p.web_tipo === 'Plataforma menú/pedidos')) return false;
            if (f.nocturno && !p.nocturno) return false;
            if (f.tel && !p.wa_phone) return false;
            if (f.celular && p.tel_tipo !== 'Celular') return false;
            if (f.nuevos && !['nuevo', 'error'].includes(p.estado)) return false;
            if ((p.reviews || 0) < f.resenas) return false;
            if (f.texto && !`${p.name} ${p.categoria}`.toLowerCase().includes(f.texto)) return false;
            return true;
        }).sort((a, b) => (b.reviews || 0) - (a.reviews || 0));
    }

    function webCell(p) {
        const cls = { 'Web propia': 'blue', 'FUDO': 'red', 'Plataforma menú/pedidos': 'red', 'Sin web': 'green' }[p.web_tipo] || 'gold';
        return `<span class="badge ${cls}">${esc(p.web_tipo || '-')}</span>`;
    }

    function linksCell(p) {
        const out = [];
        if (p.wa_link) out.push(`<a href="${esc(p.wa_link)}" target="_blank" class="lnk wa" title="Abrir chat de WhatsApp"><i class="fa-brands fa-whatsapp"></i></a>`);
        if (p.instagram) out.push(`<a href="${esc(p.instagram)}" target="_blank" class="lnk ig" title="Instagram"><i class="fa-brands fa-instagram"></i></a>`);
        if (p.web && p.web !== p.instagram) out.push(`<a href="${esc(p.web)}" target="_blank" class="lnk" title="${esc(p.web)}"><i class="fa-solid fa-globe"></i></a>`);
        if (p.maps_url) out.push(`<a href="${esc(p.maps_url)}" target="_blank" class="lnk" title="Google Maps"><i class="fa-solid fa-map-location-dot"></i></a>`);
        return out.join(' ');
    }

    function renderResults() {
        const tbody = document.querySelector('#tabla-resultados tbody');
        const list = visiblePlaces();
        $('results-title').innerHTML = `<i class="fa-solid fa-list-check"></i> ${esc(currentTitle)}`;
        $('results-count').textContent = places.length
            ? `Mostrando ${list.length} de ${places.length} locales · ${selected.size} seleccionados · ordenados por cantidad de reseñas`
            : '';
        $('btn-excel').disabled = list.length === 0;
        $('btn-preparar').disabled = selected.size === 0;
        if (!list.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="empty-state">${places.length ? 'Ningún local cumple los filtros.' : 'Hacé una búsqueda o abrí una búsqueda guardada.'}</td></tr>`;
            return;
        }
        tbody.innerHTML = list.map(p => `
            <tr>
                <td><input type="checkbox" class="row-check" data-id="${esc(p.id)}" ${selected.has(p.id) ? 'checked' : ''}></td>
                <td><strong>${esc(p.name)}</strong><br><small class="text-muted">${esc(p.categoria || p.rubro || '')}</small></td>
                <td>${p.reviews || 0}${p.rating ? `<br><small class="text-muted">★ ${p.rating}</small>` : ''}</td>
                <td>${esc(p.phone || '-')}<br><small class="text-muted">${esc(p.tel_tipo || '')}</small></td>
                <td>${webCell(p)}</td>
                <td>${p.nocturno ? '<i class="fa-solid fa-moon" style="color:#a78bfa" title="' + esc((p.horarios || []).join('\n')) + '"></i>' : ''}</td>
                <td>${badge(p.estado)}</td>
                <td class="links">${linksCell(p)}</td>
            </tr>`).join('');
        $('check-all').checked = list.every(p => selected.has(p.id));
    }

    document.querySelector('#tabla-resultados tbody').addEventListener('change', e => {
        if (!e.target.classList.contains('row-check')) return;
        e.target.checked ? selected.add(e.target.dataset.id) : selected.delete(e.target.dataset.id);
        renderResults();
    });
    $('check-all').addEventListener('change', e => {
        visiblePlaces().forEach(p => e.target.checked ? selected.add(p.id) : selected.delete(p.id));
        renderResults();
    });
    ['f-sinweb', 'f-sinfudo', 'f-nocturno', 'f-tel', 'f-celular', 'f-nuevos', 'f-resenas', 'f-texto']
        .forEach(id => $(id).addEventListener('input', renderResults));

    function loadPlaces(list, title) {
        places = list;
        currentTitle = title;
        selected.clear();
        renderResults();
    }

    // ---------------- búsqueda en Maps ----------------
    let eventSource = null;
    function endSearch(msg) {
        if (eventSource) eventSource.close();
        eventSource = null;
        $('btn-buscar').disabled = false;
        $('btn-buscar').innerHTML = '<i class="fa-solid fa-search"></i> Buscar en Maps';
        $('btn-detener').style.display = 'none';
        if (msg) $('search-log').textContent = msg;
    }

    $('btn-buscar').addEventListener('click', () => {
        const rubro = $('rubro').value.trim();
        const ciudades = $('ciudades').value.trim();
        if (!rubro || !ciudades) return alert('Completá el rubro y al menos una ciudad.');
        loadPlaces([], `${rubro} en ${ciudades.split('\n').join(' / ')}`);
        $('btn-buscar').disabled = true;
        $('btn-buscar').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Buscando...';
        $('btn-detener').style.display = '';
        $('search-log').textContent = 'Abriendo Google Maps... (aprox. 1 minuto cada 15 locales)';

        const params = new URLSearchParams({ rubro, ciudades, limit: $('limite').value });
        eventSource = new EventSource('/api/search_stream?' + params);
        eventSource.onmessage = (ev) => {
            const d = JSON.parse(ev.data);
            if (d.status === 'result') {
                places.push(d.data);
                if (['nuevo', 'error'].includes(d.data.estado)) selected.add(d.data.id);
                renderResults();
                $('search-log').textContent = `${places.length} locales leídos... último: ${d.data.name}`;
            } else if (d.status === 'log') {
                $('search-log').textContent = d.message;
            } else if (d.status === 'done') {
                endSearch(`Búsqueda terminada: ${places.length} locales. Quedó guardada en "Búsquedas guardadas".`);
            } else if (d.status === 'error') {
                endSearch('Error: ' + d.message);
            }
        };
        eventSource.onerror = () => endSearch(places.length ? `Conexión cortada. Se guardaron ${places.length} locales.` : 'No se pudo conectar con el servidor (¿hay otra búsqueda en curso?).');
    });
    $('btn-detener').addEventListener('click', () => api('/api/search/stop', { method: 'POST' }));

    // ---------------- filtros guardados ----------------
    async function renderPresets() {
        const presets = await api('/api/presets');
        $('presets-container').innerHTML = presets.map(p => `
            <span class="chip" data-id="${p.id}" data-rubro="${esc(p.rubro)}" data-ciudades="${esc(p.ciudades)}" data-limite="${p.limite}">
                ${esc(p.rubro)} · ${esc(p.ciudades.split('\n')[0])} <i class="fa-solid fa-xmark del" title="Borrar"></i>
            </span>`).join('');
    }
    $('presets-container').addEventListener('click', async e => {
        const chip = e.target.closest('.chip');
        if (!chip) return;
        if (e.target.classList.contains('del')) {
            await fetch('/api/presets/' + chip.dataset.id, { method: 'DELETE' });
            return renderPresets();
        }
        $('rubro').value = chip.dataset.rubro;
        $('ciudades').value = chip.dataset.ciudades;
        $('limite').value = chip.dataset.limite;
    });
    $('btn-save-preset').addEventListener('click', async () => {
        await api('/api/presets', { body: { rubro: $('rubro').value, ciudades: $('ciudades').value, limite: $('limite').value } });
        renderPresets();
    });

    // ---------------- Excel ----------------
    async function downloadExcel(ids, title) {
        const res = await fetch('/api/excel', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ids, title }) });
        if (!res.ok) return alert('No se pudo generar el Excel.');
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${title}.xlsx`.replace(/[\\/*?:"<>|]/g, '');
        a.click();
    }
    $('btn-excel').addEventListener('click', () => downloadExcel(visiblePlaces().map(p => p.id), currentTitle));

    // ---------------- búsquedas guardadas ----------------
    async function loadSearches() {
        const searches = await api('/api/searches');
        const tbody = document.querySelector('#tabla-listas tbody');
        tbody.innerHTML = searches.length ? searches.map(s => `
            <tr>
                <td>${esc(s.created)}</td>
                <td><strong>${esc(s.rubro)}</strong><br><small class="text-muted">${esc(s.ciudades)}</small></td>
                <td>${s.total}</td>
                <td>${s.contactados || 0}</td>
                <td class="actions">
                    <button class="btn-primary btn-sm" data-act="open" data-id="${s.id}" data-title="${esc(s.rubro + ' en ' + s.ciudades)}"><i class="fa-solid fa-folder-open"></i> Abrir</button>
                    <button class="btn-ghost btn-sm" data-act="excel" data-id="${s.id}" data-title="${esc(s.rubro + ' en ' + s.ciudades)}"><i class="fa-solid fa-file-excel"></i></button>
                    <button class="btn-danger btn-sm" data-act="del" data-id="${s.id}"><i class="fa-solid fa-trash"></i></button>
                </td>
            </tr>`).join('') : '<tr><td colspan="5" class="empty-state">Todavía no hay búsquedas guardadas.</td></tr>';
    }
    document.querySelector('#tabla-listas tbody').addEventListener('click', async e => {
        const b = e.target.closest('button');
        if (!b) return;
        const id = b.dataset.id;
        if (b.dataset.act === 'open') {
            loadPlaces(await api(`/api/searches/${id}/places`), b.dataset.title);
            showView('view-busqueda');
        } else if (b.dataset.act === 'excel') {
            const list = await api(`/api/searches/${id}/places`);
            downloadExcel(list.map(p => p.id), b.dataset.title);
        } else if (b.dataset.act === 'del' && confirm('¿Borrar esta búsqueda? Los locales que ya contactaste se conservan en Contactos.')) {
            await fetch('/api/searches/' + id, { method: 'DELETE' });
            loadSearches();
        }
    });

    // ---------------- contactos ----------------
    let contacts = [];
    async function loadContacts() {
        const estado = $('c-estado').value;
        const all = await api('/api/places' + (estado ? '?estado=' + estado : ''));
        contacts = estado ? all : all.filter(p => p.estado !== 'nuevo');
        renderContacts();
    }
    function renderContacts() {
        const t = $('c-texto').value.trim().toLowerCase();
        const list = contacts.filter(p => !t || `${p.name} ${p.categoria} ${p.notas}`.toLowerCase().includes(t));
        const opts = (cur) => Object.entries(ESTADOS).map(([k, [txt]]) => `<option value="${k}" ${k === cur ? 'selected' : ''}>${txt}</option>`).join('');
        document.querySelector('#tabla-contactos tbody').innerHTML = list.length ? list.map(p => `
            <tr data-id="${esc(p.id)}">
                <td><strong>${esc(p.name)}</strong><br><small class="text-muted">${esc(p.categoria || p.rubro || '')}</small></td>
                <td>${esc(p.phone || '-')}</td>
                <td><small>${esc(p.sent_at || '-')}</small></td>
                <td><select class="c-estado">${opts(p.estado)}</select></td>
                <td><input type="text" class="c-notas input-sm" value="${esc(p.notas || '')}" placeholder="Agregar nota..."></td>
                <td class="links">${linksCell(p)}</td>
            </tr>`).join('') : '<tr><td colspan="6" class="empty-state">No hay contactos con ese estado.</td></tr>';
    }
    $('c-estado').addEventListener('change', loadContacts);
    $('c-texto').addEventListener('input', renderContacts);
    document.querySelector('#tabla-contactos tbody').addEventListener('change', async e => {
        const tr = e.target.closest('tr');
        if (e.target.classList.contains('c-estado')) await api('/api/places/update', { body: { id: tr.dataset.id, estado: e.target.value } });
        if (e.target.classList.contains('c-notas')) await api('/api/places/update', { body: { id: tr.dataset.id, notas: e.target.value } });
        const p = contacts.find(x => x.id === tr.dataset.id);
        if (p) { p.estado = tr.querySelector('.c-estado').value; p.notas = tr.querySelector('.c-notas').value; }
    });
    $('btn-excel-contactos').addEventListener('click', () => downloadExcel(contacts.map(p => p.id), 'Contactos'));

    // ---------------- plantillas ----------------
    let templates = [];
    async function loadTemplates() {
        templates = await api('/api/templates');
        $('tpl-list').innerHTML = templates.map(t => `
            <div class="tpl-item">
                <div class="tpl-head">
                    <strong>${esc(t.name)}</strong> ${t.is_default ? '<span class="badge blue">General</span>' : ''}
                    <span class="tpl-actions">
                        <button class="btn-ghost btn-sm" data-act="edit" data-id="${t.id}"><i class="fa-solid fa-pen"></i></button>
                        <button class="btn-danger btn-sm" data-act="del" data-id="${t.id}"><i class="fa-solid fa-trash"></i></button>
                    </span>
                </div>
                <small class="text-muted">Rubros: ${esc(t.rubros || (t.is_default ? 'todos los demás' : '—'))} · ${t.body.split('|||').length} variante(s)</small>
                <p class="tpl-body">${esc(t.body.split('|||')[0].trim())}</p>
            </div>`).join('');
        return templates;
    }
    function clearTplForm() {
        ['tpl-id', 'tpl-name', 'tpl-rubros', 'tpl-body'].forEach(id => $(id).value = '');
        $('tpl-default').checked = false;
        $('tpl-form-title').textContent = 'Nueva plantilla';
        renderTplPreview();
    }
    function renderTplPreview() {
        const v = $('tpl-body').value.split('|||').map(s => s.trim()).filter(Boolean);
        $('tpl-preview').innerHTML = v.length ? '<small class="text-muted">Vista previa (ejemplo: "La Esquina", Corrientes):</small>' + v.map((m, i) =>
            `<div class="bubble"><small>Variante ${i + 1}</small><br>${esc(m.replaceAll('{nombre}', 'La Esquina').replaceAll('{ciudad}', 'Corrientes').replaceAll('{rubro}', 'bar'))}</div>`).join('') : '';
    }
    $('tpl-body').addEventListener('input', renderTplPreview);
    $('btn-tpl-new').addEventListener('click', clearTplForm);
    $('btn-tpl-save').addEventListener('click', async () => {
        const r = await api('/api/templates', { body: {
            id: $('tpl-id').value || null, name: $('tpl-name').value.trim(), rubros: $('tpl-rubros').value.trim(),
            body: $('tpl-body').value.trim(), is_default: $('tpl-default').checked } });
        if (!r.success) return alert(r.error);
        clearTplForm();
        loadTemplates();
    });
    $('tpl-list').addEventListener('click', async e => {
        const b = e.target.closest('button');
        if (!b) return;
        const t = templates.find(x => x.id == b.dataset.id);
        if (b.dataset.act === 'edit') {
            $('tpl-id').value = t.id; $('tpl-name').value = t.name; $('tpl-rubros').value = t.rubros;
            $('tpl-body').value = t.body; $('tpl-default').checked = !!t.is_default;
            $('tpl-form-title').textContent = 'Editando: ' + t.name;
            renderTplPreview();
        } else if (b.dataset.act === 'del' && confirm(`¿Borrar la plantilla "${t.name}"?`)) {
            await fetch('/api/templates/' + t.id, { method: 'DELETE' });
            loadTemplates();
        }
    });

    // Recuperar plantillas viejas que estaban guardadas solo en este navegador
    (async () => {
        try {
            const old = JSON.parse(localStorage.getItem('templates') || '[]');
            if (old.length && !localStorage.getItem('templates_migradas')) {
                const r = await api('/api/templates/import', { body: old });
                localStorage.setItem('templates_migradas', '1');
                if (r.importadas) alert(`Se recuperaron ${r.importadas} plantilla(s) que tenías guardadas en el navegador.`);
            }
        } catch (e) { /* sin acceso a localStorage */ }
    })();

    // ---------------- modal: preparar mensajes ----------------
    let preview = [];
    async function openPrepare() {
        await loadTemplates();
        $('modal-template').innerHTML = '<option value="auto">Automática según el rubro</option>' +
            templates.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join('');
        $('modal').style.display = 'flex';
        await refreshPreview();
    }
    async function refreshPreview() {
        $('modal-list').innerHTML = '<p class="text-muted">Armando mensajes...</p>';
        const ids = places.filter(p => selected.has(p.id)).sort((a, b) => (b.reviews || 0) - (a.reviews || 0)).map(p => p.id);
        preview = await api('/api/preview', { body: { ids, template_id: $('modal-template').value } });
        $('modal-list').innerHTML = preview.map((p, i) => `
            <div class="prep-item" data-i="${i}">
                <div class="prep-head">
                    <strong>${esc(p.name)}</strong>
                    <small class="text-muted">${esc(p.tel_tipo || '')} · plantilla: ${esc(p.template)}</small>
                    ${p.wa_phone ? `<a href="#" class="manual lnk wa" data-i="${i}" title="Abre el chat con el mensaje escrito y lo marca como enviado"><i class="fa-brands fa-whatsapp"></i> Enviar a mano</a>` : '<span class="badge red">Sin teléfono válido</span>'}
                </div>
                <textarea rows="3" class="prep-msg">${esc(p.message)}</textarea>
            </div>`).join('');
        $('modal-enqueue').innerHTML = `<i class="fa-solid fa-list-ol"></i> Agregar ${preview.length} a la cola de envío`;
    }
    $('btn-preparar').addEventListener('click', openPrepare);
    $('modal-template').addEventListener('change', refreshPreview);
    $('modal-close').addEventListener('click', () => $('modal').style.display = 'none');
    $('modal-list').addEventListener('input', e => {
        if (e.target.classList.contains('prep-msg')) preview[e.target.closest('.prep-item').dataset.i].message = e.target.value;
    });
    $('modal-list').addEventListener('click', async e => {
        const a = e.target.closest('.manual');
        if (!a) return;
        e.preventDefault();
        const p = preview[a.dataset.i];
        window.open(`https://wa.me/${p.wa_phone}?text=${encodeURIComponent(p.message)}`, '_blank');
        await api('/api/places/update', { body: { id: p.id, estado: 'enviado' } });
        const pl = places.find(x => x.id === p.id);
        if (pl) pl.estado = 'enviado';
        a.outerHTML = '<span class="badge green">Marcado como enviado</span>';
    });
    $('modal-enqueue').addEventListener('click', async () => {
        const items = preview.map(p => ({ id: p.id, message: p.message, template_id: p.template_id }));
        const r = await api('/api/queue', { body: { items } });
        $('modal').style.display = 'none';
        let msg = `Se agregaron ${r.agregados} mensajes a la cola.`;
        if (r.salteados.length) msg += `\n\nSe saltearon ${r.salteados.length}:\n- ` + r.salteados.slice(0, 15).join('\n- ');
        alert(msg + '\n\nAndá a "Envíos" y tocá "Iniciar envíos".');
        const ids = new Set(items.map(i => i.id));
        places.forEach(p => { if (ids.has(p.id) && p.estado === 'nuevo') p.estado = 'en_cola'; });
        selected.clear();
        renderResults();
        refreshSender();
    });

    // ---------------- envíos ----------------
    const SETTINGS = ['limite_diario', 'hora_inicio', 'hora_fin', 'demora_min', 'demora_max', 'pausa_cada', 'pausa_larga_min'];
    async function loadEnvios() {
        const s = await api('/api/settings');
        SETTINGS.forEach(k => $('s-' + k).value = s[k]);
        refreshSender();
        loadQueue();
    }
    async function loadQueue() {
        const rows = await api('/api/queue');
        const st = { pendiente: badge('en_cola').replace('En cola', 'Pendiente'), enviado: badge('enviado'), sin_whatsapp: badge('sin_whatsapp'), error: badge('error'), cancelado: '<span class="badge gray">Cancelado</span>' };
        document.querySelector('#tabla-cola tbody').innerHTML = rows.length ? rows.map(r => `
            <tr>
                <td><strong>${esc(r.name || r.wa_phone)}</strong><br><small class="text-muted">${esc(r.categoria || '')}</small></td>
                <td><small>${esc(r.message)}</small></td>
                <td>${st[r.estado] || esc(r.estado)}${r.error ? `<br><small class="text-muted">${esc(r.error)}</small>` : ''}</td>
                <td><small>${esc(r.sent_at || r.created)}</small></td>
                <td>${r.estado === 'pendiente' ? `<button class="btn-ghost btn-sm" data-id="${r.id}" title="Quitar de la cola"><i class="fa-solid fa-xmark"></i></button>` : ''}</td>
            </tr>`).join('') : '<tr><td colspan="5" class="empty-state">La cola está vacía. Prepará mensajes desde "Buscar locales".</td></tr>';
    }
    async function refreshSender() {
        try {
            const s = await api('/api/sender');
            $('st-hoy').textContent = `${s.enviados_hoy}/${s.limite_diario}`;
            $('st-pend').textContent = s.pendientes;
            $('st-prox').textContent = s.proximo_envio || '—';
            $('st-estado').textContent = s.estado;
            $('st-log').innerHTML = s.log.map(l => `<div>${esc(l)}</div>`).join('') || '<div class="text-muted">Sin actividad todavía.</div>';
            $('btn-start').style.display = s.activo ? 'none' : '';
            $('btn-stop').style.display = s.activo ? '' : 'none';
            $('badge-cola').textContent = s.pendientes || '';
            const ses = { ok: 'conectado ✅', qr: 'escaneá el QR', desconocida: 'sin verificar' }[s.sesion];
            $('sidebar-status').innerHTML = `WhatsApp: ${ses}<br>${s.activo ? '▶ Enviando' : '⏸ Envíos pausados'}`;
        } catch (e) {
            $('sidebar-status').textContent = 'Servidor desconectado';
        }
    }
    $('btn-save-settings').addEventListener('click', async () => {
        const body = {};
        SETTINGS.forEach(k => body[k] = $('s-' + k).value);
        if (+body.demora_max < +body.demora_min) return alert('La espera máxima debe ser mayor que la mínima.');
        const r = await api('/api/settings', { body });
        alert(r.success ? 'Ritmo guardado.' : r.error);
    });
    $('btn-start').addEventListener('click', async () => { await api('/api/sender/start', { method: 'POST' }); refreshSender(); });
    $('btn-stop').addEventListener('click', async () => { await api('/api/sender/stop', { method: 'POST' }); refreshSender(); });
    $('btn-wa-login').addEventListener('click', async () => {
        await api('/api/wa_login', { method: 'POST' });
        alert('Se abre una ventana de WhatsApp Web. Si pide QR, escanealo desde tu celular (WhatsApp > Dispositivos vinculados).');
    });
    $('btn-cancel-all').addEventListener('click', async () => {
        if (!confirm('¿Quitar todos los mensajes pendientes de la cola?')) return;
        await api('/api/queue/cancel_all', { method: 'POST' });
        loadQueue(); refreshSender();
    });
    document.querySelector('#tabla-cola tbody').addEventListener('click', async e => {
        const b = e.target.closest('button');
        if (!b) return;
        await fetch('/api/queue/' + b.dataset.id, { method: 'DELETE' });
        loadQueue(); refreshSender();
    });

    setInterval(() => {
        refreshSender();
        if ($('view-envios').style.display !== 'none') loadQueue();
    }, 5000);

    renderPresets();
    refreshSender();
    renderResults();
});
