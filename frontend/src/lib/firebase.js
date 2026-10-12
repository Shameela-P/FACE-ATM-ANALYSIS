/**
 * Firebase Client SDK Initialization & Services
 * Uses Firebase v10+ modular API with persistent authentication.
 */

import { initializeApp, getApps, getApp } from 'firebase/app';
import {
	getAuth,
	setPersistence,
	browserLocalPersistence,
	signInWithEmailAndPassword,
	signOut,
	onAuthStateChanged
} from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

// Client-side environment configuration from Vite
const firebaseConfig = {
	apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
	authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
	projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
	storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
	messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
	appId: import.meta.env.VITE_FIREBASE_APP_ID || ''
};

// Check if credentials have been populated with real values
export const isFirebaseConfigured = () => {
	return Boolean(
		firebaseConfig.apiKey &&
		firebaseConfig.apiKey !== 'your_firebase_api_key_here' &&
		firebaseConfig.projectId &&
		firebaseConfig.projectId !== 'your_project_id'
	);
};

// Initialize Firebase App singleton safely
let app;
let auth = null;
let db = null;

try {
	if (isFirebaseConfigured()) {
		app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
		auth = getAuth(app);
		// Configure persistent authentication
		if (typeof window !== 'undefined') {
			setPersistence(auth, browserLocalPersistence).catch((err) => {
				console.warn('Could not set browserLocalPersistence:', err);
			});
		}
		db = getFirestore(app);
	}
} catch (error) {
	console.error('Firebase initialization error:', error);
}

export { app, auth, db };

/**
 * Sign in admin user with email and password
 * @param {string} email
 * @param {string} password
 */
export async function loginAdmin(email, password) {
	if (!auth) {
		throw new Error(
			'Firebase is not yet configured. Please set your VITE_FIREBASE_* environment variables in frontend/.env.'
		);
	}
	return await signInWithEmailAndPassword(auth, email, password);
}

/**
 * Sign out current admin user
 */
export async function logoutAdmin() {
	if (!auth) return;
	return await signOut(auth);
}

/**
 * Retrieve current user's ID token for sending to the backend API
 */
export async function getAdminToken() {
	if (!auth || !auth.currentUser) return null;
	return await auth.currentUser.getIdToken();
}
