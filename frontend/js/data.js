/* ========================================
   AeroPark Smart System - Data Management
   Gestion des données avec capteurs ESP8266
   ======================================== */

const ParkingData = {
    // Configuration par défaut (modifiable par l'admin)
    getConfig() {
        const saved = localStorage.getItem('aeropark_config');
        return saved ? JSON.parse(saved) : {
            totalSpots: 5,
            hourlyRate: 1000, // FC par heure
            maxDuration: 168, // 1 semaine max
            currency: 'FC'
        };
    },

    saveConfig(config) {
        localStorage.setItem('aeropark_config', JSON.stringify(config));
    },

    // Initialiser les données de parking
    init() {
        if (!localStorage.getItem('parkingSpots')) {
            this.generateParkingSpots();
        }
        if (!localStorage.getItem('reservations')) {
            localStorage.setItem('reservations', JSON.stringify([]));
        }
        // Nettoyer les réservations obsolètes
        this.cleanupObsoleteReservations();
        // Vérifier les réservations expirées
        this.checkExpiredReservations();
    },

    // Générer les places de parking
    generateParkingSpots() {
        const config = this.getConfig();
        const spots = [];
        
        for (let spot = 1; spot <= config.totalSpots; spot++) {
            const id = `P${spot}`;
            spots.push({
                id: id,
                row: 'P',
                number: spot,
                status: 'available', // available, reserved, occupied
                reservedBy: null,
                reservedAt: null,
                reservationEndTime: null,
                duration: null,
                vehiclePlate: null,
                sensorId: `ESP8266_${spot}`,
                sensorDetected: false, // État du capteur physique
                lastSensorUpdate: null,
                createdAt: new Date().toISOString()
            });
        }
        
        localStorage.setItem('parkingSpots', JSON.stringify(spots));
        return spots;
    },

    // ========================================
    // GESTION DES PLACES PAR L'ADMIN
    // ========================================
    
    // Ajouter une nouvelle place (Admin)
    addSpot() {
        const spots = this.getAllSpots();
        const newNumber = spots.length + 1;
        const newSpot = {
            id: `P${newNumber}`,
            row: 'P',
            number: newNumber,
            status: 'available',
            reservedBy: null,
            reservedAt: null,
            reservationEndTime: null,
            duration: null,
            vehiclePlate: null,
            sensorId: `ESP8266_${newNumber}`,
            sensorDetected: false,
            lastSensorUpdate: null,
            createdAt: new Date().toISOString()
        };
        
        spots.push(newSpot);
        localStorage.setItem('parkingSpots', JSON.stringify(spots));
        
        // Mettre à jour la config
        const config = this.getConfig();
        config.totalSpots = spots.length;
        this.saveConfig(config);
        
        return newSpot;
    },

    // Supprimer une place (Admin) - seulement si disponible
    removeSpot(spotId) {
        const spots = this.getAllSpots();
        const spot = spots.find(s => s.id === spotId);
        
        if (!spot) return { success: false, message: 'Place non trouvée' };
        if (spot.status !== 'available') {
            return { success: false, message: 'Impossible de supprimer une place réservée ou occupée' };
        }
        
        const newSpots = spots.filter(s => s.id !== spotId);
        // Renuméroter les places
        newSpots.forEach((s, index) => {
            s.id = `P${index + 1}`;
            s.number = index + 1;
            s.sensorId = `ESP8266_${index + 1}`;
        });
        
        localStorage.setItem('parkingSpots', JSON.stringify(newSpots));
        
        // Mettre à jour la config
        const config = this.getConfig();
        config.totalSpots = newSpots.length;
        this.saveConfig(config);
        
        return { success: true, message: 'Place supprimée' };
    },

    // ========================================
    // GESTION DES CAPTEURS ESP8266
    // ========================================
    
    // Recevoir les données d'un capteur ESP8266
    // Appelé par le backend Python via API
    updateFromSensor(sensorId, isDetected) {
        const spots = this.getAllSpots();
        const spotIndex = spots.findIndex(s => s.sensorId === sensorId);
        
        if (spotIndex === -1) return { success: false, message: 'Capteur non trouvé' };
        
        const spot = spots[spotIndex];
        const previousState = spot.sensorDetected;
        
        spots[spotIndex].sensorDetected = isDetected;
        spots[spotIndex].lastSensorUpdate = new Date().toISOString();
        
        // LOGIQUE PRINCIPALE :
        // Si la place est RÉSERVÉE et le capteur DÉTECTE une voiture → OCCUPÉE
        if (spot.status === 'reserved' && isDetected) {
            spots[spotIndex].status = 'occupied';
            // La voiture est arrivée ! Le temps continue de s'écouler depuis la réservation
        }
        
        // Si la place est OCCUPÉE et le capteur NE DÉTECTE PLUS → la voiture est partie
        if (spot.status === 'occupied' && !isDetected) {
            // Vérifier si la réservation est encore valide
            const endTime = new Date(spot.reservationEndTime);
            if (new Date() < endTime) {
                // La voiture est partie mais le temps n'est pas écoulé
                // On remet en "reserved" car le client a payé
                spots[spotIndex].status = 'reserved';
            } else {
                // Le temps est écoulé, libérer la place
                spots[spotIndex].status = 'available';
                spots[spotIndex].reservedBy = null;
                spots[spotIndex].reservedAt = null;
                spots[spotIndex].reservationEndTime = null;
                spots[spotIndex].duration = null;
                spots[spotIndex].vehiclePlate = null;
            }
        }
        
        // Si la place est AVAILABLE et capteur DÉTECTE → occupation sans réservation (alerte !)
        if (spot.status === 'available' && isDetected) {
            spots[spotIndex].status = 'occupied';
            spots[spotIndex].unauthorizedOccupation = true; // Flag pour l'admin
        }
        
        localStorage.setItem('parkingSpots', JSON.stringify(spots));
        
        return { 
            success: true, 
            spotId: spot.id,
            previousState,
            newState: isDetected,
            status: spots[spotIndex].status
        };
    },

    // Mise à jour batch depuis plusieurs capteurs
    updateFromSensors(sensorData) {
        // sensorData = { "ESP8266_1": true, "ESP8266_2": false, ... }
        const results = {};
        Object.entries(sensorData).forEach(([sensorId, isDetected]) => {
            results[sensorId] = this.updateFromSensor(sensorId, isDetected);
        });
        return results;
    },

    // Obtenir l'état de tous les capteurs (pour le backend)
    getSensorStatus() {
        const spots = this.getAllSpots();
        return spots.map(spot => ({
            sensorId: spot.sensorId,
            spotId: spot.id,
            status: spot.status,
            sensorDetected: spot.sensorDetected,
            lastUpdate: spot.lastSensorUpdate,
            reservedBy: spot.reservedBy,
            remainingTime: this.getRemainingTime(spot.id)
        }));
    },

    // ========================================
    // GESTION DES RÉSERVATIONS
    // ========================================
    
    // Réserver une place (le temps commence MAINTENANT)
    reserveSpot(spotId, userId, duration, vehiclePlate = null) {
        const spot = this.getSpotById(spotId);
        if (!spot) return { success: false, message: 'Place non trouvée' };
        if (spot.status !== 'available') {
            return { success: false, message: 'Place non disponible' };
        }
        
        const now = new Date();
        const endTime = new Date(now.getTime() + (duration * 60 * 60 * 1000)); // durée en heures
        
        this.updateSpot(spotId, {
            status: 'reserved',
            reservedBy: userId,
            reservedAt: now.toISOString(),
            reservationEndTime: endTime.toISOString(),
            duration: duration,
            vehiclePlate: vehiclePlate
        });
        
        // Ajouter à l'historique
        const reservation = this.addReservation({
            spotId: spotId,
            userId: userId,
            duration: duration,
            vehiclePlate: vehiclePlate,
            startTime: now.toISOString(),
            endTime: endTime.toISOString(),
            amount: duration * this.getConfig().hourlyRate,
            status: 'active'
        });
        
        return { success: true, reservation, spot: this.getSpotById(spotId) };
    },

    // Calculer le temps restant d'une réservation
    getRemainingTime(spotId) {
        const spot = this.getSpotById(spotId);
        if (!spot || !spot.reservationEndTime) return null;
        
        const now = new Date();
        const endTime = new Date(spot.reservationEndTime);
        const remaining = endTime - now;
        
        if (remaining <= 0) return { expired: true, remaining: 0 };
        
        const hours = Math.floor(remaining / (1000 * 60 * 60));
        const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((remaining % (1000 * 60)) / 1000);
        
        return {
            expired: false,
            remaining: remaining,
            hours,
            minutes,
            seconds,
            formatted: `${hours}h ${minutes}m ${seconds}s`
        };
    },

    // Vérifier et libérer les réservations expirées
    checkExpiredReservations() {
        const spots = this.getAllSpots();
        const now = new Date();
        
        spots.forEach(spot => {
            if ((spot.status === 'reserved' || spot.status === 'occupied') && spot.reservationEndTime) {
                const endTime = new Date(spot.reservationEndTime);
                if (now >= endTime) {
                    // Réservation expirée
                    this.updateSpot(spot.id, {
                        status: 'available',
                        reservedBy: null,
                        reservedAt: null,
                        reservationEndTime: null,
                        duration: null,
                        vehiclePlate: null
                    });
                    
                    // Mettre à jour l'historique
                    this.updateReservationBySpot(spot.id, { status: 'completed' });
                }
            }
        });
    },

    // Obtenir toutes les places
    getAllSpots() {
        const spots = localStorage.getItem('parkingSpots');
        return spots ? JSON.parse(spots) : this.generateParkingSpots();
    },

    // Obtenir une place par ID
    getSpotById(id) {
        const spots = this.getAllSpots();
        return spots.find(spot => spot.id === id);
    },

    // Mettre à jour une place
    updateSpot(id, updates) {
        const spots = this.getAllSpots();
        const index = spots.findIndex(spot => spot.id === id);
        if (index !== -1) {
            spots[index] = { ...spots[index], ...updates };
            localStorage.setItem('parkingSpots', JSON.stringify(spots));
            return spots[index];
        }
        return null;
    },

    // Obtenir les statistiques
    getStats() {
        const spots = this.getAllSpots();
        const total = spots.length;
        const available = spots.filter(s => s.status === 'available').length;
        const occupied = spots.filter(s => s.status === 'occupied').length;
        const reserved = spots.filter(s => s.status === 'reserved').length;
        const rate = total > 0 ? Math.round(((occupied + reserved) / total) * 100) : 0;
        
        return {
            total,
            available,
            occupied,
            reserved,
            occupationRate: rate
        };
    },

    // ========================================
    // GESTION DE L'HISTORIQUE
    // ========================================

    addReservation(reservation) {
        const reservations = this.getReservations();
        reservation.id = Date.now().toString();
        reservation.createdAt = new Date().toISOString();
        reservations.push(reservation);
        localStorage.setItem('reservations', JSON.stringify(reservations));
        return reservation;
    },

    getReservations() {
        const reservations = localStorage.getItem('reservations');
        return reservations ? JSON.parse(reservations) : [];
    },

    getUserReservations(userId) {
        // Filtrer uniquement les réservations pour des places qui existent encore
        const validSpotIds = this.getAllSpots().map(s => s.id);
        return this.getReservations().filter(r => 
            r.userId === userId && validSpotIds.includes(r.spotId)
        );
    },

    getActiveUserReservations(userId) {
        // Filtrer uniquement les réservations actives pour des places existantes
        const validSpotIds = this.getAllSpots().map(s => s.id);
        return this.getReservations().filter(r => 
            r.userId === userId && 
            r.status === 'active' && 
            validSpotIds.includes(r.spotId)
        );
    },

    // Nettoyer les réservations obsolètes (places qui n'existent plus)
    cleanupObsoleteReservations() {
        const validSpotIds = this.getAllSpots().map(s => s.id);
        const reservations = this.getReservations();
        const cleanedReservations = reservations.filter(r => validSpotIds.includes(r.spotId));
        
        if (cleanedReservations.length !== reservations.length) {
            localStorage.setItem('reservations', JSON.stringify(cleanedReservations));
            console.log(`Nettoyage: ${reservations.length - cleanedReservations.length} réservations obsolètes supprimées`);
        }
        
        return cleanedReservations;
    },

    updateReservationBySpot(spotId, updates) {
        const reservations = this.getReservations();
        const index = reservations.findIndex(r => r.spotId === spotId && r.status === 'active');
        if (index !== -1) {
            reservations[index] = { ...reservations[index], ...updates };
            localStorage.setItem('reservations', JSON.stringify(reservations));
        }
    },

    cancelReservation(spotId, userId) {
        const spot = this.getSpotById(spotId);
        if (!spot) return { success: false, message: 'Place non trouvée' };
        if (spot.reservedBy !== userId) {
            return { success: false, message: 'Vous ne pouvez pas annuler cette réservation' };
        }
        
        this.updateSpot(spotId, {
            status: 'available',
            reservedBy: null,
            reservedAt: null,
            reservationEndTime: null,
            duration: null,
            vehiclePlate: null
        });
        
        this.updateReservationBySpot(spotId, { status: 'cancelled' });
        
        return { success: true, message: 'Réservation annulée' };
    },

    // ========================================
    // UTILITAIRES
    // ========================================

    reset() {
        localStorage.removeItem('parkingSpots');
        localStorage.removeItem('reservations');
        localStorage.removeItem('aeropark_config');
        this.init();
    },

    forceRegenerate() {
        localStorage.removeItem('parkingSpots');
        this.generateParkingSpots();
    },

    // API endpoint simulation (pour test sans backend)
    simulateSensorUpdate(spotNumber, isDetected) {
        return this.updateFromSensor(`ESP8266_${spotNumber}`, isDetected);
    }
};

// Initialisation
(function() {
    const existingSpots = localStorage.getItem('parkingSpots');
    if (existingSpots) {
        const spots = JSON.parse(existingSpots);
        const config = ParkingData.getConfig();
        // Régénérer si la config a changé
        if (spots.length !== config.totalSpots && !localStorage.getItem('aeropark_config')) {
            ParkingData.forceRegenerate();
        }
    }
    ParkingData.init();
    
    // Vérifier les réservations expirées toutes les minutes
    setInterval(() => {
        ParkingData.checkExpiredReservations();
    }, 60000);
})();
