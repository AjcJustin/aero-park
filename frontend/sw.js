/**
 * AeroPark GOMA - Service Worker
 * Handles offline caching and PWA functionality
 */

var CACHE_NAME = 'aeropark-v1';
var STATIC_CACHE = 'aeropark-static-v1';
var DYNAMIC_CACHE = 'aeropark-dynamic-v1';

// Static files to cache on install (relative to service worker location)
var STATIC_FILES = [
    './',
    './index.html',
    './pages/login.html',
    './pages/register.html',
    './pages/reservation.html',
    './css/style.css',
    './css/admin.css',
    './js/api.js',
    './js/auth.js',
    './js/admin.js',
    './js/main.js',
    './manifest.json'
];

// Install event - cache static files
self.addEventListener('install', function(event) {
    console.log('[SW] Installing service worker...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE).then(function(cache) {
            console.log('[SW] Caching static files');
            return cache.addAll(STATIC_FILES).catch(function(err) {
                console.log('[SW] Some files failed to cache:', err);
            });
        })
    );
    
    // Activate immediately
    self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener('activate', function(event) {
    console.log('[SW] Activating service worker...');
    
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(key) {
                    return key !== STATIC_CACHE && key !== DYNAMIC_CACHE;
                }).map(function(key) {
                    console.log('[SW] Deleting old cache:', key);
                    return caches.delete(key);
                })
            );
        })
    );
    
    // Take control immediately
    self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', function(event) {
    var request = event.request;
    var url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Skip API calls - always fetch from network
    if (url.pathname.startsWith('/api') || 
        url.pathname.startsWith('/parking') || 
        url.pathname.startsWith('/users') ||
        url.pathname.startsWith('/admin') ||
        url.pathname.startsWith('/auth')) {
        return;
    }
    
    // For HTML pages - network first, fallback to cache
    if (request.headers.get('accept').includes('text/html')) {
        event.respondWith(
            fetch(request).then(function(response) {
                // Cache the new version
                var responseClone = response.clone();
                caches.open(DYNAMIC_CACHE).then(function(cache) {
                    cache.put(request, responseClone);
                });
                return response;
            }).catch(function() {
                // Fallback to cache
                return caches.match(request).then(function(cachedResponse) {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    // Return offline page if available
                    return caches.match('/frontend/index.html');
                });
            })
        );
        return;
    }
    
    // For other assets - cache first, fallback to network
    event.respondWith(
        caches.match(request).then(function(cachedResponse) {
            if (cachedResponse) {
                return cachedResponse;
            }
            
            return fetch(request).then(function(response) {
                // Cache the fetched resource
                var responseClone = response.clone();
                caches.open(DYNAMIC_CACHE).then(function(cache) {
                    cache.put(request, responseClone);
                });
                return response;
            }).catch(function() {
                // Return nothing if offline and not cached
                console.log('[SW] Resource not available offline:', request.url);
            });
        })
    );
});

// Handle messages from the app
self.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Background sync for reservation data
self.addEventListener('sync', function(event) {
    if (event.tag === 'sync-reservation') {
        console.log('[SW] Syncing reservation data...');
        // Could sync pending reservations here
    }
});
