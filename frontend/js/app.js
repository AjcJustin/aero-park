/**
 * AeroPark GOMA - Main Application
 * PWA Initialization and Router
 */

const App = {
    /**
     * Initialize the application
     */
    async init() {
        console.log('[App] Initializing AeroPark GOMA...');
        
        // Register service worker
        await this.registerServiceWorker();
        
        // Initialize services
        StateService.init();
        NotificationService.init();
        
        // Initialize auth (requires Firebase SDK)
        if (typeof firebase !== 'undefined') {
            await AuthService.init();
        } else {
            console.warn('[App] Firebase SDK not loaded - using demo mode');
            this.initDemoMode();
        }
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Check for PWA install prompt
        this.setupPWAInstall();
        
        // Update UI based on auth state
        this.updateAuthUI();
        
        // Load initial data
        await this.loadInitialData();
        
        console.log('[App] Initialization complete');
    },
    
    /**
     * Register service worker for PWA
     */
    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/frontend/service-worker.js', {
                    scope: '/frontend/'
                });
                
                console.log('[App] Service Worker registered:', registration.scope);
                
                // Handle updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            this.showUpdateAvailable();
                        }
                    });
                });
            } catch (error) {
                console.error('[App] Service Worker registration failed:', error);
            }
        }
    },
    
    /**
     * Show update available notification
     */
    showUpdateAvailable() {
        const update = confirm('A new version of AeroPark is available. Reload to update?');
        if (update) {
            window.location.reload();
        }
    },
    
    /**
     * Setup PWA install prompt
     */
    setupPWAInstall() {
        let deferredPrompt;
        
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            
            // Show install button
            const installBtn = document.getElementById('install-btn');
            if (installBtn) {
                installBtn.style.display = 'block';
                installBtn.addEventListener('click', async () => {
                    deferredPrompt.prompt();
                    const { outcome } = await deferredPrompt.userChoice;
                    console.log('[App] Install prompt outcome:', outcome);
                    deferredPrompt = null;
                    installBtn.style.display = 'none';
                });
            }
        });
        
        window.addEventListener('appinstalled', () => {
            console.log('[App] PWA installed');
            NotificationService.success('AeroPark has been installed!', 'App Installed');
        });
    },
    
    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Online/offline status
        window.addEventListener('online', () => {
            NotificationService.backOnline();
        });
        
        window.addEventListener('offline', () => {
            NotificationService.offlineMode();
        });
        
        // Auth state changes
        if (typeof AuthService !== 'undefined') {
            AuthService.onAuthStateChanged((user) => {
                this.updateAuthUI();
            });
        }
        
        // Navigation toggle for mobile
        const navToggle = document.querySelector('.nav-toggle');
        const navMenu = document.querySelector('.nav-menu');
        
        if (navToggle && navMenu) {
            navToggle.addEventListener('click', () => {
                navMenu.classList.toggle('active');
            });
        }
        
        // Sidebar toggle for mobile
        const sidebarToggle = document.querySelector('.sidebar-toggle');
        const sidebar = document.querySelector('.sidebar');
        
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('active');
            });
        }
        
        // Close mobile menu when clicking outside
        document.addEventListener('click', (e) => {
            if (navMenu && !navMenu.contains(e.target) && !navToggle?.contains(e.target)) {
                navMenu.classList.remove('active');
            }
            if (sidebar && !sidebar.contains(e.target) && !sidebarToggle?.contains(e.target)) {
                sidebar.classList.remove('active');
            }
        });
        
        // Logout button
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                await this.handleLogout();
            });
        }
    },
    
    /**
     * Update UI based on authentication state
     */
    updateAuthUI() {
        const isAuthenticated = AuthService?.isAuthenticated() || localStorage.getItem('aeropark_token');
        const isAdmin = AuthService?.isAdmin() || localStorage.getItem('aeropark_role') === 'admin';
        const user = AuthService?.getCurrentUser();
        
        // Update body class for role-based CSS
        document.body.classList.remove('role-admin', 'role-user', 'role-guest');
        if (isAuthenticated) {
            document.body.classList.add(isAdmin ? 'role-admin' : 'role-user');
        } else {
            document.body.classList.add('role-guest');
        }
        
        // Update navigation visibility
        document.querySelectorAll('.auth-only').forEach(el => {
            el.style.display = isAuthenticated ? '' : 'none';
        });
        
        document.querySelectorAll('.guest-only').forEach(el => {
            el.style.display = isAuthenticated ? 'none' : '';
        });
        
        document.querySelectorAll('.admin-only').forEach(el => {
            el.style.display = isAdmin ? '' : 'none';
        });
        
        // Update user info display
        const userNameEl = document.querySelector('.user-name');
        const userEmailEl = document.querySelector('.user-email');
        const userAvatarEl = document.querySelector('.user-avatar');
        
        if (user) {
            if (userNameEl) userNameEl.textContent = user.displayName || 'User';
            if (userEmailEl) userEmailEl.textContent = user.email;
            if (userAvatarEl && user.photoURL) {
                userAvatarEl.src = user.photoURL;
            }
        }
    },
    
    /**
     * Initialize demo mode (when Firebase is not available)
     */
    initDemoMode() {
        console.log('[App] Running in demo mode');
        
        // Create demo user
        const demoUser = {
            uid: 'demo-user',
            email: 'demo@aeropark.com',
            displayName: 'Demo User',
            role: 'user'
        };
        
        localStorage.setItem('aeropark_user', JSON.stringify(demoUser));
        localStorage.setItem('aeropark_role', 'user');
        
        // Mock AuthService methods
        window.AuthService = {
            isAuthenticated: () => true,
            isAdmin: () => false,
            getCurrentUser: () => demoUser,
            onAuthStateChanged: (callback) => {
                callback(demoUser);
                return () => {};
            },
            logout: async () => {
                localStorage.removeItem('aeropark_user');
                localStorage.removeItem('aeropark_token');
                localStorage.removeItem('aeropark_role');
                window.location.href = '/frontend/pages/public/login.html';
            }
        };
    },
    
    /**
     * Load initial data
     */
    async loadInitialData() {
        if (!navigator.onLine) {
            console.log('[App] Offline - loading cached data');
            return;
        }
        
        try {
            // Load parking availability if on home page
            if (window.location.pathname.includes('index.html') || window.location.pathname.endsWith('/frontend/')) {
                const spots = await ApiService.getParkingSpots();
                StateService.cacheParkingSpots(spots);
            }
        } catch (error) {
            console.error('[App] Failed to load initial data:', error);
        }
    },
    
    /**
     * Handle logout
     */
    async handleLogout() {
        try {
            await AuthService.logout();
            StateService.clearAll();
            NotificationService.info('You have been logged out', 'Goodbye!');
            window.location.href = '/frontend/pages/public/login.html';
        } catch (error) {
            console.error('[App] Logout failed:', error);
            NotificationService.error('Logout failed. Please try again.');
        }
    },
    
    /**
     * Navigate to a page
     */
    navigateTo(path) {
        window.location.href = path;
    },
    
    /**
     * Check if user is on a protected route
     */
    checkAuth() {
        const publicPaths = [
            '/frontend/index.html',
            '/frontend/',
            '/frontend/pages/public/login.html',
            '/frontend/pages/public/register.html',
            '/frontend/pages/offline.html'
        ];
        
        const currentPath = window.location.pathname;
        const isPublicPage = publicPaths.some(path => currentPath.endsWith(path) || currentPath === path);
        
        if (!isPublicPage && !AuthService?.isAuthenticated()) {
            window.location.href = '/frontend/pages/public/login.html';
            return false;
        }
        
        // Check admin routes
        if (currentPath.includes('/pages/admin/') && !AuthService?.isAdmin()) {
            window.location.href = '/frontend/pages/user/dashboard.html';
            return false;
        }
        
        return true;
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export for use in other modules
window.App = App;
