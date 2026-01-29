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
    window.addEventListener('load', function() {
        // Try relative path first (works when served from frontend folder)
        var swPath = './sw.js';
        // Check if we're in a subfolder
        if (window.location.pathname.includes('/pages/') || window.location.pathname.includes('/admin/')) {
            swPath = '../sw.js';
        }
        navigator.serviceWorker.register(swPath)
            .then(function(registration) {
                console.log('[SW] Registered:', registration.scope);
            })
            .catch(function(error) {
                console.log('[SW] Registration failed:', error);
            });
    });
}

// ========================================
// OFFLINE DATA STORAGE
// ========================================

var OfflineStorage = {
    // Save last access code for offline viewing
    saveAccessCode: function(code, placeId, expiresAt) {
        localStorage.setItem('aeropark_last_access_code', code);
        localStorage.setItem('aeropark_last_place', placeId);
        localStorage.setItem('aeropark_code_expires', expiresAt);
    },
    
    // Get last access code
    getAccessCode: function() {
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
    clearAccessCode: function() {
        localStorage.removeItem('aeropark_last_access_code');
        localStorage.removeItem('aeropark_last_place');
        localStorage.removeItem('aeropark_code_expires');
    },
    
    // Save last parking status for offline
    saveParkingStatus: function(data) {
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
    getParkingStatus: function() {
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
        } catch (e) {}
        return null;
    }
};

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    initNavigation();
    Auth.updateNavigation();
    
    // Setup logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            Auth.logout();
        });
    }

    // Load home page data if on index
    if (document.getElementById('total-places')) {
        loadHomePageData();
    }
});

// ========================================
// NAVIGATION
// ========================================

function initNavigation() {
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', function() {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
        });

        // Close on link click
        navLinks.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', function() {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });

        // Close on outside click
        document.addEventListener('click', function(e) {
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

async function loadHomePageData() {
    try {
        parkingData = await API.getParkingStatus();
        updateStats(parkingData);
        updateProgressRing(parkingData);
        generateParkingPreview(parkingData);
    } catch (error) {
        console.error('Error loading parking data:', error);
    }
}

function updateStats(data) {
    var places = data.places || [];
    var total = places.length;
    // Backend uses 'etat': free, reserved, occupied
    var available = places.filter(function(p) { return (p.etat || p.status) === 'free'; }).length;
    var occupied = places.filter(function(p) { return (p.etat || p.status) === 'occupied'; }).length;
    var reserved = places.filter(function(p) { return (p.etat || p.status) === 'reserved'; }).length;
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
    const interval = setInterval(function() {
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
    var available = places.filter(function(p) { return (p.etat || p.status) === 'free'; }).length;
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
    container.innerHTML = spots.map(function(spot) {
        // Backend uses 'etat': free, reserved, occupied
        var status = spot.etat || spot.status || 'free';
        var statusClass = status === 'free' ? 'available' : status;
        // Use place_id from backend, fallback to id
        var spotId = spot.place_id || spot.id || 'P' + (spots.indexOf(spot) + 1);
        
        // Labels en français
        var statusLabel = status === 'free' ? 'Disponible' : (status === 'reserved' ? 'Réservée' : 'Occupée');
        var statusColor = status === 'free' ? '#10b981' : (status === 'reserved' ? '#f59e0b' : '#ef4444');
        var bgColor = status === 'free' ? '#f0fdf4' : (status === 'reserved' ? '#fefce8' : '#fef2f2');
        var borderColor = status === 'free' ? '#10b981' : (status === 'reserved' ? '#f59e0b' : '#ef4444');
        
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
        '</div>';
    }).join('');
    
    // Appliquer un style de grille au container - 6 colonnes fixes
    container.style.cssText = 'display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; padding: 1.5rem; background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); max-width: 900px; margin: 0 auto;';
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

    setTimeout(function() { notification.remove(); }, 3000);
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
setInterval(function() {
    if (document.getElementById('total-places')) {
        loadHomePageData();
    }
}, 30000);
