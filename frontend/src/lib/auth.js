/**
 * Authentication state management and helpers.
 */

import { writable } from 'svelte/store';
import { auth, isFirebaseConfigured, logoutAdmin } from './firebase.js';
import { onAuthStateChanged } from 'firebase/auth';

export const adminUser = writable(null);
export const authLoading = writable(true);
export const authConfigured = writable(isFirebaseConfigured());

let unsubscribe = null;

/**
 * Initialize persistent auth listener on the browser.
 */
export function initializeAuth() {
	if (typeof window === 'undefined') return;

	if (!isFirebaseConfigured() || !auth) {
		authConfigured.set(false);
		authLoading.set(false);
		return;
	}

	authConfigured.set(true);

	if (unsubscribe) return;

	unsubscribe = onAuthStateChanged(
		auth,
		(user) => {
			if (user) {
				adminUser.set({
					uid: user.uid,
					email: user.email,
					displayName: user.displayName || 'Administrator'
				});
			} else {
				adminUser.set(null);
			}
			authLoading.set(false);
		},
		(error) => {
			console.error('Auth state change error:', error);
			adminUser.set(null);
			authLoading.set(false);
		}
	);
}

/**
 * Clean user-friendly error message generator from Firebase Auth error codes.
 * @param {Error|{code: string, message: string}} error
 * @returns {string}
 */
export function getFriendlyAuthErrorMessage(error) {
	if (!error) return 'An unexpected error occurred.';

	const code = error.code || '';
	switch (code) {
		case 'auth/invalid-credential':
		case 'auth/wrong-password':
		case 'auth/user-not-found':
			return 'Invalid email or password. Please verify your credentials.';
		case 'auth/invalid-email':
			return 'Please provide a valid email address format.';
		case 'auth/too-many-requests':
			return 'Access temporarily blocked due to multiple failed attempts. Please try again later.';
		case 'auth/user-disabled':
			return 'This administrator account has been disabled.';
		case 'auth/network-request-failed':
			return 'Network connection failure. Please check your internet connectivity.';
		case 'auth/operation-not-allowed':
			return 'Email/Password authentication is not enabled in the Firebase Console.';
		default:
			return error.message || 'Authentication failed. Please verify your credentials.';
	}
}
