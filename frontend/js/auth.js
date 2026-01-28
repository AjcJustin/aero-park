/**
 * AeroPark GOMA - Auth Service
 * Simple token-based authentication
 */

const Auth = {
    TOKEN_KEY: 'aeropark_token',
    USER_KEY: 'aeropark_user',

    // ========================================
    // TOKEN MANAGEMENT
    // ========================================

    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    setToken(token) {
        localStorage.setItem(this.TOKEN_KEY, token);
    },

    getUser() {
        const user = localStorage.getItem(this.USER_KEY);
        return user ? JSON.parse(user) : null;
    },

    setUser(user) {
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    isAdmin() {
        const user = this.getUser();
        return user && user.role === 'admin';
    },

    clear() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem(this.USER_KEY);
    },

    // ========================================
    // AUTH ACTIONS
    // ========================================

    async register(name, email, password) {
        try {
            const response = await fetch(API.BASE_URL + '/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });

            const data = await response.json();

            if (!response.ok) {
                return { success: false, message: data.detail || 'Erreur inscription' };
            }

            // Store token and user
            this.setToken(data.token);
            this.setUser(data.user);

            return { success: true, user: data.user };
        } catch (error) {
            return { success: false, message: error.message || 'Erreur de connexion' };
        }
    },

    async login(email, password) {
        try {
            const response = await fetch(API.BASE_URL + '/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (!response.ok) {
                return { success: false, message: data.detail || 'Email ou mot de passe incorrect' };
            }

            // Store token and user
            this.setToken(data.token);
            this.setUser(data.user);

            return { success: true, user: data.user };
        } catch (error) {
            return { success: false, message: error.message || 'Erreur de connexion' };
        }
    },

    logout() {
        this.clear();
        // Redirect to login - works from any page
        var currentPath = window.location.pathname;
        if (currentPath.indexOf('/admin/') !== -1) {
            window.location.href = 'login.html';
        } else if (currentPath.indexOf('/pages/') !== -1) {
            window.location.href = 'login.html';
        } else {
            window.location.href = 'pages/login.html';
        }
    },

    // ========================================
    // UI HELPERS
    // ========================================

    updateNavigation() {
        const authLinks = document.getElementById('auth-links');
        const userMenu = document.getElementById('user-menu');
        const userName = document.querySelector('.user-name');

        if (this.isLoggedIn()) {
            const user = this.getUser();
            if (authLinks) authLinks.classList.add('hidden');
            if (userMenu) userMenu.classList.remove('hidden');
            if (userName) userName.textContent = user?.name || user?.email || 'Utilisateur';
        } else {
            if (authLinks) authLinks.classList.remove('hidden');
            if (userMenu) userMenu.classList.add('hidden');
        }
    },

    requireAuth() {
        if (!this.isLoggedIn()) {
            sessionStorage.setItem('redirectAfterLogin', window.location.href);
            window.location.href = '/frontend/pages/login.html';
            return false;
        }
        return true;
    },

    requireAdmin() {
        if (!this.isLoggedIn() || !this.isAdmin()) {
            window.location.href = '/frontend/admin/login.html';
            return false;
        }
        return true;
    }
};
