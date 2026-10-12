<script>
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/state';
	import { publicApiRequest } from '../../lib/api.js';

	let incidentId = $state('');
	let token = $state('');
	let initialAction = $state('');

	let isLoading = $state(true);
	let isSubmitting = $state(false);
	let errorMessage = $state('');
	let successMessage = $state('');

	let incidentData = $state(null);
	let imageUrl = $state('');

	onMount(async () => {
		// Read search params
		const urlParams = new URLSearchParams(window.location.search);
		incidentId = urlParams.get('incident') || '';
		token = urlParams.get('token') || '';
		initialAction = (urlParams.get('action') || '').toUpperCase();

		if (!incidentId || !token) {
			errorMessage = 'Missing required security incident identifier or authorization token.';
			isLoading = false;
			return;
		}

		await loadIncidentDetails();
	});

	onDestroy(() => {
		if (imageUrl && imageUrl.startsWith('blob:')) {
			try {
				URL.revokeObjectURL(imageUrl);
			} catch {
				// ignore
			}
		}
	});

	async function loadIncidentDetails() {
		isLoading = true;
		errorMessage = '';

		try {
			const res = await publicApiRequest(`/api/atm/security-alert/${incidentId}?token=${encodeURIComponent(token)}`);
			incidentData = res;

			// If image exists, load image bytes securely via blob URL
			if (res.hasCapturedImage) {
				fetchIncidentImage();
			}
		} catch (err) {
			errorMessage = err.message || 'Unable to load security incident details. The authorization link may be invalid or expired.';
		} finally {
			isLoading = false;
		}
	}

	const backendBaseUrl = (import.meta.env.VITE_BACKEND_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

	async function fetchIncidentImage() {
		try {
			const imgRes = await fetch(`${backendBaseUrl}/api/atm/security-alert/${incidentId}/image?token=${encodeURIComponent(token)}`);
			if (imgRes.ok) {
				const blob = await imgRes.blob();
				imageUrl = URL.createObjectURL(blob);
			}
		} catch (err) {
			console.warn('Could not load incident image preview:', err);
		}
	}

	async function handleDecision(decision) {
		if (!incidentId || !token || isSubmitting) return;

		isSubmitting = true;
		errorMessage = '';
		successMessage = '';

		try {
			const res = await publicApiRequest(`/api/atm/security-alert/${incidentId}/decision`, {
				method: 'POST',
				body: JSON.stringify({
					decision: decision,
					token: token
				})
			});

			if (res.success) {
				incidentData.status = res.status;
				incidentData.used = true;
				successMessage = res.message || `Decision recorded as ${res.status}.`;
			} else {
				errorMessage = res.message || 'Failed to submit decision.';
			}
		} catch (err) {
			errorMessage = err.message || 'Error processing decision. The link may have already been used or expired.';
		} finally {
			isSubmitting = false;
		}
	}
</script>

<svelte:head>
	<title>Face ATM Security Alert | Card Owner Authorization</title>
</svelte:head>

<div class="alert-page-wrapper">
	<header class="alert-header">
		<div class="brand">
			<div class="brand-icon">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
				</svg>
			</div>
			<div>
				<span class="brand-title">Face ATM Security Center</span>
				<span class="brand-subtitle">Real-time Account Protection & Biometric Verification</span>
			</div>
		</div>
	</header>

	<main class="alert-main">
		{#if isLoading}
			<div class="loading-card">
				<div class="spinner"></div>
				<p>Validating cryptographic incident token...</p>
			</div>
		{:else if errorMessage && !incidentData}
			<div class="error-card">
				<div class="error-icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="10"></circle>
						<line x1="12" y1="8" x2="12" y2="12"></line>
						<line x1="12" y1="16" x2="12.01" y2="16"></line>
					</svg>
				</div>
				<h2>Authorization Link Expired or Invalid</h2>
				<p>{errorMessage}</p>
				<p class="sub-hint">For security, authorization tokens expire automatically and can only be used once.</p>
				<a href="/atm" class="return-btn">Go to Face ATM Terminal</a>
			</div>
		{:else if incidentData}
			<div class="incident-card">
				<!-- Header status banner -->
				<div class="card-status-bar {incidentData.status.toLowerCase()}">
					<div class="status-indicator">
						<span class="dot"></span>
						<span class="status-name">Incident Status: {incidentData.status}</span>
					</div>
					<span class="incident-id">ID: {incidentData.incidentId}</span>
				</div>

				<div class="card-content">
					<h2>Security Alert: Face Verification Mismatch</h2>
					<p class="incident-desc">
						A facial recognition login attempt was detected on your registered Face ATM card, but the face captured at the terminal <strong>did not match</strong> your enrolled biometric face profile.
					</p>

					{#if successMessage}
						<div class="success-banner" role="alert">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<polyline points="20 6 9 17 4 12"></polyline>
							</svg>
							<span>{successMessage}</span>
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

					<!-- Grid with Incident Details and Captured Photo -->
					<div class="details-grid">
						<!-- Metadata details -->
						<div class="meta-section">
							<h3>Incident Summary</h3>
							<dl class="meta-list">
								<div class="meta-item">
									<dt>Card Number</dt>
									<dd class="mono">{incidentData.cardNumberMasked}</dd>
								</div>
								<div class="meta-item">
									<dt>Card Owner</dt>
									<dd>{incidentData.customerName}</dd>
								</div>
								<div class="meta-item">
									<dt>Attempt Date & Time</dt>
									<dd>{incidentData.attemptTimestamp}</dd>
								</div>
								<div class="meta-item">
									<dt>Lockout Status</dt>
									<dd>
										{#if incidentData.isLocked}
											<span class="lock-badge locked">Locked (15-min protection)</span>
										{:else}
											<span class="lock-badge unlocked">Cleared / Inactive</span>
										{/if}
									</dd>
								</div>
							</dl>
						</div>

						<!-- Captured Mismatched Face Image -->
						<div class="photo-section">
							<h3>Captured Attempt Photo</h3>
							{#if imageUrl}
								<div class="image-preview-wrap">
									<img src={imageUrl} alt="Captured attempt face" class="captured-img" />
									<span class="img-caption">Terminal camera snapshot recorded during mismatch</span>
								</div>
							{:else if incidentData.hasCapturedImage}
								<div class="image-loading-placeholder">
									<div class="spinner small"></div>
									<span>Loading captured attempt image...</span>
								</div>
							{:else}
								<div class="image-empty-placeholder">
									<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
										<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
										<circle cx="12" cy="7" r="4"></circle>
									</svg>
									<span>Biometric sensor snapshot logged securely</span>
								</div>
							{/if}
						</div>
					</div>

					<!-- Decision Options Section -->
					{#if incidentData.status === 'PENDING' && !incidentData.used}
						<div class="decision-box">
							<h3>Do you recognize and authorize this attempt?</h3>
							<p class="decision-guide">
								Please inspect the captured photo above and choose your authorization response:
							</p>

							<div class="decision-buttons">
								<button
									type="button"
									class="accept-btn"
									onclick={() => handleDecision('ACCEPT')}
									disabled={isSubmitting}
								>
									{#if isSubmitting}
										<div class="spinner small"></div>
									{:else}
										<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
											<polyline points="20 6 9 17 4 12"></polyline>
										</svg>
									{/if}
									<span>ACCEPT Attempt (Clear Lockout)</span>
								</button>

								<button
									type="button"
									class="deny-btn"
									onclick={() => handleDecision('DENY')}
									disabled={isSubmitting}
								>
									{#if isSubmitting}
										<div class="spinner small"></div>
									{:else}
										<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
											<line x1="18" y1="6" x2="6" y2="18"></line>
											<line x1="6" y1="6" x2="18" y2="18"></line>
										</svg>
									{/if}
									<span>DENY Attempt (Maintain Lockout)</span>
								</button>
							</div>

							<div class="security-notice">
								<strong>Crucial Biometric Rule:</strong>
								Selecting ACCEPT lifts the temporary lockout to allow a retry. The customer at the ATM terminal must still pass facial biometric verification against the enrolled face before any transaction is permitted. Accepting an alert does not bypass face matching.
							</div>
						</div>
					{:else}
						<div class="finalized-box">
							<div class="finalized-badge">
								Incident Finalized: <strong>{incidentData.status}</strong>
							</div>
							<p>
								This security alert has already been resolved and replay protection prevents subsequent modifications.
							</p>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</main>
</div>

<style>
	.alert-page-wrapper {
		min-height: 100vh;
		background: linear-gradient(135deg, #09131d 0%, #0d1e2e 50%, #061019 100%);
		color: #f1f5f9;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		display: flex;
		flex-direction: column;
	}

	.alert-header {
		padding: 1.25rem 2.5rem;
		background: rgba(15, 23, 42, 0.85);
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(12px);
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 1rem;
		max-width: 900px;
		margin: 0 auto;
	}

	.brand-icon {
		width: 44px;
		height: 44px;
		background: linear-gradient(135deg, #059669 0%, #047857 100%);
		border-radius: 10px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #ffffff;
		box-shadow: 0 4px 12px rgba(5, 150, 105, 0.35);
	}

	.brand-icon svg {
		width: 24px;
		height: 24px;
	}

	.brand-title {
		display: block;
		font-size: 1.25rem;
		font-weight: 700;
		color: #ffffff;
	}

	.brand-subtitle {
		display: block;
		font-size: 0.85rem;
		color: #94a3b8;
	}

	.alert-main {
		flex: 1;
		max-width: 860px;
		width: 100%;
		margin: 2rem auto;
		padding: 0 1.5rem;
		box-sizing: border-box;
	}

	.loading-card,
	.error-card,
	.incident-card {
		background: #ffffff;
		color: #0f172a;
		border-radius: 14px;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
		overflow: hidden;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.loading-card,
	.error-card {
		padding: 3rem 2rem;
		text-align: center;
	}

	.error-icon {
		width: 56px;
		height: 56px;
		background: #fee2e2;
		color: #dc2626;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 1.5rem;
	}

	.error-icon svg {
		width: 32px;
		height: 32px;
	}

	.sub-hint {
		color: #64748b;
		font-size: 0.9rem;
		margin-top: 0.5rem;
	}

	.return-btn {
		display: inline-block;
		margin-top: 1.5rem;
		background: #0f766e;
		color: #ffffff;
		padding: 0.75rem 1.5rem;
		border-radius: 8px;
		text-decoration: none;
		font-weight: 600;
	}

	.card-status-bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.85rem 1.75rem;
		font-size: 0.9rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.card-status-bar.pending {
		background: #fef3c7;
		color: #92400e;
		border-bottom: 2px solid #f59e0b;
	}

	.card-status-bar.accepted {
		background: #d1fae5;
		color: #065f46;
		border-bottom: 2px solid #10b981;
	}

	.card-status-bar.denied,
	.card-status-bar.expired {
		background: #fee2e2;
		color: #991b1b;
		border-bottom: 2px solid #ef4444;
	}

	.status-indicator {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.status-indicator .dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: currentColor;
	}

	.incident-id {
		font-family: monospace;
		font-size: 0.8rem;
		opacity: 0.85;
	}

	.card-content {
		padding: 2.25rem 2.5rem;
	}

	.card-content h2 {
		margin: 0 0 0.5rem;
		font-size: 1.6rem;
		font-weight: 800;
		color: #0f172a;
	}

	.incident-desc {
		color: #475569;
		font-size: 1rem;
		line-height: 1.5;
		margin: 0 0 1.75rem;
	}

	.details-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2rem;
		margin-bottom: 2rem;
	}

	@media (max-width: 680px) {
		.details-grid {
			grid-template-columns: 1fr;
		}
	}

	.meta-section,
	.photo-section {
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 10px;
		padding: 1.25rem 1.5rem;
	}

	.meta-section h3,
	.photo-section h3 {
		font-size: 1.05rem;
		font-weight: 700;
		margin: 0 0 1rem;
		color: #1e293b;
		border-bottom: 1px solid #e2e8f0;
		padding-bottom: 0.5rem;
	}

	.meta-list {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.meta-item {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.meta-item dt {
		font-size: 0.8rem;
		color: #64748b;
		text-transform: uppercase;
		font-weight: 600;
		letter-spacing: 0.5px;
	}

	.meta-item dd {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: #0f172a;
	}

	.meta-item dd.mono {
		font-family: monospace;
		letter-spacing: 1px;
	}

	.lock-badge {
		display: inline-block;
		padding: 3px 8px;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 700;
	}

	.lock-badge.locked {
		background: #fee2e2;
		color: #991b1b;
	}

	.lock-badge.unlocked {
		background: #d1fae5;
		color: #065f46;
	}

	.image-preview-wrap {
		text-align: center;
	}

	.captured-img {
		width: 100%;
		max-height: 220px;
		object-fit: cover;
		border-radius: 8px;
		border: 2px solid #cbd5e1;
		box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
	}

	.img-caption {
		display: block;
		font-size: 0.75rem;
		color: #64748b;
		margin-top: 0.5rem;
	}

	.image-loading-placeholder,
	.image-empty-placeholder {
		min-height: 180px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		background: #f1f5f9;
		border-radius: 8px;
		color: #64748b;
		font-size: 0.85rem;
	}

	.image-empty-placeholder svg {
		width: 36px;
		height: 36px;
		color: #94a3b8;
	}

	/* Decision Box */
	.decision-box {
		background: #f1f5f9;
		border: 2px solid #cbd5e1;
		border-radius: 12px;
		padding: 1.75rem;
		text-align: center;
	}

	.decision-box h3 {
		margin: 0 0 0.5rem;
		font-size: 1.25rem;
		font-weight: 800;
		color: #0f172a;
	}

	.decision-guide {
		margin: 0 0 1.5rem;
		color: #475569;
		font-size: 0.95rem;
	}

	.decision-buttons {
		display: flex;
		justify-content: center;
		gap: 1.25rem;
		flex-wrap: wrap;
		margin-bottom: 1.25rem;
	}

	.accept-btn,
	.deny-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		padding: 1rem 1.75rem;
		border-radius: 8px;
		font-size: 1rem;
		font-weight: 700;
		border: none;
		cursor: pointer;
		transition: transform 0.15s, box-shadow 0.15s;
		color: #ffffff;
	}

	.accept-btn {
		background: linear-gradient(135deg, #059669 0%, #047857 100%);
		box-shadow: 0 4px 14px rgba(5, 150, 105, 0.35);
	}

	.accept-btn:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 18px rgba(5, 150, 105, 0.45);
	}

	.deny-btn {
		background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
		box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35);
	}

	.deny-btn:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 6px 18px rgba(220, 38, 38, 0.45);
	}

	.accept-btn:disabled,
	.deny-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		transform: none;
	}

	.accept-btn svg,
	.deny-btn svg {
		width: 20px;
		height: 20px;
	}

	.security-notice {
		background: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 8px;
		padding: 0.85rem 1.25rem;
		font-size: 0.82rem;
		color: #475569;
		line-height: 1.4;
		text-align: left;
	}

	.finalized-box {
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 10px;
		padding: 1.5rem;
		text-align: center;
		color: #64748b;
	}

	.finalized-badge {
		font-size: 1.1rem;
		font-weight: 700;
		color: #0f172a;
		margin-bottom: 0.5rem;
	}

	.success-banner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: #d1fae5;
		color: #065f46;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.5rem;
		font-weight: 600;
		font-size: 0.95rem;
		border-left: 4px solid #10b981;
	}

	.success-banner svg {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
	}

	.error-banner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: #fee2e2;
		color: #991b1b;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.5rem;
		font-size: 0.95rem;
		border-left: 4px solid #dc2626;
	}

	.error-banner svg {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
	}

	.spinner {
		width: 24px;
		height: 24px;
		border: 3px solid rgba(0, 0, 0, 0.1);
		border-top-color: #0f766e;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin: 0 auto 1rem;
	}

	.spinner.small {
		width: 18px;
		height: 18px;
		border-width: 2px;
		border-top-color: #ffffff;
		margin: 0;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
