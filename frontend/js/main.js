/**
 * AeroPark GOMA - Main JavaScript
 * Common functions for all pages
 */

// Cached parking data
var parkingData = null;

// ========================================
// SERVICE WORKER REGISTRATION
// ========================================

if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
        // Try relative path first (works when served from frontend folder)
        var swPath = './sw.js';
        // Check if we're in a subfolder
        if (window.location.pathname.includes('/pages/') || window.location.pathname.includes('/admin/')) {
            swPath = '../sw.js';
        }
        navigator.serviceWorker.register(swPath)
            .then(function (registration) {
                console.log('[SW] Registered:', registration.scope);
            })
            .catch(function (error) {
                console.log('[SW] Registration failed:', error);
            });
    });
}

// ========================================
// OFFLINE DATA STORAGE
// ========================================

var OfflineStorage = {
    // Save last access code for offline viewing
    saveAccessCode: function (code, placeId, expiresAt) {
        localStorage.setItem('aeropark_last_access_code', code);
        localStorage.setItem('aeropark_last_place', placeId);
        localStorage.setItem('aeropark_code_expires', expiresAt);
    },

    // Get last access code
    getAccessCode: function () {
        var code = localStorage.getItem('aeropark_last_access_code');
        var placeId = localStorage.getItem('aeropark_last_place');
        var expiresAt = localStorage.getItem('aeropark_code_expires');

        if (!code) return null;

        // Check if expired
        if (expiresAt && new Date(expiresAt) < new Date()) {
            this.clearAccessCode();
            return null;
        }

        return {
            code: code,
            placeId: placeId,
            expiresAt: expiresAt
        };
    },

    // Clear access code
    clearAccessCode: function () {
        localStorage.removeItem('aeropark_last_access_code');
        localStorage.removeItem('aeropark_last_place');
        localStorage.removeItem('aeropark_code_expires');
    },

    // Save last parking status for offline
    saveParkingStatus: function (data) {
        try {
            localStorage.setItem('aeropark_parking_cache', JSON.stringify({
                data: data,
                timestamp: new Date().toISOString()
            }));
        } catch (e) {
            console.log('Could not cache parking data');
        }
    },

    // Get cached parking status
    getParkingStatus: function () {
        try {
            var cached = localStorage.getItem('aeropark_parking_cache');
            if (cached) {
                var parsed = JSON.parse(cached);
                // Cache valid for 5 minutes
                var cacheAge = new Date() - new Date(parsed.timestamp);
                if (cacheAge < 5 * 60 * 1000) {
                    return parsed.data;
                }
            }
        } catch (e) { }
        return null;
    }
};

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', function () {
    initNavigation();
    Auth.updateNavigation();

    // Setup logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function (e) {
            e.preventDefault();
            Auth.logout();
        });
    }

    // Load home page data if on index
    // Load home page data if on index
    const totalPlacesElement = document.getElementById('total-places');
    console.log('Checking for total-places element:', totalPlacesElement);

    // Always setup WebSocket for real-time updates on all pages
    setupWebSocket();

    if (totalPlacesElement) {
        console.log('Element found! Loading home page data...');
        loadHomePageData();
        loadSystemSettings();
    } else {
        console.log('Not on home page - skipping full data load');
    }
});

// ========================================
// NAVIGATION
// ========================================

function initNavigation() {
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', function () {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
        });

        // Close on link click
        navLinks.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });

        // Close on outside click
        document.addEventListener('click', function (e) {
            if (!navLinks.contains(e.target) && !hamburger.contains(e.target)) {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
            }
        });
    }
}

// ========================================
// HOME PAGE
// ========================================

async function loadSystemSettings() {
    try {
        console.log('Loading settings...');
        const settings = await API.getPublicSettings();
        console.log('Settings received:', settings);

        if (settings) {
            // Update Brand Name
            if (settings.parking_name) {
                const brands = document.querySelectorAll('#nav-brand-text, #footer-brand-text, #hero-brand-text');
                brands.forEach(el => el.textContent = settings.parking_name);
                document.title = settings.parking_name + ' - ' + (settings.slogan || 'Parking');
            }

            // Update Slogan
            if (settings.slogan) {
                const slogan = document.getElementById('hero-slogan');
                if (slogan) slogan.textContent = settings.slogan;
            }

            // Log success (temporary for debugging)
            // const debug = document.createElement('div');
            // debug.textContent = 'Settings loaded: ' + settings.parking_name;
            // debug.style = 'position:fixed;bottom:0;left:0;background:green;color:white;padding:5px;z-index:9999';
            // document.body.appendChild(debug);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        // Show error notification
        // showNotification('Erreur chargement paramètres: ' + error.message, 'error');
    }
}

async function loadHomePageData() {
    try {
        console.log('Loading parking data...');
        parkingData = await API.getParkingStatus();
        console.log('Parking data received:', parkingData);
        console.log('Number of places:', parkingData.places ? parkingData.places.length : 'NO PLACES');
        updateStats(parkingData);
        updateProgressRing(parkingData);
        generateParkingPreview(parkingData);
        updateOccupancyTimers(); // Start timer updates
    } catch (error) {
        console.error('Error loading parking data:', error);
    }
}

function updateStats(data) {
    var places = data.places || [];
    var total = places.length;
    // Backend uses 'etat': free, reserved, occupied
    var available = places.filter(function (p) { return (p.etat || p.status) === 'free'; }).length;
    var occupied = places.filter(function (p) { return (p.etat || p.status) === 'occupied'; }).length;
    var reserved = places.filter(function (p) { return (p.etat || p.status) === 'reserved'; }).length;
    var rate = total > 0 ? Math.round(((occupied + reserved) / total) * 100) : 0;

    animateNumber('total-places', total);
    animateNumber('available-places', available);
    animateNumber('occupied-places', occupied);
    animateNumber('reserved-places', reserved);
    animateNumber('occupation-rate', rate, '%');

    updateStatusIndicator(rate);
}

function animateNumber(elementId, value, suffix) {
    suffix = suffix || '';
    const element = document.getElementById(elementId);
    if (!element) return;

    let current = 0;
    const step = Math.ceil(value / 30);
    const interval = setInterval(function () {
        current += step;
        if (current >= value) {
            current = value;
            clearInterval(interval);
        }
        element.textContent = current + suffix;
    }, 30);
}

function updateProgressRing(data) {
    var places = data.places || [];
    var total = places.length;
    var available = places.filter(function (p) { return (p.etat || p.status) === 'free'; }).length;
    var rate = total > 0 ? Math.round(((total - available) / total) * 100) : 0;

    var progressCircle = document.getElementById('progress-circle');
    var progressPercent = document.getElementById('progress-percent');

    if (progressCircle && progressPercent) {
        const circumference = 2 * Math.PI * 90;
        const offset = circumference - (rate / 100) * circumference;

        progressCircle.style.strokeDasharray = circumference;
        progressCircle.style.strokeDashoffset = offset;

        if (rate < 50) {
            progressCircle.style.stroke = 'var(--available-color)';
        } else if (rate < 80) {
            progressCircle.style.stroke = 'var(--reserved-color)';
        } else {
            progressCircle.style.stroke = 'var(--occupied-color)';
        }

        progressPercent.textContent = rate + '%';
    }
}

function updateStatusIndicator(rate) {
    const indicator = document.getElementById('status-indicator');
    if (!indicator) return;

    const statusText = indicator.querySelector('.status-text');
    indicator.classList.remove('warning', 'danger');

    if (rate < 50) {
        statusText.textContent = 'Beaucoup de places disponibles';
    } else if (rate < 80) {
        indicator.classList.add('warning');
        statusText.textContent = 'Places limitées';
    } else {
        indicator.classList.add('danger');
        statusText.textContent = 'Presque complet';
    }
}

function generateParkingPreview(data) {
    var container = document.getElementById('parking-preview');
    if (!container) return;

    var spots = data.places || [];
    container.innerHTML = spots.map(function (spot) {
        // Backend uses 'etat': free, reserved, occupied
        var status = spot.etat || spot.status || 'free';
        var statusClass = status === 'free' ? 'available' : status;
        // Use place_id from backend, fallback to id
        var rawId = spot.place_id || spot.id;
        var spotId;

        // Try to use API formatter if available, otherwise manual fallback
        if (typeof API !== 'undefined' && API.formatPlaceId) {
            spotId = API.formatPlaceId(rawId);
        } else {
            // Fallback if API not loaded or old version
            spotId = rawId ? String(rawId).replace(/^a(\d+)$/i, 'P$1') : 'P' + (spots.indexOf(spot) + 1);
        }

        var statusLabel = status === 'free' ? 'Disponible' : (status === 'reserved' ? 'Réservée' : 'Occupée');
        var statusColor = status === 'free' ? '#10b981' : (status === 'reserved' ? '#f59e0b' : '#ef4444');
        var bgColor = status === 'free' ? '#f0fdf4' : (status === 'reserved' ? '#fefce8' : '#fef2f2');
        var borderColor = status === 'free' ? '#10b981' : (status === 'reserved' ? '#f59e0b' : '#ef4444');

        // Timer HTML for occupied spots OR last duration for free spots
        var timerHtml = '';
        if (status === 'occupied') {
            var reservationEndTime = spot.reservation_end_time;
            var startTime = spot.last_update || spot.start_time;

            console.log('DEBUG Occupied Spot:', {
                id: spot.place_id || spot.id,
                status: status,
                last_update: spot.last_update,
                start_time: spot.start_time,
                reservation_end_time: reservationEndTime,
                startTime: startTime,
                fullSpot: spot
            });

            if (startTime) {
                // Determine what time to use for timer calculation
                var timerStartTime = startTime;
                var isOvertimeTimer = false;

                // If there's a reservation_end_time, timer shows overtime after reservation
                if (reservationEndTime) {
                    timerStartTime = reservationEndTime;
                    isOvertimeTimer = true;
                }

                // Add data attribute for timer updates
                timerHtml = '<div class="occupancy-timer" ' +
                    'data-start="' + timerStartTime + '" ' +
                    'data-spot-id="' + (spot.place_id || spot.id) + '" ' +
                    'data-is-overtime="' + isOvertimeTimer + '" ' +
                    'style="' +
                    'margin-top: 0.5rem;' +
                    'font-size: 0.75rem;' +
                    'color: ' + (isOvertimeTimer ? '#ef4444' : '#64748b') + ';' +
                    'font-weight: 500;' +
                    '">Calcul...</div>';
            } else {
                console.warn('No start time for occupied spot:', spot.place_id || spot.id);
            }
        } else if (status === 'free') {
            // Show last occupancy duration if available
            var durationSeconds = spot.last_occupancy_duration_seconds;
            var durationMinutes = spot.last_occupancy_duration_minutes;

            if (durationSeconds !== undefined && durationSeconds !== null) {
                // Display in HH:MM:SS format
                var hours = Math.floor(durationSeconds / 3600);
                var mins = Math.floor((durationSeconds % 3600) / 60);
                var secs = durationSeconds % 60;

                var displayText = '';
                if (durationSeconds < 60) {
                    displayText = secs + 's';
                } else if (hours > 0) {
                    displayText = hours + 'h ' + mins + 'm ' + secs + 's';
                } else {
                    displayText = mins + 'm ' + secs + 's';
                }

                timerHtml = '<div style="' +
                    'margin-top: 0.5rem;' +
                    'font-size: 0.7rem;' +
                    'color: #94a3b8;' +
                    'font-style: italic;' +
                    '">Dernière: ' + displayText + '</div>';
            } else if (durationMinutes !== undefined && durationMinutes !== null && durationMinutes > 0) {
                // Fallback to minutes
                var hours = Math.floor(durationMinutes / 60);
                var remainingMins = durationMinutes % 60;
                var displayText = hours > 0 ?
                    (hours + 'h ' + (remainingMins > 0 ? remainingMins + 'm' : '')) :
                    (durationMinutes + 'm');

                timerHtml = '<div style="' +
                    'margin-top: 0.5rem;' +
                    'font-size: 0.7rem;' +
                    'color: #94a3b8;' +
                    'font-style: italic;' +
                    '">Dernière: ' + displayText + '</div>';
            }
        }

        return '<div class="parking-card-preview" style="' +
            'background: ' + bgColor + ';' +
            'border: 3px solid ' + borderColor + ';' +
            'border-radius: 12px;' +
            'padding: 1.5rem 1rem;' +
            'text-align: center;' +
            'transition: transform 0.2s, box-shadow 0.2s;' +
            '">' +
            '<div style="font-size: 1.5rem; font-weight: bold; color: #1e293b; margin-bottom: 0.75rem;">' + spotId + '</div>' +
            '<span style="' +
            'display: inline-flex;' +
            'align-items: center;' +
            'gap: 0.35rem;' +
            'background: ' + statusColor + ';' +
            'color: white;' +
            'padding: 0.35rem 0.75rem;' +
            'border-radius: 20px;' +
            'font-size: 0.8rem;' +
            'font-weight: 500;' +
            '">' +
            '<span style="width: 8px; height: 8px; background: white; border-radius: 50%; opacity: 0.8;"></span>' +
            statusLabel +
            '</span>' +
            timerHtml +
            '</div>';
    }).join('');

    // Appliquer un style de grille au container - 6 colonnes fixes
    container.style.cssText = 'display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; padding: 1.5rem; background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); max-width: 900px; margin: 0 auto;';
}

function updateOccupancyTimers() {
    var timers = document.querySelectorAll('.occupancy-timer');
    if (timers.length === 0) return;

    timers.forEach(function (timer) {
        var startTimeStr = timer.getAttribute('data-start');
        var isOvertime = timer.getAttribute('data-is-overtime') === 'true';
        if (!startTimeStr) return;

        // Ensure timezone handling
        if (startTimeStr.indexOf('Z') === -1 && startTimeStr.indexOf('+') === -1) {
            startTimeStr += 'Z';
        }

        var startTime = new Date(startTimeStr);
        var now = new Date();
        var durationSeconds = Math.floor((now - startTime) / 1000);

        // If overtime timer and current time is before reservation end, show "En cours"
        if (isOvertime && durationSeconds < 0) {
            timer.textContent = '⏱️ En cours';
            timer.style.color = '#64748b';
            return;
        }

        if (durationSeconds < 0) durationSeconds = 0;

        // Format duration
        var hours = Math.floor(durationSeconds / 3600);
        var mins = Math.floor((durationSeconds % 3600) / 60);
        var secs = durationSeconds % 60;

        var displayText = '';
        if (hours > 0) {
            displayText = hours + 'h ' + mins + 'm ' + secs + 's';
        } else if (mins > 0) {
            displayText = mins + 'm ' + secs + 's';
        } else {
            displayText = secs + 's';
        }

        // Different display for overtime vs normal occupation
        if (isOvertime) {
            timer.textContent = '🔴 Dépassement: ' + displayText;
            timer.style.color = '#ef4444'; // Red for overtime
        } else {
            timer.textContent = '⏱️ ' + displayText;
            timer.style.color = '#64748b'; // Gray for normal
        }
    });
}

// Update timers every second
setInterval(function () {
    updateOccupancyTimers();
}, 1000);


// ========================================
// REAL-TIME UPDATES (WEBSOCKET)
// ========================================

var parkingWS = null;
var wsReconnectTimer = null;

function setupWebSocket() {
    if (parkingWS) return;

    // Use current host but switch protocol to ws/wss
    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var host = window.location.hostname || 'localhost';
    // If testing locally with file://, default to localhost:8000
    if (window.location.protocol === 'file:') {
        host = 'localhost:8000';
        protocol = 'ws:';
    } else {
        // If on a port (like 5500), point to API port 8000
        // Currently hardcoded to 8000 as per API.js
        host = host + ':8000';
    }

    var wsUrl = protocol + '//' + host + '/ws/parking';
    console.log('Connecting to WebSocket:', wsUrl);

    try {
        parkingWS = new WebSocket(wsUrl);

        parkingWS.onopen = function () {
            console.log('✅ WebSocket Connected');
            // Clear reconnect timer if successful
            if (wsReconnectTimer) {
                clearTimeout(wsReconnectTimer);
                wsReconnectTimer = null;
            }
        };

        parkingWS.onmessage = function (event) {
            try {
                var data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error('Error parsing WebSocket message:', e);
            }
        };

        parkingWS.onclose = function () {
            console.log('❌ WebSocket Disconnected');
            parkingWS = null;
            // Try to reconnect in 5 seconds
            if (!wsReconnectTimer) {
                wsReconnectTimer = setTimeout(setupWebSocket, 5000);
            }
        };

        parkingWS.onerror = function (error) {
            console.error('WebSocket Error:', error);
            parkingWS.close(); // Trigger onclose to reconnect
        };

    } catch (e) {
        console.error('WebSocket Connection Failed:', e);
        // Retry later
        if (!wsReconnectTimer) {
            wsReconnectTimer = setTimeout(setupWebSocket, 5000);
        }
    }
}

function handleWebSocketMessage(data) {
    if (data.type === 'status_update') {
        // Update all UI components with new data
        console.log('🔄 Real-time update received');

        if (data.places) {
            // Update global data
            parkingData = data;

            // Refresh UI
            updateStats(data);
            updateProgressRing(data);
            generateParkingPreview(data);
            updateOccupancyTimers(); // Restart timers

            // Highlight changes (visual feedback)
            const grid = document.getElementById('parking-preview');
            if (grid) {
                grid.style.transition = 'box-shadow 0.3s';
                grid.style.boxShadow = '0 0 15px rgba(16, 185, 129, 0.3)';
                setTimeout(() => {
                    grid.style.boxShadow = '0 4px 20px rgba(0,0,0,0.08)';
                }, 500);
            }
        }
    } else if (data.type === 'place_update') {
        // Handle single place update if needed (status_update is preferred as it's full sync)
        console.log('Single place update:', data.place);
        // For now, simpler to refetch full status to ensure consistency
        loadHomePageData();
    }
}

// ========================================
// UTILITIES
// ========================================

function showNotification(message, type) {
    type = type || 'success';

    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.className = 'notification ' + type;

    const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle';
    notification.innerHTML = '<i class="fas fa-' + icon + '"></i><span>' + message + '</span>';

    notification.style.cssText =
        'position:fixed;top:100px;right:20px;padding:1rem 1.5rem;border-radius:10px;' +
        'box-shadow:0 5px 20px rgba(0,0,0,0.15);display:flex;align-items:center;gap:0.75rem;' +
        'z-index:10000;color:white;background:' +
        (type === 'success' ? 'var(--secondary-color)' : type === 'error' ? 'var(--danger-color)' : 'var(--primary-color)');

    document.body.appendChild(notification);

    setTimeout(function () { notification.remove(); }, 3000);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function calculateRemainingTime(expiresAt) {
    if (!expiresAt) return { expired: true };

    const now = new Date();
    const expires = new Date(expiresAt);
    const diff = expires - now;

    if (diff <= 0) return { expired: true };

    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    return { hours: hours, minutes: minutes, seconds: seconds, expired: false };
}

function formatRemainingTime(remaining) {
    if (!remaining || remaining.expired) {
        return '<span class="expired">Expirée</span>';
    }

    if (remaining.hours > 24) {
        var days = Math.floor(remaining.hours / 24);
        var remainingHours = remaining.hours % 24;
        return days + 'j ' + remainingHours + 'h ' + remaining.minutes + 'm';
    }

    return remaining.hours + 'h ' + remaining.minutes + 'm ' + remaining.seconds + 's';
}

// Refresh data every 30 seconds
setInterval(function () {
    if (document.getElementById('total-places')) {
        loadHomePageData();
        loadSystemSettings();
    }
}, 30000);
