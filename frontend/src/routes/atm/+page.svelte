<script>
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { publicApiRequest, setCustomerSession } from '#lib/api.js';

	// Steps: 'CARD_ENTRY' | 'CAMERA_SCAN' | 'LOCKED' | 'ERROR'
	let step = $state('CARD_ENTRY');

	// Card input state
	let rawCardNumber = $state('');
	let cardFormatted = $state('');
	let cardMasked = $state('');
	let customerName = $state('');
	let isSubmitting = $state(false);
	let errorMessage = $state('');
	let warningMessage = $state('');

	// Lockout state
	let lockoutSeconds = $state(0);
	let lockoutTimer = null;
	let lockoutPollTimer = null;

	// Camera & Face detection feedback state
	let videoElement = $state(null);
	let canvasElement = null;
	let mediaStream = null;
	let cameraLoading = $state(false);
	let cameraError = $state('');
	let isScanning = $state(false);
	let scanStatusText = $state('Align your face inside the biometric frame');
	let faceFeedbackMessage = $state('');
	let faceNotRecognizable = $state(false);
	let faceCheckTimer = null;
	let isCheckingFace = false;

	onMount(() => {
		canvasElement = document.createElement('canvas');
	});

	onDestroy(() => {
		stopCamera();
		if (lockoutTimer) clearInterval(lockoutTimer);
		if (lockoutPollTimer) clearInterval(lockoutPollTimer);
	});

	function handleCardInput(event) {
		const input = event.target.value.replace(/\D/g, '').slice(0, 16);
		rawCardNumber = input;
		cardFormatted = input.match(/.{1,4}/g)?.join(' ') || input;
		errorMessage = '';
	}

	function startLockoutCountdown(seconds) {
		lockoutSeconds = seconds;
		if (lockoutTimer) clearInterval(lockoutTimer);
		if (lockoutPollTimer) clearInterval(lockoutPollTimer);

		lockoutTimer = setInterval(() => {
			if (lockoutSeconds > 1) {
				lockoutSeconds -= 1;
			} else {
				clearInterval(lockoutTimer);
				if (lockoutPollTimer) clearInterval(lockoutPollTimer);
				lockoutSeconds = 0;
				step = 'CARD_ENTRY';
				errorMessage = 'Lockout has expired. You may now retry card entry.';
			}
		}, 1000);

		// Continuously check if real card owner approves the incident
		lockoutPollTimer = setInterval(checkOwnerApprovalStatus, 4000);
	}

	async function checkOwnerApprovalStatus() {
		if (step !== 'LOCKED' || !rawCardNumber) return;
		try {
			const res = await publicApiRequest('/api/atm/card-validate', {
				method: 'POST',
				body: JSON.stringify({ cardNumber: rawCardNumber })
			});
			if (!res.isLocked && res.valid) {
				if (lockoutTimer) clearInterval(lockoutTimer);
				if (lockoutPollTimer) clearInterval(lockoutPollTimer);
				lockoutSeconds = 0;
				customerName = res.fullName;
				cardMasked = res.cardNumberMasked;
				step = 'CAMERA_SCAN';
				warningMessage = 'Card owner authorized access! Please present your face to complete facial verification.';
				setTimeout(startCamera, 150);
			}
		} catch (err) {
			// ignore polling errors
		}
	}

	async function handleCardSubmit(e) {
		e.preventDefault();
		errorMessage = '';
		warningMessage = '';

		if (rawCardNumber.length !== 16) {
			errorMessage = 'Please enter a complete 16-digit Face ATM card number.';
			return;
		}

		isSubmitting = true;
		try {
			const res = await publicApiRequest('/api/atm/card-validate', {
				method: 'POST',
				body: JSON.stringify({ cardNumber: rawCardNumber })
			});

			if (res.isLocked) {
				step = 'LOCKED';
				startLockoutCountdown(res.lockoutRemainingSeconds || 900);
				return;
			}

			if (res.valid) {
				customerName = res.fullName;
				cardMasked = res.cardNumberMasked;
				step = 'CAMERA_SCAN';
				// Delay camera start slightly to allow DOM to render video element
				setTimeout(startCamera, 150);
			} else {
				errorMessage = res.message || 'Card validation failed.';
			}
		} catch (err) {
			errorMessage = err.message || 'Card validation error. Please verify the card number.';
		} finally {
			isSubmitting = false;
		}
	}

	async function startCamera() {
		cameraLoading = true;
		cameraError = '';
		faceNotRecognizable = false;
		faceFeedbackMessage = '';

		try {
			mediaStream = await navigator.mediaDevices.getUserMedia({
				video: {
					width: { ideal: 640 },
					height: { ideal: 480 },
					facingMode: 'user'
				},
				audio: false
			});

			if (videoElement) {
				videoElement.srcObject = mediaStream;
				await videoElement.play();
				startLiveFaceMonitoring();
			}
		} catch (err) {
			console.error('Camera access error:', err);
			cameraError = 'Camera access was denied or is unavailable. Please permit camera access to authenticate.';
		} finally {
			cameraLoading = false;
		}
	}

	function startLiveFaceMonitoring() {
		if (faceCheckTimer) clearInterval(faceCheckTimer);
		faceCheckTimer = setInterval(checkLiveFacePresence, 900);
	}

	async function checkLiveFacePresence() {
		if (!videoElement || !mediaStream || isScanning || isCheckingFace || step !== 'CAMERA_SCAN') return;
		if (!videoElement.videoWidth || !videoElement.videoHeight) return;

		isCheckingFace = true;
		try {
			canvasElement.width = 320;
			canvasElement.height = 240;
			const ctx = canvasElement.getContext('2d');
			ctx.drawImage(videoElement, 0, 0, 320, 240);
			const imageBase64 = canvasElement.toDataURL('image/jpeg', 0.85);

			const res = await publicApiRequest('/api/atm/face-check', {
				method: 'POST',
				body: JSON.stringify({ imageBase64 })
			});

			if (!res.recognizable) {
				faceNotRecognizable = true;
				faceFeedbackMessage = 'Face Not Recognizable — Please show your full face to the camera.';
			} else {
				faceNotRecognizable = false;
				faceFeedbackMessage = '';
			}
		} catch (err) {
			// ignore transient frame check errors
		} finally {
			isCheckingFace = false;
		}
	}

	function stopCamera() {
		if (faceCheckTimer) {
			clearInterval(faceCheckTimer);
			faceCheckTimer = null;
		}
		faceNotRecognizable = false;
		faceFeedbackMessage = '';
		if (mediaStream) {
			mediaStream.getTracks().forEach((track) => track.stop());
			mediaStream = null;
		}
	}

	async function captureAndVerifyFace() {
		if (!videoElement || !mediaStream) {
			cameraError = 'Camera feed not available.';
			return;
		}

		errorMessage = '';
		warningMessage = '';
		isScanning = true;
		scanStatusText = 'Extracting facial biometrics and comparing embedding...';

		try {
			// Capture current video frame to canvas
			canvasElement.width = videoElement.videoWidth || 640;
			canvasElement.height = videoElement.videoHeight || 480;
			const ctx = canvasElement.getContext('2d');
			ctx.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);

			const imageBase64 = canvasElement.toDataURL('image/jpeg', 0.92);

			const res = await publicApiRequest('/api/atm/login-face', {
				method: 'POST',
				body: JSON.stringify({
					cardNumber: rawCardNumber,
					imageBase64: imageBase64
				})
			});

			if (res.success && res.sessionToken) {
				scanStatusText = 'Biometric match confirmed! Launching ATM terminal...';
				stopCamera();
				setCustomerSession(res.sessionToken, {
					customerId: res.customerId,
					fullName: res.fullName,
					cardNumberMasked: res.cardNumberMasked,
					balance: res.balance
				});
				setTimeout(() => {
					goto('/atm/dashboard', { replaceState: true });
				}, 600);
			}
		} catch (err) {
			console.error('Face verification failed:', err);
			if (err.status === 403) {
				// Lockout triggered
				stopCamera();
				step = 'LOCKED';
				startLockoutCountdown(900);
				errorMessage = err.message || 'Card locked due to maximum failed attempts.';
			} else if (err.status === 400 && (err.message?.includes('Face Not Recognizable') || err.message?.includes('No face detected'))) {
				faceNotRecognizable = true;
				faceFeedbackMessage = 'Face Not Recognizable — Please show your full face to the camera.';
				errorMessage = 'Face Not Recognizable — Please show your full face to the camera.';
				scanStatusText = 'Face Not Recognizable — Please show your full face to the camera.';
			} else {
				errorMessage = err.message || 'Face verification failed. Please try again.';
				scanStatusText = 'Verification failed. Please realign and try again.';
			}
		} finally {
			isScanning = false;
		}
	}

	function cancelAndReturn() {
		stopCamera();
		if (lockoutPollTimer) clearInterval(lockoutPollTimer);
		step = 'CARD_ENTRY';
		errorMessage = '';
		warningMessage = '';
	}
</script>

<svelte:head>
	<title>Face ATM Terminal | Customer Authentication</title>
</svelte:head>

<div class="atm-terminal-wrapper">
	<!-- Top Navigation Header -->
	<header class="terminal-header">
		<div class="terminal-brand">
			<div class="brand-chip">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<rect x="2" y="5" width="20" height="14" rx="3"></rect>
					<line x1="2" y1="10" x2="22" y2="10"></line>
				</svg>
			</div>
			<div class="brand-title-wrap">
				<span class="brand-name">Face ATM</span>
				<span class="brand-tag">Terminal #01 &bull; Secure Biometric Banking</span>
			</div>
		</div>

		<a href="/login" class="admin-switch-btn" title="Switch to Admin Portal">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
				<circle cx="9" cy="7" r="4"></circle>
				<polyline points="16 11 18 13 22 9"></polyline>
			</svg>
			<span>Admin Portal</span>
		</a>
	</header>

	<!-- Main ATM Center Terminal -->
	<main class="terminal-body">
		<!-- Disclaimer Banner -->
		<div class="disclaimer-badge">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="12" cy="12" r="10"></circle>
				<line x1="12" y1="16" x2="12" y2="12"></line>
				<line x1="12" y1="8" x2="12.01" y2="8"></line>
			</svg>
			<span>
				<strong>Simulation Mode:</strong> Face verification runs live YuNet + SFace models. Physical anti-spoof/liveness protection is inactive in this development demo.
			</span>
		</div>

		<!-- STEP 1: CARD NUMBER ENTRY -->
		{#if step === 'CARD_ENTRY'}
			<div class="atm-card-panel">
				<div class="panel-header">
					<h2>Insert Your Face ATM Card</h2>
					<p>Enter your 16-digit customer card number to initiate facial biometric login.</p>
				</div>

				{#if errorMessage}
					<div class="error-banner" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="10"></circle>
							<line x1="12" y1="8" x2="12" y2="12"></line>
							<line x1="12" y1="16" x2="12.01" y2="16"></line>
						</svg>
						<span>{errorMessage}</span>
					</div>
				{/if}

				<form onsubmit={handleCardSubmit} class="card-entry-form">
					<!-- Visual Smart Card Preview -->
					<div class="visual-card">
						<div class="vc-top">
							<span class="vc-logo">FACE ATM SMART</span>
							<div class="vc-contactless">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M5 8.5a8 8 0 0 1 14 0"></path>
									<path d="M8 12a4 4 0 0 1 8 0"></path>
								</svg>
							</div>
						</div>
						<div class="vc-chip"></div>
						<div class="vc-number">
							{cardFormatted || '5049 &bull;&bull;&bull;&bull; &bull;&bull;&bull;&bull; &bull;&bull;&bull;&bull;'}
						</div>
						<div class="vc-bottom">
							<div>
								<div class="vc-label">CARDHOLDER</div>
								<div class="vc-val">CUSTOMER IDENTIFIER</div>
							</div>
							<div class="vc-secure-badge">BIOMETRIC ENROLLED</div>
						</div>
					</div>

					<!-- Form Input -->
					<div class="form-group">
						<label for="cardNumberInput">16-Digit Card Number</label>
						<div class="input-wrap">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<rect x="2" y="5" width="20" height="14" rx="2"></rect>
								<line x1="2" y1="10" x2="22" y2="10"></line>
							</svg>
							<input
								id="cardNumberInput"
								type="text"
								inputmode="numeric"
								placeholder="5049 XXXX XXXX XXXX"
								value={cardFormatted}
								oninput={handleCardInput}
								maxlength="19"
								autocomplete="off"
								required
							/>
						</div>
						<span class="hint">Check card number in customer registration email or admin dashboard.</span>
					</div>

					<button type="submit" class="submit-atm-btn" disabled={isSubmitting || rawCardNumber.length !== 16}>
						{#if isSubmitting}
							<div class="btn-spinner"></div>
							<span>Validating Card...</span>
						{:else}
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<circle cx="12" cy="12" r="3"></circle>
								<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
								<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
								<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
								<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
							</svg>
							<span>Proceed to Face Verification</span>
						{/if}
					</button>
				</form>
			</div>
		{/if}

		<!-- STEP 2: CAMERA BIOMETRIC SCAN -->
		{#if step === 'CAMERA_SCAN'}
			<div class="atm-camera-panel">
				<div class="panel-header">
					<div class="customer-greeting">
						<span class="welcome-label">Customer:</span>
						<span class="customer-name-highlight">{customerName}</span>
						<span class="card-pill">{cardMasked}</span>
					</div>
					<h2>Facial Biometric Verification</h2>
					<p>{scanStatusText}</p>
				</div>

				{#if faceFeedbackMessage}
					<div class="face-warning-banner" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="10"></circle>
							<line x1="12" y1="8" x2="12" y2="12"></line>
							<line x1="12" y1="16" x2="12.01" y2="16"></line>
						</svg>
						<span>{faceFeedbackMessage}</span>
					</div>
				{/if}

				{#if errorMessage}
					<div class="error-banner" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="10"></circle>
							<line x1="12" y1="8" x2="12" y2="12"></line>
							<line x1="12" y1="16" x2="12.01" y2="16"></line>
						</svg>
						<span>{errorMessage}</span>
					</div>
				{/if}

				{#if cameraError}
					<div class="error-banner" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
							<line x1="1" y1="1" x2="23" y2="23"></line>
						</svg>
						<span>{cameraError}</span>
					</div>
				{/if}

				<!-- Camera Viewport with Biometric Overlay -->
				<div class="camera-viewport-wrap">
					<!-- svelte-ignore a11y_media_has_caption -->
					<video bind:this={videoElement} autoplay playsinline muted class="camera-video"></video>

					<!-- Guideline Target Overlay -->
					<div class="biometric-hud {isScanning ? 'scanning-active' : ''}">
						<div class="face-target-oval {faceNotRecognizable ? 'oval-warning' : ''}">
							<div class="crosshair ch-tl"></div>
							<div class="crosshair ch-tr"></div>
							<div class="crosshair ch-bl"></div>
							<div class="crosshair ch-br"></div>
							{#if isScanning}
								<div class="laser-scanner"></div>
							{/if}
						</div>
					</div>

					{#if cameraLoading}
						<div class="camera-loading-overlay">
							<div class="btn-spinner large"></div>
							<p>Initializing camera...</p>
						</div>
					{/if}
				</div>

				<div class="camera-actions">
					<button type="button" class="back-btn" onclick={cancelAndReturn} disabled={isScanning}>
						&larr; Re-enter Card
					</button>

					<button
						type="button"
						class="verify-btn"
						onclick={captureAndVerifyFace}
						disabled={isScanning || cameraLoading || !!cameraError}
					>
						{#if isScanning}
							<div class="btn-spinner"></div>
							<span>Verifying Face Biometrics...</span>
						{:else}
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<circle cx="12" cy="12" r="3"></circle>
								<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
							</svg>
							<span>Verify Face & Access Account</span>
						{/if}
					</button>
				</div>
			</div>
		{/if}

		<!-- STEP 3: TEMPORARY LOCKOUT DISPLAY -->
		{#if step === 'LOCKED'}
			<div class="atm-locked-panel">
				<div class="lock-icon-wrap">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
						<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
					</svg>
				</div>

				<h2>Security Lockout Active</h2>
				<p class="lockout-desc">
					Repeated face verification failures were detected. For account security, this card has been temporarily locked. A security alert email with the captured photo was dispatched to the real card owner with ACCEPT and DENY authorization options.
				</p>

				<div class="countdown-card">
					<div class="countdown-time">
						{Math.floor(lockoutSeconds / 60)}m {lockoutSeconds % 60}s
					</div>
					<div class="countdown-sub">Time remaining until card automatically unlocks</div>
				</div>

				<div class="lockout-actions">
					<p class="help-text">
						If the real card owner selects ACCEPT in their security email, the lockout will clear automatically. You can also click below to check status immediately.
					</p>
					<div class="lockout-buttons-row">
						<button class="check-auth-btn" onclick={checkOwnerApprovalStatus}>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
								<polyline points="22 4 12 14.01 9 11.01"></polyline>
							</svg>
							<span>Check Authorization Status</span>
						</button>
						<button class="reset-btn" onclick={() => { stopCamera(); if (lockoutPollTimer) clearInterval(lockoutPollTimer); step = 'CARD_ENTRY'; }}>
							Return to Card Entry
						</button>
					</div>
				</div>
			</div>
		{/if}
	</main>
</div>

<style>
	.atm-terminal-wrapper {
		min-height: 100vh;
		background: linear-gradient(135deg, var(--color-navy) 0%, #0d1e2e 50%, var(--color-navy-dark) 100%);
		color: #f1f5f9;
		font-family: var(--font-body);
		display: flex;
		flex-direction: column;
		animation: fadeIn 0.3s ease-out;
	}

	.terminal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.25rem 2.5rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(16, 24, 40, 0.75);
		backdrop-filter: blur(12px);
	}

	.terminal-brand {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.brand-chip {
		width: 44px;
		height: 44px;
		background: linear-gradient(135deg, var(--color-teal) 0%, #0d655e 100%);
		border-radius: var(--radius-md);
		display: flex;
		align-items: center;
		justify-content: center;
		color: #ffffff;
		box-shadow: 0 4px 14px rgba(15, 118, 110, 0.35);
	}

	.brand-chip svg {
		width: 24px;
		height: 24px;
	}

	.brand-title-wrap {
		display: flex;
		flex-direction: column;
	}

	.brand-name {
		font-family: var(--font-heading);
		font-size: 1.25rem;
		font-weight: 700;
		letter-spacing: 0.5px;
		color: #ffffff;
	}

	.brand-tag {
		font-size: 0.78rem;
		color: #94a3b8;
	}

	.admin-switch-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.16);
		color: #e2e8f0;
		padding: 0.55rem 1.1rem;
		border-radius: var(--radius-md);
		text-decoration: none;
		font-size: 0.88rem;
		font-weight: 600;
		transition: all var(--transition-fast);
	}

	.admin-switch-btn:hover {
		background: rgba(255, 255, 255, 0.16);
		color: #ffffff;
		transform: translateY(-1px);
	}

	.admin-switch-btn svg {
		width: 16px;
		height: 16px;
	}

	.terminal-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2.5rem 1.5rem;
		max-width: 720px;
		margin: 0 auto;
		width: 100%;
	}

	.disclaimer-badge {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: rgba(15, 118, 110, 0.15);
		border: 1px solid rgba(15, 118, 110, 0.35);
		color: #ccfbf1;
		padding: 0.85rem 1.25rem;
		border-radius: var(--radius-md);
		font-size: 0.85rem;
		line-height: 1.4;
		margin-bottom: 1.75rem;
		width: 100%;
	}

	.disclaimer-badge svg {
		width: 22px;
		height: 22px;
		flex-shrink: 0;
		color: #2dd4bf;
	}

	.atm-card-panel,
	.atm-camera-panel,
	.atm-locked-panel {
		background: #ffffff;
		color: var(--color-navy);
		border-radius: var(--radius-lg);
		padding: 2.25rem 2.5rem;
		width: 100%;
		box-shadow: var(--shadow-hover);
		animation: slideUp 0.35s ease-out;
		border: 1px solid rgba(255, 255, 255, 0.15);
	}

	.panel-header {
		text-align: center;
		margin-bottom: 1.75rem;
	}

	.panel-header h2 {
		font-size: 1.6rem;
		font-weight: 700;
		margin: 0 0 0.4rem;
		color: var(--color-navy);
	}

	.panel-header p {
		color: var(--color-text-muted);
		font-size: 0.95rem;
		margin: 0;
	}

	.error-banner {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		background: #fee2e2;
		color: #991b1b;
		padding: 0.85rem 1rem;
		border-radius: 8px;
		margin-bottom: 1.25rem;
		font-size: 0.9rem;
		border-left: 4px solid #dc2626;
	}

	.error-banner svg {
		width: 18px;
		height: 18px;
		flex-shrink: 0;
	}

	.face-warning-banner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: #fffbeb;
		color: #92400e;
		padding: 0.85rem 1.1rem;
		border-radius: 8px;
		margin-bottom: 1.25rem;
		font-size: 0.95rem;
		font-weight: 600;
		border: 1px solid #fde68a;
		border-left: 5px solid #d97706;
		animation: pulseWarning 2s infinite ease-in-out;
	}

	.face-warning-banner svg {
		width: 22px;
		height: 22px;
		flex-shrink: 0;
		color: #d97706;
	}

	@keyframes pulseWarning {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.95; transform: scale(0.998); }
	}

	.oval-warning {
		border-color: #f59e0b !important;
		border-style: dashed !important;
		box-shadow: 0 0 20px rgba(245, 158, 11, 0.6), 0 0 0 9999px rgba(0, 0, 0, 0.45) !important;
	}

	.check-auth-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		background: linear-gradient(135deg, var(--color-teal) 0%, #0d655e 100%);
		color: #ffffff;
		padding: 0.85rem 1.4rem;
		border-radius: var(--radius-md);
		font-weight: 600;
		font-size: 0.95rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
		box-shadow: 0 4px 12px rgba(15, 118, 110, 0.3);
	}

	.check-auth-btn:hover {
		background: linear-gradient(135deg, #115e59 0%, #0a4f49 100%);
		transform: translateY(-2px);
	}

	.check-auth-btn svg {
		width: 18px;
		height: 18px;
	}

	.lockout-buttons-row {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		align-items: center;
		margin-top: 1rem;
	}

	/* Visual Card Styling */
	.visual-card {
		background: linear-gradient(135deg, #173f35 0%, #0d2822 100%);
		color: #ffffff;
		border-radius: 14px;
		padding: 1.5rem 1.75rem;
		margin-bottom: 1.75rem;
		box-shadow: 0 10px 25px rgba(23, 63, 53, 0.25);
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.vc-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.vc-logo {
		font-size: 0.95rem;
		font-weight: 700;
		letter-spacing: 1.5px;
		color: #eeddc9;
	}

	.vc-contactless svg {
		width: 22px;
		height: 22px;
		color: #eeddc9;
	}

	.vc-chip {
		width: 36px;
		height: 26px;
		background: linear-gradient(135deg, #d4af37, #aa8012);
		border-radius: 6px;
		margin: 1.25rem 0;
	}

	.vc-number {
		font-family: 'Courier New', Courier, monospace;
		font-size: 1.35rem;
		font-weight: 700;
		letter-spacing: 3px;
		color: #fbf8f3;
		margin-bottom: 1rem;
	}

	.vc-bottom {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
	}

	.vc-label {
		font-size: 0.65rem;
		letter-spacing: 1px;
		color: #9ca3af;
	}

	.vc-val {
		font-size: 0.85rem;
		font-weight: 600;
		letter-spacing: 1px;
		color: #eeddc9;
	}

	.vc-secure-badge {
		font-size: 0.7rem;
		font-weight: 700;
		background: rgba(217, 119, 69, 0.25);
		color: #eeddc9;
		padding: 3px 8px;
		border-radius: 999px;
		border: 1px solid rgba(217, 119, 69, 0.4);
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.5rem;
	}

	.form-group label {
		font-weight: 600;
		font-size: 0.9rem;
		color: #374151;
	}

	.input-wrap {
		position: relative;
		display: flex;
		align-items: center;
	}

	.input-wrap svg {
		position: absolute;
		left: 1rem;
		width: 20px;
		height: 20px;
		color: #9ca3af;
	}

	.input-wrap input {
		width: 100%;
		padding: 0.85rem 1rem 0.85rem 3rem;
		font-size: 1.2rem;
		font-family: 'Courier New', Courier, monospace;
		letter-spacing: 2px;
		font-weight: 600;
		border: 2px solid #e5e7eb;
		border-radius: 10px;
		background: #f9fafb;
		color: #111827;
		transition: border-color 0.2s;
	}

	.input-wrap input:focus {
		outline: none;
		border-color: var(--color-teal);
		background: #ffffff;
		box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.15);
	}

	.hint {
		font-size: 0.8rem;
		color: var(--color-text-light);
	}

	.submit-atm-btn,
	.verify-btn {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		background: linear-gradient(135deg, var(--color-teal) 0%, #0d655e 100%);
		color: #ffffff;
		padding: 1.05rem 1.5rem;
		border-radius: var(--radius-md);
		font-size: 1.05rem;
		font-weight: 700;
		border: none;
		cursor: pointer;
		box-shadow: 0 4px 14px rgba(15, 118, 110, 0.28);
		transition: all var(--transition-normal);
	}

	.submit-atm-btn:hover:not(:disabled),
	.verify-btn:hover:not(:disabled) {
		background: linear-gradient(135deg, #115e59 0%, #0a4f49 100%);
		transform: translateY(-2px);
		box-shadow: 0 8px 22px rgba(15, 118, 110, 0.38);
	}

	.submit-atm-btn:active:not(:disabled),
	.verify-btn:active:not(:disabled) {
		transform: translateY(0);
	}

	.submit-atm-btn:disabled,
	.verify-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		transform: none;
		box-shadow: none;
	}

	.submit-atm-btn svg,
	.verify-btn svg {
		width: 20px;
		height: 20px;
	}

	.btn-spinner {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: #ffffff;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.btn-spinner.large {
		width: 36px;
		height: 36px;
		border-width: 3px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* Camera Viewport */
	.customer-greeting {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		margin-bottom: 0.75rem;
	}

	.welcome-label {
		font-size: 0.85rem;
		color: #6b7280;
	}

	.customer-name-highlight {
		font-weight: 700;
		font-size: 1.05rem;
		color: var(--color-navy);
	}

	.card-pill {
		background: #f3f4f6;
		font-family: monospace;
		font-size: 0.8rem;
		padding: 2px 8px;
		border-radius: 6px;
		color: #4b5563;
	}

	.camera-viewport-wrap {
		position: relative;
		width: 100%;
		height: 360px;
		border-radius: 14px;
		overflow: hidden;
		background: #111827;
		margin-bottom: 1.5rem;
	}

	.camera-video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transform: scaleX(-1); /* Mirror camera view for intuitive feedback */
	}

	.biometric-hud {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		pointer-events: none;
	}

	.face-target-oval {
		width: 200px;
		height: 260px;
		border: 2px dashed rgba(255, 255, 255, 0.7);
		border-radius: 50%;
		position: relative;
		box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.35);
	}

	.scanning-active .face-target-oval {
		border-color: var(--color-teal);
		border-style: solid;
		box-shadow: 0 0 16px rgba(15, 118, 110, 0.5), 0 0 0 9999px rgba(0, 0, 0, 0.35);
	}

	.laser-scanner {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 3px;
		background: var(--color-accent-green);
		box-shadow: 0 0 12px var(--color-accent-green);
		animation: scanLoop 1.5s ease-in-out infinite alternate;
	}

	@keyframes scanLoop {
		0% { top: 10%; }
		100% { top: 90%; }
	}

	.crosshair {
		position: absolute;
		width: 16px;
		height: 16px;
		border-color: #ffffff;
		border-style: solid;
	}

	.ch-tl { top: -2px; left: 16px; border-width: 3px 0 0 3px; }
	.ch-tr { top: -2px; right: 16px; border-width: 3px 3px 0 0; }
	.ch-bl { bottom: -2px; left: 16px; border-width: 0 0 3px 3px; }
	.ch-br { bottom: -2px; right: 16px; border-width: 0 3px 3px 0; }

	.camera-loading-overlay {
		position: absolute;
		inset: 0;
		background: rgba(17, 24, 39, 0.85);
		color: #ffffff;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
	}

	.camera-actions {
		display: flex;
		gap: 1rem;
	}

	.back-btn {
		background: #f3f4f6;
		color: #374151;
		border: 1px solid #d1d5db;
		padding: 1rem 1.25rem;
		border-radius: 10px;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.2s;
	}

	.back-btn:hover:not(:disabled) {
		background: #e5e7eb;
	}

	/* Lockout panel */
	.atm-locked-panel {
		text-align: center;
	}

	.lock-icon-wrap {
		width: 72px;
		height: 72px;
		border-radius: 50%;
		background: #fee2e2;
		color: #dc2626;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 1.5rem;
	}

	.lock-icon-wrap svg {
		width: 36px;
		height: 36px;
	}

	.lockout-desc {
		color: #4b5563;
		line-height: 1.5;
		margin-bottom: 1.5rem;
	}

	.countdown-card {
		background: #fef2f2;
		border: 2px solid #fecaca;
		border-radius: 12px;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
	}

	.countdown-time {
		font-size: 2.25rem;
		font-weight: 800;
		color: #b91c1c;
		font-family: monospace;
	}

	.countdown-sub {
		font-size: 0.85rem;
		color: #7f1d1d;
		margin-top: 0.25rem;
	}

	.reset-btn {
		background: #173f35;
		color: #ffffff;
		border: none;
		padding: 0.85rem 1.75rem;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
	}

	.help-text {
		font-size: 0.85rem;
		color: #6b7280;
		margin-bottom: 1rem;
	}
</style>
