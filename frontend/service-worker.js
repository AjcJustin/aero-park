/**
 * AeroPark GOMA - Service Worker
 * PWA Offline Support & Caching Strategy
 */

const CACHE_NAME = 'aeropark-v1.0.0';
const OFFLINE_CACHE = 'aeropark-offline-v1';
const DATA_CACHE = 'aeropark-data-v1';

// Static assets to cache on install
const STATIC_ASSETS = [
    '/frontend/',
    '/frontend/index.html',
    '/frontend/manifest.json',
    '/frontend/css/styles.css',
    '/frontend/js/app.js',
    '/frontend/js/services/api.js',
    '/frontend/js/services/auth.js',
    '/frontend/js/services/state.js',
    '/frontend/js/services/notifications.js',
    '/frontend/js/utils/helpers.js',
    '/frontend/pages/public/login.html',
    '/frontend/pages/public/register.html',
    '/frontend/pages/user/dashboard.html',
    '/frontend/pages/user/reservations.html',
    '/frontend/pages/user/access-codes.html',
    '/frontend/pages/user/payments.html',
    '/frontend/pages/user/profile.html',
    '/frontend/pages/admin/dashboard.html',
    '/frontend/pages/offline.html',
    '/frontend/assets/icons/icon-192x192.png',
    '/frontend/assets/icons/icon-512x512.png'
];

// API endpoints to cache responses
const API_CACHE_PATTERNS = [
    /\/api\/parking\/spots$/,
    /\/api\/parking\/availability$/,
    /\/api\/reservations\/my$/,
    /\/api\/payments\/my$/
];

/**
 * Install Event - Cache static assets
 */
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Install');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[ServiceWorker] Skip waiting');
                return self.skipWaiting();
            })
            .catch((error) => {
                console.error('[ServiceWorker] Cache failed:', error);
            })
    );
});

/**
 * Activate Event - Clean up old caches
 */
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activate');
    
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => {
                            return name.startsWith('aeropark-') && 
                                   name !== CACHE_NAME && 
                                   name !== OFFLINE_CACHE &&
                                   name !== DATA_CACHE;
                        })
                        .map((name) => {
                            console.log('[ServiceWorker] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[ServiceWorker] Claiming clients');
                return self.clients.claim();
            })
    );
});

/**
 * Fetch Event - Network first with cache fallback
 */
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Skip external requests
    if (!url.origin.includes(self.location.origin)) {
        return;
    }
    
    // API requests - Network first, cache fallback
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // Static assets - Cache first, network fallback
    event.respondWith(handleStaticRequest(request));
});

/**
 * Handle API requests with network-first strategy
 */
async function handleApiRequest(request) {
    const url = new URL(request.url);
    
    try {
        // Try network first
        const networkResponse = await fetch(request);
        
        // Cache successful GET responses for specific endpoints
        if (networkResponse.ok && shouldCacheApiResponse(url.pathname)) {
            const cache = await caches.open(DATA_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[ServiceWorker] API fetch failed, trying cache:', url.pathname);
        
        // Try cache fallback
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            console.log('[ServiceWorker] Serving cached API response');
            return cachedResponse;
        }
        
        // Return offline JSON response
        return new Response(
            JSON.stringify({
                error: 'offline',
                message: 'You are currently offline. Please check your connection.'
            }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

/**
 * Handle static asset requests with cache-first strategy
 */
async function handleStaticRequest(request) {
    // Try cache first
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        // Refresh cache in background
        refreshCache(request);
        return cachedResponse;
    }
    
    try {
        // Try network
        const networkResponse = await fetch(request);
        
        // Cache the response
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('[ServiceWorker] Static fetch failed:', request.url);
        
        // Return offline page for navigation requests
        if (request.mode === 'navigate') {
            const offlinePage = await caches.match('/frontend/pages/offline.html');
            if (offlinePage) {
                return offlinePage;
            }
        }
        
        // Return 404 for other requests
        return new Response('Resource not available offline', { status: 404 });
    }
}

/**
 * Check if API response should be cached
 */
function shouldCacheApiResponse(pathname) {
    return API_CACHE_PATTERNS.some(pattern => pattern.test(pathname));
}

/**
 * Refresh cache in background (stale-while-revalidate)
 */
async function refreshCache(request) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse);
        }
    } catch (error) {
        // Silently fail - we already have cached version
    }
}

/**
 * Background Sync - Retry failed requests when online
 */
self.addEventListener('sync', (event) => {
    console.log('[ServiceWorker] Sync event:', event.tag);
    
    if (event.tag === 'sync-reservations') {
        event.waitUntil(syncReservations());
    }
    
    if (event.tag === 'sync-payments') {
        event.waitUntil(syncPayments());
    }
});

/**
 * Sync pending reservations
 */
async function syncReservations() {
    const pendingReservations = await getPendingData('pending-reservations');
    
    for (const reservation of pendingReservations) {
        try {
            const response = await fetch('/api/reservations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${reservation.token}`
                },
                body: JSON.stringify(reservation.data)
            });
            
            if (response.ok) {
                await removePendingData('pending-reservations', reservation.id);
                await notifyClients('reservation-synced', { id: reservation.id });
            }
        } catch (error) {
            console.error('[ServiceWorker] Sync reservation failed:', error);
        }
    }
}

/**
 * Sync pending payments
 */
async function syncPayments() {
    const pendingPayments = await getPendingData('pending-payments');
    
    for (const payment of pendingPayments) {
        try {
            const response = await fetch('/api/payments', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${payment.token}`
                },
                body: JSON.stringify(payment.data)
            });
            
            if (response.ok) {
                await removePendingData('pending-payments', payment.id);
                await notifyClients('payment-synced', { id: payment.id });
            }
        } catch (error) {
            console.error('[ServiceWorker] Sync payment failed:', error);
        }
    }
}

/**
 * Get pending data from IndexedDB
 */
async function getPendingData(storeName) {
    // This would use IndexedDB in production
    // For now, return empty array
    return [];
}

/**
 * Remove pending data from IndexedDB
 */
async function removePendingData(storeName, id) {
    // This would use IndexedDB in production
}

/**
 * Notify all clients of sync completion
 */
async function notifyClients(type, data) {
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({ type, data });
    });
}

/**
 * Push Notification Event
 */
self.addEventListener('push', (event) => {
    console.log('[ServiceWorker] Push event received');
    
    let data = {
        title: 'AeroPark GOMA',
        body: 'You have a new notification',
        icon: '/frontend/assets/icons/icon-192x192.png',
        badge: '/frontend/assets/icons/badge-72x72.png',
        tag: 'aeropark-notification'
    };
    
    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch (e) {
            data.body = event.data.text();
        }
    }
    
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: data.icon,
            badge: data.badge,
            tag: data.tag,
            vibrate: [200, 100, 200],
            data: data.url || '/frontend/',
            actions: [
                { action: 'open', title: 'Open' },
                { action: 'dismiss', title: 'Dismiss' }
            ]
        })
    );
});

/**
 * Notification Click Event
 */
self.addEventListener('notificationclick', (event) => {
    console.log('[ServiceWorker] Notification click:', event.action);
    
    event.notification.close();
    
    if (event.action === 'dismiss') {
        return;
    }
    
    const urlToOpen = event.notification.data || '/frontend/';
    
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Check if app is already open
                for (const client of clientList) {
                    if (client.url.includes('/frontend/') && 'focus' in client) {
                        client.navigate(urlToOpen);
                        return client.focus();
                    }
                }
                // Open new window
                if (self.clients.openWindow) {
                    return self.clients.openWindow(urlToOpen);
                }
            })
    );
});

/**
 * Message Event - Handle messages from clients
 */
self.addEventListener('message', (event) => {
    console.log('[ServiceWorker] Message received:', event.data);
    
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data.type === 'CACHE_URLS') {
        event.waitUntil(
            caches.open(CACHE_NAME)
                .then(cache => cache.addAll(event.data.urls))
        );
    }
    
    if (event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then(names => 
                Promise.all(names.map(name => caches.delete(name)))
            )
        );
    }
});

console.log('[ServiceWorker] Loaded successfully');
