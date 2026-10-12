/**
 * Secure Backend API Client Helper for Face ATM.
 * Automatically attaches Firebase ID Bearer Token and formats errors.
 */

import { getAdminToken } from './firebase.js';

const DEFAULT_API_URL = import.meta.env.VITE_BACKEND_API_URL || 'http://localhost:8000';

/**
 * Determine effective backend base URL (supporting both localhost and 127.0.0.1 seamlessly)
 */
function getBaseUrl() {
	return DEFAULT_API_URL.replace(/\/+$/, '');
}

/**
 * Make an authenticated administrative request to the FastAPI backend.
 * @param {string} endpoint - API route (e.g. '/api/customers/register-initiate')
 * @param {object} options - Fetch options (method, body, headers)
 * @returns {Promise<any>}
 */
export async function apiRequest(endpoint, options = {}) {
	const token = await getAdminToken();

	if (!token) {
		throw new Error('Administrative session expired. Please sign in again.');
	}

	const headers = {
		'Content-Type': 'application/json',
		Accept: 'application/json',
		Authorization: `Bearer ${token}`,
		...(options.headers || {})
	};

	const url = `${getBaseUrl()}${endpoint}`;

	let res;
	try {
		res = await fetch(url, {
			...options,
			headers
		});
	} catch (networkError) {
		console.error('API connection error:', networkError);
		throw new Error(
			`Cannot connect to backend server at ${DEFAULT_API_URL}. Ensure FastAPI is running.`
		);
	}

	let data;
	const contentType = res.headers.get('content-type') || '';
	if (contentType.includes('application/json')) {
		data = await res.json();
	} else {
		data = { detail: await res.text() };
	}

	if (!res.ok) {
		// Extract clear message from FastAPI detail or validation errors
		let errorMessage = 'An error occurred while processing your request.';

		if (typeof data.detail === 'string') {
			errorMessage = data.detail;
		} else if (Array.isArray(data.detail)) {
			// Pydantic validation error array
			errorMessage = data.detail.map((err) => `${err.loc?.slice(-1)[0]}: ${err.msg}`).join(', ');
		} else if (data.message) {
			errorMessage = data.message;
		}

		const error = new Error(errorMessage);
		error.status = res.status;
		error.data = data;
		throw error;
	}

	return data;
}

/**
 * Make an authenticated administrative request to fetch a binary Blob (e.g. secure incident image).
 * @param {string} endpoint - API route (e.g. '/api/admin/security-approvals/123/image')
 * @param {object} options - Fetch options
 * @returns {Promise<Blob>}
 */
export async function apiFetchBlob(endpoint, options = {}) {
	const token = await getAdminToken();

	if (!token) {
		throw new Error('Administrative session expired. Please sign in again.');
	}

	const headers = {
		Authorization: `Bearer ${token}`,
		...(options.headers || {})
	};

	const url = `${getBaseUrl()}${endpoint}`;

	let res;
	try {
		res = await fetch(url, {
			...options,
			headers
		});
	} catch (networkError) {
		console.error('API binary connection error:', networkError);
		throw new Error(
			`Cannot connect to backend server at ${DEFAULT_API_URL}. Ensure FastAPI is running.`
		);
	}

	if (!res.ok) {
		let message = `Failed to retrieve media (HTTP ${res.status})`;
		try {
			const errJson = await res.json();
			if (errJson.detail) message = errJson.detail;
		} catch {
			// fallback
		}
		const error = new Error(message);
		error.status = res.status;
		throw error;
	}

	return await res.blob();
}

/**
 * Make an unauthenticated public API request (e.g. card validation, initial face login).
 * @param {string} endpoint
 * @param {object} options
 * @returns {Promise<any>}
 */
export async function publicApiRequest(endpoint, options = {}) {
	const headers = {
		'Content-Type': 'application/json',
		Accept: 'application/json',
		...(options.headers || {})
	};

	const url = `${getBaseUrl()}${endpoint}`;

	let res;
	try {
		res = await fetch(url, {
			...options,
			headers
		});
	} catch (networkError) {
		console.error('API connection error:', networkError);
		throw new Error(
			`Cannot connect to backend server at ${DEFAULT_API_URL}. Ensure FastAPI is running.`
		);
	}

	let data;
	const contentType = res.headers.get('content-type') || '';
	if (contentType.includes('application/json')) {
		data = await res.json();
	} else {
		data = { detail: await res.text() };
	}

	if (!res.ok) {
		let errorMessage = 'An error occurred while processing your request.';

		if (typeof data.detail === 'string') {
			errorMessage = data.detail;
		} else if (Array.isArray(data.detail)) {
			errorMessage = data.detail.map((err) => `${err.loc?.slice(-1)[0]}: ${err.msg}`).join(', ');
		} else if (data.message) {
			errorMessage = data.message;
		}

		const error = new Error(errorMessage);
		error.status = res.status;
		error.data = data;
		throw error;
	}

	return data;
}

const CUSTOMER_TOKEN_KEY = 'face_atm_customer_token';
const CUSTOMER_DATA_KEY = 'face_atm_customer_data';

export function setCustomerSession(token, customerData) {
	if (typeof window !== 'undefined') {
		sessionStorage.setItem(CUSTOMER_TOKEN_KEY, token);
		sessionStorage.setItem(CUSTOMER_DATA_KEY, JSON.stringify(customerData));
	}
}

export function getCustomerToken() {
	if (typeof window !== 'undefined') {
		return sessionStorage.getItem(CUSTOMER_TOKEN_KEY);
	}
	return null;
}

export function getCustomerSession() {
	if (typeof window !== 'undefined') {
		const raw = sessionStorage.getItem(CUSTOMER_DATA_KEY);
		if (raw) {
			try {
				return JSON.parse(raw);
			} catch {
				return null;
			}
		}
	}
	return null;
}

export function clearCustomerSession() {
	if (typeof window !== 'undefined') {
		sessionStorage.removeItem(CUSTOMER_TOKEN_KEY);
		sessionStorage.removeItem(CUSTOMER_DATA_KEY);
	}
}

/**
 * Make an authenticated customer ATM request using customer session Bearer token.
 * @param {string} endpoint
 * @param {object} options
 * @returns {Promise<any>}
 */
export async function customerApiRequest(endpoint, options = {}) {
	const token = getCustomerToken();

	if (!token) {
		throw new Error('Customer ATM session expired. Please authenticate at the terminal.');
	}

	const headers = {
		'Content-Type': 'application/json',
		Accept: 'application/json',
		Authorization: `Bearer ${token}`,
		...(options.headers || {})
	};

	const url = `${getBaseUrl()}${endpoint}`;

	let res;
	try {
		res = await fetch(url, {
			...options,
			headers
		});
	} catch (networkError) {
		console.error('API connection error:', networkError);
		throw new Error(
			`Cannot connect to backend server at ${DEFAULT_API_URL}. Ensure FastAPI is running.`
		);
	}

	let data;
	const contentType = res.headers.get('content-type') || '';
	if (contentType.includes('application/json')) {
		data = await res.json();
	} else {
		data = { detail: await res.text() };
	}

	if (!res.ok) {
		let errorMessage = 'An error occurred while processing your request.';

		if (typeof data.detail === 'string') {
			errorMessage = data.detail;
		} else if (Array.isArray(data.detail)) {
			errorMessage = data.detail.map((err) => `${err.loc?.slice(-1)[0]}: ${err.msg}`).join(', ');
		} else if (data.message) {
			errorMessage = data.message;
		}

		if (res.status === 401) {
			clearCustomerSession();
		}

		const error = new Error(errorMessage);
		error.status = res.status;
		error.data = data;
		throw error;
	}

	return data;
}

