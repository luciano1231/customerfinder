document.addEventListener('DOMContentLoaded', () => {
    const btnBuscar = document.getElementById('btn-buscar');
    const tbody = document.querySelector('tbody');
    const navWaAuth = document.getElementById('nav-wa-auth');
    
    // --- LÓGICA DE NAVEGACIÓN ---
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            // Quitar active de todos
            navItems.forEach(n => n.classList.remove('active'));
            // Agregar al clickeado
            item.classList.add('active');
            
            // Ocultar todas las vistas
            views.forEach(v => v.style.display = 'none');
            // Mostrar la vista objetivo
            const targetId = item.getAttribute('data-target');
            document.getElementById(targetId).style.display = 'block';
        });
    });

    // --- LÓGICA DE PRESETS (Filtros Rápidos) ---
    const btnSavePreset = document.getElementById('btn-save-preset');
    const presetsContainer = document.getElementById('presets-container');
    
    function getPresets() {
        return JSON.parse(localStorage.getItem('search_presets') || '[]');
    }
    
    function savePresets(presets) {
        localStorage.setItem('search_presets', JSON.stringify(presets));
        renderPresets();
    }
    
    function renderPresets() {
        if(!presetsContainer) return;
        const presets = getPresets();
        presetsContainer.innerHTML = '';
        if(presets.length === 0) {
            presetsContainer.innerHTML = '<span class="text-sm text-muted">No tienes filtros guardados.</span>';
            return;
        }
        presets.forEach((p, i) => {
            const btn = document.createElement('button');
            btn.className = 'btn-secondary';
            btn.style.padding = '4px 10px';
            btn.style.fontSize = '0.85rem';
            btn.style.borderRadius = '15px';
            btn.style.background = 'rgba(255,255,255,0.05)';
            btn.innerHTML = `${p.rubro} - ${p.ciudad} <i class="fa-solid fa-xmark btn-delete-preset" data-index="${i}" style="margin-left:5px;cursor:pointer;color:var(--error);"></i>`;
            
            btn.addEventListener('click', (e) => {
                if(e.target.classList.contains('btn-delete-preset')) {
                    e.stopPropagation();
                    const newPresets = getPresets();
                    newPresets.splice(i, 1);
                    savePresets(newPresets);
                } else {
                    document.getElementById('rubro').value = p.rubro;
                    document.getElementById('ciudad').value = p.ciudad;
                    document.getElementById('limite').value = p.limite;
                }
            });
            presetsContainer.appendChild(btn);
        });
    }
    
    if(btnSavePreset) {
        btnSavePreset.addEventListener('click', () => {
            const rubro = document.getElementById('rubro').value;
            const ciudad = document.getElementById('ciudad').value;
            const limite = document.getElementById('limite').value;
            if(!rubro || !ciudad) return alert("Completa Rubro y Ciudad para guardar el filtro.");
            
            const presets = getPresets();
            presets.push({rubro, ciudad, limite});
            savePresets(presets);
        });
        renderPresets();
    }

    // --- LÓGICA DE LISTAS GUARDADAS ---
    const tablaListas = document.querySelector('#tabla-listas tbody');
    let currentSearchData = [];
    
    function getSavedLists() {
        return JSON.parse(localStorage.getItem('saved_lists') || '[]');
    }
    
    function saveLists(lists) {
        localStorage.setItem('saved_lists', JSON.stringify(lists));
        renderSavedLists();
    }
    
    function renderSavedLists() {
        if(!tablaListas) return;
        const lists = getSavedLists();
        tablaListas.innerHTML = '';
        if(lists.length === 0) {
            tablaListas.innerHTML = '<tr><td colspan="4" class="empty-state">No hay listas guardadas. Realiza una búsqueda primero.</td></tr>';
            return;
        }
        // Mostrar en orden reverso (más nuevas primero)
        [...lists].reverse().forEach(list => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${list.date}</td>
                <td><strong>${list.name}</strong></td>
                <td>${list.data.length} locales</td>
                <td>
                    <button class="btn-load-list" data-id="${list.id}" style="background:var(--accent); color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer; margin-right:5px;">
                        <i class="fa-solid fa-folder-open"></i> Cargar
                    </button>
                    <button class="btn-delete-list" data-id="${list.id}" style="background:var(--error); color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            `;
            tablaListas.appendChild(tr);
        });
    }
    
    function loadListToTable(listData) {
        tbody.innerHTML = '';
        currentSearchData = listData;
        
        if(listData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Lista vacía.</td></tr>';
            return;
        }
        
        listData.forEach(local => {
            const idealClient = !local.has_web && local.phone !== "No tiene";
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input type="checkbox" class="local-check" ${idealClient ? 'checked' : ''} data-phone="${local.phone}" data-name="${local.name}"></td>
                <td><strong>${local.name}</strong> ${idealClient ? '<span style="color:var(--success);font-size:0.8rem;margin-left:5px;"><i class="fa-solid fa-star"></i> Ideal</span>' : ''}</td>
                <td>${local.phone}</td>
                <td>${local.has_web ? '<span style="color:var(--accent)"><i class="fa-solid fa-check"></i> Sí</span>' : '<span style="color:var(--text-muted)"><i class="fa-solid fa-xmark"></i> No</span>'}</td>
                <td><a href="${local.url}" target="_blank" style="color: var(--accent); text-decoration: none;"><i class="fa-solid fa-map-location-dot"></i> Maps</a></td>
                <td><span class="status-badge" style="background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; font-size: 0.8rem;">Pendiente</span></td>
            `;
            tbody.appendChild(tr);
        });
        
        document.getElementById('btn-aprobar').disabled = false;
        
        // Cambiar a la vista de Búsqueda
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelector('[data-target="view-busqueda"]').classList.add('active');
        document.querySelectorAll('.view-section').forEach(v => v.style.display = 'none');
        document.getElementById('view-busqueda').style.display = 'block';
    }

    if(tablaListas) {
        renderSavedLists();
        tablaListas.addEventListener('click', (e) => {
            const btnLoad = e.target.closest('.btn-load-list');
            const btnDelete = e.target.closest('.btn-delete-list');
            
            if(btnLoad) {
                const id = parseInt(btnLoad.getAttribute('data-id'));
                const list = getSavedLists().find(l => l.id === id);
                if(list) loadListToTable(list.data);
            }
            
            if(btnDelete) {
                if(confirm("¿Eliminar esta lista guardada?")) {
                    const id = parseInt(btnDelete.getAttribute('data-id'));
                    const lists = getSavedLists().filter(l => l.id !== id);
                    saveLists(lists);
                }
            }
        });
    }

    // --- LÓGICA DE PLANTILLAS ---
    const defaultTemplate = "Hola {nombre}, mi nombre es Lucía. Noté que no tienen un sitio web activo. Ayudo a negocios en Corrientes a digitalizarse con diseños premium para atraer más clientes. ¿Te interesaría ver algunas opciones sin compromiso?";
    
    function getTemplates() {
        const t = localStorage.getItem('templates');
        return t ? JSON.parse(t) : [];
    }
    
    function saveTemplates(templates) {
        localStorage.setItem('templates', JSON.stringify(templates));
    }

    function renderTemplates() {
        const templates = getTemplates();
        const selector = document.getElementById('template-selector');
        const tabla = document.querySelector('#tabla-plantillas tbody');
        
        // Actualizar Selector en Vista Búsqueda
        selector.innerHTML = '<option value="default">Plantilla por defecto</option>';
        templates.forEach((t, i) => {
            selector.innerHTML += `<option value="${i}">${t.name}</option>`;
        });

        // Actualizar Tabla en Vista Plantillas
        if(tabla) {
            tabla.innerHTML = '';
            if(templates.length === 0) {
                tabla.innerHTML = '<tr><td colspan="3" class="empty-state">No hay plantillas personalizadas guardadas.</td></tr>';
            } else {
                templates.forEach((t, i) => {
                    tabla.innerHTML += `
                        <tr>
                            <td><strong>${t.name}</strong></td>
                            <td><div style="max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${t.content}</div></td>
                            <td>
                                <button class="btn-delete-template" data-index="${i}" style="background:var(--error); color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }
        }
    }

    renderTemplates();

    const selector = document.getElementById('template-selector');
    const txtMensaje = document.getElementById('mensaje');
    
    if(selector && txtMensaje) {
        selector.addEventListener('change', (e) => {
            if(e.target.value === 'default') {
                txtMensaje.value = defaultTemplate;
            } else {
                const templates = getTemplates();
                txtMensaje.value = templates[e.target.value].content;
            }
        });
    }

    const btnSaveTemplate = document.getElementById('btn-save-template');
    if(btnSaveTemplate) {
        btnSaveTemplate.addEventListener('click', () => {
            const name = document.getElementById('new-template-name').value;
            const content = document.getElementById('new-template-content').value;
            
            if(!name || !content) {
                alert("Por favor completa el nombre y el contenido de la plantilla.");
                return;
            }
            
            const templates = getTemplates();
            templates.push({ name, content });
            saveTemplates(templates);
            
            document.getElementById('new-template-name').value = '';
            document.getElementById('new-template-content').value = '';
            
            renderTemplates();
            alert("¡Plantilla guardada con éxito!");
        });
    }

    document.addEventListener('click', (e) => {
        if(e.target.closest('.btn-delete-template')) {
            const btn = e.target.closest('.btn-delete-template');
            const index = btn.getAttribute('data-index');
            if(confirm("¿Segura que deseas eliminar esta plantilla?")) {
                const templates = getTemplates();
                templates.splice(index, 1);
                saveTemplates(templates);
                renderTemplates();
                
                // Si la plantilla borrada estaba seleccionada, volver a default
                if(document.getElementById('template-selector').value === index) {
                    document.getElementById('template-selector').value = 'default';
                    document.getElementById('mensaje').value = defaultTemplate;
                }
            }
        }
    });

    
    // Autenticación de WhatsApp
    if(navWaAuth) {
        navWaAuth.addEventListener('click', async (e) => {
            e.preventDefault();
            alert("Se abrirá una ventana de navegador. Por favor escanea el código QR con tu WhatsApp y espera a que carguen tus chats. Luego la ventana se cerrará automáticamente y tu sesión quedará guardada de forma segura.");
            try {
                await fetch('/api/wa_auth', { method: 'POST' });
                alert("¡Excelente! WhatsApp conectado y sesión guardada correctamente.");
            } catch(error) {
                alert("Ocurrió un error al intentar abrir WhatsApp.");
                console.error(error);
            }
        });
    }
    
    btnBuscar.addEventListener('click', async () => {
        const rubro = document.getElementById('rubro').value;
        const ciudad = document.getElementById('ciudad').value;
        const limite = document.getElementById('limite').value;
        
        currentSearchData = [];
        
        // Preparar lista para guardado progresivo
        const listId = Date.now();
        const initialLists = getSavedLists();
        initialLists.push({
            id: listId,
            date: new Date().toLocaleString('es-AR'),
            name: `${rubro} en ${ciudad}`,
            data: []
        });
        saveLists(initialLists);
        
        // Efecto visual en la UI
        btnBuscar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Extrayendo datos de Maps...';
        btnBuscar.disabled = true;
        
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Iniciando motor de búsqueda para "${rubro}" en "${ciudad}"...<br><small>Esto puede tomar desde unos segundos hasta varios minutos (aprox. 1 minuto por cada 20 resultados) dependiendo de la cantidad de ciudades y el límite.</small></td></tr>`;
        
        try {
            // Construir la URL con parámetros para GET
            const params = new URLSearchParams({
                rubro,
                ciudad,
                limit: parseInt(limite)
            });
            
            const eventSource = new EventSource('/api/search_stream?' + params.toString());
            let hasResults = false;
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.status === 'result') {
                    if (!hasResults) {
                        tbody.innerHTML = ''; // Limpiar el mensaje de carga con el primer resultado
                        hasResults = true;
                    }
                    
                    const local = data.data;
                    currentSearchData.push(local);
                    
                    // Guardado progresivo en localStorage
                    const currentLists = getSavedLists();
                    const targetList = currentLists.find(l => l.id === listId);
                    if (targetList) {
                        targetList.data.push(local);
                        localStorage.setItem('saved_lists', JSON.stringify(currentLists));
                    }
                    
                    const tr = document.createElement('tr');
                    const idealClient = !local.has_web && local.phone !== "No tiene";
                    
                    tr.innerHTML = `
                        <td><input type="checkbox" class="local-check" ${idealClient ? 'checked' : ''} data-phone="${local.phone}" data-name="${local.name}"></td>
                        <td><strong>${local.name}</strong> ${idealClient ? '<span style="color:var(--success);font-size:0.8rem;margin-left:5px;"><i class="fa-solid fa-star"></i> Ideal</span>' : ''}</td>
                        <td>${local.phone}</td>
                        <td>${local.has_web ? '<span style="color:var(--accent)"><i class="fa-solid fa-check"></i> Sí</span>' : '<span style="color:var(--text-muted)"><i class="fa-solid fa-xmark"></i> No</span>'}</td>
                        <td><a href="${local.url}" target="_blank" style="color: var(--accent); text-decoration: none;"><i class="fa-solid fa-map-location-dot"></i> Maps</a></td>
                        <td><span class="status-badge" style="background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 4px; font-size: 0.8rem;">Pendiente</span></td>
                    `;
                    tbody.appendChild(tr);
                    
                    // Habilitar botón de enviar
                    document.getElementById('btn-aprobar').disabled = false;
                    
                    // Hacer scroll automático hacia abajo si es necesario
                    document.querySelector('.table-container').scrollTop = document.querySelector('.table-container').scrollHeight;
                    
                } else if (data.status === 'done') {
                    eventSource.close();
                    if (!hasResults) {
                        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Búsqueda finalizada. No se encontraron resultados viables.</td></tr>`;
                        // Eliminar la lista vacía si no hubo resultados
                        const currentLists = getSavedLists();
                        const newLists = currentLists.filter(l => l.id !== listId);
                        saveLists(newLists);
                    } else {
                        // Renderizar las listas guardadas para actualizar la vista
                        renderSavedLists();
                    }
                    btnBuscar.innerHTML = '<i class="fa-solid fa-search"></i> Buscar en Maps';
                    btnBuscar.disabled = false;
                } else if (data.status === 'error') {
                    eventSource.close();
                    if (!hasResults) {
                        tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: #ef4444;">Ocurrió un error: ${data.message}</td></tr>`;
                        // Eliminar la lista vacía si no hubo resultados
                        const currentLists = getSavedLists();
                        const newLists = currentLists.filter(l => l.id !== listId);
                        saveLists(newLists);
                    } else {
                        renderSavedLists();
                    }
                    btnBuscar.innerHTML = '<i class="fa-solid fa-search"></i> Buscar en Maps';
                    btnBuscar.disabled = false;
                    console.error("Error backend:", data.message);
                }
            };
            
            eventSource.onerror = function(error) {
                console.error("EventSource failed:", error);
                eventSource.close();
                if (!hasResults) {
                    tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: #ef4444;">Error de conexión con el servidor. Revisar consola.</td></tr>`;
                    // Eliminar la lista vacía
                    const currentLists = getSavedLists();
                    const newLists = currentLists.filter(l => l.id !== listId);
                    saveLists(newLists);
                } else {
                    renderSavedLists();
                }
                btnBuscar.innerHTML = '<i class="fa-solid fa-search"></i> Buscar en Maps';
                btnBuscar.disabled = false;
            };
            
        } catch (error) {
            console.error("Error iniciando búsqueda:", error);
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color: #ef4444;">No se pudo iniciar el stream. Revisa la consola.</td></tr>`;
            btnBuscar.innerHTML = '<i class="fa-solid fa-search"></i> Buscar en Maps';
            btnBuscar.disabled = false;
        }
    });

    // Lógica para Aprobar y Enviar
    const btnAprobar = document.getElementById('btn-aprobar');
    if(btnAprobar) {
        btnAprobar.addEventListener('click', async () => {
            const checkboxes = document.querySelectorAll('.local-check:checked');
            const template = document.getElementById('mensaje').value;
            
            if (checkboxes.length === 0) {
                alert("Por favor, selecciona al menos un local de la tabla para enviar.");
                return;
            }
            
            const clients = [];
            checkboxes.forEach(cb => {
                clients.push({
                    phone: cb.dataset.phone,
                    name: cb.dataset.name
                });
            });
            
            if(!confirm(`¿Estás segura de iniciar el envío a ${clients.length} locales?`)) return;
            
            const originalText = btnAprobar.innerHTML;
            btnAprobar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando mensajes...';
            btnAprobar.disabled = true;
            
            try {
                const response = await fetch('/api/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ clients, template })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Actualizar el estado en la tabla
                    data.results.forEach(res => {
                        const row = Array.from(document.querySelectorAll('.local-check')).find(cb => cb.dataset.phone === res.phone)?.closest('tr');
                        if (row) {
                            const statusCell = row.cells[5];
                            if (res.status === "Enviado") {
                                statusCell.innerHTML = `<span class="status-badge" style="background: rgba(16,185,129,0.2); color: var(--success); padding: 4px 8px; border-radius: 4px; font-size: 0.8rem;"><i class="fa-solid fa-check-double"></i> Enviado</span>`;
                                row.querySelector('.local-check').checked = false;
                            } else {
                                statusCell.innerHTML = `<span class="status-badge" style="background: rgba(239,68,68,0.2); color: #ef4444; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem;"><i class="fa-solid fa-circle-exclamation"></i> Error</span>`;
                            }
                        }
                    });
                    alert("¡Campaña finalizada con éxito!");
                } else {
                    alert("Aviso del Sistema: " + data.error);
                }
            } catch (e) {
                console.error(e);
                alert("Ocurrió un error de conexión con el servidor local.");
            } finally {
                btnAprobar.innerHTML = originalText;
                btnAprobar.disabled = false;
            }
        });
    }
});
