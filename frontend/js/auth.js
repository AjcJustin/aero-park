/**
 * AeroPark GOMA - Auth Service
 * Simple token-based authentication with auto-refresh
 */

const Auth = {
    TOKEN_KEY: 'aeropark_token',
    REFRESH_TOKEN_KEY: 'aeropark_refresh_token',
    TOKEN_EXPIRES_KEY: 'aeropark_token_expires',
    USER_KEY: 'aeropark_user',

    // ========================================
    // TOKEN MANAGEMENT
    // ========================================

    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    setToken(token, expiresIn) {
        localStorage.setItem(this.TOKEN_KEY, token);
        if (expiresIn) {
            // Store expiration time (current time + expiresIn seconds - 5 min buffer)
            var expiresAt = Date.now() + (expiresIn - 300) * 1000;
            localStorage.setItem(this.TOKEN_EXPIRES_KEY, expiresAt.toString());
        }
    },

    getRefreshToken() {
        return localStorage.getItem(this.REFRESH_TOKEN_KEY);
    },

    setRefreshToken(refreshToken) {
        localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);
    },

    isTokenExpired() {
        var expiresAt = localStorage.getItem(this.TOKEN_EXPIRES_KEY);
        if (!expiresAt) return true;
        return Date.now() >= parseInt(expiresAt, 10);
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
        localStorage.removeItem(this.REFRESH_TOKEN_KEY);
        localStorage.removeItem(this.TOKEN_EXPIRES_KEY);
        localStorage.removeItem(this.USER_KEY);
    },

    // ========================================
    // TOKEN REFRESH
    // ========================================

    async refreshTokenIfNeeded() {
        // Check if token needs refresh
        if (!this.isTokenExpired()) {
            return true; // Token still valid
        }

        var refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            console.log('[Auth] No refresh token, user needs to login again');
            return false;
        }

        try {
            console.log('[Auth] Token expired, refreshing...');
            var response = await fetch(API.BASE_URL + '/auth/refresh?refresh_token=' + encodeURIComponent(refreshToken), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            var data = await response.json();

            if (!response.ok || !data.success) {
                console.log('[Auth] Refresh failed, user needs to login again');
                this.clear();
                return false;
            }

            // Store new tokens
            this.setToken(data.token, parseInt(data.expires_in || 3600));
            if (data.refresh_token) {
                this.setRefreshToken(data.refresh_token);
            }
            
            console.log('[Auth] Token refreshed successfully');
            return true;
        } catch (error) {
            console.error('[Auth] Token refresh error:', error);
            return false;
        }
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

            // Store token, refresh token and user
            this.setToken(data.token, data.expires_in || 3600);
            if (data.refresh_token) {
                this.setRefreshToken(data.refresh_token);
            }
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

            // Store token, refresh token and user
            this.setToken(data.token, data.expires_in || 3600);
            if (data.refresh_token) {
                this.setRefreshToken(data.refresh_token);
            }
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
