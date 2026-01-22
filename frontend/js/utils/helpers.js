/**
 * AeroPark GOMA - Utility Functions
 */

const Helpers = {
    /**
     * Format date to locale string
     */
    formatDate(date, options = {}) {
        const d = new Date(date);
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            ...options
        });
    },
    
    /**
     * Format date and time
     */
    formatDateTime(date) {
        const d = new Date(date);
        return d.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    /**
     * Format time only
     */
    formatTime(date) {
        const d = new Date(date);
        return d.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    /**
     * Format currency
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency
        }).format(amount);
    },
    
    /**
     * Format duration in hours/minutes
     */
    formatDuration(minutes) {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        
        if (hours === 0) {
            return `${mins} min`;
        } else if (mins === 0) {
            return `${hours} hr`;
        } else {
            return `${hours} hr ${mins} min`;
        }
    },
    
    /**
     * Get time remaining from now to a date
     */
    getTimeRemaining(endTime) {
        const total = new Date(endTime) - new Date();
        
        if (total <= 0) {
            return { expired: true, text: 'Expired' };
        }
        
        const days = Math.floor(total / (1000 * 60 * 60 * 24));
        const hours = Math.floor((total % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((total % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((total % (1000 * 60)) / 1000);
        
        let text = '';
        if (days > 0) text += `${days}d `;
        if (hours > 0 || days > 0) text += `${hours}h `;
        if (minutes > 0 || hours > 0 || days > 0) text += `${minutes}m `;
        text += `${seconds}s`;
        
        return { expired: false, text, days, hours, minutes, seconds, total };
    },
    
    /**
     * Get status badge class
     */
    getStatusBadgeClass(status) {
        const statusMap = {
            'free': 'success',
            'available': 'success',
            'reserved': 'warning',
            'pending': 'warning',
            'occupied': 'danger',
            'cancelled': 'danger',
            'completed': 'success',
            'paid': 'success',
            'unpaid': 'warning',
            'active': 'info',
            'expired': 'danger'
        };
        return statusMap[status?.toLowerCase()] || 'info';
    },
    
    /**
     * Get parking status icon
     */
    getParkingStatusIcon(status) {
        const iconMap = {
            'free': '🟢',
            'reserved': '🟡',
            'occupied': '🔴'
        };
        return iconMap[status?.toLowerCase()] || '⚪';
    },
    
    /**
     * Get parking status text
     */
    getParkingStatusText(status) {
        const textMap = {
            'free': 'Available',
            'reserved': 'Reserved',
            'occupied': 'Occupied'
        };
        return textMap[status?.toLowerCase()] || status;
    },
    
    /**
     * Debounce function
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    /**
     * Throttle function
     */
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    /**
     * Generate random ID
     */
    generateId(length = 8) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    },
    
    /**
     * Validate email format
     */
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },
    
    /**
     * Validate password strength
     */
    validatePassword(password) {
        const result = {
            isValid: false,
            errors: []
        };
        
        if (password.length < 8) {
            result.errors.push('Password must be at least 8 characters');
        }
        if (!/[A-Z]/.test(password)) {
            result.errors.push('Password must contain an uppercase letter');
        }
        if (!/[a-z]/.test(password)) {
            result.errors.push('Password must contain a lowercase letter');
        }
        if (!/[0-9]/.test(password)) {
            result.errors.push('Password must contain a number');
        }
        
        result.isValid = result.errors.length === 0;
        return result;
    },
    
    /**
     * Parse URL query parameters
     */
    getQueryParams() {
        const params = {};
        const searchParams = new URLSearchParams(window.location.search);
        for (const [key, value] of searchParams) {
            params[key] = value;
        }
        return params;
    },
    
    /**
     * Build URL with query parameters
     */
    buildUrl(baseUrl, params = {}) {
        const url = new URL(baseUrl, window.location.origin);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                url.searchParams.append(key, value);
            }
        });
        return url.toString();
    },
    
    /**
     * Copy text to clipboard
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            const success = document.execCommand('copy');
            document.body.removeChild(textarea);
            return success;
        }
    },
    
    /**
     * Smooth scroll to element
     */
    scrollToElement(selector, offset = 80) {
        const element = document.querySelector(selector);
        if (element) {
            const top = element.getBoundingClientRect().top + window.pageYOffset - offset;
            window.scrollTo({ top, behavior: 'smooth' });
        }
    },
    
    /**
     * Create element from HTML string
     */
    createElement(html) {
        const template = document.createElement('template');
        template.innerHTML = html.trim();
        return template.content.firstChild;
    },
    
    /**
     * Show loading overlay
     */
    showLoading(message = 'Loading...') {
        let overlay = document.querySelector('.loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.innerHTML = `
                <div class="loading-spinner"></div>
                <p class="loading-message">${message}</p>
            `;
            document.body.appendChild(overlay);
        } else {
            overlay.querySelector('.loading-message').textContent = message;
            overlay.style.display = 'flex';
        }
    },
    
    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    },
    
    /**
     * Calculate parking fee
     */
    calculateParkingFee(startTime, endTime, ratePerHour = 5) {
        const start = new Date(startTime);
        const end = new Date(endTime);
        const hours = Math.ceil((end - start) / (1000 * 60 * 60));
        return hours * ratePerHour;
    },
    
    /**
     * Check if date is today
     */
    isToday(date) {
        const today = new Date();
        const d = new Date(date);
        return d.toDateString() === today.toDateString();
    },
    
    /**
     * Get relative time (e.g., "2 hours ago")
     */
    getRelativeTime(date) {
        const now = new Date();
        const d = new Date(date);
        const diff = now - d;
        
        const minutes = Math.floor(diff / (1000 * 60));
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        
        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes} min ago`;
        if (hours < 24) return `${hours} hr ago`;
        if (days < 7) return `${days} days ago`;
        return this.formatDate(date);
    }
};

// Export for use in other modules
window.Helpers = Helpers;
