/* ========================================
   AeroPark Smart System - Main JavaScript
   Logique principale de l'application
   ======================================== */

// Attendre que le DOM soit chargé
document.addEventListener('DOMContentLoaded', () => {
    // Initialisation
    initNavigation();
    initHomePage();
    startRealTimeSimulation();
});

/* ========================================
   Navigation
   ======================================== */
function initNavigation() {
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', () => {
            const isActive = hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
            
            // Accessibilité - mise à jour aria-expanded
            hamburger.setAttribute('aria-expanded', isActive);
            
            // Empêcher le scroll du body quand le menu est ouvert
            document.body.style.overflow = isActive ? 'hidden' : '';
        });

        // Fermer le menu mobile au clic sur un lien
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                hamburger.setAttribute('aria-expanded', 'false');
                document.body.style.overflow = '';
            });
        });

        // Fermer le menu avec la touche Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && navLinks.classList.contains('active')) {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                hamburger.setAttribute('aria-expanded', 'false');
                document.body.style.overflow = '';
                hamburger.focus();
            }
        });

        // Fermer le menu au clic en dehors
        document.addEventListener('click', (e) => {
            if (navLinks.classList.contains('active') && 
                !navLinks.contains(e.target) && 
                !hamburger.contains(e.target)) {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                hamburger.setAttribute('aria-expanded', 'false');
                document.body.style.overflow = '';
            }
        });
    }
}

/* ========================================
   Page d'accueil
   ======================================== */
function initHomePage() {
    // Vérifier si on est sur la page d'accueil
    if (!document.getElementById('total-places')) return;

    updateStats();
    updateProgressRing();
    generateParkingPreview();
}

// Mettre à jour les statistiques
function updateStats() {
    const stats = ParkingData.getStats();

    // Animation des nombres
    animateNumber('total-places', stats.total);
    animateNumber('available-places', stats.available);
    animateNumber('occupied-places', stats.occupied + stats.reserved);
    animateNumber('occupation-rate', stats.occupationRate, '%');

    // Mettre à jour l'indicateur de statut
    updateStatusIndicator(stats.occupationRate);
}

// Animation des nombres
function animateNumber(elementId, targetValue, suffix = '') {
    const element = document.getElementById(elementId);
    if (!element) return;

    const startValue = 0;
    const duration = 1000;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const currentValue = Math.round(startValue + (targetValue - startValue) * easeOutQuart);
        
        element.textContent = currentValue + suffix;

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// Mettre à jour l'anneau de progression
function updateProgressRing() {
    const stats = ParkingData.getStats();
    const progressCircle = document.getElementById('progress-circle');
    const progressPercent = document.getElementById('progress-percent');
    
    if (!progressCircle || !progressPercent) return;

    const circumference = 2 * Math.PI * 90; // rayon = 90
    const offset = circumference - (stats.occupationRate / 100) * circumference;
    
    progressCircle.style.strokeDasharray = circumference;
    progressCircle.style.strokeDashoffset = offset;

    // Changer la couleur selon le taux d'occupation
    if (stats.occupationRate < 50) {
        progressCircle.style.stroke = 'var(--available-color)';
    } else if (stats.occupationRate < 80) {
        progressCircle.style.stroke = 'var(--reserved-color)';
    } else {
        progressCircle.style.stroke = 'var(--occupied-color)';
    }

    progressPercent.textContent = stats.occupationRate + '%';
}

// Mettre à jour l'indicateur de statut
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

// Générer l'aperçu du parking
function generateParkingPreview() {
    const container = document.getElementById('parking-preview');
    if (!container) return;

    container.innerHTML = '';
    const spots = ParkingData.getAllSpots();

    spots.forEach(spot => {
        const spotElement = document.createElement('div');
        spotElement.className = `parking-spot-mini ${spot.status}`;
        spotElement.textContent = spot.id;
        spotElement.title = `Place ${spot.id} - ${getStatusLabel(spot.status)}`;
        container.appendChild(spotElement);
    });
}

// Obtenir le label du statut
function getStatusLabel(status) {
    const labels = {
        'available': 'Disponible',
        'occupied': 'Occupée',
        'reserved': 'Réservée'
    };
    return labels[status] || status;
}

/* ========================================
   Mise à jour en temps réel
   ======================================== */
let updateInterval = null;

function startRealTimeSimulation() {
    // Mettre à jour toutes les 2 secondes
    updateInterval = setInterval(() => {
        // Vérifier les réservations expirées
        ParkingData.checkExpiredReservations();
        
        // Mettre à jour l'affichage
        updateStats();
        updateProgressRing();
        generateParkingPreview();
        
        // Mettre à jour aussi la page de réservation si on y est
        if (typeof updateParkingGrid === 'function') {
            updateParkingGrid();
        }
        if (typeof updateCountdowns === 'function') {
            updateCountdowns();
        }
    }, 2000);
}

function stopRealTimeSimulation() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

/* ========================================
   Utilitaires
   ======================================== */

// Formater une date
function formatDate(dateString) {
    const options = { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return new Date(dateString).toLocaleDateString('fr-FR', options);
}

// Afficher une notification
function showNotification(message, type = 'success') {
    // Supprimer les notifications existantes
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;

    // Styles inline pour la notification
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: ${type === 'success' ? 'var(--secondary-color)' : type === 'error' ? 'var(--danger-color)' : 'var(--primary-color)'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-lg);
        display: flex;
        align-items: center;
        gap: 0.75rem;
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(notification);

    // Auto-remove après 3 secondes
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Ajouter l'animation fadeOut
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100px); }
    }
`;
document.head.appendChild(style);
