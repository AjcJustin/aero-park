/**
 * AeroPark GOMA - Notifications Service
 * Toast notifications and push notification handling
 */

const NotificationService = {
    container: null,
    
    /**
     * Initialize notification service
     */
    init() {
        // Create toast container
        this.createContainer();
        
        // Setup service worker message listener
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('message', (event) => {
                this.handleServiceWorkerMessage(event.data);
            });
        }
        
        console.log('[Notifications] Initialized');
    },
    
    /**
     * Create toast container
     */
    createContainer() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            this.container.id = 'toast-container';
            document.body.appendChild(this.container);
        }
    },
    
    /**
     * Show a toast notification
     */
    show(options) {
        const {
            type = 'info',
            title = '',
            message = '',
            duration = 5000,
            closable = true
        } = options;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${this.getIcon(type)}</span>
            <div class="toast-content">
                ${title ? `<div class="toast-title">${title}</div>` : ''}
                <div class="toast-message">${message}</div>
            </div>
            ${closable ? '<button class="toast-close" aria-label="Close">&times;</button>' : ''}
        `;
        
        // Add close handler
        if (closable) {
            toast.querySelector('.toast-close').addEventListener('click', () => {
                this.dismiss(toast);
            });
        }
        
        // Add to container
        this.container.appendChild(toast);
        
        // Auto dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(toast), duration);
        }
        
        return toast;
    },
    
    /**
     * Dismiss a toast
     */
    dismiss(toast) {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    },
    
    /**
     * Show success toast
     */
    success(message, title = 'Success') {
        return this.show({ type: 'success', title, message });
    },
    
    /**
     * Show error toast
     */
    error(message, title = 'Error') {
        return this.show({ type: 'error', title, message, duration: 8000 });
    },
    
    /**
     * Show warning toast
     */
    warning(message, title = 'Warning') {
        return this.show({ type: 'warning', title, message });
    },
    
    /**
     * Show info toast
     */
    info(message, title = 'Info') {
        return this.show({ type: 'info', title, message });
    },
    
    /**
     * Get icon for toast type
     */
    getIcon(type) {
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        return icons[type] || icons.info;
    },
    
    // ==========================================
    // PUSH NOTIFICATIONS
    // ==========================================
    
    /**
     * Request push notification permission
     */
    async requestPermission() {
        if (!('Notification' in window)) {
            console.warn('[Notifications] Push notifications not supported');
            return false;
        }
        
        if (Notification.permission === 'granted') {
            return true;
        }
        
        if (Notification.permission === 'denied') {
            console.warn('[Notifications] Push notifications denied');
            return false;
        }
        
        const permission = await Notification.requestPermission();
        return permission === 'granted';
    },
    
    /**
     * Subscribe to push notifications
     */
    async subscribeToPush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.warn('[Notifications] Push not supported');
            return null;
        }
        
        try {
            const registration = await navigator.serviceWorker.ready;
            
            // Check existing subscription
            let subscription = await registration.pushManager.getSubscription();
            
            if (!subscription) {
                // Create new subscription
                subscription = await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: this.urlBase64ToUint8Array(
                        'YOUR_VAPID_PUBLIC_KEY' // Replace with actual VAPID key
                    )
                });
            }
            
            // Send subscription to server
            await this.sendSubscriptionToServer(subscription);
            
            console.log('[Notifications] Push subscription:', subscription);
            return subscription;
        } catch (error) {
            console.error('[Notifications] Push subscription failed:', error);
            return null;
        }
    },
    
    /**
     * Unsubscribe from push notifications
     */
    async unsubscribeFromPush() {
        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                await subscription.unsubscribe();
                console.log('[Notifications] Unsubscribed from push');
            }
        } catch (error) {
            console.error('[Notifications] Unsubscribe failed:', error);
        }
    },
    
    /**
     * Send subscription to server
     */
    async sendSubscriptionToServer(subscription) {
        // This would send the subscription to your backend
        // await ApiService.request('/notifications/subscribe', {
        //     method: 'POST',
        //     body: JSON.stringify(subscription)
        // });
        console.log('[Notifications] Subscription sent to server');
    },
    
    /**
     * Convert VAPID key to Uint8Array
     */
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    },
    
    /**
     * Handle messages from service worker
     */
    handleServiceWorkerMessage(data) {
        console.log('[Notifications] Service worker message:', data);
        
        switch (data.type) {
            case 'reservation-synced':
                this.success('Your reservation has been synced', 'Sync Complete');
                break;
            case 'payment-synced':
                this.success('Your payment has been processed', 'Payment Complete');
                break;
            default:
                break;
        }
    },
    
    // ==========================================
    // APP NOTIFICATIONS
    // ==========================================
    
    /**
     * Notify reservation created
     */
    reservationCreated(reservation) {
        this.success(
            `Spot ${reservation.spot_id} reserved for ${new Date(reservation.start_time).toLocaleString()}`,
            'Reservation Confirmed'
        );
    },
    
    /**
     * Notify reservation cancelled
     */
    reservationCancelled() {
        this.info('Your reservation has been cancelled', 'Reservation Cancelled');
    },
    
    /**
     * Notify access code generated
     */
    accessCodeGenerated(code) {
        this.success(
            `Your access code is: ${code.code}`,
            'Access Code Generated'
        );
    },
    
    /**
     * Notify payment success
     */
    paymentSuccess(amount) {
        this.success(
            `Payment of $${amount.toFixed(2)} successful`,
            'Payment Complete'
        );
    },
    
    /**
     * Notify offline mode
     */
    offlineMode() {
        this.warning(
            'You are currently offline. Some features may be limited.',
            'Offline Mode'
        );
    },
    
    /**
     * Notify back online
     */
    backOnline() {
        this.success(
            'You are back online. Syncing data...',
            'Connected'
        );
    }
};

// Add slide out animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize on load
document.addEventListener('DOMContentLoaded', () => NotificationService.init());

// Export for use in other modules
window.NotificationService = NotificationService;
