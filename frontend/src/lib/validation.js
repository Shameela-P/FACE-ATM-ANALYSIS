/**
 * Client-side input validation and Verhoeff checksum helpers for Face ATM.
 */

// Verhoeff algorithm lookup tables for Indian Aadhaar validation
const VERHOEFF_D = [
	[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	[1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
	[2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
	[3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
	[4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
	[5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
	[6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
	[7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
	[8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
	[9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
];

const VERHOEFF_P = [
	[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
	[1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
	[5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
	[8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
	[9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
	[4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
	[2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
	[7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
];

/**
 * Validate 12-digit Aadhaar number using official Verhoeff checksum
 * @param {string} numStr
 * @returns {boolean}
 */
export function validateVerhoeff(numStr) {
	const clean = (numStr || '').replace(/[\s-]/g, '');
	if (!/^\d{12}$/.test(clean)) return false;
	if (new Set(clean).size === 1) return false; // Reject repeated like 111111111111

	let c = 0;
	const reversed = clean.split('').reverse().map(Number);
	for (let i = 0; i < reversed.length; i++) {
		c = VERHOEFF_D[c][VERHOEFF_P[i % 8][reversed[i]]];
	}
	return c === 0;
}

/**
 * Validate email format
 * @param {string} email
 * @returns {boolean}
 */
export function validateEmail(email) {
	if (!email) return false;
	const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
	return re.test(email.trim());
}

/**
 * Validate 10-digit mobile phone
 * @param {string} phone
 * @returns {boolean}
 */
export function validatePhone(phone) {
	const clean = (phone || '').replace(/[\s\-()+]/g, '');
	const standard = clean.startsWith('91') && clean.length === 12 ? clean.slice(2) : clean;
	return /^[6-9]\d{9}$/.test(standard);
}

/**
 * Validate Date of Birth (must be at least 18 years old)
 * @param {string} dobStr - YYYY-MM-DD
 * @returns {{ valid: boolean, message?: string }}
 */
export function validateDob(dobStr) {
	if (!dobStr) return { valid: false, message: 'Date of birth is required.' };
	const birthDate = new Date(dobStr);
	if (isNaN(birthDate.getTime())) {
		return { valid: false, message: 'Invalid date format.' };
	}
	const today = new Date();
	let age = today.getFullYear() - birthDate.getFullYear();
	const monthDiff = today.getMonth() - birthDate.getMonth();
	if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
		age--;
	}

	if (age < 18) {
		return { valid: false, message: 'Customer must be at least 18 years old.' };
	}
	if (age > 120) {
		return { valid: false, message: 'Please enter a valid date of birth.' };
	}
	return { valid: true };
}

/**
 * Validate Bank Account Number (9 to 18 digits)
 * @param {string} acc
 * @returns {boolean}
 */
export function validateBankAccount(acc) {
	const clean = (acc || '').replace(/[\s-]/g, '');
	return /^\d{9,18}$/.test(clean);
}

/**
 * Format Aadhaar for user input display: 'XXXX XXXX XXXX'
 * @param {string} val
 * @returns {string}
 */
export function formatAadhaarInput(val) {
	const clean = (val || '').replace(/\D/g, '').slice(0, 12);
	const parts = [];
	for (let i = 0; i < clean.length; i += 4) {
		parts.push(clean.slice(i, i + 4));
	}
	return parts.join(' ');
}
