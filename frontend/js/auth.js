/* 
   AeroPark Smart System - Authentication
   Gestion de l'authentification côté client
 */

const Auth = {
    // Clé de stockage
    storageKey: 'aeropark_users',
    sessionKey: 'aeropark_session',

    // Initialiser le stockage des utilisateurs
    init() {
        if (!localStorage.getItem(this.storageKey)) {
            localStorage.setItem(this.storageKey, JSON.stringify([]));
        }
    },

    // Obtenir tous les utilisateurs
    getUsers() {
        const users = localStorage.getItem(this.storageKey);
        return users ? JSON.parse(users) : [];
    },

    // Trouver un utilisateur par email
    findUserByEmail(email) {
        const users = this.getUsers();
        return users.find(user => user.email.toLowerCase() === email.toLowerCase());
    },

    // Inscription d'un nouvel utilisateur
    register(name, email, password) {
        // Validation
        if (!name || !email || !password) {
            return { success: false, message: 'Tous les champs sont obligatoires.' };
        }

        if (!this.isValidEmail(email)) {
            return { success: false, message: 'Adresse email invalide.' };
        }

        if (password.length < 6) {
            return { success: false, message: 'Le mot de passe doit contenir au moins 6 caractères.' };
        }

        // Vérifier si l'email existe déjà
        if (this.findUserByEmail(email)) {
            return { success: false, message: 'Cette adresse email est déjà utilisée.' };
        }

        // Créer le nouvel utilisateur
        const users = this.getUsers();
        const newUser = {
            id: Date.now().toString(),
            name: name.trim(),
            email: email.toLowerCase().trim(),
            password: this.hashPassword(password), // Simulation de hashage
            createdAt: new Date().toISOString()
        };

        users.push(newUser);
        localStorage.setItem(this.storageKey, JSON.stringify(users));

        return { success: true, message: 'Inscription réussie !', user: this.sanitizeUser(newUser) };
    },

    // Connexion d'un utilisateur
    login(email, password) {
        // Validation
        if (!email || !password) {
            return { success: false, message: 'Email et mot de passe requis.' };
        }

        const user = this.findUserByEmail(email);
        
        if (!user) {
            return { success: false, message: 'Aucun compte trouvé avec cette adresse email.' };
        }

        if (user.password !== this.hashPassword(password)) {
            return { success: false, message: 'Mot de passe incorrect.' };
        }

        // Créer la session
        const session = {
            userId: user.id,
            name: user.name,
            email: user.email,
            loginAt: new Date().toISOString()
        };

        localStorage.setItem(this.sessionKey, JSON.stringify(session));

        return { success: true, message: 'Connexion réussie !', user: this.sanitizeUser(user) };
    },

    // Déconnexion
    logout() {
        localStorage.removeItem(this.sessionKey);
        return { success: true, message: 'Déconnexion réussie.' };
    },

    // Vérifier si l'utilisateur est connecté
    isLoggedIn() {
        return localStorage.getItem(this.sessionKey) !== null;
    },

    // Obtenir l'utilisateur connecté
    getCurrentUser() {
        const session = localStorage.getItem(this.sessionKey);
        if (session) {
            return JSON.parse(session);
        }
        return null;
    },

    // Validation de l'email
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    // Simulation de hashage (à remplacer par un vrai hash côté backend)
    hashPassword(password) {
        // Simple simulation - NE PAS UTILISER EN PRODUCTION
        let hash = 0;
        for (let i = 0; i < password.length; i++) {
            const char = password.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return 'hash_' + Math.abs(hash).toString(16);
    },

    // Nettoyer les données utilisateur (retirer le mot de passe)
    sanitizeUser(user) {
        const { password, ...safeUser } = user;
        return safeUser;
    },

    // Mettre à jour l'interface selon l'état de connexion
    updateUI() {
        const authLinks = document.getElementById('auth-links');
        const userMenu = document.getElementById('user-menu');
        const userName = document.querySelector('.user-name');

        if (this.isLoggedIn()) {
            const user = this.getCurrentUser();
            if (authLinks) authLinks.classList.add('hidden');
            if (userMenu) {
                userMenu.classList.remove('hidden');
                if (userName) userName.textContent = user.name;
            }
        } else {
            if (authLinks) authLinks.classList.remove('hidden');
            if (userMenu) userMenu.classList.add('hidden');
        }
    },

    // Protéger une page (rediriger si non connecté)
    requireAuth(redirectUrl = '../pages/login.html') {
        if (!this.isLoggedIn()) {
            window.location.href = redirectUrl;
            return false;
        }
        return true;
    }
};

// Initialiser l'authentification
Auth.init();

// Mettre à jour l'UI au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    Auth.updateUI();

    // Gérer le bouton de déconnexion
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            Auth.logout();
            window.location.href = window.location.pathname.includes('/pages/') ? '../index.html' : 'index.html';
        });
    }
});
