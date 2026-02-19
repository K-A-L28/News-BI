// Dashboard JavaScript

let dashboard = null;

// Función global para descargar auditoría - definida al principio para que esté disponible inmediatamente
function downloadAuditLogs() {
    if (window.dashboard && typeof window.dashboard.downloadAuditLogs === 'function') {
        window.dashboard.downloadAuditLogs();
    } else {
        console.error('Dashboard no inicializado');
        alert('Error: El dashboard no está completamente cargado. Por favor espere un momento y reintente.');
    }
}

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
        this.currentUser = null;
        this.checkAuthentication().then(() => {
            this.init();
        });
    }

    async checkAuthentication() {
        try {
            const response = await fetch('/api/auth/me', {
                credentials: 'include'
            });
            if (response.ok) {
                this.currentUser = await response.json();
                this.updateUserInfo();
            } else {
                // Limpiar datos locales si la sesión no es válida
                this.currentUser = null;
                window.location.href = '/';
            }
        } catch (error) {
            console.error('Error verificando autenticación:', error);
            // Limpiar datos locales en caso de error
            this.currentUser = null;
            window.location.href = '/';
        }
    }

    updateUserInfo() {
        const userNameElement = document.getElementById('user-name');
        const userEmailElement = document.getElementById('user-email');
        
        if (userNameElement && this.currentUser) {
            userNameElement.textContent = this.currentUser.full_name;
        }
        if (userEmailElement && this.currentUser) {
            userEmailElement.textContent = this.currentUser.email;
        }
    }

    init() {
        this.setupEventListeners();
        this.updateTime();
        this.loadData();
        this.startAutoRefresh();
        this.loadTestMode(); // Cargar estado del modo prueba
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
            const response = await fetch('/api/stats', {
                credentials: 'include'
            });
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
            const response = await fetch('/api/envios', {
                credentials: 'include'
            });
            return await response.json();
        } catch (error) {
            return [];
        }
    }

    async fetchProximos() {
        try {
            const response = await fetch('/api/proximos', {
                credentials: 'include'
            });
            return await response.json();
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
            <div class="form-group test-mode-section">
                <label class="checkbox-label">
                    <input type="checkbox" id="test-mode-checkbox" onchange="dashboard.toggleTestMode()">
                    <span class="checkmark"></span>
                    Modo Prueba
                </label>
                <small class="form-text" style="color: var(--test-color); font-weight: 500;">
                    <i class="fas fa-flask"></i> 
                    Al activar el modo prueba, todos los correos se enviarán únicamente a: k.acevedo@clinicassanrafael.com
                </small>
            </div>
            
            <div class="form-group">
                <label>Dominios Permitidos:</label>
                <input type="text" id="allowed-domains" class="form-control" placeholder="gmail.com,empresa.com,hotmail.com" value="">
                <small class="form-text">Dominios permitidos para correos electrónicos (separados por coma). Si no especificas, se permitirán todos los dominios.</small>
            </div>
            
            <div class="form-group">
                <label>Remitente de Correos:</label>
                <input type="email" id="email-remite" class="form-control" placeholder="noreply@empresa.com" value="">
                <small class="form-text">Dirección de correo que aparecerá como remitente de todos los boletines</small>
            </div>
            
            <div class="form-group">
                <label>Limite por lista de correos:</label>
                <input type="number" id="limite-correos" class="form-control" placeholder="100" min="1" value="">
                <small class="form-text">Número máximo de correos que se enviarán por lista de correos</small>
            </div>
            
            <div class="form-group">
                <label>Pie de Página:</label>
                <textarea id="pie-pagina" class="form-control" rows="3" placeholder="© 2026 Empresa S.A. Todos los derechos reservados."></textarea>
                <small class="form-text">Texto que aparecerá al final de cada boletín</small>
            </div>
            
            <div class="credentials-section">
                <div style="position: relative; display: inline-block; width: 100%;">
                    <button class="btn-credentials" onclick="dashboard.showCredentialsModal()">
                        <i class="fas fa-key"></i> 
                        <span>Gestionar Credenciales</span>
                    </button>
                </div>
                <small class="form-text">
                    <i class="fas fa-lock"></i> Acceso seguro a variables de entorno y API keys del sistema
                </small>
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
            // Cargar configuración desde el servidor
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
                if (settings.limiteCorreos) {
                    document.getElementById('limite-correos').value = settings.limiteCorreos;
                }
                if (settings.is_test_mode !== undefined) {
                    document.getElementById('test-mode-checkbox').checked = settings.is_test_mode;
                }
                
                // Cargar dominios permitidos
                try {
                    const domainsResponse = await fetch('/api/config/allowed-domains');
                    if (domainsResponse.ok) {
                        const domainsData = await domainsResponse.json();
                        if (domainsData.allowed_domains) {
                            document.getElementById('allowed-domains').value = domainsData.allowed_domains;
                        }
                    }
                } catch (error) {
                    this.showToast('Error cargando dominios permitidos', 'error');
                }
            } else {
                this.showToast('Error cargando configuración desde servidor', 'error');
            }
            
        } catch (error) {
            this.showToast('Error cargando configuración', 'error');
        }
    }

    async loadTestMode() {
        try {
            const response = await fetch('/api/test-mode');
            
            if (response.ok) {
                const data = await response.json();
                this.updateTestModeIndicator(data.is_test_mode);
            } else {
                this.showToast('Error cargando modo prueba', 'error');
            }
        } catch (error) {
            this.showToast('Error cargando modo prueba', 'error');
        }
    }

    updateTestModeIndicator(isTestMode) {
        const indicator = document.getElementById('test-mode-indicator');
        if (isTestMode) {
            indicator.style.display = 'flex';
        } else {
            indicator.style.display = 'none';
        }
    }

    async toggleTestMode() {
        try {
            const checkbox = document.getElementById('test-mode-checkbox');
            const newTestMode = checkbox.checked;
            
            const response = await fetch('/api/test-mode', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    is_test_mode: newTestMode
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                this.updateTestModeIndicator(newTestMode);
                this.showToast(result.message, 'success');
                
                if (newTestMode) {
                } else {
                }
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error cambiando modo prueba', 'error');
                // Revertir checkbox si hubo error
                checkbox.checked = !newTestMode;
            }
        } catch (error) {
            this.showToast('Error cambiando modo prueba', 'error');
            // Revertir checkbox si hubo error
            const checkbox = document.getElementById('test-mode-checkbox');
            checkbox.checked = !checkbox.checked;
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
                <textarea class="form-control" rows="10" readonly style="font-family: monospace; font-size: 1.2rem;">${logs}</textarea>
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
            
            // Create email list options
            const emailListOptions = scheduleData.emailLists && scheduleData.emailLists.length > 0 ? scheduleData.emailLists.map(list => 
                '<option value="' + list.list_id + '"' + (list.list_id === scheduleData.email_list_id ? ' selected' : '') + '>' + list.list_name + ' (' + list.email_count + ' correos)</option>'
            ).join('') : '<option value="">No hay listas disponibles</option>';
            
            // Build modal HTML without template literals
            const modalContent = '<form id="edit-schedule-form" enctype="multipart/form-data">' +
                '<div class="form-group">' +
                    '<label for="newsletter-select">Nombre del Boletin:</label>' +
                    '<select id="newsletter-select" class="form-control" required>' +
                        newsletterOptions +
                    '</select>' +
                '</div>' +
                '<div class="form-group">' +
                    '<label for="email-list-select">Lista de Destinatarios:</label>' +
                    '<select id="email-list-select" class="form-control">' +
                        '<option value="">Selecciona una lista...</option>' +
                        emailListOptions +
                    '</select>' +
                    '<small class="form-text">Lista actual: ' + (scheduleData.current_email_list || 'No asignada') + '</small>' +
                    '<small class="form-text">Selecciona una lista para cambiar los destinatarios (opcional)</small>' +
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
                    '<label>Nueva Plantilla de Correo (.html):</label>' +
                    '<div class="file-upload-area" onclick="dashboard.selectEditFile(\'email-template\')">' +
                        '<i class="fas fa-envelope"></i>' +
                        '<span id="edit-email-template-file-name">Haz clic para seleccionar nueva plantilla (opcional)</span>' +
                    '</div>' +
                    '<small class="form-text">Plantilla actual: ' + (scheduleData.current_template || 'No asignada') + '</small>' +
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
            const emailListId = document.getElementById('email-list-select').value;
            const sendTime = document.getElementById('time-input').value;
            const timezone = document.getElementById('timezone-select').value;
            const isEnabled = document.getElementById('enabled-checkbox').checked;
            
            // Validate inputs
            if (!newsletterId || !sendTime) {
                this.showToast('Por favor completa todos los campos requeridos', 'error');
                return;
            }
            
            // Create FormData for file upload
            const formData = new FormData();
            formData.append('newsletter_id', newsletterId);
            formData.append('email_list_id', emailListId);
            formData.append('send_time', sendTime);
            formData.append('timezone', timezone);
            formData.append('is_enabled', isEnabled);
            
            // Add files if they were selected
            
            if (this.editFiles && this.editFiles['email-template']) {
                formData.append('email_template', this.editFiles['email-template']);
            }
            
            if (this.editFiles && this.editFiles['email-csv']) {
                formData.append('email_csv', this.editFiles['email-csv']);
            }
            
            // Send update request
            const response = await fetch(`/api/schedule/${id}`, {
                method: 'PUT',
                body: formData
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
            // Clear edit files
            this.editFiles = {};
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
                <p>Esta acción eliminará permanentemente el boletín y todas sus tareas programadas.</p>
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
                    <label for="email-list-select">Lista de Correos:</label>
                    <select id="email-list-select" class="form-control" required>
                        <option value="" disabled selected>Selecciona una lista de correos...</option>
                    </select>
                    <small class="form-text">Selecciona la lista % de correos a la que se enviará este boletín</small>
                </div>

                <div class="form-group">
                    <label>Plantilla HTML del Correo (.html):</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('email-template')">
                        <i class="fas fa-envelope"></i>
                        <span id="email-template-file-name">Haz clic para seleccionar la plantilla HTML del correo</span>
                    </div>
                    <small class="form-text">Plantilla para el cuerpo del correo electrónico "asunto y mensaje" (opcional)</small>
                </div>
                
                <div class="form-group">
                    <label>Script Python (.py): <span class="text-danger">*</span></label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('script')">
                        <i class="fas fa-file-code"></i>
                        <span id="script-file-name">Haz clic para seleccionar el script Python</span>
                    </div>
                    <small class="form-text">El script debe implementar la lógica de extracción de datos y envio de correo (obligatorio)</small>
                </div>
                
                <div class="form-group">
                    <label>Archivos de Consulta (.json):</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('query')">
                        <i class="fas fa-file-alt"></i>
                        <span id="query-file-name">Haz clic para seleccionar uno o más archivos JSON</span>
                    </div>
                    <small class="form-text">Puedes seleccionar múltiples archivos query.json (opcional)</small>
                </div>
                
                <div class="form-group">
                    <label>Plantilla HTML (.html): <span class="text-danger">*</span></label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('template')">
                        <i class="fas fa-file-code"></i>
                        <span id="template-file-name">Haz clic para seleccionar la plantilla HTML</span>
                    </div>
                    <small class="form-text">Plantilla para el contenido del boletín (obligatorio)</small>
                </div>
                
                <div class="form-group">
                    <label>Imágenes para el HTML:</label>
                    <div class="file-upload-area" onclick="dashboard.selectFile('images')">
                        <i class="fas fa-image"></i>
                        <span id="images-file-name">Haz clic para seleccionar imágenes (PNG, JPG, etc.)</span>
                    </div>
                    <small class="form-text">Puedes seleccionar múltiples imágenes para usar en la plantilla HTML (opcional)</small>
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
        
        // Cargar listas de correos en el select
        this.loadEmailListsForBulletin();
        
        // Agregar event listener al formulario
        document.getElementById('upload-bulletin-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadBulletin();
        });
    }
    
    loadEmailListsForBulletin() {
        fetch('/api/email-lists')
            .then(response => response.json())
            .then(lists => {
                const select = document.getElementById('email-list-select');
                if (select) {
                    select.innerHTML = '<option value="">Selecciona una lista de correos...</option>';
                    lists.forEach(list => {
                        const option = document.createElement('option');
                        option.value = list.list_id;
                        option.textContent = `${list.list_name} (${list.email_count} correos)`;
                        select.appendChild(option);
                    });
                }
            })
            .catch(error => {
                const select = document.getElementById('email-list-select');
                if (select) {
                    select.innerHTML = '<option value="">Error cargando listas</option>';
                }
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
    
    selectEditFile(type) {
        
        // Create a temporary file input for edit modal
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = type === 'email-template' ? '.html,.htm' : '.csv';
        input.style.display = 'none';
        
        input.onchange = (e) => {
            const files = e.target.files;
            const nameElement = document.getElementById(`edit-${type}-file-name`);
            
            if (files.length > 0) {
            }
            
            if (files.length === 0) {
                nameElement.textContent = `Haz clic para seleccionar nuevo archivo (opcional)`;
                return;
            }
            
            nameElement.textContent = `Seleccionado: ${files[0].name}`;
            // Store the file reference for later upload
            this.editFiles = this.editFiles || {};
            this.editFiles[type] = files[0];
            
        };
        
        document.body.appendChild(input);
        input.click();
        document.body.removeChild(input);
    }
    
    async uploadBulletin() {
        const bulletinName = document.getElementById('bulletin-name').value.trim();
        const emailListId = document.getElementById('email-list-select').value;
        const scriptFile = document.getElementById('script-input').files[0];
        const queryFiles = document.getElementById('query-input').files;
        const templateFile = document.getElementById('template-input').files[0];
        const emailTemplateFile = document.getElementById('email-template-input').files[0];
        const imageFiles = document.getElementById('images-input').files;
        
        // Validaciones
        if (!bulletinName) {
            this.showToast('Por favor ingresa el nombre del boletín', 'error');
            return;
        }
        
        if (!emailListId || emailListId === '') {
            this.showToast('Por favor selecciona una lista de correos (es requerido)', 'error');
            return;
        }
        
        if (!scriptFile) {
            this.showToast('Por favor selecciona el script Python (obligatorio)', 'error');
            return;
        }
        
        if (!templateFile) {
            this.showToast('Por favor selecciona la plantilla HTML del boletín (obligatorio)', 'error');
            return;
        }
        
        // Validar que el nombre del boletín no exista
        try {
            this.showToast('Verificando disponibilidad del nombre...', 'info');
            
            // Obtener la lista de newsletters actuales
            const response = await fetch('/api/newsletters');
            if (!response.ok) {
                throw new Error('Error obteniendo lista de boletines');
            }
            
            const newsletters = await response.json();
            
            // Verificar si ya existe un boletín con ese nombre (case-insensitive)
            const existingNewsletter = newsletters.find(nl => 
                nl.name.toLowerCase() === bulletinName.toLowerCase()
            );
            
            if (existingNewsletter) {
                this.showToast(`Ya existe un boletín con el nombre "${bulletinName}". Por favor usa un nombre diferente.`, 'error');
                return;
            }
            
        } catch (error) {
            this.showToast('Error verificando disponibilidad del nombre. Intenta de nuevo.', 'error');
            return;
        }
        
        // Crear FormData
        const formData = new FormData();
        formData.append('bulletin_name', bulletinName);
        formData.append('email_list_id', emailListId);
        formData.append('script_file', scriptFile);
        
        // Agregar archivos de consulta
        for (let i = 0; i < queryFiles.length; i++) {
            formData.append('query_files', queryFiles[i]);
        }
        
        // Agregar plantilla si existe
        if (templateFile) {
            formData.append('template_file', templateFile);
        }
        
        // Agregar plantilla de correo si existe
        if (emailTemplateFile) {
            formData.append('email_template_file', emailTemplateFile);
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
                // Mostrar el error específico del servidor
                const errorMessage = result.error || result.message || result.detail || 'Error desconocido';
                this.showToast(`Error: ${errorMessage}`, 'error');
            }
            
        } catch (error) {
            this.showToast('Error de conexión al cargar boletín', 'error');
        }
    }
    
    selectEditFile(type) {
        // Create a temporary file input for edit modal
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = type === 'email-template' ? '.html,.htm' : '.csv';
        input.style.display = 'none';
        
        input.onchange = (e) => {
            const files = e.target.files;
            const nameElement = document.getElementById(`edit-${type}-file-name`);
            
            if (files.length === 0) {
                nameElement.textContent = `Haz clic para seleccionar nuevo archivo (opcional)`;
                return;
            }
            
            nameElement.textContent = `Seleccionado: ${files[0].name}`;
            // Store the file reference for later upload
            this.editFiles = this.editFiles || {};
            this.editFiles[type] = files[0];
        };
        
        document.body.appendChild(input);
        input.click();
        document.body.removeChild(input);
    }
    
    async saveSettings() {
        try {
            // Obtener valores del formulario
            const emailRemitente = document.getElementById('email-remite').value;
            const piePagina = document.getElementById('pie-pagina').value;
            const limiteCorreos = document.getElementById('limite-correos').value;
            const allowedDomains = document.getElementById('allowed-domains').value;
            
            // Validar email si se proporciona
            if (emailRemitente && !this.validateEmail(emailRemitente)) {
                this.showToast('El email del remitente no es válido', 'error');
                return;
            }
            
            // Validar límite de correos si se proporciona
            if (limiteCorreos && (isNaN(limiteCorreos) || parseInt(limiteCorreos) < 1)) {
                this.showToast('El límite de correos debe ser un número mayor a 0', 'error');
                return;
            }
            
            // Preparar configuración para enviar al servidor
            const config = {
                emailRemitente: emailRemitente,
                piePagina: piePagina,
                limiteCorreos: parseInt(limiteCorreos) || null
            };
            
            // Enviar configuración general al servidor
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    // Guardar dominios permitidos por separado
                    try {
                        const domainsResponse = await fetch('/api/config/allowed-domains', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ allowed_domains: allowedDomains })
                        });
                        
                        if (domainsResponse.ok) {
                            const domainsResult = await domainsResponse.json();
                            if (domainsResult.success) {
                                this.closeModal();
                                this.showToast('Configuración guardada exitosamente', 'success');
                            } else {
                                this.showToast('Error guardando dominios permitidos', 'error');
                            }
                        } else {
                            this.showToast('Error guardando dominios permitidos', 'error');
                        }
                    } catch (error) {
                        this.showToast('Error guardando dominios permitidos', 'error');
                    }
                } else {
                    this.showToast(result.message || 'Error guardando configuración', 'error');
                }
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error guardando configuración', 'error');
            }
            
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
    
    async getConfiguration() {
        try {
            // Cargar configuración desde el servidor
            const response = await fetch('/api/settings');
            
            if (response.ok) {
                const settings = await response.json();
                return settings;
            } else {
                // Retornar configuración por defecto si hay error
                return {
                    limiteCorreos: 100 // Valor por defecto
                };
            }
        } catch (error) {
            // Retornar configuración por defecto si hay error
            return {
                limiteCorreos: 100 // Valor por defecto
            };
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
    showToast(message, type = 'info', duration = 5000) {
        // Eliminar todos los toast existentes antes de mostrar uno nuevo
        const container = document.getElementById('toast-container');
        const existingToasts = container.querySelectorAll('.toast');
        existingToasts.forEach(toast => toast.remove());
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        // Auto remove después del tiempo especificado (default 5 segundos)
        setTimeout(() => {
            toast.remove();
        }, duration);
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

function logout() {
    // Eliminar cualquier dato local del usuario
    if (window.dashboard) {
        window.dashboard.currentUser = null;
    }
    
    // Limpiar completamente el almacenamiento del navegador
    try {
        // Limpiar sessionStorage
        sessionStorage.clear();
        
        // Limpiar localStorage (solo si hay datos de la app)
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.includes('user') || key.includes('auth') || key.includes('session') || key.includes('dashboard'))) {
                keysToRemove.push(key);
            }
        }
        keysToRemove.forEach(key => localStorage.removeItem(key));
        
        // Limpiar caché del navegador
        if ('caches' in window) {
            caches.keys().then(names => {
                names.forEach(name => {
                    if (name.includes('auth') || name.includes('user') || name.includes('dashboard')) {
                        caches.delete(name);
                    }
                });
            });
        }
    } catch (error) {
        console.warn('Error limpiando almacenamiento:', error);
    }
    
    // Forzar redirección inmediata al logout del servidor
    window.location.href = '/auth/logout';
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
        margin-bottom: 0.8rem;
        font-weight: 500;
        color: var(--text-primary);
        font-size: 1.6rem;
    }
    
    .form-control {
        width: 100%;
        padding: 0.8rem 1.2rem;
        border: 1px solid var(--border-color);
        border-radius: 0.375rem;
        font-size: 1.6rem;
    }
    
    .form-actions {
        display: flex;
        gap: 0.5rem;
        justify-content: flex-end;
        margin-top: 1.8rem;
    }
    
    .btn-primary, .btn-secondary {
        padding: 0.8rem 1.6rem;
        border-radius: 0.375rem;
        font-size: 1.6rem;
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
        font-size: 1.4rem;
    }
    
    .logs-container {
        max-height: 30rem;
        overflow-y: auto;
        border: 1px solid var(--border-color);
        border-radius: 0.375rem;
        padding: 0.5rem;
    }
    
    .log-entry {
        display: flex;
        gap: 0.5rem;
        padding: 0.4rem 0;
        font-family: monospace;
        font-size: 1.2rem;
        border-bottom: 1px solid var(--border-color);
    }
    
    .log-time {
        color: var(--text-secondary);
        min-width: 15rem;
    }
    
    .log-level {
        min-width: 6rem;
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
        margin-right: 0.5rem;
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
        font-size: 1.3rem;
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
        font-size: 1.4rem;
        font-weight: 500;
        color: var(--text-secondary);
        white-space: nowrap;
    }
    
    .date-filter input[type="date"] {
        border: none;
        background: transparent;
        color: var(--text-primary);
        font-size: 1.4rem;
        padding: 0.4rem;
        outline: none;
        min-width: 12rem;
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
    }`;
document.head.appendChild(style);

function showEmailListManager() {
    loadEmailLists();
    
    const modal = document.getElementById('email-list-modal');
    
    if (!modal) {
        return;
    }
    
    modal.style.display = 'block';
}

function closeEmailListModal() {
    document.getElementById('email-list-modal').style.display = 'none';
}

async function uploadEmailList() {
    const listName = document.getElementById('email-list-name').value;
    const descriptionElement = document.getElementById('email-list-description');
    const description = descriptionElement ? descriptionElement.value : '';
    const csvFile = document.getElementById('email-csv-file').files[0];
    
    if (!listName || !csvFile) {
        dashboard.showToast('Por favor complete todos los campos obligatorios', 'error');
        return;
    }
    
    try {
        // Validar que el archivo sea un CSV
        if (!csvFile.name.toLowerCase().endsWith('.csv')) {
            dashboard.showToast('Por favor selecciona un archivo CSV válido', 'error');
            return;
        }
        
        // Leer archivo CSV
        const csvText = await csvFile.text();
        
        if (!csvText || csvText.trim().length === 0) {
            dashboard.showToast('El archivo CSV está vacío', 'error');
            return;
        }
        
        
        const emails = parseCSV(csvText);
        
        
        if (emails.length === 0) {
            dashboard.showToast('No se encontraron correos válidos en el CSV. Verifica el formato del archivo.', 'error');
            return;
        }
        
        // Obtener límite global desde configuraciones
        let maxRecipients = 100; // valor por defecto
        try {
            const configResponse = await fetch('/api/settings');
            if (configResponse.ok) {
                const config = await configResponse.json();
                if (config.limiteCorreos && !isNaN(config.limiteCorreos)) {
                    maxRecipients = parseInt(config.limiteCorreos);
                }
            }
        } catch (error) {
            // No se pudo obtener el límite de correos, usando valor por defecto
        }
        
        // Validar límite de correos global
        if (emails.length > maxRecipients) {
            dashboard.showToast(
                `El archivo CSV contiene ${emails.length} correos, pero el límite global es de ${maxRecipients} correos por lista.`, 
                'error'
            );
            return;
        }
        
        // Crear la lista sin max_recipients (ahora es global)
        const response = await fetch('/api/email-lists', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                list_name: listName,
                description: description,
                max_recipients: maxRecipients, // Guardar para referencia, pero no se usa en validación
                emails: emails
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Construir mensaje completo
            let message = result.message;
            
            // Mostrar un solo mensaje con toda la información
            dashboard.showToast(message, result.domain_rejected > 0 ? 'warning' : 'success', 8000);
            
            // Limpiar formulario
            document.getElementById('email-list-name').value = '';
            document.getElementById('email-list-description').value = '';
            document.getElementById('email-csv-file').value = '';
            
            // Recargar listas
            loadEmailLists();
        } else {
            const error = await response.json();
            dashboard.showToast(error.detail || 'Error creando lista de correos', 'error');
        }
        
    } catch (error) {
        dashboard.showToast(`Error procesando el archivo CSV: ${error.message}`, 'error');
    }
}

function parseCSV(csvText) {
    const lines = csvText.split('\n').filter(line => line.trim());
    
    const emails = [];
    
    
    // Procesar todas las líneas (excepto posible encabezado)
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line) {
            // Omitir primera línea si parece un encabezado
            if (i === 0 && (line.toLowerCase().includes('email') || line.toLowerCase().includes('correo') || line.toLowerCase().includes('mail'))) {
                continue;
            }
            
            // Dividir por comas o punto y coma
            const columns = line.split(/[,\;]/).map(col => col.trim().replace(/"/g, ''));
            
            // Buscar email en cada columna
            for (const column of columns) {
                if (column) {
                    // Detectar correos en la columna
                    const emailMatch = column.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
                    if (emailMatch) {
                        emails.push(emailMatch[1]);
                        break; // Solo tomar el primer email de la línea
                    }
                }
            }
        }
    }
    
    const uniqueEmails = [...new Set(emails)];
    
    return uniqueEmails;
}

async function loadEmailLists() {
    try {
        const response = await fetch('/api/email-lists');
        const result = await response.json();
        
        const container = document.getElementById('email-lists-container');
        
        if (!result || !Array.isArray(result)) {
            container.innerHTML = '<p class="error">Error cargando las listas de correos</p>';
            return;
        }
        
        if (result.length === 0) {
            container.innerHTML = '<p class="no-data">No hay listas creadas</p>';
            return;
        }
        
        container.innerHTML = result.map(list => `
            <div class="list-item">
                <div class="list-info">
                    <h4>${list.list_name}</h4>
                    <p>${list.description || 'Sin descripción'}</p>
                    <small class="list-meta">
                        <i class="fas fa-envelope"></i> ${list.email_count} correos
                        <i class="fas fa-calendar"></i> ${new Date(list.created_at).toLocaleDateString()}
                        <i class="fas fa-shield-alt"></i> Límite: ${list.max_recipients}
                    </small>
                </div>
                <div class="list-actions">
                    <button class="btn-sm danger" onclick="deleteEmailList('${list.list_id}', '${list.list_name}')">
                        <i class="fas fa-trash"></i> Eliminar
                    </button>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        document.getElementById('email-lists-container').innerHTML = 
            '<p class="error">Error cargando las listas de correos</p>';
    }
}

async function deleteEmailList(listId, listName) {
    if (!confirm(`¿Está seguro de eliminar la lista "${listName}"? Esta acción no se puede deshacer.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/email-lists/${listId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            dashboard.showToast(`Lista "${listName}" eliminada exitosamente`, 'success');
            loadEmailLists();
        } else {
            dashboard.showToast(result.detail || 'Error eliminando la lista', 'error');
        }
        
    } catch (error) {
        dashboard.showToast('Error eliminando la lista', 'error');
    }
}

// Método para mostrar modal de credenciales
Dashboard.prototype.showCredentialsModal = async function() {
    try {
        // Mostrar indicador de carga
        this.showModal('Credenciales del Sistema', `
            <div class="loading-credentials">
                <i class="fas fa-spinner fa-spin"></i> Cargando credenciales...
            </div>
        `);
        
        // Obtener credenciales completas (sin ocultar)
        const response = await fetch('/api/credentials/raw');
        
        if (!response.ok) {
            throw new Error('Error cargando credenciales');
        }
        
        const data = await response.json();
        const credentials = data.credentials;
        
        // Generar formulario de credenciales con orden específico
        let credentialsForm = '<div class="credentials-form">';
        
        // Orden específico para las credenciales
        const credentialOrder = [
            'TENANT_ID',
            'CLIENT_ID', 
            'CLIENT_SECRET',
            'GEMINI_API_KEY'
        ];
        
        // Primero agregar las credenciales en el orden específico
        for (const key of credentialOrder) {
            if (credentials.hasOwnProperty(key)) {
                const value = credentials[key];
                const isSensitive = key.toUpperCase().includes('PASSWORD') || 
                                  key.toUpperCase().includes('SECRET') || 
                                  key.toUpperCase().includes('KEY') || 
                                  key.toUpperCase().includes('TOKEN');
                
                credentialsForm += `
                    <div class="form-group">
                        <label for="cred-${key}">${key}:</label>
                        <div class="input-group">
                            <input type="${isSensitive ? 'password' : 'text'}" 
                                   id="cred-${key}" 
                                   class="form-control credential-input" 
                                   data-key="${key}"
                                   value="${this.escapeHtml(value)}"
                                   placeholder="Ingrese ${key}">
                            ${isSensitive ? `
                                <button type="button" class="btn-toggle-password" onclick="dashboard.togglePasswordVisibility('cred-${key}')">
                                    <i class="fas fa-eye"></i>
                                </button>
                            ` : ''}
                        </div>
                        <small class="form-text">
                            ${isSensitive ? 
                                '<i class="fas fa-lock"></i> Información sensible - mantener segura' : 
                                '<i class="fas fa-info-circle"></i> Variable de configuración'}
                        </small>
                    </div>
                `;
            }
        }
        
        // Luego agregar cualquier otra credencial que no esté en el orden específico
        for (const [key, value] of Object.entries(credentials)) {
            if (!credentialOrder.includes(key)) {
                const isSensitive = key.toUpperCase().includes('PASSWORD') || 
                                  key.toUpperCase().includes('SECRET') || 
                                  key.toUpperCase().includes('KEY') || 
                                  key.toUpperCase().includes('TOKEN');
                
                credentialsForm += `
                    <div class="form-group">
                        <label for="cred-${key}">${key}:</label>
                        <div class="input-group">
                            <input type="${isSensitive ? 'password' : 'text'}" 
                                   id="cred-${key}" 
                                   class="form-control credential-input" 
                                   data-key="${key}"
                                   value="${this.escapeHtml(value)}"
                                   placeholder="Ingrese ${key}">
                            ${isSensitive ? `
                                <button type="button" class="btn-toggle-password" onclick="dashboard.togglePasswordVisibility('cred-${key}')">
                                    <i class="fas fa-eye"></i>
                                </button>
                            ` : ''}
                        </div>
                        <small class="form-text">
                            ${isSensitive ? 
                                '<i class="fas fa-lock"></i> Información sensible - mantener segura' : 
                                '<i class="fas fa-info-circle"></i> Variable de configuración'}
                        </small>
                    </div>
                `;
            }
        }
        
        credentialsForm += `
            </div>
            
            <div class="form-actions">
                <button class="btn-primary" onclick="dashboard.saveCredentials()">
                    <i class="fas fa-save"></i> Guardar y Encriptar
                </button>
                <button class="btn-secondary" onclick="dashboard.closeModal()">Cancelar</button>
            </div>
            
            <div class="security-notice">
                <i class="fas fa-shield-alt"></i>
                <strong>Nota de seguridad:</strong> Las credenciales se guardan de forma segura y no son visibles para otros usuarios.
            </div>
        `;
        
        // Actualizar modal con el formulario
        this.showModal('Credenciales del Sistema', credentialsForm);
        
        // Agregar evento para detectar cambios
        const inputs = document.querySelectorAll('.credential-input');
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                this.markCredentialsAsChanged();
            });
        });
        
        this.credentialsChanged = false;
        
    } catch (error) {
        console.error('Error mostrando modal de credenciales:', error);
        this.showToast('Error cargando credenciales', 'error');
        this.closeModal();
    }
};

// Método para alternar visibilidad de contraseñas
Dashboard.prototype.togglePasswordVisibility = function(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    const icon = button.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
};

// Método para marcar credenciales como modificadas
Dashboard.prototype.markCredentialsAsChanged = function() {
    this.credentialsChanged = true;
};

// Método para guardar credenciales
Dashboard.prototype.saveCredentials = async function() {
    try {
        if (!this.credentialsChanged) {
            this.showToast('No hay cambios para guardar', 'info');
            return;
        }
        
        // Recopilar todas las credenciales del formulario
        const credentials = {};
        const inputs = document.querySelectorAll('.credential-input');
        
        inputs.forEach(input => {
            const key = input.dataset.key;
            const value = input.value;
            credentials[key] = value;
        });
        
        // Mostrar confirmación
        if (!confirm('¿Está seguro de guardar las credenciales? El archivo .env será encriptado.')) {
            return;
        }
        
        // Enviar al servidor
        const response = await fetch('/api/credentials', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                credentials: credentials
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            this.showToast(result.message || 'Credenciales guardadas exitosamente', 'success');
            this.closeModal();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Error guardando credenciales');
        }
        
    } catch (error) {
        console.error('Error guardando credenciales:', error);
        this.showToast(error.message || 'Error guardando credenciales', 'error');
    }
};

// Método para escapar HTML
Dashboard.prototype.escapeHtml = function(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

// Método para descargar registros de auditoría
Dashboard.prototype.downloadAuditLogs = async function() {
    try {
        // Mostrar indicador de carga
        this.showToast('Preparando descarga de auditoría...', 'info');
        
        // Realizar la petición para descargar el CSV
        const response = await fetch('/api/audit/download', {
            method: 'GET',
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error descargando registros de auditoría');
        }
        
        // Obtener el nombre del archivo desde los headers
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'audit_logs.csv';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }
        
        // Convertir la respuesta a blob y descargar
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        
        // Crear un enlace temporal para la descarga
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        // Limpiar
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        this.showToast('Archivo de auditoría descargado exitosamente', 'success');
        
    } catch (error) {
        console.error('Error descargando auditoría:', error);
        this.showToast(error.message || 'Error descargando registros de auditoría', 'error');
    }
};
