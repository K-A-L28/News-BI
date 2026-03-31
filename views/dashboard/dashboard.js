// Dashboard JavaScript

let dashboard = null;

// Variables globales para gestión de usuarios
let allUsers = [];
let currentPage = 1;
let usersPerPage = 6;
let filteredUsers = [];
let currentStatusFilter = 'all'; // 'all', 'active', 'inactive'

// Función global para manejar el registro de usuarios
function handleUserRegistrationClick() {
    // Limpiar el formulario antes de mostrar el modal
    const form = document.getElementById('user-registration-form');
    if (form) {
        form.reset();
        
        // Limpiar campo oculto de ID si existe
        const userIdField = document.getElementById('user-id');
        if (userIdField) {
            userIdField.remove();
        }
        
        // Restaurar atributos del campo de correo para modo de registro
        const emailField = document.getElementById('user-email');
        if (emailField) {
            emailField.readOnly = false;
            emailField.style.backgroundColor = '';
            emailField.style.cursor = '';
            emailField.setAttribute('required', 'required');
        }
        
        // Restaurar título del modal
        const modalTitle = document.querySelector('#user-registration-modal .modal-header h2');
        if (modalTitle) {
            modalTitle.innerHTML = '<i class="fas fa-user-plus"></i> Registrar Nuevo Usuario';
        }
        
        // Restaurar texto del botón de submit
        const submitBtn = document.querySelector('#user-registration-form button[type="submit"]');
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fas fa-save"></i> Registrar Usuario';
        }
    }
    
    if (typeof showUserRegistration === 'function') {
        showUserRegistration();
    } else {
        // Método alternativo si la función no está cargada
        const modal = document.getElementById('user-registration-modal');
        if (modal) {
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        } else {
            console.error('Modal de registro de usuario no encontrado');
            alert('Error: No se pudo abrir el formulario de registro de usuario');
        }
    }
}

// Interceptor global para manejar sesiones expiradas
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    try {
        const response = await originalFetch.apply(this, args);
        
        // Si la respuesta es 401, limpiar cookie y redirigir al login
        if (response.status === 401) {
            // Limpiar datos de usuario
            if (window.dashboard) {
                window.dashboard.currentUser = null;
            }
            // Limpiar cookie de sesión
            document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
            // Redirigir al login
            window.location.href = '/';
            return response;
        }
        
        return response;
    } catch (error) {
        return Promise.reject(error);
    }
};

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
        this.currentPage = 'dashboard';
        this.editingSchedule = false; // Flag to block refresh when editing
        this.retryInProgress = new Set(); // Track which retries are in progress
        this.currentUser = null;
        this.modalStack = []; // Stack to manage multiple modals
        this.savedFormState = null; // Save form state when viewing examples
        this.originalFormHTML = null; // Store original form HTML
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
            // Combinar nombres y apellidos para mostrar el nombre completo
            const fullName = `${this.currentUser.nombres || ''} ${this.currentUser.apellidos || ''}`.trim();
            userNameElement.textContent = fullName || 'Usuario';
        }
        if (userEmailElement && this.currentUser) {
            userEmailElement.textContent = this.currentUser.email;
        }
        
        // Actualizar visibilidad de elementos solo para administradores
        this.updateAdminUI();
    }

    isAdmin() {
        // Verificar si el usuario es administrador o desarrollador (ambos son "admin" para la mayoría de funciones)
        return this.currentUser && (this.currentUser.role === 'ADMIN' || this.currentUser.role === 'DEVELOPER');
    }

    isStrictAdmin() {
        // Verificar si el usuario es solo ADMIN (no desarrollador) - para operaciones sensibles como eliminar
        return this.currentUser && this.currentUser.role === 'ADMIN';
    }

    updateAdminUI() {
        const adminElements = document.querySelectorAll('.admin-only');
        if (this.isAdmin()) {
            adminElements.forEach(el => el.classList.add('visible'));
        } else {
            adminElements.forEach(el => el.classList.remove('visible'));
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
        const isAdmin = this.isAdmin();
        
        // ADMIN y DEVELOPER pueden ver botón de retry
        const retryButton = (envio.status === 'failed' && isAdmin) ? `
            <button class="btn-action" onclick="dashboard.retryExecution('${envioId}')" title="Reintentar">
                <i class="fas fa-redo"></i>
            </button>
        ` : '';
        
        row.innerHTML = `
            <td>${envio.fecha}</td>
            <td>${envio.boletin}</td>
            <td>${this.createStatusBadge(envio.status)}</td>
            <td>${envio.duracion}</td>
            <td>
                <button class="btn-action" onclick="dashboard.showDetails('${envioId}')" title="Ver detalles">
                    <i class="fas fa-eye"></i>
                </button>
                ${retryButton}
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
        const isAdmin = this.isAdmin();
        const isStrictAdmin = this.isStrictAdmin();
        
        // Solo ADMIN estricto puede toggle y delete
        const adminOnlyButtons = isStrictAdmin ? `
            <button class="btn-action" onclick="dashboard.toggleSchedule('${proximo.id}')" title="Habilitar/Deshabilitar">
                <i class="fas fa-toggle-${proximo.estado === 'enabled' ? 'on' : 'off'}"></i>
            </button>
            <button class="btn-action" onclick="dashboard.deleteSchedule('${proximo.id}')" title="Eliminar">
                <i class="fas fa-trash"></i>
            </button>
        ` : '';
        
        // Todos los usuarios pueden ver el botón de editar
        row.innerHTML = `
            <td>${proximo.boletin}</td>
            <td>${proximo.hora}</td>
            <td>${this.createStatusBadge(proximo.estado)}</td>
            <td>${proximo.ultimaEjecucion}</td>
            <td>
                <button class="btn-action" onclick="dashboard.editSchedule('${proximo.id}')" title="Editar">
                    <i class="fas fa-edit"></i>
                </button>
                ${adminOnlyButtons}
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
        // Verificar si el usuario es desarrollador para mostrar el modo prueba
        const isDeveloper = this.currentUser && this.currentUser.role === 'DEVELOPER';
        
        const testModeSection = isDeveloper ? `
            <div class="form-group test-mode-section">
                <label class="checkbox-label">
                    <input type="checkbox" id="test-mode-checkbox" onchange="dashboard.toggleTestMode()">
                    <span class="checkmark"></span>
                    Modo Prueba
                </label>
                <small class="form-text" style="color: var(--test-color); font-weight: 500;">
                    <i class="fas fa-flask"></i> 
                    Al activar el modo prueba, todos los correos se enviarán únicamente al correo de prueba configurado
                </small>
            </div>
            
            <div class="form-group" id="test-email-group">
                <label>Correo de Prueba:</label>
                <input type="email" id="test-email" class="form-control" placeholder="test@example.com" value="">
                <small class="form-text" style="color: var(--test-color);">
                    <i class="fas fa-envelope"></i> 
                    Correo que recibirá todos los boletines cuando el modo prueba esté activo
                </small>
                <button type="button" class="btn-primary btn-size" onclick="dashboard.saveTestEmail()" style="margin-top: 0.8rem;">
                    <i class="fas fa-save"></i> Guardar Correo de Prueba
                </button>
            </div>
        ` : '';
        
        this.showModal('Configuración General', `
            ${testModeSection}
            
            <div class="form-group">
                <label>Dominios Permitidos:</label>
                <input type="text" id="allowed-domains" class="form-control" placeholder="gmail.com,empresa.com,hotmail.com" value="">
                <small class="form-text">Dominios permitidos para correos electrónicos (separados por coma). Si no especificas, se permitirán todos los dominios.</small>
            </div>
            
            <div class="form-group">
                <label>Remitente de Correos:</label>
                <input type="email" id="email-remite" class="form-control" placeholder="noreply@empresa.com" value="" required>
                <small class="form-text">Dirección de correo que aparecerá como remitente de todos los boletines</small>
            </div>
            
            <div class="form-group">
                <label>Limite por lista de correos:</label>
                <input type="number" id="limite-correos" class="form-control" placeholder="100" min="1" value="" required>
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
                <button type="button" class="btn-primary" onclick="dashboard.saveSettings()">
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
                
                // Solo cargar el checkbox de modo prueba si existe (solo para desarrolladores)
                const testModeCheckbox = document.getElementById('test-mode-checkbox');
                if (testModeCheckbox && settings.is_test_mode !== undefined) {
                    testModeCheckbox.checked = settings.is_test_mode;
                }
                
                // Cargar correo de prueba si existe
                if (settings.test_email) {
                    const testEmailInput = document.getElementById('test-email');
                    if (testEmailInput) {
                        testEmailInput.value = settings.test_email;
                    }
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
            const testEmailInput = document.getElementById('test-email');
            const newTestMode = checkbox.checked;
            const testEmail = testEmailInput ? testEmailInput.value.trim() : '';
            
            // Validar email si se está activando el modo prueba
            if (newTestMode && !testEmail) {
                this.showToast('Por favor ingresa un correo de prueba válido', 'error');
                checkbox.checked = false;
                return;
            }
            
            const response = await fetch('/api/test-mode', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    is_test_mode: newTestMode,
                    test_email: testEmail
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                this.updateTestModeIndicator(newTestMode);
                this.showToast(result.message, 'success');
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error cambiando modo prueba', 'error');
                checkbox.checked = !newTestMode;
            }
        } catch (error) {
            this.showToast('Error cambiando modo prueba', 'error');
            const checkbox = document.getElementById('test-mode-checkbox');
            checkbox.checked = !checkbox.checked;
        }
    }

    async saveTestEmail() {
        try {
            const testEmailInput = document.getElementById('test-email');
            const testEmail = testEmailInput ? testEmailInput.value.trim() : '';
            
            if (!testEmail) {
                this.showToast('Por favor ingresa un correo de prueba válido', 'error');
                return;
            }
            
            // Validar formato de email
            const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailPattern.test(testEmail)) {
                this.showToast('Por favor ingresa un correo válido', 'error');
                return;
            }
            
            const response = await fetch('/api/test-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    test_email: testEmail
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showToast(result.message || 'Correo de prueba guardado exitosamente', 'success');
            } else {
                const error = await response.json();
                this.showToast(error.detail || 'Error guardando correo de prueba', 'error');
            }
        } catch (error) {
            this.showToast('Error guardando correo de prueba', 'error');
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
            
            // Check user role
            const isAdmin = this.isAdmin();
            const userRole = this.currentUser ? this.currentUser.role : 'USER';
            
            // Create newsletter options
            const newsletterOptions = scheduleData.newsletters.map(nl => 
                '<option value="' + nl.id + '"' + (nl.id === scheduleData.newsletter_id ? ' selected' : '') + '>' + nl.name + '</option>'
            ).join('');
            
            // Create email list options
            const emailListOptions = scheduleData.emailLists && scheduleData.emailLists.length > 0 ? scheduleData.emailLists.map(list => 
                '<option value="' + list.list_id + '"' + (list.list_id === scheduleData.email_list_id ? ' selected' : '') + '>' + list.list_name + ' (' + list.email_count + ' correos)</option>'
            ).join('') : '<option value="">No hay listas disponibles</option>';
            
            // Build modal content based on user role
            let modalContent;
            
            if (isAdmin) {
                // ADMIN y DEVELOPER pueden editar todos los campos
                modalContent = '<form id="edit-schedule-form" enctype="multipart/form-data">' +
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
            } else {
                // USER solo puede editar la lista de correos - otros campos en modo solo lectura
                modalContent = '<form id="edit-schedule-form" enctype="multipart/form-data">' +
                    '<div class="form-group">' +
                        '<label for="newsletter-select">Nombre del Boletin:</label>' +
                        '<select id="newsletter-select" class="form-control" disabled>' +
                            newsletterOptions +
                        '</select>' +
                        '<small class="form-text" style="color: #6c757d;">Solo los administradores pueden cambiar el boletín</small>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="email-list-select">Lista de Destinatarios:</label>' +
                        '<select id="email-list-select" class="form-control">' +
                            '<option value="">Selecciona una lista...</option>' +
                            emailListOptions +
                        '</select>' +
                        '<small class="form-text">Lista actual: ' + (scheduleData.current_email_list || 'No asignada') + '</small>' +
                        '<small class="form-text" style="color: #28a745;">✓ Puedes cambiar la lista de destinatarios</small>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="time-input">Hora de Ejecucion:</label>' +
                        '<input type="time" id="time-input" class="form-control" value="' + scheduleData.send_time + '" disabled>' +
                        '<small class="form-text" style="color: #6c757d;">Solo los administradores pueden cambiar la hora</small>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="timezone-select">Zona Horaria:</label>' +
                        '<select id="timezone-select" class="form-control" disabled>' +
                            '<option value="America/Bogota"' + (scheduleData.timezone === 'America/Bogota' ? ' selected' : '') + '>America/Bogota</option>' +
                            '<option value="UTC"' + (scheduleData.timezone === 'UTC' ? ' selected' : '') + '>UTC</option>' +
                        '</select>' +
                        '<small class="form-text" style="color: #6c757d;">Solo los administradores pueden cambiar la zona horaria</small>' +
                    '</div>' +
                    '<div class="form-group" style="opacity: 0.6;">' +
                        '<label>Nueva Plantilla de Correo (.html):</label>' +
                        '<div class="file-upload-area" style="cursor: not-allowed; background: #e9ecef;">' +
                            '<i class="fas fa-envelope"></i>' +
                            '<span>Plantilla actual: ' + (scheduleData.current_template || 'No asignada') + '</span>' +
                        '</div>' +
                        '<small class="form-text" style="color: #6c757d;">Solo los administradores pueden cambiar la plantilla</small>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label class="checkbox-label" style="opacity: 0.6;">' +
                            '<input type="checkbox" id="enabled-checkbox"' + (scheduleData.is_enabled ? ' checked' : '') + ' disabled>' +
                            'Tarea habilitada (solo administradores pueden cambiar)' +
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
            }
            
            this.showModal('Editar Tarea Programada', modalContent);
            
            // Add form submit handler
            document.getElementById('edit-schedule-form').addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveSchedule(id, userRole);
            });
            
        } catch (error) {
            this.showToast('Error cargando datos de la tarea', 'error');
            this.editingSchedule = false; // Unblock on error
        }
    }


    async saveSchedule(id, userRole) {
        try {
            // Get form values
            const emailListId = document.getElementById('email-list-select').value;
            
            // Validate inputs based on user role
            const isAdmin = userRole === 'ADMIN' || userRole === 'DEVELOPER';
            const isUser = userRole === 'USER';
            
            if (!emailListId) {
                this.showToast('Por favor selecciona una lista de correos', 'error');
                return;
            }
            
            // USER role: only update email list using specific endpoint
            if (isUser) {
                const response = await fetch(`/api/schedule/${id}/email-list`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email_list_id: emailListId })
                });
                
                const result = await response.json();
                
                if (response.ok && result.success) {
                    this.showToast('Lista de correos actualizada exitosamente', 'success');
                    this.closeModal();
                } else {
                    throw new Error(result.message || 'Error actualizando lista de correos');
                }
            } else {
                // ADMIN/DEVELOPER: use full update endpoint
                const newsletterId = document.getElementById('newsletter-select').value;
                const sendTime = document.getElementById('time-input').value;
                const timezone = document.getElementById('timezone-select').value;
                const isEnabled = document.getElementById('enabled-checkbox').checked;
                
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
        const formHTML = `
            <form id="upload-bulletin-form">
                <div class="form-group">
                    <label for="bulletin-name">Nombre del Boletín:</label>
                    <input type="text" id="bulletin-name" class="form-control" placeholder="Ej: Reporte Diario de Ventas" required>
                    <small class="form-text text-muted">Solo se permiten letras, números, espacios, guiones (-), guiones bajos (_), paréntesis () y caracteres con acentos</small>
                    <div id="bulletin-name-error" class="invalid-feedback" style="display: none; color: #dc3545; font-size: 1.2rem; margin-top: 0.25rem;"></div>
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
                    <div class="mt-2">
                        <button type="button" class="btn btn-sm btn-outline-info" onclick="dashboard.showExampleModal()">
                            <i class="fas fa-eye"></i> Ver ejemplo
                        </button>
                    </div>
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
                    <div class="mt-2">
                        <button type="button" class="btn btn-sm btn-outline-info" onclick="dashboard.showTemplateExampleModal()">
                            <i class="fas fa-eye"></i> Ver ejemplo
                        </button>
                    </div>
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
            </form>`;
        
        // Store the original form HTML
        this.originalFormHTML = formHTML;
        
        this.showModal('Cargar Nuevo Boletín', formHTML);
        
        // Cargar listas de correos en el select
        this.loadEmailListsForBulletin();
        
        // Setup form submission and validation listeners
        this.setupFormEventListeners();
    }

    setupFormEventListeners() {
        // Setup form submission
        const form = document.getElementById('upload-bulletin-form');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.uploadBulletin();
            };
        }
        
        // Setup bulletin name validation
        const bulletinNameInput = document.getElementById('bulletin-name');
        if (bulletinNameInput) {
            bulletinNameInput.addEventListener('input', () => {
                this.validateBulletinName();
            });
        }
    }

    validateBulletinName() {
        const bulletinNameInput = document.getElementById('bulletin-name');
        const bulletinNameError = document.getElementById('bulletin-name-error');
        
        if (!bulletinNameInput || !bulletinNameError) return;
        
        const value = bulletinNameInput.value.trim();
        // Allow letters, numbers, spaces, hyphens, underscores, parentheses, and accented characters
        const validPattern = /^[a-zA-Z0-9\s\-_()áéíóúÁÉÍÓÚñÑüÜ]+$/;
        
        if (!validPattern.test(value)) {
            bulletinNameInput.style.borderColor = '#dc3545';
            bulletinNameError.style.display = 'block';
            bulletinNameError.textContent = 'El nombre contiene caracteres no permitidos';
        } else {
            bulletinNameInput.style.borderColor = '';
            bulletinNameError.style.display = 'none';
        }
    }

    loadEmailListsForBulletin() {
        return fetch('/api/email-lists')
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
                return lists; // Return lists for chaining
            })
            .catch(error => {
                const select = document.getElementById('email-list-select');
                if (select) {
                    select.innerHTML = '<option value="">Error cargando listas</option>';
                }
                throw error; // Re-throw error
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
        
        // Validar que el nombre del boletín no contenga símbolos extraños
        // Permitir: letras, números, espacios, guiones, guiones bajos, paréntesis, y caracteres con acentos
        const validNamePattern = /^[a-zA-Z0-9\sáéíóúÁÉÍÓÚñÑüÜ\-_()]+$/;
        if (!validNamePattern.test(bulletinName)) {
            this.showToast('El nombre del boletín solo puede contener letras, números, espacios, guiones (-), guiones bajos (_), paréntesis () y caracteres con acentos', 'error');
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
            
            
            // Validación simple y directa
            if (!emailRemitente || emailRemitente.trim() === '') {
                this.showToast('Por favor complete el email del remitente (es requerido)', 'error');
                return;
            }
            
            if (!limiteCorreos || limiteCorreos.trim() === '') {
                this.showToast('Por favor complete el límite de correos (es requerido)', 'error');
                return;
            }
                        
            // Validar email del remitente
            if (!this.validateEmail(emailRemitente)) {
                this.showToast('El email del remitente no es válido', 'error');
                return;
            }
            
            // Validar límite de correos
            if (isNaN(limiteCorreos) || parseInt(limiteCorreos) < 1) {
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

    async showExampleModal() {
        try {
            // Save current form state before showing example
            this.savedFormState = this.saveFormState();
            
            // Show loading modal first
            this.showModal('Ejemplo de Script Python', `
                <div class="loading-example">
                    <i class="fas fa-spinner fa-spin"></i> Cargando ejemplo...
                </div>
            `);

            // Fetch the example file content
            const response = await fetch('/api/example-script');
            
            if (!response.ok) {
                throw new Error('Error cargando el ejemplo');
            }
            
            const exampleContent = await response.text();
            
            // Show the content with syntax highlighting
            this.showModal('Ejemplo de Script Python', `
                <div class="example-container">
                    <div class="example-header">
                        <button class="btn-back" onclick="dashboard.backToBulletinForm()">
                            <i class="fas fa-arrow-left"></i> Volver al formulario
                        </button>
                        <p class="text-muted mb-3">
                            <i class="fas fa-info-circle"></i> 
                            Este es un ejemplo completo de cómo debe estructurarse tu script Python para generar boletines.
                            Puedes copiar este código y adaptarlo a tus necesidades.
                        </p>
                        <div class="example-actions">
                            <div class="action-buttons">
                                <button class="btn btn-sm btn-primary" onclick="dashboard.copyExampleCode()">
                                    <i class="fas fa-copy"></i> Copiar código
                                </button>
                                <button class="btn btn-sm btn-secondary" onclick="dashboard.downloadExample()">
                                    <i class="fas fa-download"></i> Descargar
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="code-container">
                        <pre><code class="language-python" id="example-code">${this.escapeHtml(exampleContent)}</code></pre>
                    </div>
                </div>
            `);
            
            // Apply syntax highlighting
            if (typeof hljs !== 'undefined') {
                hljs.highlightElement(document.getElementById('example-code'));
            }
            
        } catch (error) {
            console.error('Error loading example:', error);
            this.showModal('Error', `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle text-danger"></i>
                    <p>No se pudo cargar el ejemplo de script. Por favor, inténtalo más tarde.</p>
                </div>
            `);
        }
    }

    copyExampleCode() {
        const codeElement = document.getElementById('example-code');
        if (codeElement) {
            const textArea = document.createElement('textarea');
            textArea.value = codeElement.textContent;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            this.showToast('Código copiado al portapapeles', 'success', 3000);
        }
    }

    async downloadExample() {
        try {
            const response = await fetch('/api/example-script');
            if (!response.ok) {
                throw new Error('Error descargando el ejemplo');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'main_example.py';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            this.showToast('Ejemplo descargado correctamente', 'success', 3000);
        } catch (error) {
            console.error('Error downloading example:', error);
            this.showToast('Error descargando el ejemplo', 'error', 3000);
        }
    }

    async showTemplateExampleModal() {
        try {
            // Save current form state before showing example
            this.savedFormState = this.saveFormState();
            
            // Show loading modal first
            this.showModal('Ejemplo de Plantilla HTML', `
                <div class="loading-example">
                    <i class="fas fa-spinner fa-spin"></i> Cargando ejemplo...
                </div>
            `);

            // Fetch the template example file content
            const response = await fetch('/api/example-template');
            
            if (!response.ok) {
                throw new Error('Error cargando el ejemplo');
            }
            
            const exampleContent = await response.text();
            
            // Show the content with syntax highlighting
            this.showModal('Ejemplo de Plantilla HTML', `
                <div class="example-container">
                    <div class="example-header">
                        <button class="btn-back" onclick="dashboard.backToBulletinForm()">
                            <i class="fas fa-arrow-left"></i> Volver al formulario
                        </button>
                        <p class="text-muted mb-3">
                            <i class="fas fa-info-circle"></i> 
                            Este es un ejemplo completo de cómo debe estructurarse tu plantilla HTML para el boletín.
                            Puedes copiar este código y adaptarlo a tus necesidades.
                        </p>
                        <div class="example-actions">
                            <div class="action-buttons">
                                <button class="btn btn-sm btn-primary" onclick="dashboard.copyTemplateExampleCode()">
                                    <i class="fas fa-copy"></i> Copiar código
                                </button>
                                <button class="btn btn-sm btn-secondary" onclick="dashboard.downloadTemplateExample()">
                                    <i class="fas fa-download"></i> Descargar
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="code-container">
                        <pre><code class="language-html" id="template-example-code">${this.escapeHtml(exampleContent)}</code></pre>
                    </div>
                </div>
            `);
            
            // Apply syntax highlighting
            if (typeof hljs !== 'undefined') {
                hljs.highlightElement(document.getElementById('template-example-code'));
            }
            
        } catch (error) {
            console.error('Error loading template example:', error);
            this.showModal('Error', `
                <div class="error-message">
                    <i class="fas fa-exclamation-triangle text-danger"></i>
                    <p>No se pudo cargar el ejemplo de plantilla. Por favor, inténtalo más tarde.</p>
                </div>
            `);
        }
    }

    copyTemplateExampleCode() {
        const codeElement = document.getElementById('template-example-code');
        if (codeElement) {
            const textArea = document.createElement('textarea');
            textArea.value = codeElement.textContent;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            this.showToast('Código de plantilla copiado al portapapeles', 'success', 3000);
        }
    }

    async downloadTemplateExample() {
        try {
            const response = await fetch('/api/example-template');
            if (!response.ok) {
                throw new Error('Error descargando el ejemplo');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'boletin_template_example.html';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            this.showToast('Plantilla ejemplo descargada correctamente', 'success', 3000);
        } catch (error) {
            console.error('Error downloading template example:', error);
            this.showToast('Error descargando la plantilla ejemplo', 'error', 3000);
        }
    }

    saveFormState() {
        // Get the current form from the DOM (not from getBulletinFormContent)
        const bulletinNameInput = document.getElementById('bulletin-name');
        const emailListSelect = document.getElementById('email-list-select');
        const emailTemplateFileName = document.getElementById('email-template-file-name');
        const scriptFileName = document.getElementById('script-file-name');
        const queryFileName = document.getElementById('query-file-name');
        const templateFileName = document.getElementById('template-file-name');
        const imagesFileName = document.getElementById('images-file-name');
        
        const state = {
            bulletinName: bulletinNameInput?.value || '',
            emailList: emailListSelect?.value || '',
            emailTemplateFileName: emailTemplateFileName?.textContent || 'Haz clic para seleccionar la plantilla HTML del correo',
            scriptFileName: scriptFileName?.textContent || 'Haz clic para seleccionar el script Python',
            queryFileName: queryFileName?.textContent || 'Haz clic para seleccionar uno o más archivos JSON',
            templateFileName: templateFileName?.textContent || 'Haz clic para seleccionar la plantilla HTML',
            imagesFileName: imagesFileName?.textContent || 'Haz clic para seleccionar una o más imágenes'
        };
        
        return state;
    }

    restoreFormState(state) {
        if (!state) return;
        
        // First load email lists, then restore the selected value
        this.loadEmailListsForBulletin().then(() => {
            setTimeout(() => {
                // Restore form values
                const bulletinNameInput = document.getElementById('bulletin-name');
                if (bulletinNameInput && state.bulletinName) {
                    bulletinNameInput.value = state.bulletinName;
                }
                
                const emailListSelect = document.getElementById('email-list-select');
                if (emailListSelect && state.emailList) {
                    emailListSelect.value = state.emailList;
                }
                
                // Restore file names
                const emailTemplateFileName = document.getElementById('email-template-file-name');
                if (emailTemplateFileName && state.emailTemplateFileName) {
                    emailTemplateFileName.textContent = state.emailTemplateFileName;
                }
                
                const scriptFileName = document.getElementById('script-file-name');
                if (scriptFileName && state.scriptFileName) {
                    scriptFileName.textContent = state.scriptFileName;
                }
                
                const queryFileName = document.getElementById('query-file-name');
                if (queryFileName && state.queryFileName) {
                    queryFileName.textContent = state.queryFileName;
                }
                
                const templateFileName = document.getElementById('template-file-name');
                if (templateFileName && state.templateFileName) {
                    templateFileName.textContent = state.templateFileName;
                }
                
                const imagesFileName = document.getElementById('images-file-name');
                if (imagesFileName && state.imagesFileName) {
                    imagesFileName.textContent = state.imagesFileName;
                }
            }, 200); // Give more time for lists to load
        });
    }

    backToBulletinForm() {
        // Apply fade-out effect to current content
        const modalBody = document.getElementById('modal-body');
        const modalTitle = document.getElementById('modal-title');
        
        // Apply instant fade transition
        modalBody.style.opacity = '0';
        modalBody.style.transform = 'scale(0.98)';
        
        // Change content instantly after a very short delay
        setTimeout(() => {
            modalTitle.textContent = 'Cargar Nuevo Boletín';
            
            // Use the stored original form HTML instead of recreating it
            if (this.originalFormHTML) {
                modalBody.innerHTML = this.originalFormHTML;
            } else {
                // Fallback: regenerate the form HTML
                modalBody.innerHTML = this.getBulletinFormContent();
            }
            
            // Fade back in
            modalBody.style.opacity = '1';
            modalBody.style.transform = 'scale(1)';
            
            // Restore the saved form state
            this.restoreFormState(this.savedFormState);
            
            // Initialize the form with full functionality
            this.initializeBulletinForm();
        }, 50); // Very short delay for smooth transition
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    initializeBulletinForm() {
        // Load email lists
        this.loadEmailListsForBulletin();
        
        // Setup form submission
        const form = document.getElementById('upload-bulletin-form');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.uploadBulletin();
            };
        }
        
        // Setup bulletin name validation
        const bulletinNameInput = document.getElementById('bulletin-name');
        if (bulletinNameInput) {
            bulletinNameInput.addEventListener('input', () => {
                this.validateBulletinName();
            });
        }
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
    } else {
        console.error('Dashboard no está disponible');
        return null;
    }
}

function showEmailListModal() {
    if (window.dashboard) {
        return window.dashboard.showEmailListModal();
    } else {
        console.error('Dashboard no está disponible');
        return null;
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
    
    // Forzar redirección inmediata al logout local del servidor
    window.location.href = '/auth/local-logout';
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
    
    // Agregar validación en tiempo real para el nombre de la lista
    const emailListNameInput = document.getElementById('email-list-name');
    const emailListNameError = document.getElementById('email-list-name-error');
    
    if (emailListNameInput && emailListNameError) {
        // Remover event listener anterior si existe para evitar duplicados
        emailListNameInput.removeEventListener('input', handleEmailListNameValidation);
        
        // Agregar event listener para validación en tiempo real
        emailListNameInput.addEventListener('input', handleEmailListNameValidation);
    }
}

function handleEmailListNameValidation() {
    const emailListNameInput = document.getElementById('email-list-name');
    const emailListNameError = document.getElementById('email-list-name-error');
    
    if (!emailListNameInput || !emailListNameError) return;
    
    const value = emailListNameInput.value.trim();
    const validNamePattern = /^[a-zA-Z0-9\sáéíóúÁÉÍÓÚñÑüÜ\-_()]+$/;
    
    if (value && !validNamePattern.test(value)) {
        emailListNameInput.style.borderColor = '#dc3545';
        emailListNameError.style.display = 'block';
        emailListNameError.textContent = 'El nombre contiene caracteres no permitidos';
    } else {
        emailListNameInput.style.borderColor = '';
        emailListNameError.style.display = 'none';
    }
}

function closeEmailListModal() {
    document.getElementById('email-list-modal').style.display = 'none';
}

async function uploadEmailList() {
    const listName = document.getElementById('email-list-name').value.trim();
    const descriptionElement = document.getElementById('email-list-description');
    const description = descriptionElement ? descriptionElement.value : '';
    const csvFile = document.getElementById('email-csv-file').files[0];
    
    if (!listName || !csvFile) {
        dashboard.showToast('Por favor complete todos los campos obligatorios', 'error');
        return;
    }
    
    // Validar que el nombre de la lista no contenga símbolos extraños
    // Permitir: letras, números, espacios, guiones, guiones bajos, paréntesis, y caracteres con acentos
    const validNamePattern = /^[a-zA-Z0-9\sáéíóúÁÉÍÓÚñÑüÜ\-_()]+$/;
    if (!validNamePattern.test(listName)) {
        dashboard.showToast('El nombre de la lista solo puede contener letras, números, espacios, guiones (-), guiones bajos (_), paréntesis () y caracteres con acentos', 'error');
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
            let errorMessage = 'Error creando lista de correos';
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('application/json')) {
                try {
                    const error = await response.json();
                    errorMessage = error.detail || errorMessage;
                } catch (e) {
                    errorMessage = 'Error del servidor (JSON inválido)';
                }
            } else {
                // Para respuestas no-JSON, obtener el texto directamente
                const errorText = await response.text();
                errorMessage = errorText || errorMessage;
            }
            
            dashboard.showToast(errorMessage, 'error');
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
        let hasEmptyFields = false;
        const emptyFields = [];
        
        inputs.forEach(input => {
            const key = input.dataset.key;
            const value = input.value.trim();
            
            if (!value) {
                hasEmptyFields = true;
                emptyFields.push(key);
            }
            
            credentials[key] = value;
        });
        
        // Validar que no haya campos vacíos
        if (hasEmptyFields) {
            this.showToast(`El campo no puede estar vacío: ${emptyFields.join(', ')}`, 'error');
            return;
        }
        
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
            // Manejar diferentes tipos de error
            const errorText = await response.text();
            let errorMessage = 'Error guardando credenciales';
            
            try {
                const error = JSON.parse(errorText);
                errorMessage = error.detail || errorMessage;
            } catch (e) {
                // Si no es JSON, usar el texto directamente
                if (response.status === 400) {
                    errorMessage = errorText || 'Error de validación';
                } else if (response.status === 500) {
                    errorMessage = 'Error interno del servidor';
                }
            }
            
            throw new Error(errorMessage);
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

// Funciones para Registro de Usuarios
function showUserRegistration() {
    const modal = document.getElementById('user-registration-modal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // Mostrar formulario de registro, ocultar formulario de edición
    document.getElementById('user-registration-form').style.display = 'block';
    document.getElementById('user-edit-form').style.display = 'none';
    
    // Cambiar título del modal
    const modalTitle = modal.querySelector('.modal-header h2');
    if (modalTitle) {
        modalTitle.innerHTML = '<i class="fas fa-user-plus"></i> Registrar Nuevo Usuario';
    }
    
    // Limpiar formulario de registro
    document.getElementById('user-registration-form').reset();
    
    // Cargar datos iniciales para el formulario de registro
    loadEmpresas();
    
    // Agregar event listener al formulario de registro
    const registerForm = document.getElementById('user-registration-form');
    if (registerForm) {
        registerForm.removeEventListener('submit', handleUserRegistration);
        registerForm.addEventListener('submit', handleUserRegistration);
    }
    
    // Agregar event listener para validación de email
    const emailInput = document.getElementById('user-email');
    if (emailInput) {
        emailInput.removeEventListener('blur', validateEmailDomain);
        emailInput.addEventListener('blur', validateEmailDomain);
    }
    
    // Agregar event listener para cambio de empresa
    const empresaSelect = document.getElementById('user-empresa');
    if (empresaSelect) {
        empresaSelect.removeEventListener('change', handleEmpresaChange);
        empresaSelect.addEventListener('change', handleEmpresaChange);
    }
    
    // Agregar event listener para cambio de sede
    const sedeSelect = document.getElementById('user-sede');
    if (sedeSelect) {
        sedeSelect.removeEventListener('change', handleSedeChange);
        sedeSelect.addEventListener('change', handleSedeChange);
    }
}

function closeUserRegistrationModal() {
    const modal = document.getElementById('user-registration-modal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
    
    // Limpiar formulario de registro
    const form = document.getElementById('user-registration-form');
    form.reset();
    
    // Limpiar errores
    document.getElementById('email-error').style.display = 'none';
    
    // Resetear selects
    document.getElementById('user-sede').disabled = true;
    document.getElementById('user-area').disabled = true;
    document.getElementById('add-sede-btn').disabled = true;
    document.getElementById('add-area-btn').disabled = true;
}

// Función para mostrar formulario de edición
function showUserEdit() {
    const modal = document.getElementById('user-registration-modal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // Ocultar formulario de registro, mostrar formulario de edición
    document.getElementById('user-registration-form').style.display = 'none';
    document.getElementById('user-edit-form').style.display = 'block';
    
    // Cambiar título del modal
    const modalTitle = modal.querySelector('.modal-header h2');
    if (modalTitle) {
        modalTitle.innerHTML = '<i class="fas fa-user-edit"></i> Editar Usuario';
    }
    
    // Agregar event listener al formulario de edición
    const editForm = document.getElementById('user-edit-form');
    if (editForm) {
        editForm.removeEventListener('submit', handleUserEdit);
        editForm.addEventListener('submit', handleUserEdit);
    }
}

function closeUserEditModal() {
    const modal = document.getElementById('user-registration-modal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
    
    // Limpiar formulario de edición
    const form = document.getElementById('user-edit-form');
    form.reset();
    
    // Resetear a modo registro
    document.getElementById('user-registration-form').style.display = 'block';
    document.getElementById('user-edit-form').style.display = 'none';
}

function validateEmailDomain() {
    const emailInput = document.getElementById('user-email');
    const emailError = document.getElementById('email-error');
    
    // Verificar que los elementos existan
    if (!emailInput) {
        return true; // Si no existe el elemento, no validar
    }
    
    if (!emailError) {
        return true; // Si no existe el elemento, no validar
    }
    
    const email = emailInput.value;
    
    // Verificar que email no sea undefined antes de hacer trim
    if (!email || typeof email !== 'string') {
        emailError.style.display = 'none';
        return true;
    }
    
    const emailTrimmed = email.trim();
    
    if (!emailTrimmed) {
        emailError.style.display = 'none';
        return true;
    }
    
    // Validar dominio @clinicassanrafael.com
    if (!emailTrimmed.endsWith('@clinicassanrafael.com')) {
        emailError.textContent = 'Usuario Administrador, recuerde que los correos que no son del dominio @clinicassanrafael.com deben ser invitados en Microsoft Entra ID';
        emailError.style.display = 'block';
        emailError.style.color = '#ffc107'; // Amarillo
        return false;
    }
    
    emailError.style.display = 'none';
    return true;
}

async function loadEmpresas() {
    try {
        const response = await fetch('/api/empresas', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando empresas');
        }
        
        const empresas = await response.json();
        const empresaSelect = document.getElementById('user-empresa');
        
        // Limpiar opciones existentes
        empresaSelect.innerHTML = '<option value="">Seleccionar empresa...</option>';
        
        // Agregar opción por defecto "Clinica San Rafael" si no existe
        const clinicaSanRafael = empresas.find(e => e.nombre === 'Clinica San Rafael');
        if (!clinicaSanRafael) {
            // Crear empresa por defecto si no existe
            await createDefaultEmpresa();
            // Recargar empresas
            await loadEmpresas();
            return;
        }
        
        // Agregar empresas al select
        empresas.forEach(empresa => {
            if (empresa.activa) {
                const option = document.createElement('option');
                option.value = empresa.empresa_id;
                option.textContent = empresa.nombre;
                empresaSelect.appendChild(option);
            }
        });
        
        // Seleccionar "Clinica San Rafael" por defecto
        const defaultOption = Array.from(empresaSelect.options).find(opt => opt.textContent === 'Clinica San Rafael');
        if (defaultOption) {
            empresaSelect.value = defaultOption.value;
            handleEmpresaChange();
        }
        
    } catch (error) {
        console.error('Error cargando empresas:', error);
        showToast('Error cargando empresas', 'error');
    }
}

async function createDefaultEmpresa() {
    try {
        const response = await fetch('/api/empresas', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nombre: 'Clinica San Rafael',
                dominio_correo: 'clinicassanrafael.com'
            }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error creando empresa por defecto');
        }
        
    } catch (error) {
        console.error('Error creando empresa por defecto:', error);
    }
}

async function handleEmpresaChange() {
    const empresaSelect = document.getElementById('user-empresa');
    const sedeSelect = document.getElementById('user-sede');
    const areaSelect = document.getElementById('user-area');
    const addSedeBtn = document.getElementById('add-sede-btn');
    const addAreaBtn = document.getElementById('add-area-btn');
    
    const empresaId = empresaSelect.value;
    
    // Resetear selects dependientes
    sedeSelect.innerHTML = '<option value="">Seleccionar sede...</option>';
    areaSelect.innerHTML = '<option value="">Seleccionar área...</option>';
    
    if (!empresaId) {
        sedeSelect.disabled = true;
        areaSelect.disabled = true;
        addSedeBtn.disabled = true;
        addAreaBtn.disabled = true;
        return;
    }
    
    try {
        // Cargar sedes de la empresa seleccionada
        const response = await fetch(`/api/empresas/${empresaId}/sedes`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando sedes');
        }
        
        const sedes = await response.json();
        
        // Agregar sedes al select
        sedes.forEach(sede => {
            if (sede.activa) {
                const option = document.createElement('option');
                option.value = sede.sede_id;
                option.textContent = sede.nombre;
                sedeSelect.appendChild(option);
            }
        });
        
        sedeSelect.disabled = false;
        addSedeBtn.disabled = false;
        
    } catch (error) {
        console.error('Error cargando sedes:', error);
        showToast('Error cargando sedes', 'error');
    }
}

async function handleSedeChange() {
    const sedeSelect = document.getElementById('user-sede');
    const areaSelect = document.getElementById('user-area');
    const addAreaBtn = document.getElementById('add-area-btn');
    
    const sedeId = sedeSelect.value;
    
    // Resetear área
    areaSelect.innerHTML = '<option value="">Seleccionar área...</option>';
    
    if (!sedeId) {
        areaSelect.disabled = true;
        addAreaBtn.disabled = true;
        return;
    }
    
    try {
        // Cargar áreas de la sede seleccionada
        const response = await fetch(`/api/sedes/${sedeId}/areas`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando áreas');
        }
        
        const areas = await response.json();
        
        // Agregar áreas al select
        areas.forEach(area => {
            if (area.activa) {
                const option = document.createElement('option');
                option.value = area.area_id;
                option.textContent = area.nombre;
                areaSelect.appendChild(option);
            }
        });
        
        areaSelect.disabled = false;
        addAreaBtn.disabled = false;
        
    } catch (error) {
        console.error('Error cargando áreas:', error);
        showToast('Error cargando áreas', 'error');
    }
}

function addNewEmpresa() {
    document.getElementById('new-empresa-group').style.display = 'block';
    document.getElementById('new-empresa-name').focus();
}

function cancelNewEmpresa() {
    document.getElementById('new-empresa-group').style.display = 'none';
    document.getElementById('new-empresa-name').value = '';
}

async function saveNewEmpresa() {
    const nombre = document.getElementById('new-empresa-name').value.trim();
    
    if (!nombre) {
        showToast('El nombre de la empresa es requerido', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/empresas', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nombre }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error creando empresa');
        }
        
        showToast('Empresa creada exitosamente', 'success');
        cancelNewEmpresa();
        
        // Recargar empresas y seleccionar la nueva empresa
        await loadEmpresas();
        
        // Seleccionar la nueva empresa creada
        const empresaSelect = document.getElementById('user-empresa');
        const newOption = Array.from(empresaSelect.options).find(opt => opt.textContent === nombre);
        if (newOption) {
            empresaSelect.value = newOption.value;
            await handleEmpresaChange();
        }
        
    } catch (error) {
        console.error('Error creando empresa:', error);
        showToast(error.message || 'Error creando empresa', 'error');
    }
}

function addNewSede() {
    document.getElementById('new-sede-group').style.display = 'block';
    document.getElementById('new-sede-name').focus();
}

function cancelNewSede() {
    document.getElementById('new-sede-group').style.display = 'none';
    document.getElementById('new-sede-name').value = '';
}

async function saveNewSede() {
    const nombre = document.getElementById('new-sede-name').value.trim();
    const empresaId = document.getElementById('user-empresa').value;
    
    if (!nombre) {
        showToast('El nombre de la sede es requerido', 'error');
        return;
    }
    
    if (!empresaId) {
        showToast('Debe seleccionar una empresa primero', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/sedes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nombre, empresa_id: empresaId }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error creando sede');
        }
        
        showToast('Sede creada exitosamente', 'success');
        cancelNewSede();
        
        // Recargar sedes y seleccionar la nueva sede
        await handleEmpresaChange();
        
        // Seleccionar la nueva sede creada
        const sedeSelect = document.getElementById('user-sede');
        const newOption = Array.from(sedeSelect.options).find(opt => opt.textContent === nombre);
        if (newOption) {
            sedeSelect.value = newOption.value;
            await handleSedeChange();
        }
        
    } catch (error) {
        console.error('Error creando sede:', error);
        showToast(error.message || 'Error creando sede', 'error');
    }
}

function addNewArea() {
    document.getElementById('new-area-group').style.display = 'block';
    document.getElementById('new-area-name').focus();
}

function cancelNewArea() {
    document.getElementById('new-area-group').style.display = 'none';
    document.getElementById('new-area-name').value = '';
}

async function saveNewArea() {
    const nombre = document.getElementById('new-area-name').value.trim();
    const sedeId = document.getElementById('user-sede').value;
    
    if (!nombre) {
        showToast('El nombre del área es requerido', 'error');
        return;
    }
    
    if (!sedeId) {
        showToast('Debe seleccionar una sede primero', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/areas', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ nombre, sede_id: sedeId }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error creando área');
        }
        
        showToast('Área creada exitosamente', 'success');
        cancelNewArea();
        
        // Recargar áreas y seleccionar la nueva área
        await handleSedeChange();
        
        // Seleccionar la nueva área creada
        const areaSelect = document.getElementById('user-area');
        const newOption = Array.from(areaSelect.options).find(opt => opt.textContent === nombre);
        if (newOption) {
            areaSelect.value = newOption.value;
        }
        
    } catch (error) {
        console.error('Error creando área:', error);
        showToast(error.message || 'Error creando área', 'error');
    }
}

async function handleUserRegistration(e) {
    e.preventDefault();
    
    // Validar dominio del email
    if (!validateEmailDomain()) {
        showToast('El dominio del correo no es válido', 'error');
        return;
    }
    
    const formData = new FormData(e.target);
    
    // Modo registro - crear nuevo usuario
    try {
        const response = await fetch('/api/users/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: formData.get('email'),
                nombres: formData.get('nombres'),
                apellidos: formData.get('apellidos'),
                telefono: formData.get('telefono'),
                direccion: formData.get('direccion'),
                departamento: formData.get('departamento'),
                municipio: formData.get('municipio'),
                role: formData.get('role'),
                empresa_id: formData.get('empresa'),
                sede_id: formData.get('sede'),
                area_id: formData.get('area')
            }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error registrando usuario');
        }
        
        showToast('Usuario registrado exitosamente', 'success');
        closeUserRegistrationModal();
        
    } catch (error) {
        console.error('Error registrando usuario:', error);
        showToast(error.message || 'Error registrando usuario', 'error');
    }
}

// Funciones para gestión de lista de usuarios
function showUserList() {
    const modal = document.getElementById('user-list-modal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        loadUsers();
    }
}

function closeUserListModal() {
    const modal = document.getElementById('user-list-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

async function loadUsers() {
    try {
        document.getElementById('users-loading').style.display = 'block';
        
        const response = await fetch('/api/users', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando usuarios');
        }
        
        allUsers = await response.json();
        filteredUsers = [...allUsers];
        currentPage = 1;
        
        renderUsersTable();
        updatePagination();
        
    } catch (error) {
        console.error('Error cargando usuarios:', error);
        showToast('Error cargando usuarios', 'error');
    } finally {
        document.getElementById('users-loading').style.display = 'none';
    }
}

function renderUsersTable() {
    const tbody = document.getElementById('users-tbody');
    tbody.innerHTML = '';
    
    const startIndex = (currentPage - 1) * usersPerPage;
    const endIndex = startIndex + usersPerPage;
    const pageUsers = filteredUsers.slice(startIndex, endIndex);
    
    if (pageUsers.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                    No se encontraron usuarios
                </td>
            </tr>
        `;
        return;
    }
    
    pageUsers.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td title="${user.user_id}">${user.user_id.substring(0, 8)}...</td>
            <td>${(user.nombres || '') + ' ' + (user.apellidos || '')}</td>
            <td>${user.email}</td>
            <td>
                <span class="role-badge ${getRoleClass(user.role)}">${getRoleDisplayName(user.role)}</span>
            </td>
            <td>
                <button class="btn-view" onclick="viewUser('${user.user_id}')" title="Ver usuario">
                    <i class="fas fa-eye"></i> Ver
                </button>
                <button class="btn-edit" onclick="editUser('${user.user_id}')" title="Editar usuario">
                    <i class="fas fa-edit"></i> Editar
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    // Actualizar contador
    document.getElementById('user-count-info').textContent = 
        `Mostrando ${pageUsers.length} de ${filteredUsers.length} usuarios`;
}

function getRoleClass(role) {
    switch(role) {
        case 'ADMIN': return 'role-admin';
        case 'DEVELOPER': return 'role-developer';
        case 'USER': return 'role-user';
        default: return 'role-user';
    }
}

function getRoleDisplayName(role) {
    switch(role) {
        case 'ADMIN': return 'Administrador';
        case 'DEVELOPER': return 'Desarrollador';
        case 'USER': return 'Usuario';
        default: return role;
    }
}

function updatePagination() {
    const totalPages = Math.ceil(filteredUsers.length / usersPerPage);
    
    document.getElementById('current-page').textContent = currentPage;
    document.getElementById('total-pages').textContent = totalPages || 1;
    
    document.getElementById('prev-page-btn').disabled = currentPage === 1;
    document.getElementById('next-page-btn').disabled = currentPage >= totalPages;
}

function previousUserPage() {
    if (currentPage > 1) {
        currentPage--;
        renderUsersTable();
        updatePagination();
    }
}

function nextUserPage() {
    const totalPages = Math.ceil(filteredUsers.length / usersPerPage);
    if (currentPage < totalPages) {
        currentPage++;
        renderUsersTable();
        updatePagination();
    }
}

function filterUsersByStatus(status) {
    // Actualizar el filtro actual
    currentStatusFilter = status;
    
    // Actualizar botones activos
    document.querySelectorAll('.filter-status .btn-filter').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.filter === status) {
            btn.classList.add('active');
        }
    });
    
    // Aplicar filtro
    applyFilters();
}

function applyFilters() {
    const searchTerm = document.getElementById('user-search').value.toLowerCase().trim();
    
    // Filtrar por estado
    let tempUsers = allUsers;
    if (currentStatusFilter === 'active') {
        tempUsers = tempUsers.filter(user => user.is_active === true);
    } else if (currentStatusFilter === 'inactive') {
        tempUsers = tempUsers.filter(user => user.is_active === false);
    }
    
    // Filtrar por término de búsqueda
    if (searchTerm !== '') {
        tempUsers = tempUsers.filter(user => 
            user.user_id.toLowerCase().includes(searchTerm) ||
            (user.nombres || '').toLowerCase().includes(searchTerm) ||
            (user.apellidos || '').toLowerCase().includes(searchTerm) ||
            user.email.toLowerCase().includes(searchTerm) ||
            (user.role || '').toLowerCase().includes(searchTerm)
        );
    }
    
    filteredUsers = tempUsers;
    currentPage = 1;
    renderUsersTable();
    updatePagination();
}

function searchUsers() {
    // Usar applyFilters para mantener consistencia con el filtro de estado
    applyFilters();
}

function viewUser(userId) {
    
    // Cerrar el modal de lista de usuarios primero
    closeUserListModal();
    
    // Buscar el usuario en la lista cargada
    const user = allUsers.find(u => u.user_id === userId);
    
    if (!user) {
        showToast('Usuario no encontrado', 'error');
        return;
    }
    
    // Mostrar el formulario de visualización específico
    showUserView();
    
    // Cargar los datos del usuario después de que el formulario esté visible
    setTimeout(() => {
        // Cargar los datos en el formulario de visualización
        const nombresField = document.getElementById('view-user-nombres');
        const apellidosField = document.getElementById('view-user-apellidos');
        const telefonoField = document.getElementById('view-user-telefono');
        const direccionField = document.getElementById('view-user-direccion');
        const departamentoField = document.getElementById('view-user-departamento');
        const municipioField = document.getElementById('view-user-municipio');
        const emailField = document.getElementById('view-user-email');
        const roleField = document.getElementById('view-user-role');
        const empresaField = document.getElementById('view-user-empresa');
        const sedeField = document.getElementById('view-user-sede');
        const areaField = document.getElementById('view-user-area');
        const statusField = document.getElementById('view-user-status');
        
        if (nombresField) nombresField.value = user.nombres || '';
        if (apellidosField) apellidosField.value = user.apellidos || '';
        if (telefonoField) telefonoField.value = user.telefono || '';
        if (direccionField) direccionField.value = user.direccion || '';
        if (departamentoField) departamentoField.value = user.departamento || '';
        if (municipioField) municipioField.value = user.municipio || '';
        if (emailField) {
            emailField.value = user.email;
        }
        if (roleField) roleField.value = getRoleDisplayName(user.role);
        if (statusField) statusField.value = user.is_active ? 'Activo' : 'Inactivo';
        
        // Cargar información adicional (empresa, sede, área)
        loadUserInfoForView(user);
    }, 200); // Pequeño retraso para asegurar que el DOM esté listo
}

function showUserView() {
    const modal = document.getElementById('user-view-modal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    }
}

function closeUserViewModal() {
    const modal = document.getElementById('user-view-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

function loadUserInfoForView(user) {
    // Cargar información de empresa, sede y área para visualización
    // Ahora los nombres vienen directamente en la respuesta de la API
    const empresaField = document.getElementById('view-user-empresa');
    const sedeField = document.getElementById('view-user-sede');
    const areaField = document.getElementById('view-user-area');
    
    // Usar los nombres que vienen en la respuesta de la API (empresa_name, sede_name, area_name)
    if (empresaField) {
        empresaField.value = user.empresa_name || user.empresa_id || 'No asignada';
    }
    if (sedeField) {
        sedeField.value = user.sede_name || user.sede_id || 'No asignada';
    }
    if (areaField) {
        areaField.value = user.area_name || user.area_id || 'No asignada';
    }
}

function editUser(userId) {
    
    // Cerrar el modal de lista de usuarios primero
    closeUserListModal();
    
    // Buscar el usuario en la lista cargada
    const user = allUsers.find(u => u.user_id === userId);
    
    if (!user) {
        showToast('Usuario no encontrado', 'error');
        return;
    }
    
    // Mostrar el formulario de edición específico
    showUserEdit();
    
    // Cargar los datos del usuario después de que el formulario esté visible
    setTimeout(() => {
        // Cargar los datos en el formulario de edición
        const nombresField = document.getElementById('edit-user-nombres');
        const apellidosField = document.getElementById('edit-user-apellidos');
        const telefonoField = document.getElementById('edit-user-telefono');
        const direccionField = document.getElementById('edit-user-direccion');
        const departamentoField = document.getElementById('edit-user-departamento');
        const municipioField = document.getElementById('edit-user-municipio');
        const emailField = document.getElementById('edit-user-email');
        const roleField = document.getElementById('edit-user-role');
        const statusField = document.getElementById('edit-user-status');
        const empresaField = document.getElementById('edit-user-empresa');
        
        if (nombresField) nombresField.value = user.nombres || '';
        if (apellidosField) apellidosField.value = user.apellidos || '';
        if (telefonoField) telefonoField.value = user.telefono || '';
        if (direccionField) direccionField.value = user.direccion || '';
        if (departamentoField) departamentoField.value = user.departamento || '';
        if (municipioField) municipioField.value = user.municipio || '';
        if (emailField) {
            emailField.value = user.email;
        }
        if (roleField) roleField.value = user.role;
        if (statusField) statusField.value = user.is_active ? 'true' : 'false';
        
        // Cargar empresas y luego seleccionar la del usuario
        loadEmpresasForEdit().then(() => {
            if (empresaField && user.empresa_id) {
                empresaField.value = user.empresa_id;
                handleEmpresaChangeEdit(); // Cargar sedes
                setTimeout(() => {
                    const sedeField = document.getElementById('edit-user-sede');
                    if (sedeField && user.sede_id) {
                        sedeField.value = user.sede_id;
                        handleSedeChangeEdit(); // Cargar áreas
                        setTimeout(() => {
                            const areaField = document.getElementById('edit-user-area');
                            if (areaField && user.area_id) {
                                areaField.value = user.area_id;
                            }
                        }, 500);
                    }
                }, 500);
            }
        });
        
        // Cambiar el título del modal
        const modal = document.getElementById('user-registration-modal');
        const modalTitle = modal.querySelector('.modal-header h2');
        if (modalTitle) {
            modalTitle.innerHTML = '<i class="fas fa-user-edit"></i> Editar Usuario';
        }
        
        // Agregar campo oculto para el ID del usuario
        let userIdField = document.getElementById('edit-user-id');
        if (!userIdField) {
            userIdField = document.createElement('input');
            userIdField.type = 'hidden';
            userIdField.id = 'edit-user-id';
            userIdField.name = 'user_id';
            document.getElementById('user-edit-form').appendChild(userIdField);
        }
        userIdField.value = userId;
        
        showToast(`Editando usuario: ${(user.nombres || '') + ' ' + (user.apellidos || '')}`, 'info');
    }, 200); // Pequeño retraso para asegurar que el DOM esté listo
}

// Función para cargar empresas en el formulario de edición
async function loadEmpresasForEdit() {
    try {
        const response = await fetch('/api/empresas', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando empresas');
        }
        
        const empresas = await response.json();
        const empresaSelect = document.getElementById('edit-user-empresa');
        
        // Limpiar y agregar opciones
        empresaSelect.innerHTML = '<option value="">Seleccionar empresa...</option>';
        
        empresas.forEach(empresa => {
            if (empresa.activa) {
                const option = document.createElement('option');
                option.value = empresa.empresa_id;
                option.textContent = empresa.nombre;
                empresaSelect.appendChild(option);
            }
        });
                
    } catch (error) {
        console.error('Error cargando empresas para edición:', error);
        showToast('Error cargando empresas', 'error');
    }
}

// Función específica para mostrar el formulario de edición
function showUserEdit() {
    const modal = document.getElementById('user-registration-modal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';
    
    // Ocultar formulario de registro y mostrar formulario de edición
    const registerForm = document.getElementById('user-registration-form');
    const editForm = document.getElementById('user-edit-form');
    
    registerForm.style.display = 'none';
    editForm.style.display = 'block';
    
    // Cargar datos iniciales para el formulario de edición
    loadEmpresasForEdit();
    
    // Agregar event listener al formulario de edición
    if (editForm) {
        editForm.addEventListener('submit', handleUserEdit);
    }
    
    // Agregar event listener para cambio de empresa en formulario de edición
    const empresaEditSelect = document.getElementById('edit-user-empresa');
    if (empresaEditSelect) {
        empresaEditSelect.addEventListener('change', handleEmpresaChangeEdit);
    }
    
    // Agregar event listener para cambio de sede en formulario de edición
    const sedeEditSelect = document.getElementById('edit-user-sede');
    if (sedeEditSelect) {
        sedeEditSelect.addEventListener('change', handleSedeChangeEdit);
    }
}

// Funciones específicas para el formulario de edición
async function handleEmpresaChangeEdit() {
    const empresaId = document.getElementById('edit-user-empresa').value;
    const sedeSelect = document.getElementById('edit-user-sede');
    const addSedeBtn = document.getElementById('edit-add-sede-btn');
    
    // Limpiar selects dependientes
    sedeSelect.innerHTML = '<option value="">Seleccionar empresa primero...</option>';
    document.getElementById('edit-user-area').innerHTML = '<option value="">Seleccionar sede primero...</option>';
    
    if (!empresaId) {
        sedeSelect.disabled = true;
        document.getElementById('edit-user-area').disabled = true;
        addSedeBtn.disabled = true;
        return;
    }
    
    try {
        const response = await fetch(`/api/empresas/${empresaId}/sedes`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando sedes');
        }
        
        const sedes = await response.json();
        
        // Agregar sedes al select
        sedes.forEach(sede => {
            if (sede.activa) {
                const option = document.createElement('option');
                option.value = sede.sede_id;
                option.textContent = sede.nombre;
                sedeSelect.appendChild(option);
            }
        });
        
        sedeSelect.disabled = false;
        addSedeBtn.disabled = false;
        
    } catch (error) {
        console.error('Error cargando sedes:', error);
        showToast('Error cargando sedes', 'error');
    }
}

async function handleSedeChangeEdit() {
    const sedeId = document.getElementById('edit-user-sede').value;
    const areaSelect = document.getElementById('edit-user-area');
    const addAreaBtn = document.getElementById('edit-add-area-btn');
    
    // Limpiar select de áreas
    areaSelect.innerHTML = '<option value="">Seleccionar sede primero...</option>';
    
    if (!sedeId) {
        areaSelect.disabled = true;
        addAreaBtn.disabled = true;
        return;
    }
    
    try {
        const response = await fetch(`/api/sedes/${sedeId}/areas`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Error cargando áreas');
        }
        
        const areas = await response.json();
        
        // Agregar áreas al select
        areas.forEach(area => {
            if (area.activa) {
                const option = document.createElement('option');
                option.value = area.area_id;
                option.textContent = area.nombre;
                areaSelect.appendChild(option);
            }
        });
        
        // Agregar opción "Tics" por defecto si no existe
        const ticsOption = Array.from(areaSelect.options).find(opt => opt.textContent === 'Tics');
        if (!ticsOption) {
            const option = document.createElement('option');
            option.value = 'tics-default';
            option.textContent = 'Tics';
            areaSelect.appendChild(option);
        }
        
        areaSelect.disabled = false;
        addAreaBtn.disabled = false;
        
    } catch (error) {
        console.error('Error cargando áreas:', error);
        showToast('Error cargando áreas', 'error');
    }
}

function addNewEmpresaToEdit() {
    // Implementar si se necesita crear empresa desde edición
    showToast('Función de nueva empresa en edición en desarrollo', 'info');
}

function addNewSedeToEdit() {
    // Implementar si se necesita crear sede desde edición
    showToast('Función de nueva sede en edición en desarrollo', 'info');
}

function addNewAreaToEdit() {
    // Implementar si se necesita crear área desde edición
    showToast('Función de nueva área en edición en desarrollo', 'info');
}

function closeUserEditModal() {
    const modal = document.getElementById('user-registration-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Función para manejar el envío del formulario de edición
async function handleUserEdit(e) {
    e.preventDefault();
    
    const userIdField = document.getElementById('edit-user-id');
    
    if (!userIdField || !userIdField.value) {
        showToast('ID de usuario no encontrado', 'error');
        return;
    }
    
    const userId = userIdField.value;
    const formData = new FormData(e.target);
    const newIsActive = formData.get('is_active') === 'true';
    
    // Buscar el usuario original para comparar el estado
    const originalUser = allUsers.find(u => u.user_id === userId);
    
    // Verificar si el estado ha cambiado
    if (originalUser && originalUser.is_active !== newIsActive) {
        const actionText = newIsActive ? 'ACTIVAR' : 'DESACTIVAR';
        const message = newIsActive 
            ? `¿Estás seguro de que deseas ACTIVAR al usuario ${originalUser.nombres} ${originalUser.apellidos}?\n\nEl usuario podrá iniciar sesión nuevamente.`
            : `¿Estás seguro de que deseas DESACTIVAR al usuario ${originalUser.nombres} ${originalUser.apellidos}?\n\nEl usuario NO podrá iniciar sesión hasta ser reactivado.`;
        
        // Mostrar diálogo de confirmación
        const confirmed = confirm(`⚠️ CONFIRMACIÓN REQUERIDA\n\n${message}\n\n`);
        
        if (!confirmed) {
            // Usuario canceló, no enviar el formulario
            return;
        }
    }
    
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nombres: formData.get('nombres'),
                apellidos: formData.get('apellidos'),
                telefono: formData.get('telefono'),
                direccion: formData.get('direccion'),
                departamento: formData.get('departamento'),
                municipio: formData.get('municipio'),
                role: formData.get('role'),
                is_active: newIsActive,
                empresa_id: formData.get('empresa'),
                sede_id: formData.get('sede'),
                area_id: formData.get('area')
            }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error actualizando usuario');
        }
        
        showToast('Usuario actualizado exitosamente', 'success');
        closeUserEditModal();
        
    } catch (error) {
        console.error('Error actualizando usuario:', error);
        showToast(error.message || 'Error actualizando usuario', 'error');
    }
}

// Agregar estilos CSS dinámicamente para los badges de roles
const roleStyles = `
    <style>
    .role-badge {
        padding: 0.3rem 0.8rem;
        border-radius: 1rem;
        font-size: 1.1rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .role-admin {
        background: #dc3545;
        color: white;
    }
    .role-developer {
        background: #6f42c1;
        color: white;
    }
    .role-user {
        background: #28a745;
        color: white;
    }
    </style>
`;

document.head.insertAdjacentHTML('beforeend', roleStyles);

// Función global para mostrar toast (compatibilidad)
function showToast(message, type = 'info') {
    if (window.dashboard && typeof window.dashboard.showToast === 'function') {
        window.dashboard.showToast(message, type);
    } else {
        alert(message);
    }
}
