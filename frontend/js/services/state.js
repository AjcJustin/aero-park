/**
 * AeroPark GOMA - State Management Service
 * Handles local storage, offline data, and app state
 */

const StateService = {
    // State keys
    KEYS: {
        USER: 'aeropark_user',
        TOKEN: 'aeropark_token',
        ROLE: 'aeropark_role',
        LAST_RESERVATION: 'aeropark_last_reservation',
        LAST_ACCESS_CODE: 'aeropark_last_access_code',
        PARKING_CACHE: 'aeropark_parking_cache',
        SETTINGS: 'aeropark_settings',
        PENDING_ACTIONS: 'aeropark_pending_actions'
    },
    
    // In-memory state
    state: {
        isOnline: navigator.onLine,
        parkingSpots: [],
        myReservations: [],
        myPayments: [],
        myAccessCodes: []
    },
    
    // State change listeners
    listeners: {},
    
    /**
     * Initialize state service
     */
    init() {
        // Load cached state
        this.loadCachedState();
        
        // Setup online/offline listeners
        window.addEventListener('online', () => this.handleOnlineStatus(true));
        window.addEventListener('offline', () => this.handleOnlineStatus(false));
        
        console.log('[State] Initialized, online:', this.state.isOnline);
    },
    
    /**
     * Handle online/offline status change
     */
    handleOnlineStatus(isOnline) {
        this.state.isOnline = isOnline;
        this.notify('onlineStatus', isOnline);
        
        // Show/hide offline banner
        const banner = document.querySelector('.offline-banner');
        if (banner) {
            banner.classList.toggle('active', !isOnline);
        }
        
        // Sync pending actions when back online
        if (isOnline) {
            this.syncPendingActions();
        }
        
        console.log('[State] Online status:', isOnline);
    },
    
    /**
     * Load cached state from localStorage
     */
    loadCachedState() {
        // Load parking cache
        const parkingCache = this.get(this.KEYS.PARKING_CACHE);
        if (parkingCache) {
            this.state.parkingSpots = parkingCache;
        }
        
        // Load last reservation for offline display
        const lastReservation = this.get(this.KEYS.LAST_RESERVATION);
        if (lastReservation) {
            this.state.lastReservation = lastReservation;
        }
        
        // Load last access code for offline display
        const lastAccessCode = this.get(this.KEYS.LAST_ACCESS_CODE);
        if (lastAccessCode) {
            this.state.lastAccessCode = lastAccessCode;
        }
    },
    
    // ==========================================
    // LOCAL STORAGE OPERATIONS
    // ==========================================
    
    /**
     * Get item from localStorage
     */
    get(key) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : null;
        } catch (error) {
            console.error('[State] Get error:', error);
            return null;
        }
    },
    
    /**
     * Set item in localStorage
     */
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (error) {
            console.error('[State] Set error:', error);
            return false;
        }
    },
    
    /**
     * Remove item from localStorage
     */
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (error) {
            console.error('[State] Remove error:', error);
            return false;
        }
    },
    
    /**
     * Clear all app data
     */
    clearAll() {
        Object.values(this.KEYS).forEach(key => {
            localStorage.removeItem(key);
        });
        this.state = {
            isOnline: navigator.onLine,
            parkingSpots: [],
            myReservations: [],
            myPayments: [],
            myAccessCodes: []
        };
    },
    
    // ==========================================
    // PARKING STATE
    // ==========================================
    
    /**
     * Cache parking spots
     */
    cacheParkingSpots(spots) {
        this.state.parkingSpots = spots;
        this.set(this.KEYS.PARKING_CACHE, {
            spots,
            timestamp: Date.now()
        });
        this.notify('parkingSpots', spots);
    },
    
    /**
     * Get cached parking spots
     */
    getCachedParkingSpots() {
        const cache = this.get(this.KEYS.PARKING_CACHE);
        if (cache && cache.spots) {
            // Check if cache is less than 5 minutes old
            const isValid = Date.now() - cache.timestamp < 5 * 60 * 1000;
            return { spots: cache.spots, isValid };
        }
        return { spots: [], isValid: false };
    },
    
    // ==========================================
    // RESERVATION STATE
    // ==========================================
    
    /**
     * Save last reservation for offline access
     */
    saveLastReservation(reservation) {
        this.state.lastReservation = reservation;
        this.set(this.KEYS.LAST_RESERVATION, {
            ...reservation,
            cachedAt: Date.now()
        });
        this.notify('lastReservation', reservation);
    },
    
    /**
     * Get last reservation
     */
    getLastReservation() {
        return this.state.lastReservation || this.get(this.KEYS.LAST_RESERVATION);
    },
    
    // ==========================================
    // ACCESS CODE STATE
    // ==========================================
    
    /**
     * Save last access code for offline display
     */
    saveLastAccessCode(accessCode) {
        this.state.lastAccessCode = accessCode;
        this.set(this.KEYS.LAST_ACCESS_CODE, {
            ...accessCode,
            cachedAt: Date.now()
        });
        this.notify('lastAccessCode', accessCode);
    },
    
    /**
     * Get last access code
     */
    getLastAccessCode() {
        const code = this.state.lastAccessCode || this.get(this.KEYS.LAST_ACCESS_CODE);
        if (code) {
            // Check if code is still valid
            const expiresAt = new Date(code.expires_at).getTime();
            if (Date.now() < expiresAt) {
                return code;
            }
        }
        return null;
    },
    
    // ==========================================
    // OFFLINE ACTIONS
    // ==========================================
    
    /**
     * Queue action for later sync
     */
    queueAction(action) {
        const pending = this.get(this.KEYS.PENDING_ACTIONS) || [];
        pending.push({
            ...action,
            id: Date.now(),
            queuedAt: Date.now()
        });
        this.set(this.KEYS.PENDING_ACTIONS, pending);
        
        console.log('[State] Action queued:', action.type);
    },
    
    /**
     * Sync pending actions when online
     */
    async syncPendingActions() {
        const pending = this.get(this.KEYS.PENDING_ACTIONS) || [];
        if (pending.length === 0) return;
        
        console.log('[State] Syncing', pending.length, 'pending actions');
        
        for (const action of pending) {
            try {
                await this.executeAction(action);
                // Remove from pending
                const remaining = this.get(this.KEYS.PENDING_ACTIONS) || [];
                this.set(this.KEYS.PENDING_ACTIONS, remaining.filter(a => a.id !== action.id));
            } catch (error) {
                console.error('[State] Sync action failed:', error);
            }
        }
    },
    
    /**
     * Execute a pending action
     */
    async executeAction(action) {
        switch (action.type) {
            case 'CREATE_RESERVATION':
                await ApiService.createReservation(action.data);
                break;
            case 'CANCEL_RESERVATION':
                await ApiService.cancelReservation(action.data.reservationId);
                break;
            default:
                console.warn('[State] Unknown action type:', action.type);
        }
    },
    
    // ==========================================
    // SETTINGS
    // ==========================================
    
    /**
     * Get app settings
     */
    getSettings() {
        return this.get(this.KEYS.SETTINGS) || {
            notifications: true,
            darkMode: false,
            language: 'en'
        };
    },
    
    /**
     * Update settings
     */
    updateSettings(updates) {
        const settings = this.getSettings();
        const newSettings = { ...settings, ...updates };
        this.set(this.KEYS.SETTINGS, newSettings);
        this.notify('settings', newSettings);
        return newSettings;
    },
    
    // ==========================================
    // EVENT SYSTEM
    // ==========================================
    
    /**
     * Subscribe to state changes
     */
    subscribe(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
        
        // Return unsubscribe function
        return () => {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        };
    },
    
    /**
     * Notify listeners of state change
     */
    notify(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => callback(data));
        }
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => StateService.init());

// Export for use in other modules
window.StateService = StateService;
