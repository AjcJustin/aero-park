/**
 * AeroPark GOMA - API Service
 * Handles all HTTP requests to the backend API
 * 
 * Backend Routes:
 * - /users/* - Auth & Profile
 * - /parking/* - Parking management
 * - /admin/parking/* - Admin operations
 * - /api/v1/access/* - Access code validation
 * - /api/v1/barrier/* - Barrier control
 * - /api/v1/payment/* - Payment processing
 */

const API_BASE_URL = 'http://localhost:8000';

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
                throw new Error('Vous êtes actuellement hors ligne');
            }
            
            const response = await fetch(url, config);
            
            // Handle non-JSON responses
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                if (!response.ok) {
                    throw new Error(`Erreur HTTP! Status: ${response.status}`);
                }
                return { success: true };
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || data.message || `Requête échouée avec status ${response.status}`);
            }
            
            return data;
        } catch (error) {
            console.error('[API] Requête échouée:', error);
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
    // PARKING ENDPOINTS - /parking/*
    // ==========================================
    
    /**
     * Get parking status with all spots
     */
    async getParkingSpots() {
        const data = await this.request('/parking/status');
        // Normalize the response to return spots array
        return data.places || data.spots || [];
    },
    
    /**
     * Get parking availability summary
     */
    async getParkingAvailability() {
        return this.request('/parking/available');
    },
    
    /**
     * Get specific parking spot
     */
    async getParkingSpot(spotId) {
        return this.request(`/parking/place/${spotId}`);
    },
    
    /**
     * Get real-time parking status (public)
     */
    async getParkingStatus() {
        return this.request('/parking/status');
    },
    
    // ==========================================
    // RESERVATION ENDPOINTS - /parking/*
    // ==========================================
    
    /**
     * Create a new reservation
     */
    async createReservation(data) {
        return this.request('/parking/reserve', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * Get my reservations
     */
    async getMyReservations() {
        return this.request('/users/me/reservation');
    },
    
    /**
     * Get reservation by ID
     */
    async getReservation(reservationId) {
        return this.request(`/parking/reservation/${reservationId}`);
    },
    
    /**
     * Cancel a reservation
     */
    async cancelReservation(reservationId) {
        return this.request(`/parking/cancel/${reservationId}`, {
            method: 'POST'
        });
    },
    
    /**
     * Extend a reservation
     */
    async extendReservation(reservationId, newEndTime) {
        return this.request(`/parking/extend/${reservationId}`, {
            method: 'POST',
            body: JSON.stringify({ new_end_time: newEndTime })
        });
    },
    
    // ==========================================
    // ACCESS CODE ENDPOINTS - /api/v1/access/*
    // ==========================================
    
    /**
     * Generate access code for a reservation
     */
    async generateAccessCode(reservationId, codeType = 'entry') {
        return this.request(`/api/v1/access/generate/${reservationId}`, {
            method: 'POST',
            body: JSON.stringify({ code_type: codeType })
        });
    },
    
    /**
     * Validate an access code (for entry/exit)
     */
    async validateAccessCode(code, sensorPresence = true, barrierId = 'entry') {
        return this.request('/api/v1/access/validate-code', {
            method: 'POST',
            body: JSON.stringify({
                code: code,
                sensor_presence: sensorPresence,
                barrier_id: barrierId
            })
        });
    },
    
    /**
     * Check entry access (auto or with code)
     */
    async checkEntryAccess(accessCode = null) {
        const params = new URLSearchParams({ sensor_presence: 'true' });
        if (accessCode) params.append('access_code', accessCode);
        return this.request(`/api/v1/access/check-entry?${params}`, {
            method: 'POST'
        });
    },
    
    /**
     * Get my access codes
     */
    async getMyAccessCodes() {
        return this.request('/admin/parking/access-codes');
    },
    
    // ==========================================
    // PAYMENT ENDPOINTS - /api/v1/payment/*
    // ==========================================
    
    /**
     * Get pricing information
     */
    async getPricing() {
        return this.request('/api/v1/payment/pricing');
    },
    
    /**
     * Calculate payment amount for duration
     */
    async calculatePayment(hours, minutes = 0) {
        return this.request(`/api/v1/payment/calculate?hours=${hours}&minutes=${minutes}`, {
            method: 'POST'
        });
    },
    
    /**
     * Simulate payment (Orange Money, Airtel Money, M-Pesa)
     */
    async processPayment(data) {
        return this.request('/api/v1/payment/simulate', {
            method: 'POST',
            body: JSON.stringify({
                place_id: data.place_id || data.spot_id,
                duration_minutes: data.duration_minutes,
                method: data.method || data.provider, // ORANGE_MONEY, AIRTEL_MONEY, MPESA
                simulate_failure: data.simulate_failure || false
            })
        });
    },
    
    /**
     * Process Mobile Money payment
     */
    async processMobileMoneyPayment(provider, phoneNumber, amount, reservationId) {
        return this.request('/api/v1/payment/mobile-money', {
            method: 'POST',
            body: JSON.stringify({
                provider: provider, // ORANGE_MONEY, AIRTEL_MONEY, MPESA
                phone_number: phoneNumber,
                amount: amount,
                reservation_id: reservationId
            })
        });
    },
    
    /**
     * Get my payments
     */
    async getMyPayments() {
        return this.request('/api/v1/payment/history');
    },
    
    /**
     * Get payment by ID
     */
    async getPayment(paymentId) {
        return this.request(`/api/v1/payment/${paymentId}`);
    },
    
    // ==========================================
    // USER PROFILE ENDPOINTS - /users/*
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
        const params = new URLSearchParams();
        if (data.display_name) params.append('display_name', data.display_name);
        if (data.vehicle_plate) params.append('vehicle_plate', data.vehicle_plate);
        return this.request(`/users/me/profile?${params}`, {
            method: 'PUT'
        });
    },
    
    /**
     * Get current user's active reservation
     */
    async getMyActiveReservation() {
        return this.request('/users/me/reservation');
    },
    
    // ==========================================
    // ADMIN ENDPOINTS - /admin/parking/*
    // ==========================================
    
    /**
     * Get admin dashboard stats
     */
    async getAdminStats() {
        return this.request('/admin/parking/stats');
    },
    
    /**
     * Get all parking places (admin)
     */
    async getAllParkingPlaces() {
        return this.request('/admin/parking/all');
    },
    
    /**
     * Get all access codes (admin)
     */
    async getAllAccessCodes(statusFilter = null) {
        const params = statusFilter ? `?status_filter=${statusFilter}` : '';
        return this.request(`/admin/parking/access-codes${params}`);
    },
    
    /**
     * Force release a parking spot (admin)
     */
    async forceRelease(placeId, reason = null) {
        const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
        return this.request(`/admin/parking/force-release/${placeId}${params}`, {
            method: 'POST'
        });
    },
    
    /**
     * Invalidate an access code (admin)
     */
    async invalidateAccessCode(code, reason = null) {
        return this.request(`/admin/parking/access-codes/${code}/invalidate`, {
            method: 'POST',
            body: JSON.stringify({ reason: reason })
        });
    },
    
    /**
     * Initialize parking places (admin)
     */
    async initializePlaces(count = 6) {
        return this.request(`/admin/parking/initialize?count=${count}`, {
            method: 'POST'
        });
    },
    
    /**
     * Get all reservations (admin)
     */
    async getAllReservations(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/parking/reservations${queryString ? '?' + queryString : ''}`);
    },
    
    /**
     * Get all payments (admin)
     */
    async getAllPayments(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/parking/payments${queryString ? '?' + queryString : ''}`);
    },
    
    /**
     * Get all users (admin)
     */
    async getAllUsers(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/parking/users${queryString ? '?' + queryString : ''}`);
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
        return this.request('/health');
    },
    
    /**
     * Get audit logs (admin)
     */
    async getAuditLogs(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/admin/parking/audit-logs${queryString ? '?' + queryString : ''}`);
    },
    
    // ==========================================
    // BARRIER ENDPOINTS - /api/v1/barrier/*
    // ==========================================
    
    /**
     * Get barrier status
     */
    async getBarrierStatus(barrierId = 'entry') {
        return this.request(`/api/v1/barrier/status?barrier_id=${barrierId}`);
    },
    
    /**
     * Open barrier
     */
    async openBarrier(barrierId = 'entry', reason = 'manual') {
        return this.request('/api/v1/barrier/open', {
            method: 'POST',
            body: JSON.stringify({
                barrier_id: barrierId,
                reason: reason
            })
        });
    }
};

// Export for use in other modules
window.ApiService = ApiService;
