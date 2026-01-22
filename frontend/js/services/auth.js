/**
 * AeroPark GOMA - Authentication Service
 * Firebase Authentication Integration
 */

// Firebase Configuration
const firebaseConfig = {
    apiKey: "AIzaSyB6xxxxxxxxxxxxxxxxxxxxxxxx", // Replace with your Firebase API key
    authDomain: "aeropark-a191e.firebaseapp.com",
    projectId: "aeropark-a191e",
    storageBucket: "aeropark-a191e.appspot.com",
    messagingSenderId: "123456789",
    appId: "1:123456789:web:xxxxxxxxxxxxxx"
};

// Auth Service
const AuthService = {
    user: null,
    token: null,
    role: null,
    initialized: false,
    authListeners: [],
    
    /**
     * Initialize Firebase Auth
     */
    async init() {
        if (this.initialized) return;
        
        try {
            // Check if Firebase is loaded
            if (typeof firebase === 'undefined') {
                console.error('[Auth] Firebase SDK not loaded');
                return;
            }
            
            // Initialize Firebase
            if (!firebase.apps.length) {
                firebase.initializeApp(firebaseConfig);
            }
            
            // Listen for auth state changes
            firebase.auth().onAuthStateChanged(async (user) => {
                if (user) {
                    // User is signed in
                    this.user = user;
                    this.token = await user.getIdToken();
                    
                    // Store token
                    localStorage.setItem('aeropark_token', this.token);
                    localStorage.setItem('aeropark_user', JSON.stringify({
                        uid: user.uid,
                        email: user.email,
                        displayName: user.displayName,
                        photoURL: user.photoURL
                    }));
                    
                    // Get user role from backend
                    await this.fetchUserRole();
                    
                    console.log('[Auth] User signed in:', user.email);
                } else {
                    // User is signed out
                    this.user = null;
                    this.token = null;
                    this.role = null;
                    
                    localStorage.removeItem('aeropark_token');
                    localStorage.removeItem('aeropark_user');
                    localStorage.removeItem('aeropark_role');
                    
                    console.log('[Auth] User signed out');
                }
                
                // Notify listeners
                this.notifyListeners();
            });
            
            this.initialized = true;
            console.log('[Auth] Initialized');
        } catch (error) {
            console.error('[Auth] Initialization failed:', error);
        }
    },
    
    /**
     * Fetch user role from backend
     */
    async fetchUserRole() {
        try {
            const response = await ApiService.getProfile();
            this.role = response.role || 'user';
            localStorage.setItem('aeropark_role', this.role);
            
            // Update body class for role-based CSS
            document.body.classList.remove('role-admin', 'role-user');
            document.body.classList.add(`role-${this.role}`);
            
            console.log('[Auth] User role:', this.role);
        } catch (error) {
            console.error('[Auth] Failed to fetch user role:', error);
            this.role = 'user';
        }
    },
    
    /**
     * Register with email and password
     */
    async register(email, password, displayName) {
        try {
            const credential = await firebase.auth().createUserWithEmailAndPassword(email, password);
            
            // Update display name
            if (displayName) {
                await credential.user.updateProfile({ displayName });
            }
            
            console.log('[Auth] Registration successful');
            return { success: true, user: credential.user };
        } catch (error) {
            console.error('[Auth] Registration failed:', error);
            return { success: false, error: this.getErrorMessage(error.code) };
        }
    },
    
    /**
     * Sign in with email and password
     */
    async login(email, password) {
        try {
            const credential = await firebase.auth().signInWithEmailAndPassword(email, password);
            console.log('[Auth] Login successful');
            return { success: true, user: credential.user };
        } catch (error) {
            console.error('[Auth] Login failed:', error);
            return { success: false, error: this.getErrorMessage(error.code) };
        }
    },
    
    /**
     * Sign in with Google
     */
    async loginWithGoogle() {
        try {
            const provider = new firebase.auth.GoogleAuthProvider();
            const credential = await firebase.auth().signInWithPopup(provider);
            console.log('[Auth] Google login successful');
            return { success: true, user: credential.user };
        } catch (error) {
            console.error('[Auth] Google login failed:', error);
            return { success: false, error: this.getErrorMessage(error.code) };
        }
    },
    
    /**
     * Sign out
     */
    async logout() {
        try {
            await firebase.auth().signOut();
            console.log('[Auth] Logout successful');
            return { success: true };
        } catch (error) {
            console.error('[Auth] Logout failed:', error);
            return { success: false, error: error.message };
        }
    },
    
    /**
     * Send password reset email
     */
    async resetPassword(email) {
        try {
            await firebase.auth().sendPasswordResetEmail(email);
            console.log('[Auth] Password reset email sent');
            return { success: true };
        } catch (error) {
            console.error('[Auth] Password reset failed:', error);
            return { success: false, error: this.getErrorMessage(error.code) };
        }
    },
    
    /**
     * Get current token (refreshed if needed)
     */
    async getToken() {
        if (this.user) {
            try {
                this.token = await this.user.getIdToken(true);
                localStorage.setItem('aeropark_token', this.token);
                return this.token;
            } catch (error) {
                console.error('[Auth] Token refresh failed:', error);
            }
        }
        return localStorage.getItem('aeropark_token');
    },
    
    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.user || !!localStorage.getItem('aeropark_token');
    },
    
    /**
     * Check if user is admin
     */
    isAdmin() {
        return this.role === 'admin' || localStorage.getItem('aeropark_role') === 'admin';
    },
    
    /**
     * Get current user
     */
    getCurrentUser() {
        if (this.user) {
            return {
                uid: this.user.uid,
                email: this.user.email,
                displayName: this.user.displayName,
                photoURL: this.user.photoURL,
                role: this.role
            };
        }
        
        const storedUser = localStorage.getItem('aeropark_user');
        if (storedUser) {
            return {
                ...JSON.parse(storedUser),
                role: localStorage.getItem('aeropark_role')
            };
        }
        
        return null;
    },
    
    /**
     * Add auth state listener
     */
    onAuthStateChanged(callback) {
        this.authListeners.push(callback);
        
        // Return unsubscribe function
        return () => {
            this.authListeners = this.authListeners.filter(cb => cb !== callback);
        };
    },
    
    /**
     * Notify all listeners
     */
    notifyListeners() {
        const user = this.getCurrentUser();
        this.authListeners.forEach(callback => callback(user));
    },
    
    /**
     * Get user-friendly error message
     */
    getErrorMessage(errorCode) {
        const messages = {
            'auth/email-already-in-use': 'This email is already registered',
            'auth/invalid-email': 'Please enter a valid email address',
            'auth/operation-not-allowed': 'Email/password accounts are not enabled',
            'auth/weak-password': 'Password should be at least 6 characters',
            'auth/user-disabled': 'This account has been disabled',
            'auth/user-not-found': 'No account found with this email',
            'auth/wrong-password': 'Incorrect password',
            'auth/too-many-requests': 'Too many failed attempts. Please try again later',
            'auth/network-request-failed': 'Network error. Please check your connection',
            'auth/popup-closed-by-user': 'Sign-in popup was closed',
            'auth/cancelled-popup-request': 'Sign-in was cancelled'
        };
        
        return messages[errorCode] || 'An error occurred. Please try again';
    }
};

// Export for use in other modules
window.AuthService = AuthService;
