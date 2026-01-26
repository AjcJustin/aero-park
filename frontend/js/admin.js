// Configuration Admin par défaut
const DEFAULT_ADMIN = {
    username: 'Abraham',
    password: '123456',
    name: 'Administrateur'
};

// Authentification Admin
const AdminAuth = {
    storageKey: 'aeropark_admin_session',
    adminsKey: 'aeropark_admins',

    // Initialiser les admins
    init() {
        if (!localStorage.getItem(this.adminsKey)) {
            localStorage.setItem(this.adminsKey, JSON.stringify([DEFAULT_ADMIN]));
        }
    },

    // Connexion admin
    login(username, password) {
        this.init();
        const admins = JSON.parse(localStorage.getItem(this.adminsKey));
        const admin = admins.find(a => a.username === username && a.password === password);

        if (admin) {
            const session = {
                username: admin.username,
                name: admin.name,
                loginAt: new Date().toISOString()
            };
            localStorage.setItem(this.storageKey, JSON.stringify(session));
            return { success: true, message: 'Connexion réussie' };
        }

        return { success: false, message: 'Identifiant ou mot de passe incorrect' };
    },

    // Déconnexion
    logout() {
        localStorage.removeItem(this.storageKey);
    },

    // Vérifier si connecté
    isLoggedIn() {
        return localStorage.getItem(this.storageKey) !== null;
    },

    // Obtenir l'admin actuel
    getCurrentAdmin() {
        const session = localStorage.getItem(this.storageKey);
        return session ? JSON.parse(session) : null;
    },

    // Changer le mot de passe
    changePassword(oldPassword, newPassword) {
        const admins = JSON.parse(localStorage.getItem(this.adminsKey));
        const currentAdmin = this.getCurrentAdmin();
        
        if (!currentAdmin) return { success: false, message: 'Non connecté' };

        const adminIndex = admins.findIndex(a => a.username === currentAdmin.username);
        
        if (adminIndex === -1) return { success: false, message: 'Admin non trouvé' };
        
        if (admins[adminIndex].password !== oldPassword) {
            return { success: false, message: 'Ancien mot de passe incorrect' };
        }

        admins[adminIndex].password = newPassword;
        localStorage.setItem(this.adminsKey, JSON.stringify(admins));
        
        return { success: true, message: 'Mot de passe modifié avec succès' };
    }
};

// Gestion des utilisateurs
const UserManager = {
    getAll() {
        return JSON.parse(localStorage.getItem('aeropark_users') || '[]');
    },

    getById(userId) {
        const users = this.getAll();
        return users.find(u => u.id === userId);
    },

    update(userId, updates) {
        const users = this.getAll();
        const index = users.findIndex(u => u.id === userId);
        if (index !== -1) {
            users[index] = { ...users[index], ...updates };
            localStorage.setItem('aeropark_users', JSON.stringify(users));
            return true;
        }
        return false;
    },

    delete(userId) {
        const users = this.getAll();
        const filtered = users.filter(u => u.id !== userId);
        localStorage.setItem('aeropark_users', JSON.stringify(filtered));
        return true;
    },

    block(userId) {
        return this.update(userId, { blocked: true });
    },

    unblock(userId) {
        return this.update(userId, { blocked: false });
    },

    getStats() {
        const users = this.getAll();
        return {
            total: users.length,
            blocked: users.filter(u => u.blocked).length,
            active: users.filter(u => !u.blocked).length
        };
    }
};

// Gestion des paiements
const PaymentManager = {
    getAll() {
        return JSON.parse(localStorage.getItem('aeropark_payments') || '[]');
    },

    getByDateRange(startDate, endDate) {
        const payments = this.getAll();
        return payments.filter(p => {
            const date = new Date(p.paidAt);
            return date >= startDate && date <= endDate;
        });
    },

    getByMethod(method) {
        const payments = this.getAll();
        return payments.filter(p => p.paymentMethod === method);
    },

    getTotalRevenue() {
        const payments = this.getAll();
        return payments.reduce((sum, p) => sum + (p.amount || 0), 0);
    },

    getRevenueByMethod() {
        const payments = this.getAll();
        const byMethod = {};
        
        payments.forEach(p => {
            if (!byMethod[p.paymentMethod]) {
                byMethod[p.paymentMethod] = 0;
            }
            byMethod[p.paymentMethod] += p.amount || 0;
        });
        
        return byMethod;
    },

    getStats() {
        const payments = this.getAll();
        return {
            total: payments.length,
            completed: payments.filter(p => p.status === 'completed').length,
            failed: payments.filter(p => p.status === 'failed').length,
            revenue: this.getTotalRevenue()
        };
    }
};

// Gestion des réservations
const ReservationManager = {
    getAll() {
        // Nettoyer d'abord les réservations obsolètes
        ParkingData.cleanupObsoleteReservations();
        
        // Filtrer uniquement les réservations pour des places qui existent
        const validSpotIds = ParkingData.getAllSpots().map(s => s.id);
        return ParkingData.getReservations().filter(r => validSpotIds.includes(r.spotId));
    },

    getActive() {
        return this.getAll().filter(r => r.status === 'active');
    },

    getById(reservationId) {
        return this.getAll().find(r => r.id === reservationId);
    },

    cancel(reservationId) {
        const reservations = ParkingData.getReservations();
        const index = reservations.findIndex(r => r.id === reservationId);
        
        if (index !== -1) {
            const reservation = reservations[index];
            reservations[index].status = 'cancelled';
            localStorage.setItem('reservations', JSON.stringify(reservations));
            
            // Libérer la place si elle existe
            const spot = ParkingData.getSpotById(reservation.spotId);
            if (spot) {
                ParkingData.updateSpot(reservation.spotId, {
                    status: 'available',
                    reservedBy: null,
                    reservedAt: null,
                    reservationEndTime: null,
                    duration: null,
                    vehiclePlate: null
                });
            }
            
            return true;
        }
        return false;
    },

    complete(reservationId) {
        const reservations = ParkingData.getReservations();
        const index = reservations.findIndex(r => r.id === reservationId);
        
        if (index !== -1) {
            const reservation = reservations[index];
            reservations[index].status = 'completed';
            localStorage.setItem('reservations', JSON.stringify(reservations));
            
            // Libérer la place si elle existe
            const spot = ParkingData.getSpotById(reservation.spotId);
            if (spot) {
                ParkingData.updateSpot(reservation.spotId, {
                    status: 'available',
                    reservedBy: null,
                    reservedAt: null,
                    reservationEndTime: null,
                    duration: null,
                    vehiclePlate: null
                });
            }
            
            return true;
        }
        return false;
    },

    getStats() {
        const reservations = this.getAll();
        return {
            total: reservations.length,
            active: reservations.filter(r => r.status === 'active').length,
            cancelled: reservations.filter(r => r.status === 'cancelled').length,
            completed: reservations.filter(r => r.status === 'completed').length
        };
    }
};

// Paramètres du parking
const ParkingSettings = {
    storageKey: 'aeropark_settings',

    getDefaults() {
        return {
            parkingName: 'AeroPark GOMA',
            totalSpots: 50,
            ratePerHour: 1000,
            currency: 'FC',
            maxDuration: 168,
            address: 'Aéroport de Goma, RDC',
            phone: '+243 XXX XXX XXX',
            email: 'aeroportgoma@gmail.com'
        };
    },

    get() {
        const settings = localStorage.getItem(this.storageKey);
        return settings ? JSON.parse(settings) : this.getDefaults();
    },

    update(newSettings) {
        const current = this.get();
        const updated = { ...current, ...newSettings };
        localStorage.setItem(this.storageKey, JSON.stringify(updated));
        return updated;
    },

    reset() {
        localStorage.setItem(this.storageKey, JSON.stringify(this.getDefaults()));
        return this.getDefaults();
    }
};

// Utilitaires
const AdminUtils = {
    formatDate(dateString) {
        return new Date(dateString).toLocaleDateString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatMoney(amount) {
        return amount.toLocaleString('fr-FR') + ' FC';
    },

    exportToCSV(data, filename) {
        if (data.length === 0) return;

        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(h => `"${row[h] || ''}"`).join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
    },

    showNotification(message, type = 'success') {
        const existing = document.querySelector('.admin-notification');
        if (existing) existing.remove();

        const notification = document.createElement('div');
        notification.className = `admin-notification ${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'}"></i>
            <div class="notification-content">
                <strong>${type === 'success' ? 'Succès' : 'Erreur'}</strong>
                <span>${message}</span>
            </div>
            <button class="notification-close" onclick="this.parentElement.classList.remove('show'); setTimeout(() => this.parentElement.remove(), 300)">
                <i class="fas fa-times"></i>
            </button>
        `;
        notification.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            padding: 1rem 1.25rem;
            background: white;
            color: #334155;
            border-radius: 14px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 1rem;
            z-index: 100000;
            transform: translateX(120%);
            transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            border-left: 4px solid ${type === 'success' ? '#10b981' : '#ef4444'};
            max-width: 400px;
        `;

        // Styles pour le contenu
        const content = notification.querySelector('.notification-content');
        content.style.cssText = `
            display: flex;
            flex-direction: column;
            gap: 0.125rem;
            flex: 1;
        `;
        content.querySelector('strong').style.cssText = `
            font-size: 0.9rem;
            color: ${type === 'success' ? '#059669' : '#dc2626'};
        `;
        content.querySelector('span').style.cssText = `
            font-size: 0.875rem;
            color: #64748b;
        `;

        // Style pour l'icône
        notification.querySelector('i:first-child').style.cssText = `
            font-size: 1.5rem;
            color: ${type === 'success' ? '#10b981' : '#ef4444'};
        `;

        // Style pour le bouton close
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.style.cssText = `
            background: #f1f5f9;
            border: none;
            width: 28px;
            height: 28px;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #94a3b8;
            transition: all 0.2s ease;
        `;

        document.body.appendChild(notification);
        
        // Trigger animation
        requestAnimationFrame(() => {
            notification.classList.add('show');
            notification.style.transform = 'translateX(0)';
        });

        // Auto-remove after 4 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(120%)';
            setTimeout(() => notification.remove(), 400);
        }, 4000);
    }
};

// Initialisation de AdminAuth
AdminAuth.init();
