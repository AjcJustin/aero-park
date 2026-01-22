/**
 * AeroPark GOMA - API Service
 * Handles all HTTP requests to the backend API
 */

const API_BASE_URL = 'http://localhost:8000/api';

// API Configuration
const ApiService = {
    baseUrl: API_BASE_URL,
    
    /**
     * Get authorization headers
     */
    getAuthHeaders() {
        const token = localStorage.getItem('aeropark_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },
    
    /**
     * Make HTTP request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const defaultHeaders = {
            'Content-Type': 'application/json',
            ...this.getAuthHeaders()
        };
        
        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...options.headers
            }
        };
        
        try {
            // Check if online
            if (!navigator.onLine) {
                throw new Error('You are currently offline');
            }
            
            const response = await fetch(url, config);
            
            // Handle non-JSON responses
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return { success: true };
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || data.message || `Request failed with status ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error('[API] Request failed:', error);
            throw error;
        }
    },
    
    // ==========================================
    // HEALTH CHECK
    // ==========================================
    
    async healthCheck() {
        return this.request('/health');
    },
    
    // ==========================================
    // PARKING ENDPOINTS
    // ==========================================
    
    /**
     * Get all parking spots
     */
    async getParkingSpots() {
        return this.request('/parking/spots');
    },
    
    /**
     * Get parking availability summary
     */
    async getParkingAvailability() {
        return this.request('/parking/availability');
    },
    
    /**
     * Get specific parking spot
     */
    async getParkingSpot(spotId) {
        return this.request(`/parking/spots/${spotId}`);
    },
    
    /**
     * Get real-time parking status (public)
     */
    async getParkingStatus() {
        return this.request('/parking/status');
    },
    
    // ==========================================
    // RESERVATION ENDPOINTS
    // ==========================================
    
    /**
     * Create a new reservation
     */
    async createReservation(data) {
        return this.request('/reservations', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * Get my reservations
     */
    async getMyReservations() {
        return this.request('/reservations/my');
    },
    
    /**
     * Get reservation by ID
     */
    async getReservation(reservationId) {
        return this.request(`/reservations/${reservationId}`);
    },
    
    /**
     * Cancel a reservation
     */
    async cancelReservation(reservationId) {
        return this.request(`/reservations/${reservationId}/cancel`, {
            method: 'POST'
        });
    },
    
    /**
     * Extend a reservation
     */
    async extendReservation(reservationId, newEndTime) {
        return this.request(`/reservations/${reservationId}/extend`, {
            method: 'POST',
            body: JSON.stringify({ new_end_time: newEndTime })
        });
    },
    
    // ==========================================
    // ACCESS CODE ENDPOINTS
    // ==========================================
    
    /**
     * Generate access code for a reservation
     */
    async generateAccessCode(reservationId, codeType = 'entry') {
        return this.request(`/access/generate/${reservationId}`, {
            method: 'POST',
            body: JSON.stringify({ code_type: codeType })
        });
    },
    
    /**
     * Validate an access code
     */
    async validateAccessCode(code) {
        return this.request(`/access/validate/${code}`, {
            method: 'POST'
        });
    },
    
    /**
     * Get my access codes
     */
    async getMyAccessCodes() {
        return this.request('/access/my-codes');
    },
    
    // ==========================================
    // PAYMENT ENDPOINTS
    // ==========================================
    
    /**
     * Calculate payment amount for a reservation
     */
    async calculatePayment(reservationId) {
        return this.request(`/payments/calculate/${reservationId}`);
    },
    
    /**
     * Process a payment
     */
    async processPayment(data) {
        return this.request('/payments', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * Get my payments
     */
    async getMyPayments() {
        return this.request('/payments/my');
    },
    
    /**
     * Get payment by ID
     */
    async getPayment(paymentId) {
        return this.request(`/payments/${paymentId}`);
    },
    
    // ==========================================
    // USER PROFILE ENDPOINTS
    // ==========================================
    
    /**
     * Get current user profile
     */
    async getProfile() {
        return this.request('/users/me');
    },
    
    /**
     * Update user profile
     */
    async updateProfile(data) {
        return this.request('/users/me', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // ==========================================
    // ADMIN ENDPOINTS
    // ==========================================
    
    /**
     * Get admin dashboard stats
     */
    async getAdminStats() {
        return this.request('/admin/stats');
    },
    
    /**
     * Get all reservations (admin)
     */
    async getAllReservations(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/reservations${queryString ? '?' + queryString : ''}`);
    },
    
    /**
     * Get all payments (admin)
     */
    async getAllPayments(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/payments${queryString ? '?' + queryString : ''}`);
    },
    
    /**
     * Get all users (admin)
     */
    async getAllUsers(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/users${queryString ? '?' + queryString : ''}`);
    },
    
    /**
     * Update parking spot status (admin)
     */
    async updateParkingSpot(spotId, data) {
        return this.request(`/admin/parking/spots/${spotId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * Create parking spot (admin)
     */
    async createParkingSpot(data) {
        return this.request('/admin/parking/spots', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * Delete parking spot (admin)
     */
    async deleteParkingSpot(spotId) {
        return this.request(`/admin/parking/spots/${spotId}`, {
            method: 'DELETE'
        });
    },
    
    /**
     * Get system status (admin)
     */
    async getSystemStatus() {
        return this.request('/admin/system/status');
    },
    
    /**
     * Get audit logs (admin)
     */
    async getAuditLogs(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/audit-logs${queryString ? '?' + queryString : ''}`);
    }
};

// Export for use in other modules
window.ApiService = ApiService;
