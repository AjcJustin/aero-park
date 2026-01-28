/**
 * AeroPark GOMA - API Service
 * Simple fetch wrapper for all backend API calls
 */

var API = {
    BASE_URL: 'http://localhost:8000',

    // Get stored token
    getToken: function() {
        return localStorage.getItem('aeropark_token');
    },

    // Make API request
    request: async function(endpoint, options) {
        options = options || {};
        var url = this.BASE_URL + endpoint;
        var token = this.getToken();

        var headers = {
            'Content-Type': 'application/json'
        };
        
        if (token) {
            headers['Authorization'] = 'Bearer ' + token;
        }

        var config = {
            method: options.method || 'GET',
            headers: headers
        };

        if (options.body) {
            config.body = JSON.stringify(options.body);
        }

        try {
            var response = await fetch(url, config);
            var data = await response.json().catch(function() { return {}; });

            if (!response.ok) {
                throw { 
                    status: response.status, 
                    message: data.detail || 'Erreur serveur',
                    data: data
                };
            }

            return data;
        } catch (error) {
            if (error.status) throw error;
            throw { status: 0, message: 'Erreur réseau - vérifiez votre connexion' };
        }
    },

    // ========================================
    // PARKING (Public + Auth)
    // ========================================

    // GET /parking/status - Get all parking places status
    getParkingStatus: function() {
        return this.request('/parking/status');
    },

    // GET /parking/available - Get available places only
    getAvailablePlaces: function() {
        return this.request('/parking/available');
    },

    // GET /parking/place/{place_id} - Get single place details
    getPlaceDetails: function(placeId) {
        return this.request('/parking/place/' + placeId);
    },

    // POST /parking/reserve - Create reservation (requires auth)
    createReservation: function(placeId, durationMinutes) {
        return this.request('/parking/reserve', {
            method: 'POST',
            body: {
                place_id: placeId,
                duration_minutes: durationMinutes
            }
        });
    },

    // POST /parking/release/{place_id} - Release/cancel reservation
    releasePlace: function(placeId) {
        return this.request('/parking/release/' + placeId, { method: 'POST' });
    },

    // GET /parking/my-reservation - Get user's active reservation
    getMyReservation: function() {
        return this.request('/parking/my-reservation');
    },

    // ========================================
    // USER PROFILE (Auth required)
    // ========================================

    // GET /users/me - Get current user profile
    getProfile: function() {
        return this.request('/users/me');
    },

    // GET /users/me/reservation - Get user's active reservation
    getUserReservation: function() {
        return this.request('/users/me/reservation');
    },

    // ========================================
    // PAYMENT (Mobile Money)
    // ========================================

    // GET /api/v1/payment/pricing - Get pricing info
    getPricing: function() {
        return this.request('/api/v1/payment/pricing');
    },

    // GET /api/v1/payment/calculate - Calculate amount
    calculateAmount: function(hours, minutes) {
        minutes = minutes || 0;
        return this.request('/api/v1/payment/calculate?hours=' + hours + '&minutes=' + minutes);
    },

    // POST /api/v1/payment/mobile-money/simulate - Mobile money payment
    processMobilePayment: function(provider, phoneNumber, amount, reservationId) {
        return this.request('/api/v1/payment/mobile-money/simulate', {
            method: 'POST',
            body: {
                provider: provider,
                phone_number: phoneNumber,
                amount: amount,
                reservation_id: reservationId
            }
        });
    },

    // GET /api/v1/payment/mobile-money/providers - Get supported providers
    getPaymentProviders: function() {
        return this.request('/api/v1/payment/mobile-money/providers');
    },

    // ========================================
    // ADMIN ENDPOINTS
    // ========================================

    // GET /admin/parking/stats - Get parking statistics
    getAdminStats: function() {
        return this.request('/admin/parking/stats');
    },

    // GET /admin/parking/all - Get all places with admin details
    getAdminPlaces: function() {
        return this.request('/admin/parking/all');
    },

    // POST /admin/parking/force-release/{place_id} - Force release a place
    forceRelease: function(placeId, reason) {
        var url = '/admin/parking/force-release/' + placeId;
        if (reason) url += '?reason=' + encodeURIComponent(reason);
        return this.request(url, { method: 'POST' });
    },

    // GET /admin/parking/reservations - Get all reservations
    getAdminReservations: function(statusFilter, limit) {
        var url = '/admin/parking/reservations';
        var params = [];
        if (statusFilter) params.push('status_filter=' + statusFilter);
        if (limit) params.push('limit=' + limit);
        if (params.length) url += '?' + params.join('&');
        return this.request(url);
    },

    // POST /admin/parking/reservations/cancel/{reservation_id} - Cancel reservation
    cancelAdminReservation: function(reservationId, reason) {
        var url = '/admin/parking/reservations/cancel/' + reservationId;
        if (reason) url += '?reason=' + encodeURIComponent(reason);
        return this.request(url, { method: 'POST' });
    },

    // GET /admin/parking/access-codes - Get all access codes
    getAdminAccessCodes: function(statusFilter) {
        var url = '/admin/parking/access-codes';
        if (statusFilter) url += '?status_filter=' + statusFilter;
        return this.request(url);
    },

    // POST /admin/parking/access-codes/invalidate/{code} - Invalidate code
    invalidateAccessCode: function(code, reason) {
        var url = '/admin/parking/access-codes/invalidate/' + code;
        if (reason) url += '?reason=' + encodeURIComponent(reason);
        return this.request(url, { method: 'POST' });
    },

    // POST /admin/parking/access-codes/cleanup - Cleanup expired codes
    cleanupExpiredCodes: function() {
        return this.request('/admin/parking/access-codes/cleanup', { method: 'POST' });
    },

    // GET /admin/parking/payments - Get all payments
    getAdminPayments: function(statusFilter, limit) {
        var url = '/admin/parking/payments';
        var params = [];
        if (statusFilter) params.push('status_filter=' + statusFilter);
        if (limit) params.push('limit=' + limit);
        if (params.length) url += '?' + params.join('&');
        return this.request(url);
    },

    // POST /admin/parking/payments/refund/{payment_id} - Refund payment
    refundPayment: function(paymentId, reason) {
        var url = '/admin/parking/payments/refund/' + paymentId;
        if (reason) url += '?reason=' + encodeURIComponent(reason);
        return this.request(url, { method: 'POST' });
    }
};
