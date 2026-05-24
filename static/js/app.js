/* ============================================================================
   ENTERPRISE HRIS - APPLICATION CORE
   API Client, Authentication, Utilities, and Global Functions
   ============================================================================ */

// API Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';
const PAGINATION_SIZE = 20;

// User Info from localStorage
let currentUser = null;

// Initialize app on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuthentication();
    updateActiveNavLink();
    initializeEventListeners();
    loadUserInfo();
});

// ============================================================================
// AUTHENTICATION & TOKEN MANAGEMENT
// ============================================================================

class AuthManager {
    static getAccessToken() {
        return localStorage.getItem('access_token');
    }

    static getRefreshToken() {
        return localStorage.getItem('refresh_token');
    }

    static setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    }

    static setUserInfo(user) {
        currentUser = user;
        localStorage.setItem('user_id', user.id);
        localStorage.setItem('user_email', user.email);
        localStorage.setItem('user_name', user.full_name);
        localStorage.setItem('is_hr_admin', user.is_hr_admin);
        localStorage.setItem('is_manager', user.is_manager);
    }

    static getUserInfo() {
        if (currentUser) return currentUser;

        currentUser = {
            id: localStorage.getItem('user_id'),
            email: localStorage.getItem('user_email'),
            name: localStorage.getItem('user_name'),
            isHRAdmin: localStorage.getItem('is_hr_admin') === 'true',
            isManager: localStorage.getItem('is_manager') === 'true'
        };
        return currentUser;
    }

    static isAuthenticated() {
        return !!this.getAccessToken();
    }

    static logout() {
        localStorage.clear();
        window.location.href = 'index.html';
    }

    static async refreshAccessToken() {
        try {
            const refresh = this.getRefreshToken();
            if (!refresh) {
                this.logout();
                return false;
            }

            const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh })
            });

            if (response.ok) {
                const data = await response.json();
                this.setTokens(data.access, refresh);
                return true;
            } else {
                this.logout();
                return false;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
            this.logout();
            return false;
        }
    }
}

// ============================================================================
// API REQUEST HANDLER
// ============================================================================

class APIClient {
    static getHeaders(includeAuth = true) {
        const headers = {
            'Content-Type': 'application/json'
        };

        if (includeAuth) {
            const token = AuthManager.getAccessToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
        }

        return headers;
    }

    static async request(endpoint, options = {}) {
        const method = options.method || 'GET';
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = this.getHeaders();

        const config = {
            method,
            headers,
            ...options
        };

        if (options.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body);
        }

        try {
            let response = await fetch(url, config);

            if (response.status === 401) {
                const refreshed = await AuthManager.refreshAccessToken();
                if (refreshed) {
                    const newHeaders = this.getHeaders();
                    config.headers = newHeaders;
                    response = await fetch(url, config);
                } else {
                    throw new Error('Authentication failed');
                }
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw {
                    status: response.status,
                    message: errorData.detail || errorData.message || response.statusText,
                    data: errorData
                };
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    static get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    static post(endpoint, body) {
        return this.request(endpoint, { method: 'POST', body });
    }

    static patch(endpoint, body) {
        return this.request(endpoint, { method: 'PATCH', body });
    }

    static delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    static async upload(endpoint, formData) {
        const token = AuthManager.getAccessToken();
        const headers = { 'Authorization': `Bearer ${token}` };

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers,
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw {
                status: response.status,
                message: errorData.detail || 'Upload failed'
            };
        }

        return await response.json();
    }
}

// ============================================================================
// NOTIFICATION SYSTEM
// ============================================================================

class Notification {
    static show(message, type = 'info', duration = 4000) {
        const notification = document.createElement('div');
        notification.className = `notification notification--${type}`;
        notification.innerHTML = `
            <div class="notification__content">
                <span class="notification__message">${escapeHtml(message)}</span>
                <button class="notification__close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;

        document.body.appendChild(notification);
        notification.offsetHeight; // Trigger reflow
        notification.classList.add('show');

        if (duration > 0) {
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }

        return notification;
    }

    static success(message) {
        return this.show(message, 'success');
    }

    static error(message) {
        return this.show(message, 'error');
    }

    static warning(message) {
        return this.show(message, 'warning');
    }

    static info(message) {
        return this.show(message, 'info');
    }
}

// ============================================================================
// MODAL SYSTEM
// ============================================================================

class Modal {
    static open(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            modal.focus();
        }
    }

    static close(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    static closeAll() {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }

    static create(title, content, actions = []) {
        const modalId = 'modal-' + Date.now();
        const modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal__overlay"></div>
            <div class="modal__content">
                <div class="modal__header">
                    <h2 class="modal__title">${escapeHtml(title)}</h2>
                    <button class="modal__close" onclick="Modal.close('${modalId}')">×</button>
                </div>
                <div class="modal__body">${content}</div>
                <div class="modal__footer">
                    ${actions.map(action =>
                        `<button class="btn btn--${action.type || 'secondary'}" onclick="${action.onClick}">${action.label}</button>`
                    ).join('')}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        return modalId;
    }

    static confirm(title, message, onConfirm, onCancel = null) {
        const modalId = this.create(title, message, [
            {
                label: 'Cancel',
                type: 'secondary',
                onClick: `Modal.close('${modalId}'); ${onCancel ? onCancel : ''}`
            },
            {
                label: 'Confirm',
                type: 'primary',
                onClick: `${onConfirm}; Modal.close('${modalId}');`
            }
        ]);
        this.open(modalId);
        return modalId;
    }
}

// ============================================================================
// FORM UTILITIES
// ============================================================================

class FormHandler {
    static getFormData(formElement) {
        const formData = new FormData(formElement);
        const data = {};
        formData.forEach((value, key) => {
            if (data[key]) {
                if (!Array.isArray(data[key])) {
                    data[key] = [data[key]];
                }
                data[key].push(value);
            } else {
                data[key] = value;
            }
        });
        return data;
    }

    static setFormData(formElement, data) {
        Object.keys(data).forEach(key => {
            const field = formElement.elements[key];
            if (field) {
                if (field.type === 'checkbox') {
                    field.checked = !!data[key];
                } else if (field.type === 'radio') {
                    formElement.querySelector(`input[name="${key}"][value="${data[key]}"]`).checked = true;
                } else {
                    field.value = data[key] || '';
                }
            }
        });
    }

    static showErrors(formElement, errors) {
        formElement.querySelectorAll('.form-error').forEach(el => el.remove());

        Object.keys(errors).forEach(field => {
            const input = formElement.elements[field];
            if (input) {
                const errorMsg = document.createElement('div');
                errorMsg.className = 'form-error';
                errorMsg.textContent = Array.isArray(errors[field]) ? errors[field][0] : errors[field];
                input.parentElement.appendChild(errorMsg);
                input.classList.add('input-error');
            }
        });
    }

    static clearErrors(formElement) {
        formElement.querySelectorAll('.form-error').forEach(el => el.remove());
        formElement.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
    }
}

// ============================================================================
// DATA TABLE UTILITIES
// ============================================================================

class DataTable {
    constructor(containerId, columns) {
        this.container = document.getElementById(containerId);
        this.columns = columns;
        this.data = [];
        this.currentPage = 1;
        this.pageSize = PAGINATION_SIZE;
        this.totalItems = 0;
    }

    render(data, total = data.length) {
        this.data = data;
        this.totalItems = total;

        const table = document.createElement('table');
        table.className = 'data-table';

        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        this.columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col.label;
            th.style.width = col.width || 'auto';
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        data.forEach((row, idx) => {
            const tr = document.createElement('tr');
            this.columns.forEach(col => {
                const td = document.createElement('td');
                if (col.render) {
                    td.innerHTML = col.render(row, idx);
                } else if (col.field) {
                    td.textContent = getNestedProperty(row, col.field) || '-';
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);

        this.container.innerHTML = '';
        this.container.appendChild(table);
    }

    showLoading() {
        this.container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
    }

    showEmpty() {
        this.container.innerHTML = '<div class="empty-state"><p>No data available</p></div>';
    }

    showError(message) {
        this.container.innerHTML = `<div class="error-state"><p>${escapeHtml(message)}</p></div>`;
    }
}

// ============================================================================
// FORMAT & UTILITY FUNCTIONS
// ============================================================================

function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0
    }).format(value);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatDateTime(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatTime(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getStatusBadge(status) {
    const statusMap = {
        'active': 'success',
        'pending': 'warning',
        'approved': 'success',
        'rejected': 'danger',
        'inactive': 'secondary',
        'completed': 'success',
        'failed': 'danger',
        'processing': 'info'
    };

    const type = statusMap[status] || 'secondary';
    return `<span class="badge badge--${type}">${escapeHtml(status)}</span>`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getNestedProperty(obj, path) {
    return path.split('.').reduce((current, prop) => current?.[prop], obj);
}

function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

function getDaysBetween(startDate, endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diffTime = Math.abs(end - start);
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
}

// ============================================================================
// AUTHENTICATION CHECK & PAGE INITIALIZATION
// ============================================================================

function checkAuthentication() {
    const publicPages = ['index.html', ''];
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';

    const isPublicPage = publicPages.includes(currentPage);
    const isAuthenticated = AuthManager.isAuthenticated();

    if (!isAuthenticated && !isPublicPage) {
        window.location.href = 'index.html';
    } else if (isAuthenticated && publicPages.includes(currentPage)) {
        window.location.href = 'dashboard.html';
    }
}

function loadUserInfo() {
    const user = AuthManager.getUserInfo();
    const userElement = document.getElementById('userInfo');
    if (userElement && user.name) {
        userElement.textContent = user.name;
    }

    // Show/hide admin-only elements
    if (user.isHRAdmin) {
        document.querySelectorAll('[data-admin-only]').forEach(el => {
            el.style.display = '';
        });
    } else {
        document.querySelectorAll('[data-admin-only]').forEach(el => {
            el.style.display = 'none';
        });
    }

    // Show/hide manager-only elements
    if (user.isManager) {
        document.querySelectorAll('[data-manager-only]').forEach(el => {
            el.style.display = '';
        });
    } else {
        document.querySelectorAll('[data-manager-only]').forEach(el => {
            el.style.display = 'none';
        });
    }
}

function updateActiveNavLink() {
    const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
    document.querySelectorAll('.sidebar__link, .sidebar-nav a').forEach(link => {
        const href = link.getAttribute('href');
        link.classList.toggle('active', href === currentPage || href === currentPage.split('?')[0]);
    });
}

// ============================================================================
// SIDEBAR TOGGLE
// ============================================================================

function initializeEventListeners() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            const isClickInsideSidebar = sidebar?.contains(e.target);
            const isClickOnToggle = sidebarToggle?.contains(e.target);

            if (!isClickInsideSidebar && !isClickOnToggle && window.innerWidth <= 768) {
                sidebar?.classList.add('hidden');
            }
        });
    }

    // Modal close on overlay click
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal') || e.target.classList.contains('modal__overlay')) {
            const modal = e.target.closest('.modal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        }
    });

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            Modal.closeAll();
        }
    });
}

// ============================================================================
// EXPORT GLOBAL FUNCTIONS
// ============================================================================

window.APIClient = APIClient;
window.AuthManager = AuthManager;
window.Notification = Notification;
window.Modal = Modal;
window.FormHandler = FormHandler;
window.DataTable = DataTable;
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.formatTime = formatTime;
window.getStatusBadge = getStatusBadge;
window.debounce = debounce;
window.getDaysBetween = getDaysBetween;

window.logout = function() {
    if (confirm('Are you sure you want to logout?')) {
        AuthManager.logout();
    }
};
