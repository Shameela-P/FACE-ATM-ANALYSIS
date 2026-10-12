<script>
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { adminUser } from '#lib/auth.js';
	import { apiRequest } from '#lib/api.js';
	import {
		validateVerhoeff,
		validateEmail,
		validatePhone,
		validateDob,
		validateBankAccount,
		formatAadhaarInput
	} from '#lib/validation.js';

	// Wizard step tracking (1: Details, 2: OTP, 3: Face, 4: Success)
	let currentStep = $state(1);

	// Step 1: Customer Form State
	let form = $state({
		fullName: '',
		email: '',
		phone: '',
		dob: '',
		aadhaarNumber: '',
		bankAccountNumber: '',
		bankName: 'State Bank of India'
	});

	let formErrors = $state({});
	let isSubmitting = $state(false);
	let submitError = $state('');

	// Popular Bank quick-select options
	const popularBanks = [
		'State Bank of India',
		'HDFC Bank',
		'ICICI Bank',
		'Axis Bank',
		'Punjab National Bank',
		'Bank of Baroda'
	];

	// Step 2: OTP State
	let verificationSession = $state(null);
	let otpValue = $state('');
	let otpError = $state('');
	let otpVerifying = $state(false);
	let otpResending = $state(false);
	let otpExpiryRemaining = $state(600); // 10 minutes in seconds
	let resendCooldownRemaining = $state(60); // 60 seconds
	let expiryTimerInterval = null;
	let cooldownTimerInterval = null;

	// Step 3: Biometric Face Enrollment State
	let consentObtained = $state(false);
	let videoElement = $state(null);
	let canvasElement = $state(null);
	let mediaStream = $state(null);
	let cameraState = $state('idle'); // 'idle' | 'requesting' | 'ready' | 'denied' | 'error'
	let cameraErrorMessage = $state('');
	let capturedImageBase64 = $state('');
	let isEnrollingFace = $state(false);
	let faceEnrollError = $state('');

	// Step 4: Success & Card State
	let enrollmentResult = $state(null);
	let showFullCardNumber = $state(false);
	let copySuccess = $state(false);
	let resendingCardEmail = $state(false);
	let cardEmailStatus = $state(null);

	// Cleanup timers and camera on unmount
	onDestroy(() => {
		stopCamera();
		clearInterval(expiryTimerInterval);
		clearInterval(cooldownTimerInterval);
	});

	// --- Step 1: Form Validation & Submission ---

	function handleAadhaarInput(e) {
		form.aadhaarNumber = formatAadhaarInput(e.target.value);
	}

	function validateStep1() {
		const errors = {};

		if (!form.fullName || form.fullName.trim().length < 2) {
			errors.fullName = 'Full legal name must be at least 2 characters.';
		}

		if (!validateEmail(form.email)) {
			errors.email = 'Please provide a valid email address.';
		}

		if (!validatePhone(form.phone)) {
			errors.phone = 'Please provide a valid 10-digit Indian mobile number (starts with 6-9).';
		}

		const dobCheck = validateDob(form.dob);
		if (!dobCheck.valid) {
			errors.dob = dobCheck.message;
		}

		const cleanAadhaar = form.aadhaarNumber.replace(/[\s-]/g, '');
		if (cleanAadhaar.length !== 12 || !/^\d{12}$/.test(cleanAadhaar)) {
			errors.aadhaarNumber = 'Aadhaar must be exactly 12 numeric digits.';
		} else if (!validateVerhoeff(cleanAadhaar)) {
			errors.aadhaarNumber = 'Invalid Aadhaar number: failed official Verhoeff checksum validation.';
		}

		if (!validateBankAccount(form.bankAccountNumber)) {
			errors.bankAccountNumber = 'Bank account number must be between 9 and 18 numeric digits.';
		}

		if (!form.bankName || form.bankName.trim().length < 2) {
			errors.bankName = 'Bank name must be provided.';
		}

		formErrors = errors;
		return Object.keys(errors).length === 0;
	}

	async function submitCustomerDetails() {
		submitError = '';
		if (!validateStep1()) return;

		isSubmitting = true;
		try {
			const cleanPhone = form.phone.replace(/[\s\-()+]/g, '');
			const cleanAadhaar = form.aadhaarNumber.replace(/[\s-]/g, '');
			const cleanAccount = form.bankAccountNumber.replace(/[\s-]/g, '');

			const payload = {
				fullName: form.fullName.trim(),
				email: form.email.trim().toLowerCase(),
				phone: cleanPhone,
				dob: form.dob.trim(),
				aadhaarNumber: cleanAadhaar,
				bankAccountNumber: cleanAccount,
				bankName: form.bankName.trim()
			};

			const response = await apiRequest('/api/customers/register-initiate', {
				method: 'POST',
				body: JSON.stringify(payload)
			});

			verificationSession = response;
			currentStep = 2;
			startOtpTimers(response.expiresInSeconds || 600, response.cooldownSeconds || 60);
		} catch (err) {
			submitError = err.message || 'Failed to initiate customer registration.';
		} finally {
			isSubmitting = false;
		}
	}

	// --- Step 2: OTP Verification & Timers ---

	function startOtpTimers(expirySeconds, cooldownSeconds) {
		clearInterval(expiryTimerInterval);
		clearInterval(cooldownTimerInterval);

		otpExpiryRemaining = expirySeconds;
		resendCooldownRemaining = cooldownSeconds;

		expiryTimerInterval = setInterval(() => {
			if (otpExpiryRemaining > 0) {
				otpExpiryRemaining--;
			} else {
				clearInterval(expiryTimerInterval);
			}
		}, 1000);

		cooldownTimerInterval = setInterval(() => {
			if (resendCooldownRemaining > 0) {
				resendCooldownRemaining--;
			} else {
				clearInterval(cooldownTimerInterval);
			}
		}, 1000);
	}

	function formatSeconds(secs) {
		const m = Math.floor(secs / 60);
		const s = secs % 60;
		return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
	}

	async function verifyOtp() {
		otpError = '';
		const cleanOtp = otpValue.trim();

		if (cleanOtp.length !== 6 || !/^\d{6}$/.test(cleanOtp)) {
			otpError = 'Please enter a complete 6-digit numeric verification code.';
			return;
		}

		otpVerifying = true;
		try {
			const res = await apiRequest('/api/customers/otp-verify', {
				method: 'POST',
				body: JSON.stringify({
					verificationId: verificationSession.verificationId,
					otp: cleanOtp
				})
			});

			if (res.verified) {
				currentStep = 3;
				// Camera will initialize after consent is toggled
			}
		} catch (err) {
			otpError = err.message || 'Verification failed. Please check the code and try again.';
		} finally {
			otpVerifying = false;
		}
	}

	async function resendOtp() {
		if (resendCooldownRemaining > 0 || otpResending) return;

		otpResending = true;
		otpError = '';
		try {
			const res = await apiRequest('/api/customers/otp-resend', {
				method: 'POST',
				body: JSON.stringify({
					verificationId: verificationSession.verificationId
				})
			});

			if (verificationSession && res.emailDelivery) {
				verificationSession.emailDelivery = res.emailDelivery;
			}

			startOtpTimers(res.expiresInSeconds || 600, res.cooldownSeconds || 60);
			otpValue = '';
		} catch (err) {
			otpError = err.message || 'Failed to resend verification code.';
		} finally {
			otpResending = false;
		}
	}

	// --- Step 3: Biometric Face Camera & Enrollment ---

	async function startCamera() {
		if (!consentObtained) return;

		cameraState = 'requesting';
		cameraErrorMessage = '';
		faceEnrollError = '';

		try {
			if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
				throw new Error('Camera access is not supported by this browser.');
			}

			const stream = await navigator.mediaDevices.getUserMedia({
				video: {
					width: { ideal: 640 },
					height: { ideal: 480 },
					facingMode: 'user'
				},
				audio: false
			});

			mediaStream = stream;
			cameraState = 'ready';

			// Attach to video element
			setTimeout(() => {
				if (videoElement) {
					videoElement.srcObject = stream;
					videoElement.play().catch((e) => console.warn('Video play error:', e));
				}
			}, 50);
		} catch (err) {
			console.error('Camera initialization error:', err);
			if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
				cameraState = 'denied';
				cameraErrorMessage =
					'Camera permission was denied. Please allow camera permissions in your browser address bar to proceed.';
			} else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
				cameraState = 'error';
				cameraErrorMessage = 'No camera hardware device found on this system.';
			} else {
				cameraState = 'error';
				cameraErrorMessage = err.message || 'Unable to access device camera.';
			}
		}
	}

	function stopCamera() {
		if (mediaStream) {
			mediaStream.getTracks().forEach((track) => track.stop());
			mediaStream = null;
		}
		if (videoElement) {
			videoElement.srcObject = null;
		}
		cameraState = 'idle';
	}

	function handleConsentToggle() {
		consentObtained = !consentObtained;
		if (consentObtained) {
			startCamera();
		} else {
			stopCamera();
			capturedImageBase64 = '';
		}
	}

	function capturePhoto() {
		if (!videoElement || cameraState !== 'ready') return;

		const width = videoElement.videoWidth || 640;
		const height = videoElement.videoHeight || 480;

		if (!canvasElement) {
			canvasElement = document.createElement('canvas');
		}
		canvasElement.width = width;
		canvasElement.height = height;

		const ctx = canvasElement.getContext('2d');
		ctx.drawImage(videoElement, 0, 0, width, height);

		capturedImageBase64 = canvasElement.toDataURL('image/jpeg', 0.92);
		faceEnrollError = '';
	}

	function retakePhoto() {
		capturedImageBase64 = '';
		faceEnrollError = '';
		if (consentObtained && cameraState !== 'ready') {
			startCamera();
		}
	}

	async function submitFaceEnrollment() {
		if (!capturedImageBase64) {
			faceEnrollError = 'Please capture a photo before submitting enrollment.';
			return;
		}

		if (!consentObtained) {
			faceEnrollError = 'Customer consent must be affirmed before biometric enrollment.';
			return;
		}

		isEnrollingFace = true;
		faceEnrollError = '';

		try {
			const res = await apiRequest('/api/customers/enroll-face', {
				method: 'POST',
				body: JSON.stringify({
					verificationId: verificationSession.verificationId,
					imageBase64: capturedImageBase64,
					consentObtained: true
				})
			});

			enrollmentResult = res;
			cardEmailStatus = res.emailDelivery;
			stopCamera();
			currentStep = 4;
		} catch (err) {
			faceEnrollError = err.message || 'Face enrollment failed. Please retake photo with better lighting.';
		} finally {
			isEnrollingFace = false;
		}
	}

	// --- Step 4: Card Copy & Retry Helpers ---

	function copyCardNumber() {
		if (!enrollmentResult || !enrollmentResult.cardNumber) return;
		const clean = enrollmentResult.cardNumber.replace(/\s+/g, '');
		navigator.clipboard.writeText(clean).then(() => {
			copySuccess = true;
			setTimeout(() => {
				copySuccess = false;
			}, 3000);
		});
	}

	async function retryCardEmail() {
		if (!enrollmentResult || resendingCardEmail) return;

		resendingCardEmail = true;
		try {
			const res = await apiRequest('/api/customers/resend-card-email', {
				method: 'POST',
				body: JSON.stringify({
					customerId: enrollmentResult.customerId
				})
			});
			cardEmailStatus = { delivered: res.delivered, error: res.error };
		} catch (err) {
			cardEmailStatus = { delivered: false, error: err.message };
		} finally {
			resendingCardEmail = false;
		}
	}

	function resetRegistrationForm() {
		form = {
			fullName: '',
			email: '',
			phone: '',
			dob: '',
			aadhaarNumber: '',
			bankAccountNumber: '',
			bankName: 'State Bank of India'
		};
		formErrors = {};
		verificationSession = null;
		otpValue = '';
		consentObtained = false;
		capturedImageBase64 = '';
		enrollmentResult = null;
		submitError = '';
		otpError = '';
		faceEnrollError = '';
		currentStep = 1;
	}
</script>

<svelte:head>
	<title>Customer Registration & Face Enrollment | Face ATM</title>
</svelte:head>

<div class="registration-page">
	<!-- Page Header -->
	<header class="page-header">
		<div class="header-left">
			<a href="/admin/dashboard" class="back-link">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M19 12H5M12 19l-7-7 7-7" />
				</svg>
				<span>Back to Dashboard</span>
			</a>
			<h1 class="page-title">Customer Registration & Face Enrollment</h1>
			<p class="page-subtitle">
				Register customer banking details, verify identity with OTP, and securely enroll biometric face credentials.
			</p>
		</div>
		<div class="header-badge">
			<span class="badge badge-active">Phase 2 Biometric Workflow</span>
		</div>
	</header>

	<!-- Stepper Indicator -->
	<nav class="stepper-bar" aria-label="Registration Progress">
		<div class="step-item {currentStep >= 1 ? 'completed' : ''} {currentStep === 1 ? 'active' : ''}">
			<div class="step-circle">{currentStep > 1 ? '✓' : '1'}</div>
			<div class="step-label">
				<span class="step-num">Step 1</span>
				<span class="step-name">Customer Details</span>
			</div>
		</div>
		<div class="step-divider {currentStep >= 2 ? 'filled' : ''}"></div>

		<div class="step-item {currentStep >= 2 ? 'completed' : ''} {currentStep === 2 ? 'active' : ''}">
			<div class="step-circle">{currentStep > 2 ? '✓' : '2'}</div>
			<div class="step-label">
				<span class="step-num">Step 2</span>
				<span class="step-name">Email OTP</span>
			</div>
		</div>
		<div class="step-divider {currentStep >= 3 ? 'filled' : ''}"></div>

		<div class="step-item {currentStep >= 3 ? 'completed' : ''} {currentStep === 3 ? 'active' : ''}">
			<div class="step-circle">{currentStep > 3 ? '✓' : '3'}</div>
			<div class="step-label">
				<span class="step-num">Step 3</span>
				<span class="step-name">Face Enrollment</span>
			</div>
		</div>
		<div class="step-divider {currentStep >= 4 ? 'filled' : ''}"></div>

		<div class="step-item {currentStep === 4 ? 'active completed' : ''}">
			<div class="step-circle">{currentStep === 4 ? '✓' : '4'}</div>
			<div class="step-label">
				<span class="step-num">Step 4</span>
				<span class="step-name">Card Issuance</span>
			</div>
		</div>
	</nav>

	<!-- ========================================================
	     STEP 1: CUSTOMER DETAILS FORM
	     ======================================================== -->
	{#if currentStep === 1}
		<section class="form-container" aria-label="Customer Information Form">
			<!-- Security & Privacy Banner -->
			<div class="security-banner">
				<div class="security-icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
					</svg>
				</div>
				<div class="security-text">
					<strong>Bank-Grade AES-256-GCM Protection:</strong>
					Aadhaar and Bank Account details are encrypted with authenticated server-side encryption.
					Deterministic keyed HMAC indexes prevent duplicates without revealing confidential PII.
				</div>
			</div>

			{#if submitError}
				<div class="alert alert-error" role="alert">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="10" />
						<line x1="12" y1="8" x2="12" y2="12" />
						<line x1="12" y1="16" x2="12.01" y2="16" />
					</svg>
					<span>{submitError}</span>
				</div>
			{/if}

			<form onsubmit={(e) => { e.preventDefault(); submitCustomerDetails(); }} class="register-form" novalidate>
				<div class="form-grid">
					<!-- Full Legal Name -->
					<div class="form-group">
						<label for="fullName">Full Legal Name <span class="required">*</span></label>
						<input
							type="text"
							id="fullName"
							placeholder="e.g. Ramesh Kumar Sharma"
							bind:value={form.fullName}
							class={formErrors.fullName ? 'has-error' : ''}
							disabled={isSubmitting}
						/>
						{#if formErrors.fullName}
							<span class="field-error">{formErrors.fullName}</span>
						{/if}
					</div>

					<!-- Email Address -->
					<div class="form-group">
						<label for="email">Customer Email Address <span class="required">*</span></label>
						<input
							type="email"
							id="email"
							placeholder="ramesh.sharma@example.com"
							bind:value={form.email}
							class={formErrors.email ? 'has-error' : ''}
							disabled={isSubmitting}
						/>
						{#if formErrors.email}
							<span class="field-error">{formErrors.email}</span>
						{:else}
							<span class="field-hint">A 6-digit OTP verification code will be dispatched to this email.</span>
						{/if}
					</div>

					<!-- Phone Number -->
					<div class="form-group">
						<label for="phone">Mobile Phone Number <span class="required">*</span></label>
						<div class="input-prefix-wrapper">
							<span class="input-prefix">+91</span>
							<input
								type="tel"
								id="phone"
								placeholder="98765 43210"
								maxlength="14"
								bind:value={form.phone}
								class={formErrors.phone ? 'has-error' : ''}
								disabled={isSubmitting}
							/>
						</div>
						{#if formErrors.phone}
							<span class="field-error">{formErrors.phone}</span>
						{/if}
					</div>

					<!-- Date of Birth -->
					<div class="form-group">
						<label for="dob">Date of Birth <span class="required">*</span></label>
						<input
							type="date"
							id="dob"
							bind:value={form.dob}
							class={formErrors.dob ? 'has-error' : ''}
							disabled={isSubmitting}
						/>
						{#if formErrors.dob}
							<span class="field-error">{formErrors.dob}</span>
						{:else}
							<span class="field-hint">Customer must be 18 years or older for biometric banking registration.</span>
						{/if}
					</div>

					<!-- Aadhaar Number -->
					<div class="form-group full-width">
						<label for="aadhaar">Aadhaar Number (12 Digits) <span class="required">*</span></label>
						<input
							type="text"
							id="aadhaar"
							placeholder="XXXX XXXX XXXX"
							maxlength="14"
							value={form.aadhaarNumber}
							oninput={handleAadhaarInput}
							class={formErrors.aadhaarNumber ? 'has-error' : ''}
							disabled={isSubmitting}
						/>
						{#if formErrors.aadhaarNumber}
							<span class="field-error">{formErrors.aadhaarNumber}</span>
						{:else}
							<span class="field-hint">Validated via official Verhoeff checksum. Encrypted before storage.</span>
						{/if}
					</div>

					<!-- Bank Name -->
					<div class="form-group full-width">
						<label for="bankName">Bank Institution Name <span class="required">*</span></label>
						<input
							type="text"
							id="bankName"
							placeholder="Enter bank name or pick below"
							bind:value={form.bankName}
							class={formErrors.bankName ? 'has-error' : ''}
							disabled={isSubmitting}
						/>
						<!-- Quick Bank Selectors -->
						<div class="bank-pill-row">
							{#each popularBanks as b}
								<button
									type="button"
									class="bank-pill {form.bankName === b ? 'selected' : ''}"
									onclick={() => { form.bankName = b; }}
								>
									{b}
								</button>
							{/each}
						</div>
						{#if formErrors.bankName}
							<span class="field-error">{formErrors.bankName}</span>
						{/if}
					</div>

					<!-- Bank Account Number -->
					<div class="form-group full-width">
						<label for="bankAccount">Bank Account Number <span class="required">*</span></label>
						<input
							type="text"
							id="bankAccount"
							placeholder="Enter 9 to 18-digit bank account number"
							maxlength="18"
							bind:value={form.bankAccountNumber}
							class={formErrors.bankAccountNumber ? 'has-error' : ''}
							disabled={isSubmitting}
						/>
						{#if formErrors.bankAccountNumber}
							<span class="field-error">{formErrors.bankAccountNumber}</span>
						{:else}
							<span class="field-hint">Stored strictly encrypted. Never exposed in API responses.</span>
						{/if}
					</div>
				</div>

				<div class="form-actions">
					<a href="/admin/dashboard" class="btn-secondary">Cancel</a>
					<button type="submit" class="btn-primary" disabled={isSubmitting}>
						{#if isSubmitting}
							<div class="btn-spinner"></div>
							<span>Validating & Dispatching OTP...</span>
						{:else}
							<span>Proceed to Email OTP Verification &rarr;</span>
						{/if}
					</button>
				</div>
			</form>
		</section>
	{/if}

	<!-- ========================================================
	     STEP 2: EMAIL OTP VERIFICATION
	     ======================================================== -->
	{#if currentStep === 2}
		<section class="otp-container" aria-label="Email Verification Step">
			<div class="otp-card">
				<div class="otp-header">
					<div class="otp-icon-bubble">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
							<polyline points="22,6 12,13 2,6" />
						</svg>
					</div>
					<h2>Verify Customer Email Address</h2>
					<p class="otp-subtitle">
						We sent a 6-digit verification code to
						<strong>{verificationSession?.email}</strong>.
					</p>
					{#if verificationSession?.emailDelivery && !verificationSession.emailDelivery.delivered}
						<div class="sandbox-note">
							<small>
								⚠️ <strong>Notice:</strong> Email delivery status:
								{verificationSession.emailDelivery.error || 'Pending delivery'}.
							</small>
						</div>
					{:else if verificationSession?.emailDelivery?.delivered}
						<div class="sandbox-success-note">
							<small>
								✅ <strong>Email Dispatched:</strong> Verification code sent via Gmail SMTP from <strong>{verificationSession.emailDelivery.sender || 'Face ATM'}</strong>.
							</small>
						</div>
					{/if}
				</div>

				{#if otpError}
					<div class="alert alert-error" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="10" />
							<line x1="12" y1="8" x2="12" y2="12" />
							<line x1="12" y1="16" x2="12.01" y2="16" />
						</svg>
						<span>{otpError}</span>
					</div>
				{/if}

				<form onsubmit={(e) => { e.preventDefault(); verifyOtp(); }} class="otp-form">
					<div class="otp-input-wrapper">
						<label for="otpCode">Enter 6-Digit One-Time Passcode</label>
						<input
							type="text"
							id="otpCode"
							maxlength="6"
							placeholder="• • • • • •"
							class="otp-digit-input"
							bind:value={otpValue}
							disabled={otpVerifying || otpExpiryRemaining <= 0}
							autocomplete="one-time-code"
						/>
					</div>

					<div class="otp-meta-row">
						<div class="timer-box">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<circle cx="12" cy="12" r="10" />
								<polyline points="12 6 12 12 16 14" />
							</svg>
							{#if otpExpiryRemaining > 0}
								<span>Expires in: <strong>{formatSeconds(otpExpiryRemaining)}</strong></span>
							{:else}
								<span class="expired-label">Code Expired</span>
							{/if}
						</div>

						<button
							type="button"
							class="resend-btn"
							onclick={resendOtp}
							disabled={resendCooldownRemaining > 0 || otpResending}
						>
							{#if otpResending}
								<span>Sending new code...</span>
							{:else if resendCooldownRemaining > 0}
								<span>Resend available in {resendCooldownRemaining}s</span>
							{:else}
								<span>Resend Verification Code</span>
							{/if}
						</button>
					</div>

					<div class="otp-actions">
						<button
							type="button"
							class="btn-secondary"
							onclick={() => { currentStep = 1; }}
							disabled={otpVerifying}
						>
							&larr; Edit Details
						</button>
						<button type="submit" class="btn-primary" disabled={otpVerifying || otpExpiryRemaining <= 0}>
							{#if otpVerifying}
								<div class="btn-spinner"></div>
								<span>Verifying Code...</span>
							{:else}
								<span>Verify & Proceed to Face Enrollment &rarr;</span>
							{/if}
						</button>
					</div>
				</form>
			</div>
		</section>
	{/if}

	<!-- ========================================================
	     STEP 3: BIOMETRIC FACE ENROLLMENT
	     ======================================================== -->
	{#if currentStep === 3}
		<section class="face-container" aria-label="Biometric Face Enrollment Step">
			<div class="face-card">
				<div class="face-header">
					<h2>Biometric Face Enrollment</h2>
					<p class="face-subtitle">
						Capture a clear, direct facial photo of customer
						<strong>{verificationSession?.customerSummary?.fullName}</strong>.
					</p>
				</div>

				<!-- Mandatory Consent Box -->
				<div class="consent-box {consentObtained ? 'consented' : ''}">
					<label class="consent-label">
						<input
							type="checkbox"
							checked={consentObtained}
							onchange={handleConsentToggle}
							disabled={isEnrollingFace}
						/>
						<span class="consent-text">
							<strong>Explicit Customer Consent (Mandatory):</strong>
							I confirm that the customer has provided explicit informed consent to capture and process
							facial biometrics solely for Face ATM authentication. Biometrics are securely converted
							into an irreversible 128-dimensional mathematical feature vector; raw facial photographs
							are immediately discarded and never stored in persistent storage.
						</span>
					</label>
				</div>

				{#if faceEnrollError}
					<div class="alert alert-error" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="10" />
							<line x1="12" y1="8" x2="12" y2="12" />
							<line x1="12" y1="16" x2="12.01" y2="16" />
						</svg>
						<span>{faceEnrollError}</span>
					</div>
				{/if}

				<!-- Camera Viewport Area -->
				<div class="camera-viewport-card">
					{#if !consentObtained}
						<div class="camera-placeholder">
							<div class="placeholder-icon">🛡️</div>
							<h3>Consent Required to Activate Camera</h3>
							<p>Please check the mandatory consent confirmation above to enable camera capture.</p>
						</div>
					{:else if cameraState === 'requesting'}
						<div class="camera-placeholder">
							<div class="btn-spinner large"></div>
							<h3>Requesting Camera Access...</h3>
							<p>Please approve the camera permission dialog in your web browser.</p>
						</div>
					{:else if cameraState === 'denied' || cameraState === 'error'}
						<div class="camera-placeholder error">
							<div class="placeholder-icon">🚫</div>
							<h3>Camera Access Unavailable</h3>
							<p>{cameraErrorMessage}</p>
							<button type="button" class="btn-secondary" onclick={startCamera}>
								Retry Camera Access
							</button>
						</div>
					{:else}
						<!-- Active Camera Feed / Captured Preview -->
						<div class="camera-feed-wrapper">
							{#if capturedImageBase64}
								<!-- Review Mode -->
								<div class="preview-wrapper">
									<img src={capturedImageBase64} alt="Captured Face Preview" class="captured-preview-img" />
									<div class="preview-badge">Snapshot Captured</div>
								</div>
							{:else}
								<!-- Live Video Feed -->
								<div class="video-container">
									<!-- svelte-ignore a11y_media_has_caption -->
									<video bind:this={videoElement} autoplay playsinline muted class="camera-video"></video>
									<!-- Facial Alignment Reticle Overlay -->
									<div class="face-guide-overlay">
										<div class="guide-oval"></div>
										<div class="corner-bracket top-left"></div>
										<div class="corner-bracket top-right"></div>
										<div class="corner-bracket bottom-left"></div>
										<div class="corner-bracket bottom-right"></div>
										<div class="scan-beam"></div>
									</div>
								</div>
							{/if}
						</div>
					{/if}
				</div>

				<!-- Technical Transparency Notice -->
				<div class="transparency-note">
					<small>
						ℹ️ <strong>Biometric Pipeline Notice:</strong>
						Enrollment uses OpenCV YuNet for face geometry detection and OpenCV SFace for 128-dimensional feature embedding.
						Liveness/spoof protection is not active in this pipeline; single-face detection, size, and geometry thresholds are strictly validated.
					</small>
				</div>

				<!-- Camera Action Controls -->
				<div class="camera-actions">
					{#if !capturedImageBase64}
						<button
							type="button"
							class="btn-primary capture-btn"
							onclick={capturePhoto}
							disabled={cameraState !== 'ready' || !consentObtained}
						>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<circle cx="12" cy="12" r="3" />
								<path d="M19 4h-3.17L14.4 2H9.6L8.17 4H5c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2z" />
							</svg>
							<span>Capture Customer Photo</span>
						</button>
					{:else}
						<div class="review-actions">
							<button
								type="button"
								class="btn-secondary"
								onclick={retakePhoto}
								disabled={isEnrollingFace}
							>
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<polyline points="1 4 1 10 7 10" />
									<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
								</svg>
								<span>Retake Photo</span>
							</button>

							<button
								type="button"
								class="btn-primary"
								onclick={submitFaceEnrollment}
								disabled={isEnrollingFace}
							>
								{#if isEnrollingFace}
									<div class="btn-spinner"></div>
									<span>Extracting Features & Generating Card...</span>
								{:else}
									<span>Confirm & Complete Enrollment &rarr;</span>
								{/if}
							</button>
						</div>
					{/if}
				</div>
			</div>
		</section>
	{/if}

	<!-- ========================================================
	     STEP 4: REGISTRATION SUCCESS & CARD ISSUANCE
	     ======================================================== -->
	{#if currentStep === 4 && enrollmentResult}
		<section class="success-container" aria-label="Customer Registration Success">
			<div class="success-header">
				<div class="success-checkmark">✓</div>
				<h2>Customer Registration & Biometric Enrollment Complete!</h2>
				<p class="success-subtitle">
					The customer record has been created, biometrics securely hashed into a 128-dim embedding, and a unique Face ATM Smart Card has been issued.
				</p>
			</div>

			<!-- ATM Smart Card Visual -->
			<div class="card-showcase">
				<div class="smart-card">
					<div class="card-bank-header">
						<span class="card-brand-title">FACE ATM SMART CARD</span>
						<span class="card-contactless">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M5 12.55a11 11 0 0 1 14.08 0" />
								<path d="M1.42 9a16 16 0 0 1 21.16 0" />
								<path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
							</svg>
						</span>
					</div>

					<div class="card-chip-element">
						<div class="chip-line"></div>
						<div class="chip-line"></div>
					</div>

					<div class="card-number-display">
						<span class="card-digits">
							{showFullCardNumber ? enrollmentResult.cardNumber : enrollmentResult.cardNumberMasked}
						</span>
						<button
							type="button"
							class="card-visibility-toggle"
							onclick={() => { showFullCardNumber = !showFullCardNumber; }}
							title={showFullCardNumber ? 'Mask card number' : 'Show full card number'}
						>
							{#if showFullCardNumber}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
									<line x1="1" y1="1" x2="23" y2="23" />
								</svg>
							{:else}
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
									<circle cx="12" cy="12" r="3" />
								</svg>
							{/if}
						</button>
						<button
							type="button"
							class="card-copy-btn"
							onclick={copyCardNumber}
							title="Copy 16-digit card number"
						>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
								<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
							</svg>
							<span>{copySuccess ? 'Copied!' : 'Copy'}</span>
						</button>
					</div>

					<div class="card-footer-info">
						<div class="holder-section">
							<span class="holder-label">CARDHOLDER</span>
							<span class="holder-name">{enrollmentResult.fullName}</span>
						</div>
						<div class="biometric-indicator">
							<span class="indicator-dot"></span>
							<span>FACE ENROLLED</span>
						</div>
					</div>
				</div>
			</div>

			<!-- Customer Summary Card -->
			<div class="summary-details-card">
				<h3>Registered Customer Summary</h3>
				<div class="summary-grid">
					<div class="summary-row">
						<span class="sum-label">Customer ID:</span>
						<span class="sum-value mono">{enrollmentResult.customerId}</span>
					</div>
					<div class="summary-row">
						<span class="sum-label">Customer Name:</span>
						<span class="sum-value">{enrollmentResult.fullName}</span>
					</div>
					<div class="summary-row">
						<span class="sum-label">Verified Email:</span>
						<span class="sum-value">{enrollmentResult.email}</span>
					</div>
					<div class="summary-row">
						<span class="sum-label">Aadhaar (Protected):</span>
						<span class="sum-value">{verificationSession?.customerSummary?.aadhaarMasked || 'XXXX-XXXX-••••'}</span>
					</div>
					<div class="summary-row">
						<span class="sum-label">Linked Bank:</span>
						<span class="sum-value">{verificationSession?.customerSummary?.bankName}</span>
					</div>
					<div class="summary-row">
						<span class="sum-label">Account (Protected):</span>
						<span class="sum-value">{verificationSession?.customerSummary?.bankAccountMasked || 'XXXXXXXX••••'}</span>
					</div>
					<div class="summary-row">
						<span class="sum-label">Biometric Verification:</span>
						<span class="sum-value highlight">128-Dim SFace Vector (Score: {(enrollmentResult.confidence * 100).toFixed(1)}%)</span>
					</div>
				</div>
			</div>

			<!-- Email Notification Status Banner -->
			<div class="email-status-banner">
				<div class="email-banner-icon">✉️</div>
				<div class="email-banner-content">
					<strong>Card Activation Notification:</strong>
					{#if cardEmailStatus?.delivered}
						<span>The unique card number was emailed to <strong>{enrollmentResult.email}</strong> via Gmail SMTP.</span>
					{:else}
						<span>
							Email delivery status: {cardEmailStatus?.error || 'Pending delivery'}.
						</span>
						<button
							type="button"
							class="resend-email-btn"
							onclick={retryCardEmail}
							disabled={resendingCardEmail}
						>
							{resendingCardEmail ? 'Retrying dispatch...' : 'Retry Sending Card Email'}
						</button>
					{/if}
				</div>
			</div>

			<!-- Final Actions -->
			<div class="success-actions">
				<button type="button" class="btn-secondary" onclick={resetRegistrationForm}>
					Register Another Customer
				</button>
				<a href="/admin/dashboard" class="btn-primary">
					Return to Admin Dashboard &rarr;
				</a>
			</div>
		</section>
	{/if}
</div>

<style>
	.registration-page {
		max-width: 980px;
		margin: 0 auto;
		padding: 1rem 0 3rem;
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1.5rem;
		flex-wrap: wrap;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-gray);
		margin-bottom: 0.5rem;
		transition: color var(--transition-fast);
	}

	.back-link svg {
		width: 16px;
		height: 16px;
	}

	.back-link:hover {
		color: var(--color-forest);
	}

	.page-title {
		font-size: 1.85rem;
		font-weight: 800;
		color: var(--color-forest);
		line-height: 1.25;
	}

	.page-subtitle {
		font-size: 0.95rem;
		color: var(--color-gray);
		margin-top: 0.35rem;
		max-width: 650px;
	}

	/* Stepper Styles */
	.stepper-bar {
		display: flex;
		align-items: center;
		background: var(--color-white);
		padding: 1.25rem 2rem;
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-sm);
		border: 1px solid var(--color-gray-border);
		overflow-x: auto;
	}

	.step-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		color: var(--color-gray-light);
		white-space: nowrap;
	}

	.step-circle {
		width: 34px;
		height: 34px;
		border-radius: 50%;
		background-color: rgba(102, 115, 111, 0.12);
		color: var(--color-gray);
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.9rem;
		transition: all var(--transition-normal);
	}

	.step-label {
		display: flex;
		flex-direction: column;
	}

	.step-num {
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.step-name {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--color-gray);
	}

	.step-item.active .step-circle {
		background-color: var(--color-forest);
		color: var(--color-white);
		box-shadow: 0 0 0 4px rgba(23, 63, 53, 0.15);
	}

	.step-item.active .step-name {
		color: var(--color-forest);
		font-weight: 700;
	}

	.step-item.completed .step-circle {
		background-color: var(--color-forest);
		color: var(--color-white);
	}

	.step-item.completed .step-name {
		color: var(--color-forest);
	}

	.step-divider {
		flex: 1;
		min-width: 32px;
		height: 2px;
		background-color: rgba(102, 115, 111, 0.15);
		margin: 0 1rem;
		transition: background-color var(--transition-normal);
	}

	.step-divider.filled {
		background-color: var(--color-forest);
	}

	/* Form Container */
	.form-container,
	.otp-container,
	.face-container,
	.success-container {
		background: var(--color-white);
		padding: 2.25rem;
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		border: 1px solid var(--color-gray-border);
	}

	.security-banner {
		display: flex;
		align-items: center;
		gap: 1rem;
		background: rgba(23, 63, 53, 0.05);
		border: 1px solid rgba(23, 63, 53, 0.15);
		padding: 1rem 1.25rem;
		border-radius: var(--radius-md);
		margin-bottom: 2rem;
		font-size: 0.88rem;
		line-height: 1.5;
		color: var(--color-forest);
	}

	.security-icon svg {
		width: 28px;
		height: 28px;
		color: var(--color-forest);
		flex-shrink: 0;
	}

	.form-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 1.5rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.form-group.full-width {
		grid-column: span 2;
	}

	.form-group label {
		font-size: 0.88rem;
		font-weight: 600;
		color: var(--color-forest);
	}

	.required {
		color: #c53030;
	}

	.form-group input {
		width: 100%;
		padding: 0.8rem 1rem;
		border: 1.5px solid var(--color-gray-border);
		border-radius: var(--radius-md);
		font-family: inherit;
		background-color: var(--color-cream-light);
		transition: all var(--transition-fast);
		color: var(--color-forest);
	}

	.form-group input:focus {
		outline: none;
		border-color: var(--color-forest);
		background-color: var(--color-white);
		box-shadow: 0 0 0 3px rgba(23, 63, 53, 0.12);
	}

	.form-group input.has-error {
		border-color: #e53e3e;
		background-color: #fff5f5;
	}

	.field-error {
		font-size: 0.8rem;
		color: #c53030;
		font-weight: 500;
	}

	.field-hint {
		font-size: 0.78rem;
		color: var(--color-gray);
	}

	.input-prefix-wrapper {
		display: flex;
		align-items: center;
	}

	.input-prefix {
		background: var(--color-cream-surface);
		border: 1.5px solid var(--color-gray-border);
		border-right: none;
		border-radius: var(--radius-md) 0 0 var(--radius-md);
		padding: 0.8rem 0.85rem;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--color-forest);
	}

	.input-prefix-wrapper input {
		border-radius: 0 var(--radius-md) var(--radius-md) 0;
	}

	.bank-pill-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.4rem;
	}

	.bank-pill {
		padding: 0.35rem 0.75rem;
		border-radius: var(--radius-full);
		font-size: 0.78rem;
		font-weight: 600;
		background: var(--color-cream);
		border: 1px solid var(--color-gray-border);
		color: var(--color-forest);
		transition: all var(--transition-fast);
	}

	.bank-pill:hover {
		border-color: var(--color-forest);
		background: rgba(23, 63, 53, 0.08);
	}

	.bank-pill.selected {
		background: var(--color-forest);
		color: var(--color-white);
		border-color: var(--color-forest);
	}

	.form-actions {
		display: flex;
		justify-content: flex-end;
		gap: 1rem;
		margin-top: 2rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-gray-border);
	}

	/* Alert Banner */
	.alert {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.9rem 1.25rem;
		border-radius: var(--radius-md);
		margin-bottom: 1.5rem;
		font-size: 0.9rem;
		line-height: 1.4;
	}

	.alert-error {
		background-color: #fff5f5;
		border: 1px solid #feb2b2;
		color: #9b2c2c;
	}

	.alert-error svg {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
	}

	/* OTP Step Styles */
	.otp-card {
		max-width: 520px;
		margin: 0 auto;
		text-align: center;
	}

	.otp-icon-bubble {
		width: 64px;
		height: 64px;
		border-radius: 50%;
		background: rgba(23, 63, 53, 0.08);
		color: var(--color-forest);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 1rem;
	}

	.otp-icon-bubble svg {
		width: 32px;
		height: 32px;
	}

	.otp-subtitle {
		font-size: 0.95rem;
		color: var(--color-gray);
		margin-top: 0.4rem;
	}

	.sandbox-note {
		margin-top: 0.5rem;
		color: #92400e;
		background: #fffbeb;
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius-sm);
		border: 1px solid #fde68a;
		line-height: 1.4;
	}

	.sandbox-success-note {
		margin-top: 0.5rem;
		color: #065f46;
		background: #ecfdf5;
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius-sm);
		border: 1px solid #a7f3d0;
		line-height: 1.4;
	}

	.otp-form {
		margin-top: 2rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.otp-digit-input {
		width: 240px;
		margin: 0.5rem auto 0;
		font-family: monospace;
		font-size: 2.25rem;
		letter-spacing: 0.5rem;
		text-align: center;
		padding: 0.6rem 0.5rem;
		border: 2px solid var(--color-forest);
		border-radius: var(--radius-md);
		background: var(--color-cream-light);
		color: var(--color-forest);
	}

	.otp-meta-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.85rem;
		flex-wrap: wrap;
		gap: 0.75rem;
	}

	.timer-box {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		color: var(--color-gray);
	}

	.timer-box svg {
		width: 16px;
		height: 16px;
	}

	.resend-btn {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-terracotta);
		text-decoration: underline;
	}

	.resend-btn:disabled {
		color: var(--color-gray-light);
		cursor: not-allowed;
		text-decoration: none;
	}

	.otp-actions {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		margin-top: 1rem;
	}

	/* Face Enrollment Styles */
	.face-card {
		max-width: 680px;
		margin: 0 auto;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.face-header {
		text-align: center;
	}

	.face-subtitle {
		font-size: 0.95rem;
		color: var(--color-gray);
		margin-top: 0.35rem;
	}

	.consent-box {
		background: rgba(23, 63, 53, 0.04);
		border: 1.5px dashed var(--color-gray-border);
		padding: 1.25rem;
		border-radius: var(--radius-md);
		transition: all var(--transition-normal);
	}

	.consent-box.consented {
		background: rgba(35, 92, 78, 0.08);
		border: 1.5px solid var(--color-forest);
	}

	.consent-label {
		display: flex;
		align-items: flex-start;
		gap: 0.85rem;
		cursor: pointer;
	}

	.consent-label input {
		margin-top: 0.25rem;
		width: 20px;
		height: 20px;
		accent-color: var(--color-forest);
		flex-shrink: 0;
	}

	.consent-text {
		font-size: 0.85rem;
		line-height: 1.55;
		color: var(--color-forest);
	}

	.camera-viewport-card {
		width: 100%;
		min-height: 380px;
		background: #0f1e1a;
		border-radius: var(--radius-lg);
		overflow: hidden;
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		box-shadow: 0 8px 24px rgba(15, 30, 26, 0.3);
	}

	.camera-placeholder {
		text-align: center;
		padding: 2.5rem 1.5rem;
		color: var(--color-cream);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
	}

	.placeholder-icon {
		font-size: 3rem;
	}

	.camera-feed-wrapper {
		width: 100%;
		height: 100%;
		display: flex;
		justify-content: center;
		align-items: center;
		position: relative;
	}

	.video-container {
		position: relative;
		width: 100%;
		max-width: 520px;
		aspect-ratio: 4/3;
		overflow: hidden;
	}

	.camera-video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transform: scaleX(-1); /* Mirror camera preview */
	}

	.face-guide-overlay {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	.guide-oval {
		position: absolute;
		top: 15%;
		left: 25%;
		width: 50%;
		height: 70%;
		border: 2px dashed rgba(255, 255, 255, 0.6);
		border-radius: 50%;
		box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.35);
	}

	.corner-bracket {
		position: absolute;
		width: 24px;
		height: 24px;
		border-color: #38b2ac;
		border-style: solid;
	}

	.corner-bracket.top-left {
		top: 20px;
		left: 20px;
		border-width: 3px 0 0 3px;
	}

	.corner-bracket.top-right {
		top: 20px;
		right: 20px;
		border-width: 3px 3px 0 0;
	}

	.corner-bracket.bottom-left {
		bottom: 20px;
		left: 20px;
		border-width: 0 0 3px 3px;
	}

	.corner-bracket.bottom-right {
		bottom: 20px;
		right: 20px;
		border-width: 0 3px 3px 0;
	}

	.scan-beam {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 2px;
		background: linear-gradient(90deg, transparent, #38b2ac, transparent);
		animation: scanSweep 2.5s ease-in-out infinite;
	}

	@keyframes scanSweep {
		0%, 100% { top: 15%; opacity: 0; }
		50% { top: 85%; opacity: 1; }
	}

	.preview-wrapper {
		position: relative;
		max-width: 520px;
		aspect-ratio: 4/3;
	}

	.captured-preview-img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		border-radius: var(--radius-md);
	}

	.preview-badge {
		position: absolute;
		top: 12px;
		right: 12px;
		background: var(--color-forest);
		color: var(--color-white);
		padding: 4px 10px;
		border-radius: var(--radius-full);
		font-size: 0.75rem;
		font-weight: 700;
	}

	.transparency-note {
		background: #fbf8f3;
		border: 1px solid var(--color-gray-border);
		padding: 0.75rem 1rem;
		border-radius: var(--radius-sm);
		font-size: 0.8rem;
		color: var(--color-gray);
		line-height: 1.45;
	}

	.camera-actions {
		display: flex;
		justify-content: center;
		margin-top: 0.5rem;
	}

	.capture-btn {
		width: 100%;
		max-width: 320px;
		padding: 1rem 1.5rem;
	}

	.capture-btn svg {
		width: 22px;
		height: 22px;
	}

	.review-actions {
		display: flex;
		gap: 1rem;
		width: 100%;
		justify-content: center;
	}

	/* Success & Card Styles */
	.success-header {
		text-align: center;
		margin-bottom: 2rem;
	}

	.success-checkmark {
		width: 64px;
		height: 64px;
		border-radius: 50%;
		background: #235c4e;
		color: var(--color-white);
		font-size: 2rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 1rem;
		box-shadow: 0 4px 14px rgba(35, 92, 78, 0.3);
	}

	.success-subtitle {
		font-size: 0.95rem;
		color: var(--color-gray);
		margin-top: 0.4rem;
	}

	/* Smart Card Component */
	.card-showcase {
		display: flex;
		justify-content: center;
		margin: 1.5rem 0 2rem;
	}

	.smart-card {
		width: 100%;
		max-width: 440px;
		aspect-ratio: 1.586;
		background: linear-gradient(135deg, #173f35 0%, #0c201b 100%);
		border-radius: 18px;
		padding: 1.75rem;
		color: var(--color-cream);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		box-shadow: 0 16px 36px rgba(23, 63, 53, 0.35);
		border: 1px solid rgba(255, 255, 255, 0.1);
		position: relative;
	}

	.card-bank-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.card-brand-title {
		font-size: 0.95rem;
		font-weight: 800;
		letter-spacing: 0.08em;
		color: #eeddc9;
	}

	.card-contactless svg {
		width: 22px;
		height: 22px;
		color: #eeddc9;
	}

	.card-chip-element {
		width: 42px;
		height: 32px;
		background: linear-gradient(135deg, #d4af37, #9b7512);
		border-radius: 6px;
		border: 1px solid #7c5c0a;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		padding: 4px;
	}

	.chip-line {
		height: 1px;
		background: rgba(0, 0, 0, 0.4);
	}

	.card-number-display {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.card-digits {
		font-family: 'Courier New', Courier, monospace;
		font-size: 1.45rem;
		font-weight: 700;
		letter-spacing: 0.15em;
		color: var(--color-white);
	}

	.card-visibility-toggle,
	.card-copy-btn {
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.2);
		color: var(--color-white);
		padding: 4px 8px;
		border-radius: var(--radius-sm);
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.75rem;
		transition: all var(--transition-fast);
	}

	.card-visibility-toggle:hover,
	.card-copy-btn:hover {
		background: rgba(255, 255, 255, 0.25);
	}

	.card-visibility-toggle svg,
	.card-copy-btn svg {
		width: 14px;
		height: 14px;
	}

	.card-footer-info {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
	}

	.holder-section {
		display: flex;
		flex-direction: column;
	}

	.holder-label {
		font-size: 0.65rem;
		letter-spacing: 0.1em;
		color: #9ba8a4;
	}

	.holder-name {
		font-size: 0.95rem;
		font-weight: 700;
		color: var(--color-white);
	}

	.biometric-indicator {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: #68d391;
	}

	.indicator-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background-color: #68d391;
		box-shadow: 0 0 8px #68d391;
	}

	/* Summary Details Grid */
	.summary-details-card {
		background: var(--color-cream-light);
		border: 1px solid var(--color-gray-border);
		border-radius: var(--radius-md);
		padding: 1.5rem;
		margin-bottom: 1.5rem;
	}

	.summary-details-card h3 {
		font-size: 1.1rem;
		margin-bottom: 1rem;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0.85rem 1.5rem;
	}

	.summary-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.88rem;
		padding-bottom: 0.4rem;
		border-bottom: 1px solid rgba(102, 115, 111, 0.1);
	}

	.sum-label {
		color: var(--color-gray);
	}

	.sum-value {
		font-weight: 600;
		color: var(--color-forest);
	}

	.sum-value.mono {
		font-family: monospace;
	}

	.sum-value.highlight {
		color: #235c4e;
	}

	.email-status-banner {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		background: #ebf8ff;
		border: 1px solid #bee3f8;
		padding: 0.9rem 1.25rem;
		border-radius: var(--radius-md);
		color: #2b6cb0;
		font-size: 0.88rem;
		margin-bottom: 2rem;
	}

	.resend-email-btn {
		margin-left: 0.5rem;
		font-weight: 700;
		color: #2b6cb0;
		text-decoration: underline;
	}

	.success-actions {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}

	/* Micro-animation Spinner */
	.btn-spinner {
		width: 16px;
		height: 16px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: white;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	.btn-spinner.large {
		width: 36px;
		height: 36px;
		border-width: 3px;
		border-top-color: var(--color-forest);
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* Responsive Tweaks */
	@media (max-width: 768px) {
		.form-grid,
		.summary-grid {
			grid-template-columns: 1fr;
		}

		.form-group.full-width {
			grid-column: span 1;
		}

		.stepper-bar {
			padding: 1rem;
		}

		.step-label {
			display: none;
		}

		.smart-card {
			aspect-ratio: auto;
			min-height: 220px;
		}

		.card-digits {
			font-size: 1.15rem;
			letter-spacing: 0.08em;
		}
	}
</style>
