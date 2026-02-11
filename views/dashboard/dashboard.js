// Dashboard JavaScript

let dashboard = null;

document.addEventListener('change', (e) => {
    if (e && e.target && e.target.id === 'estado-filter') {
        if (window.dashboard && typeof window.dashboard.filtrarProximos === 'function') {
            window.dashboard.filtrarProximos();
        }
    }
});

document.addEventListener('input', (e) => {
    if (e && e.target && e.target.id === 'estado-filter') {
        if (window.dashboard && typeof window.dashboard.filtrarProximos === 'function') {
            window.dashboard.filtrarProximos();
        }
    }
});

class Dashboard {
    constructor() {
        this.refreshInterval = null;
        this.editingSchedule = false; // Flag to block refresh when editing
        this.retryInProgress = new Set(); // Track which retries are in progress
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.updateTime();
        this.loadData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.loadData();
            this.showToast('Datos actualizados', 'success');
        });

        // Botón Nuevo Boletín
        const addBulletinBtn = document.getElementById('btn-add-bulletin');
        if (addBulletinBtn) {
            addBulletinBtn.addEventListener('click', () => {
                this.showUploadBulletinModal();
            });
        }

        // Filtro de estado para próximos envíos
        const estadoFilter = document.getElementById('estado-filter');
        if (estadoFilter) {
            estadoFilter.addEventListener('change', () => {
                this.filtrarProximos();
            });
        }

        // Filtro de fecha para últimos envíos
        const fechaFilter = document.getElementById('fecha-filter');
        if (fechaFilter) {
            fechaFilter.addEventListener('change', () => {
                this.filtrarEnvios();
            });

            // Establecer fecha por defecto a hoy
            const today = new Date().toISOString().split('T')[0];
            fechaFilter.value = today;
        }

        // Update time every second
        setInterval(() => this.updateTime(), 1000);
    }

    updateTime() {
        const now = new Date();
        const timeString = now.toLocaleString('es-CO', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        document.getElementById('current-time').textContent = timeString;
    }

    startAutoRefresh() {
        // Auto refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.loadData();
        }, 30000);
    }

    async loadData() {
        // Don't refresh if we're editing a schedule or if there are retries in progress
        if (this.editingSchedule) {
            return;
        }
        
        if (this.retryInProgress.size > 0) {
            return;
        }
        
        try {
            // Load all data in parallel
            const [stats, envios, proximos] = await Promise.all([
                this.fetchStats(),
                this.fetchEnvios(),
                this.fetchProximos()
            ]);

            this.updateStats(stats);
            this.updateEnviosTable(envios);
            this.updateProximosTable(proximos);
        } catch (error) {
            this.showToast('Error cargando datos', 'error');
        }
    }

    async fetchStats() {
        try {
            const response = await fetch('/api/stats');
            return await response.json();
        } catch (error) {
            return {
                enviosHoy: 0,
                fallidos: 0,
                proximos: 0,
                tareasActivas: 0
            };
        }
    }

    async fetchEnvios() {
        try {
            const response = await fetch('/api/envios');
            return await response.json();
        } catch (error) {
            return [];
        }
    }

    async fetchProximos() {
        try {
            const response = await fetch('/api/proximos');
            
            if (!response.ok) {
                return [];
            }
            
            const data = await response.json();
            
            return data;
        } catch (error) {
            return [];
        }
    }

    updateStats(stats) {
        document.getElementById('envios-hoy').textContent = stats.enviosHoy;
        document.getElementById('envios-fallidos').textContent = stats.fallidos;
        document.getElementById('proximos-envios').textContent = stats.proximos;
        document.getElementById('tareas-activas').textContent = stats.tareasActivas;
    }

    updateEnviosTable(envios) {
        try {
            // Almacenar todos los datos para el filtro
            this.allEnvios = envios;
            
            // Aplicar filtro actual
            this.filtrarEnvios();
        } catch (error) {
            // Mostrar mensaje de error en la tabla
            const tbody = document.getElementById('envios-tbody');
            const loading = document.getElementById('envios-loading');
            
            if (loading) loading.style.display = 'none';
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--error-color);">Error cargando datos de envíos</td></tr>';
            }
        }
    }

    filtrarEnvios() {
        const tbody = document.getElementById('envios-tbody');
        const loading = document.getElementById('envios-loading');
        const fechaFilter = document.getElementById('fecha-filter');
        
        if (!fechaFilter) {
            return;
        }
        
        loading.style.display = 'none';
        tbody.innerHTML = '';

        // Obtener valor del filtro de fecha
        const fechaSeleccionada = fechaFilter.value;
        
        const allEnvios = Array.isArray(this.allEnvios) ? this.allEnvios : [];
        
        let enviosFiltrados = allEnvios;

        // Filtrar por fecha si se seleccionó una
        if (fechaSeleccionada) {
            try {
                enviosFiltrados = allEnvios.filter(envio => {
                    if (!envio || !envio.fecha) {
                        return false;
                    }
                    
                    // Extraer la fecha del envío (formato real: "2026-02-10 14:35")
                    const fechaEnvioStr = envio.fecha.split(' ')[0]; // "2026-02-10"
                    
                    // Validar formato de fecha (YYYY-MM-DD)
                    if (!fechaEnvioStr || fechaEnvioStr.split('-').length !== 3) {
                        return false;
                    }
                    
                    // La fecha ya está en formato YYYY-MM-DD,可以直接比较
                    return fechaEnvioStr === fechaSeleccionada;
                });
            } catch (error) {
                // Si hay error en el filtrado, mostrar todos los envíos
                enviosFiltrados = allEnvios;
            }
        }

        if (enviosFiltrados.length === 0) {
            const mensaje = fechaSeleccionada ? 
                `No hay envíos registrados para el ${this.formatearFecha(fechaSeleccionada)}` : 
                'No hay envíos registrados hoy';
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">${mensaje}</td></tr>`;
            return;
        }

        // Indexar envíos por id para el modal de detalles y evitar duplicados visuales
        this.enviosById = new Map();
        const enviosUnique = [];
        enviosFiltrados.forEach((envio) => {
            try {
                if (!envio || envio.id == null) return;
                const key = String(envio.id);
                if (!this.enviosById.has(key)) {
                    this.enviosById.set(key, envio);
                    enviosUnique.push(envio);
                }
            } catch (error) {
                // Silenciosamente ignorar envíos con errores
            }
        });

        enviosUnique.forEach(envio => {
            try {
                const row = this.createEnvioRow(envio);
                tbody.appendChild(row);
            } catch (error) {
                // Silenciosamente ignorar errores al crear filas
            }
        });
    }

    formatearFecha(fechaISO) {
        // La fecha ya viene en formato YYYY-MM-DD, convertirla a DD/MM/YYYY
        const [año, mes, dia] = fechaISO.split('-');
        return `${dia}/${mes}/${año}`;
    }

    clearDateFilter() {
        const fechaFilter = document.getElementById('fecha-filter');
        if (fechaFilter) {
            fechaFilter.value = '';
            this.filtrarEnvios();
        }
    }

    createEnvioRow(envio) {
        const row = document.createElement('tr');
        const envioId = String(envio.id).replace(/'/g, "\\'");
        row.innerHTML = `
            <td>${envio.fecha}</td>
            <td>${envio.boletin}</td>
            <td>${this.createStatusBadge(envio.status)}</td>
            <td>${envio.duracion}</td>
            <td>
                <button class="btn-action" onclick="dashboard.showDetails('${envioId}')" title="Ver detalles">
                    <i class="fas fa-eye"></i>
                </button>
                ${envio.status === 'failed' ? `
                    <button class="btn-action" onclick="dashboard.retryExecution('${envioId}')" title="Reintentar">
                        <i class="fas fa-redo"></i>
                    </button>
                ` : ''}
            </td>
        `;
        return row;
    }

    updateProximosTable(proximos) {
        // Almacenar todos los datos para el filtro
        this.allProximos = proximos;
        
        // Aplicar filtro actual
        this.filtrarProximos();
    }

    filtrarProximos() {
        const tbody = document.getElementById('proximos-tbody');
        const loading = document.getElementById('proximos-loading');
        const filterSelect = document.getElementById('estado-filter');
        const filterCount = document.getElementById('filter-count');
        
        if (!filterSelect) {
            return;
        }
        
        loading.style.display = 'none';
        tbody.innerHTML = '';

        // Obtener valor del filtro
        const filtroValue = filterSelect.value;

        if (filterCount) {
            filterCount.textContent = 'Mostrando 0 boletines';
        }
        
        const allProximos = Array.isArray(this.allProximos) ? this.allProximos : [];

        let proximosFiltrados = allProximos;

        if (filtroValue === 'enabled') {
            proximosFiltrados = allProximos.filter(p => p.estado === 'enabled');
        } else if (filtroValue === 'disabled') {
            proximosFiltrados = allProximos.filter(p => p.estado === 'disabled');
        }
        
        // Actualizar contador
        if (filterCount) {
            filterCount.textContent = `Mostrando ${proximosFiltrados.length} boletines`;
        }

        if (proximosFiltrados.length === 0) {
            const mensaje = filtroValue === 'todos' ? 
                'No hay envíos programados' : 
                `No hay boletines ${filtroValue === 'enabled' ? 'activos' : 'desactivados'}`;
            tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary);">${mensaje}</td></tr>`;
            return;
        }

        proximosFiltrados.forEach(proximo => {
            const row = this.createProximoRow(proximo);
            tbody.appendChild(row);
        });
    }

    createProximoRow(proximo) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${proximo.boletin}</td>
            <td>${proximo.hora}</td>
            <td>${this.createStatusBadge(proximo.estado)}</td>
            <td>${proximo.ultimaEjecucion}</td>
            <td>
                <button class="btn-action" onclick="dashboard.editSchedule('${proximo.id}')" title="Editar">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn-action" onclick="dashboard.toggleSchedule('${proximo.id}')" title="Habilitar/Deshabilitar">
                    <i class="fas fa-toggle-${proximo.estado === 'enabled' ? 'on' : 'off'}"></i>
                </button>
                <button class="btn-action" onclick="dashboard.deleteSchedule('${proximo.id}')" title="Eliminar">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;
        return row;
    }

    createStatusBadge(status) {
        const statusConfig = {
            success: { class: 'success', text: 'Éxito', icon: 'check-circle' },
            failed: { class: 'failed', text: 'Fallido', icon: 'times-circle' },
            running: { class: 'running', text: 'Ejecutando', icon: 'spinner fa-spin' },
            pending: { class: 'pending', text: 'Pendiente', icon: 'clock' },
            enabled: { class: 'success', text: 'Habilitado', icon: 'check-circle' },
            disabled: { class: 'failed', text: 'Deshabilitado', icon: 'times-circle' }
        };

        const config = statusConfig[status] || statusConfig.pending;
        return `
            <span class="status-badge ${config.class}">
                <i class="fas fa-${config.icon}"></i>
                ${config.text}
            </span>
        `;
    }

    // Action Methods
    showSettings() {
        this.showModal('Configuración General', `
            <div class="form-group">
                <label>Remitente de Correos:</label>
                <input type="email" id="email-remite" class="form-control" placeholder="noreply@empresa.com" value="">
                <small class="form-text">Dirección de correo que aparecerá como remitente de todos los boletines</small>
            </div>
            
            <div class="form-group">
                <label>Pie de Página:</label>
                <textarea id="pie-pagina" class="form-control" rows="3" placeholder="© 2026 Empresa S.A. Todos los derechos reservados."></textarea>
                <small class="form-text">Texto que aparecerá al final de cada boletín</small>
            </div>
            
            <div class="form-group">
                <label>Logs de Retención:</label>
                <select id="logs-retencion" class="form-control">
                    <option value="7">7 días</option>
                    <option value="15">15 días</option>
                    <option value="30" selected>30 días (por defecto)</option>
                    <option value="60">60 días</option>
                    <option value="90">90 días</option>
                    <option value="365">1 año</option>
                </select>
                <small class="form-text">Tiempo que se conservará el historial de envíos en el sistema</small>
            </div>
            
            <div class="form-actions">
                <button class="btn-primary" onclick="dashboard.saveSettings()">
                    <i class="fas fa-save"></i> Guardar Configuración
                </button>
                <button class="btn-secondary" onclick="dashboard.closeModal()">Cancelar</button>
            </div>
        `);
        
        // Cargar configuración existente
        this.loadSettings();
    }
    
    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            if (response.ok) {
                const settings = await response.json();
                
                // Llenar el formulario con los valores existentes
                if (settings.emailRemitente) {
                    document.getElementById('email-remite').value = settings.emailRemitente;
                }
                if (settings.piePagina) {
                    document.getElementById('pie-pagina').value = settings.piePagina;
                }
                if (settings.logsRetencion) {
                    document.getElementById('logs-retencion').value = settings.logsRetencion;
                }
                if (settings.guardarBackups !== undefined) {
                    document.getElementById('guardar-backups').checked = settings.guardarBackups;
                }
                if (settings.logsDetallados !== undefined) {
                    document.getElementById('logs-detallados').checked = settings.logsDetallados;
                }
            }
        } catch (error) {
            this.showToast('Error cargando configuración', 'error');
        }
    }

    showDetails(id) {
        const key = String(id);
        const envio = this.enviosById ? this.enviosById.get(key) : null;

        const estadoHtml = envio ? this.createStatusBadge(envio.status) : this.createStatusBadge('pending');
        const fecha = envio && envio.fecha ? envio.fecha : 'N/A';
        const boletin = envio && envio.boletin ? envio.boletin : 'N/A';
        const duracion = envio && envio.duracion ? envio.duracion : 'N/A';
        const error = envio && envio.error ? envio.error : '';
        const logs = envio && envio.logs ? envio.logs : '';

        this.showModal('Detalles de Ejecución', `
            <div class="detail-item">
                <label>ID:</label>
                <span>#${key}</span>
            </div>
            <div class="detail-item">
                <label>Boletín:</label>
                <span>${boletin}</span>
            </div>
            <div class="detail-item">
                <label>Fecha:</label>
                <span>${fecha}</span>
            </div>
            <div class="detail-item">
                <label>Estado:</label>
                <span>${estadoHtml}</span>
            </div>
            <div class="detail-item">
                <label>Duración:</label>
                <span>${duracion}</span>
            </div>
            ${error ? `
            <div class="detail-item">
                <label>Error / Detalle:</label>
                <textarea class="form-control" rows="4" readonly>${error}</textarea>
            </div>
            ` : ''}
            ${logs ? `
            <div class="detail-item">
                <label>Logs de Ejecución:</label>
                <textarea class="form-control" rows="10" readonly style="font-family: monospace; font-size: 12px;">${logs}</textarea>
            </div>
            ` : ''}
            <div class="form-actions">
                <button class="btn-secondary" onclick="dashboard.closeModal()">Cerrar</button>
            </div>
        `);
    }

    async retryExecution(id) {
        // Check if retry is already in progress for this ID
        if (this.retryInProgress.has(id)) {
            this.showToast('Ya hay un reintento en progreso para este envío', 'warning');
            return;
        }

        // Add to in-progress set
        this.retryInProgress.add(id);
        
        // Disable the retry button
        this.disableRetryButton(id);
        
        // Update the status to "running" immediately
        this.updateExecutionStatus(id, 'running');
        
        try {
            this.showToast('Iniciando ejecución...', 'info');
            
            // Call the retry API endpoint
            const response = await fetch(`/api/retry-execution/${id}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                
                // Handle the synchronous response
                if (result.status === 'success') {
                    this.showToast(result.message || 'Ejecución completada exitosamente', 'success');
                    this.updateExecutionStatus(id, 'success');
                    // Recargar datos para mostrar la nueva ejecución en la tabla
                    setTimeout(() => this.loadData(), 1000);
                } else if (result.status === 'failed') {
                    this.showToast(result.message || 'La ejecución falló', 'error');
                    this.updateExecutionStatus(id, 'failed');
                    // Para fallos, también recargar para mostrar el nuevo registro de intento fallido
                    setTimeout(() => this.loadData(), 1000);
                } else {
                    this.showToast('Estado de ejecución desconocido', 'warning');
                    this.updateExecutionStatus(id, 'failed');
                    setTimeout(() => this.loadData(), 1000);
                }
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error al reintentar ejecución', 'error');
                // Revert to failed status on error
                this.updateExecutionStatus(id, 'failed');
            }
        } catch (error) {
            this.showToast('Error de conexión al reintentar ejecución', 'error');
            // Revert to failed status on error
            this.updateExecutionStatus(id, 'failed');
        } finally {
            // Remove from in-progress set and re-enable button
            this.retryInProgress.delete(id);
            this.enableRetryButton(id);
        }
    }

    async pollExecutionStatus(id) {
        const maxPolls = 30; // Maximum 30 polls (30 seconds with 1-second intervals)
        let pollCount = 0;
        
        const poll = async () => {
            if (pollCount >= maxPolls) {
                this.showToast('Tiempo de espera agotado para la ejecución', 'warning');
                this.updateExecutionStatus(id, 'failed');
                this.retryInProgress.delete(id);
                this.enableRetryButton(id);
                return;
            }
            
            try {
                const response = await fetch(`/api/execution-status/${id}`);
                
                if (response.ok) {
                    const statusData = await response.json();
                    
                    if (statusData.status === 'success') {
                        this.showToast('Ejecución completada exitosamente', 'success');
                        this.updateExecutionStatus(id, 'success');
                        this.retryInProgress.delete(id);
                        this.enableRetryButton(id);
                        // Solo recargar datos si fue exitoso para mostrar información completa
                        setTimeout(() => this.loadData(), 1000);
                    } else if (statusData.status === 'failed') {
                        this.showToast(statusData.message || 'La ejecución falló', 'error');
                        this.updateExecutionStatus(id, 'failed');
                        this.retryInProgress.delete(id);
                        this.enableRetryButton(id);
                        // NO recargar datos en caso de fallo para mantener la información visible
                    } else if (statusData.status === 'running') {
                        // Still running, continue polling
                        pollCount++;
                        setTimeout(poll, 1000);
                    } else {
                        // Unknown status, continue polling
                        pollCount++;
                        setTimeout(poll, 1000);
                    }
                } else {
                    // Error checking status, continue polling
                    pollCount++;
                    setTimeout(poll, 1000);
                }
            } catch (error) {
                pollCount++;
                setTimeout(poll, 1000);
            }
        };
        
        // Start polling
        setTimeout(poll, 1000);
    }

    updateExecutionStatus(id, status) {
        // Find the envio in the cache
        const envio = this.enviosById ? this.enviosById.get(String(id)) : null;
        if (envio) {
            // Update the status in the cache
            envio.status = status;
            
            // Find the actual row in the DOM and update only the status cell
            const tbody = document.getElementById('envios-tbody');
            const rows = tbody.getElementsByTagName('tr');
            
            for (let row of rows) {
                // Look for the retry button with this specific ID
                const retryButton = row.querySelector(`button[onclick*="retryExecution('${id}')"]`);
                if (retryButton) {
                    // Found the row, now update the status cell (usually index 2)
                    const statusCell = row.cells[2]; // Status column
                    if (statusCell) {
                        statusCell.innerHTML = this.createStatusBadge(status);
                    }
                    break;
                }
            }
        }
    }

    disableRetryButton(id) {
        const retryButtons = document.querySelectorAll(`button[onclick*="retryExecution('${id}')"]`);
        retryButtons.forEach(button => {
            button.disabled = true;
            button.style.opacity = '0.5';
            button.style.cursor = 'not-allowed';
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            button.title = 'Reintentando...';
        });
    }

    enableRetryButton(id) {
        const retryButtons = document.querySelectorAll(`button[onclick*="retryExecution('${id}')"]`);
        retryButtons.forEach(button => {
            button.disabled = false;
            button.style.opacity = '';
            button.style.cursor = '';
            button.innerHTML = '<i class="fas fa-redo"></i>';
            button.title = 'Reintentar';
        });
    }

    async editSchedule(id) {
        try {
            // Block refresh while editing
            this.editingSchedule = true;
            
            // Fetch schedule data
            const response = await fetch(`/api/schedule/${id}`);
            
            if (!response.ok) {
                throw new Error('Error obteniendo datos de la tarea');
            }
            
            const scheduleData = await response.json();
            
            // Create newsletter options
            const newsletterOptions = scheduleData.newsletters.map(nl => 
                '<option value="' + nl.id + '"' + (nl.id === scheduleData.newsletter_id ? ' selected' : '') + '>' + nl.name + '</option>'
            ).join('');
            
            // Build modal HTML without template literals
            const modalContent = '<form id="edit-schedule-form">' +
                '<div class="form-group">' +
                    '<label for="newsletter-select">Nombre del Boletin:</label>' +
                    '<select id="newsletter-select" class="form-control" required>' +
                        newsletterOptions +
                    '</select>' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="time-input">Hora de Ejecucion:</label>' +
                    '<input type="time" id="time-input" class="form-control" value="' + scheduleData.send_time + '" required>' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="timezone-select">Zona Horaria:</label>' +
                    '<select id="timezone-select" class="form-control">' +
                        '<option value="America/Bogota"' + (scheduleData.timezone === 'America/Bogota' ? ' selected' : '') + '>America/Bogota</option>' +
                        '<option value="UTC"' + (scheduleData.timezone === 'UTC' ? ' selected' : '') + '>UTC</option>' +
                    '</select>' +
                '</div>' +
                '<div class="form-group">' +
                    '<label class="checkbox-label">' +
                        '<input type="checkbox" id="enabled-checkbox"' + (scheduleData.is_enabled ? ' checked' : '') + '>' +
                        'Tarea habilitada' +
                    '</label>' +
                '</div>' +
                '<div class="form-actions">' +
                    '<button type="submit" class="btn-primary">' +
                        '<i class="fas fa-save"></i> Guardar Cambios' +
                    '</button>' +
                    '<button type="button" class="btn-secondary" onclick="dashboard.cancelEdit()">' +
                        '<i class="fas fa-times"></i> Cancelar' +
                    '</button>' +
                '</div>' +
            '</form>';
            
            this.showModal('Editar Tarea Programada', modalContent);
            
            // Add form submit handler
            document.getElementById('edit-schedule-form').addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveSchedule(id);
            });
            
        } catch (error) {
            this.showToast('Error cargando datos de la tarea', 'error');
            this.editingSchedule = false; // Unblock on error
        }
    }

    async saveSchedule(id) {
        try {
            // Get form values
            const newsletterId = document.getElementById('newsletter-select').value;
            const sendTime = document.getElementById('time-input').value;
            const timezone = document.getElementById('timezone-select').value;
            const isEnabled = document.getElementById('enabled-checkbox').checked;
            
            // Validate inputs
            if (!newsletterId || !sendTime) {
                this.showToast('Por favor complete todos los campos requeridos', 'error');
                return;
            }
            
            // Send update request
            const response = await fetch(`/api/schedule/${id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    newsletter_id: newsletterId,
                    send_time: sendTime,
                    is_enabled: isEnabled,
                    timezone: timezone
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showToast('Tarea actualizada exitosamente', 'success');
                this.closeModal();
            } else {
                throw new Error(result.message || 'Error actualizando tarea');
            }
            
        } catch (error) {
            this.showToast(`Error: ${error.message}`, 'error');
        } finally {
            // Unblock refresh and reload data
            this.editingSchedule = false;
            this.loadData();
        }
    }

    async toggleSchedule(id) {
        // Obtener información del boletín para mostrar en la confirmación
        const proximo = this.allProximos ? this.allProximos.find(p => p.id === id) : null;
        const boletinNombre = proximo ? proximo.boletin : 'Boletín';
        const estadoActual = proximo ? proximo.estado : 'unknown';
        const nuevoEstado = estadoActual === 'enabled' ? 'deshabilitar' : 'habilitar';
        
        // Mostrar modal de confirmación
        this.showModal('Confirmar Cambio de Estado', `
            <div class="confirmation-message">
                <p>¿Está seguro de que desea <strong>${nuevoEstado}</strong> el boletín <strong>"${boletinNombre}"</strong>?</p>
                <p>Esta acción ${nuevoEstado === 'habilitar' ? 'activará' : 'desactivará'} los envíos automáticos programados.</p>
            </div>
            <div class="form-actions">
                <button class="btn-primary" onclick="dashboard.confirmToggleSchedule('${id}')">
                    <i class="fas fa-${nuevoEstado === 'habilitar' ? 'check' : 'times'}-circle"></i> 
                    Sí, ${nuevoEstado.charAt(0).toUpperCase() + nuevoEstado.slice(1)}
                </button>
                <button class="btn-secondary" onclick="dashboard.closeModal()">
                    <i class="fas fa-times"></i> Cancelar
                </button>
            </div>
        `);
    }

    async confirmToggleSchedule(id) {
        try {
            this.showToast('Actualizando estado...', 'info');
            
            const response = await fetch(`/api/toggle-schedule/${id}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showToast(result.message, 'success');
                this.closeModal();
                this.loadData();
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error actualizando estado', 'error');
                this.closeModal();
            }
        } catch (error) {
            console.error('Error:', error);
            this.showToast('Error de conexión', 'error');
            this.closeModal();
        }
    }

    async deleteSchedule(id) {
        // Obtener información del boletín para mostrar en la confirmación
        const proximo = this.allProximos ? this.allProximos.find(p => p.id === id) : null;
        const boletinNombre = proximo ? proximo.boletin : 'Boletín';
        const horaEjecucion = proximo ? proximo.hora : 'N/A';
        
        // Mostrar modal de confirmación
        this.showModal('Confirmar Eliminación', `
            <div class="confirmation-message">
                <p>¿Está seguro de que desea <strong>eliminar</strong> el boletín <strong>"${boletinNombre}"</strong>?</p>
                <p>Esta acción eliminará permanentemente la tarea programada para las <strong>${horaEjecucion}</strong>.</p>
                <p style="color: var(--error-color); font-weight: 500;">⚠️ Esta acción no se puede deshacer</p>
            </div>
            <div class="form-actions">
                <button class="btn-primary" style="background: var(--error-color);" onclick="dashboard.confirmDeleteSchedule('${id}')">
                    <i class="fas fa-trash"></i> 
                    Sí, Eliminar
                </button>
                <button class="btn-secondary" onclick="dashboard.closeModal()">
                    <i class="fas fa-times"></i> Cancelar
                </button>
            </div>
        `);
    }

    async confirmDeleteSchedule(id) {
        try {
            this.showToast('Eliminando tarea...', 'info');
            
            const response = await fetch(`/api/delete-schedule/${id}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showToast(result.message, 'success');
                this.closeModal();
                this.loadData();
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error eliminando tarea', 'error');
                this.closeModal();
            }
        } catch (error) {
            this.showToast('Error de conexión', 'error');
            this.closeModal();
        }
    }

    showUploadBulletinModal() {
        this.showModal('Cargar Nuevo Boletín', `
            <form id="upload-bulletin-form">
                <div class="form-group">
                    <label for="bulletin-name">Nombre del Boletín:</label>
                    <input type="text" id="bulletin-name" class="form-control" placeholder="Ej: Reporte Diario de Ventas" required>
                </div>
                
                <div class="form-group">
                    <label>Script Python (.py):</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('script')">
                        <i class="fas fa-file-code"></i>
                        <span id="script-file-name">Haz clic para seleccionar el script Python</span>
                    </div>
                    <small class="form-text">El script debe implementar la interfaz ScriptUserInterface</small>
                </div>
                
                <div class="form-group">
                    <label>Archivos de Consulta (.json):</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('query')">
                        <i class="fas fa-file-alt"></i>
                        <span id="query-file-name">Haz clic para seleccionar uno o más archivos JSON</span>
                    </div>
                    <small class="form-text">Puedes seleccionar múltiples archivos query.json</small>
                </div>
                
                <div class="form-group">
                    <label>Plantilla HTML (.html):</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('template')">
                        <i class="fas fa-file-code"></i>
                        <span id="template-file-name">Haz clic para seleccionar la plantilla HTML</span>
                    </div>
                    <small class="form-text">Plantilla para el correo electrónico (opcional)</small>
                </div>
                
                <div class="form-group">
                    <label>Imágenes para el HTML:</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('images')">
                        <i class="fas fa-image"></i>
                        <span id="images-file-name">Haz clic para seleccionar imágenes (PNG, JPG, etc.)</span>
                    </div>
                    <small class="form-text">Puedes seleccionar múltiples imágenes para usar en la plantilla HTML</small>
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="btn-primary">
                        <i class="fas fa-upload"></i> Cargar Boletín
                    </button>
                    <button type="button" class="btn-secondary" onclick="dashboard.closeModal()">
                        <i class="fas fa-times"></i> Cancelar
                    </button>
                </div>
            </form>
        `);
        
        // Agregar event listener al formulario
        document.getElementById('upload-bulletin-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadBulletin();
        });
    }
    
    selectFile(type) {
        const input = document.getElementById(`${type}-input`);
        input.click();
        
        input.onchange = (e) => {
            const files = e.target.files;
            const nameElement = document.getElementById(`${type}-file-name`);
            
            if (files.length === 0) {
                if (type === 'query' || type === 'images') {
                    nameElement.textContent = `Haz clic para seleccionar uno o más archivos`;
                } else {
                    nameElement.textContent = `Haz clic para seleccionar el archivo`;
                }
                return;
            }
            
            if (files.length === 1) {
                nameElement.textContent = `Seleccionado: ${files[0].name}`;
            } else {
                const fileText = type === 'images' ? 'imágenes' : 'archivos';
                nameElement.textContent = `Seleccionados: ${files.length} ${fileText}`;
            }
        };
    }
    
    async uploadBulletin() {
        const bulletinName = document.getElementById('bulletin-name').value.trim();
        const scriptFile = document.getElementById('script-input').files[0];
        const queryFiles = document.getElementById('query-input').files;
        const templateFile = document.getElementById('template-input').files[0];
        const imageFiles = document.getElementById('images-input').files;
        
        // Validaciones
        if (!bulletinName) {
            this.showToast('Por favor ingresa el nombre del boletín', 'error');
            return;
        }
        
        if (!scriptFile) {
            this.showToast('Por favor selecciona el script Python', 'error');
            return;
        }
        
        // Crear FormData
        const formData = new FormData();
        formData.append('bulletin_name', bulletinName);
        formData.append('script_file', scriptFile);
        
        // Agregar archivos de consulta
        for (let i = 0; i < queryFiles.length; i++) {
            formData.append('query_files', queryFiles[i]);
        }
        
        // Agregar plantilla si existe
        if (templateFile) {
            formData.append('template_file', templateFile);
        }
        
        // Agregar imágenes si existen
        for (let i = 0; i < imageFiles.length; i++) {
            formData.append('image_files', imageFiles[i]);
        }
        
        try {
            this.showToast('Cargando boletín...', 'info');
            
            const response = await fetch('/api/upload-bulletin', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showToast('Boletín cargado exitosamente', 'success');
                this.closeModal();
                this.loadData(); // Recargar datos
            } else {
                this.showToast(`Error: ${result.message || 'Error desconocido'}`, 'error');
            }
            
        } catch (error) {
            this.showToast('Error de conexión al cargar el boletín', 'error');
        }
    }

    createSchedule() {
        this.closeModal();
        this.showToast('Tarea creada exitosamente', 'success');
        this.loadData();
    }

    
    saveSettings() {
        try {
            // Obtener valores del formulario
            const emailRemitente = document.getElementById('email-remite').value;
            const piePagina = document.getElementById('pie-pagina').value;
            const logsRetencion = document.getElementById('logs-retencion').value;
            const guardarBackups = document.getElementById('guardar-backups').checked;
            const logsDetallados = document.getElementById('logs-detallados').checked;
            
            // Validar email si se proporciona
            if (emailRemitente && !this.validateEmail(emailRemitente)) {
                this.showToast('El email del remitente no es válido', 'error');
                return;
            }
            
            // Guardar configuración en localStorage
            const config = {
                emailRemitente: emailRemitente,
                piePagina: piePagina,
                logsRetencion: parseInt(logsRetencion),
                guardarBackups: guardarBackups,
                logsDetallados: logsDetallados,
                updatedAt: new Date().toISOString()
            };
            
            localStorage.setItem('dashboard_config', JSON.stringify(config));
            
            // Enviar configuración al servidor (opcional)
            this.saveConfigToServer(config);
            
            this.closeModal();
            this.showToast('Configuración guardada exitosamente', 'success');
            
        } catch (error) {
            this.showToast('Error guardando configuración', 'error');
        }
    }
    
    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    async saveConfigToServer(config) {
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
        } catch (error) {
            // Silenciosamente ignorar errores de conexión al servidor
        }
    }

    // Modal Methods
    showModal(title, content) {
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-body').innerHTML = content;
        document.getElementById('modal-overlay').classList.add('active');
    }

    closeModal() {
        document.getElementById('modal-overlay').classList.remove('active');
        // Unblock refresh when closing modal
        this.editingSchedule = false;
    }
    
    cancelEdit() {
        this.closeModal();
        this.loadData(); // Refresh data after canceling
    }

    // Toast Methods
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        const container = document.getElementById('toast-container');
        container.appendChild(toast);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// Funciones globales para acceso desde HTML
function showUploadBulletinModal() {
    if (window.dashboard) {
        return window.dashboard.showUploadBulletinModal();
    }
}

function selectFile(type) {
    if (window.dashboard) {
        return window.dashboard.selectFile(type);
    }
}

function closeModal() {
    if (window.dashboard) {
        return window.dashboard.closeModal();
    }
}

function clearDateFilter() {
    if (window.dashboard) {
        return window.dashboard.clearDateFilter();
    }
}

function filterTable(tableType, filter) {
    const tbody = document.getElementById(`${tableType}-tbody`);
    const rows = tbody.getElementsByTagName('tr');
    
    Array.from(rows).forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else {
            const statusCell = row.cells[2]; // Status column
            const status = statusCell.textContent.toLowerCase();
            const matches = status.includes(filter) || 
                          (filter === 'success' && status.includes('éxito')) ||
                          (filter === 'failed' && status.includes('fallido'));
            row.style.display = matches ? '' : 'none';
        }
    });
}

// Global wrapper functions for immediate HTML access
function showSettings() {
    if (dashboard) dashboard.showSettings();
}

function closeModal() {
    if (dashboard) dashboard.closeModal();
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    try {
        dashboard = new Dashboard();
        window.dashboard = dashboard;
    } catch (error) {
        // Silenciosamente ignorar errores de inicialización
    }
});

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        to {
            transform: translateX(120%);
            opacity: 0;
        }
    }
    
    .form-group {
        margin-bottom: 1rem;
    }
    
    .form-group label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: 500;
        color: var(--text-primary);
    }
    
    .form-control {
        width: 100%;
        padding: 0.5rem;
        border: 1px solid var(--border-color);
        border-radius: 0.375rem;
        font-size: 0.875rem;
    }
    
    .form-actions {
        display: flex;
        gap: 0.5rem;
        justify-content: flex-end;
        margin-top: 1.5rem;
    }
    
    .btn-primary, .btn-secondary {
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
        font-size: 0.875rem;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border: none;
    }
    
    .btn-primary {
        background: var(--primary-color);
        color: white;
    }
    
    .btn-secondary {
        background: var(--light-bg);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
    }
    
    .btn-action {
        background: none;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        padding: 0.25rem;
        border-radius: 0.25rem;
        margin-right: 0.25rem;
        transition: all 0.2s;
    }
    
    .btn-action:hover {
        background: var(--light-bg);
        color: var(--text-primary);
    }
    
    .detail-item {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid var(--border-color);
    }
    
    .detail-item label {
        font-weight: 500;
        color: var(--text-secondary);
    }
    
    .logs-container {
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid var(--border-color);
        border-radius: 0.375rem;
        padding: 0.5rem;
    }
    
    .log-entry {
        display: flex;
        gap: 0.5rem;
        padding: 0.25rem 0;
        font-family: monospace;
        font-size: 0.75rem;
        border-bottom: 1px solid var(--border-color);
    }
    
    .log-time {
        color: var(--text-secondary);
        min-width: 150px;
    }
    
    .log-level {
        min-width: 60px;
        font-weight: bold;
    }
    
    .log-entry.info .log-level { color: var(--info-color); }
    .log-entry.success .log-level { color: var(--success-color); }
    .log-entry.error .log-level { color: var(--error-color); }
    .log-entry.warning .log-level { color: var(--warning-color); }
    
    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
    }
    
    .checkbox-label input[type="checkbox"] {
        margin: 0;
    }
    
    .confirmation-message {
        text-align: center;
        padding: 1.5rem 0;
    }
    
    .confirmation-message p {
        margin-bottom: 1rem;
        line-height: 1.5;
        color: var(--text-primary);
    }
    
    .confirmation-message p:last-child {
        margin-bottom: 0;
        color: var(--text-secondary);
        font-size: 0.9rem;
    }
    
    .table-controls {
        display: flex;
        align-items: center;
        gap: 1rem;
        flex-wrap: wrap;
    }
    
    .date-filter {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        background: var(--light-bg);
        padding: 0 0.1rem;
        border-radius: 0.375rem;
        border: 1px solid var(--border-color);
    }
    
    .date-filter label {
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--text-secondary);
        white-space: nowrap;
    }
    
    .date-filter input[type="date"] {
        border: none;
        background: transparent;
        color: var(--text-primary);
        font-size: 0.875rem;
        padding: 0.25rem;
        outline: none;
        min-width: 120px;
    }
    
    .date-filter input[type="date"]::-webkit-calendar-picker-indicator {
        cursor: pointer;
        filter: invert(0.5);
    }
    
    .btn-clear-date {
        background: none;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        padding: 0.25rem;
        border-radius: 0.25rem;
        transition: all 0.2s;
    }
    
    .btn-clear-date:hover {
        background: var(--error-color);
        color: white;
    }
    
    @media (max-width: 768px) {
        .table-controls {
            flex-direction: column;
            align-items: stretch;
        }
        
        .date-filter {
            justify-content: space-between;
        }
    }
`;
document.head.appendChild(style);
