<script>
	import { onMount, onDestroy } from 'svelte';
	import { apiRequest, apiFetchBlob } from '#lib/api.js';

	let approvals = $state([]);
	let isLoading = $state(true);
	let isActionLoading = $state(false);
	let errorMessage = $state('');
	let successMessage = $state('');

	// Action dialog: null | { approval, decision: 'ACCEPT' | 'DENY' }
	let activeDialog = $state(null);
	let adminNotes = $state('');

	// Secure incident image cache and zoom modal
	let incidentImageUrls = $state({});
	let imageLoadingStates = $state({});
	let zoomedImage = $state(null);

	onMount(() => {
		loadSecurityApprovals();
	});

	onDestroy(() => {
		// Revoke all local object URLs to prevent memory leaks
		Object.values(incidentImageUrls).forEach((url) => {
			if (url && typeof url === 'string' && url.startsWith('blob:')) {
				try {
					URL.revokeObjectURL(url);
				} catch {
					// ignore
				}
			}
		});
	});

	async function loadSecurityApprovals() {
		isLoading = true;
		errorMessage = '';
		try {
			const res = await apiRequest('/api/admin/security-approvals');
			approvals = res.approvals || [];
			// Auto-fetch images for pending approvals with captured images
			for (const item of approvals) {
				if (item.hasCapturedImage && !incidentImageUrls[item.id]) {
					fetchIncidentImage(item.id);
				}
			}
		} catch (err) {
			console.error('Failed to load security approvals:', err);
			errorMessage = err.message || 'Unable to load security approvals.';
		} finally {
			isLoading = false;
		}
	}

	async function fetchIncidentImage(approvalId) {
		if (incidentImageUrls[approvalId] || imageLoadingStates[approvalId]) return;
		imageLoadingStates[approvalId] = true;
		try {
			const blob = await apiFetchBlob(`/api/admin/security-approvals/${approvalId}/image`);
			const objectUrl = URL.createObjectURL(blob);
			incidentImageUrls[approvalId] = objectUrl;
		} catch (err) {
			console.warn(`Could not load incident image for ${approvalId}:`, err);
		} finally {
			imageLoadingStates[approvalId] = false;
		}
	}

	function openZoomModal(item) {
		zoomedImage = {
			item,
			url: incidentImageUrls[item.id] || null
		};
	}

	function closeZoomModal() {
		zoomedImage = null;
	}

	function openDecisionDialog(approval, decision) {
		activeDialog = { approval, decision };
		adminNotes = '';
		errorMessage = '';
		successMessage = '';
	}

	function closeDialog() {
		activeDialog = null;
		adminNotes = '';
	}

	async function submitDecision() {
		if (!activeDialog) return;

		isActionLoading = true;
		errorMessage = '';
		successMessage = '';

		const approvalId = activeDialog.approval.id;
		const decision = activeDialog.decision;

		try {
			const res = await apiRequest(`/api/admin/security-approvals/${approvalId}/decision`, {
				method: 'POST',
				body: JSON.stringify({
					decision: decision,
					notes: adminNotes.trim() || undefined
				})
			});

			successMessage = res.message;
			closeDialog();
			await loadSecurityApprovals();
		} catch (err) {
			console.error('Decision submission error:', err);
			errorMessage = err.message || 'Failed to submit approval decision.';
		} finally {
			isActionLoading = false;
		}
	}
</script>

<svelte:head>
	<title>Security Approvals | Face ATM Admin</title>
</svelte:head>

<div class="approvals-page-wrapper">
	<!-- Page Header -->
	<div class="page-title-row">
		<div>
			<h1 class="page-title">Biometric Security Approvals</h1>
			<p class="page-subtitle">
				Review failed face verification lockout events and securely inspect captured attempt frames.
			</p>
		</div>
		<button class="refresh-btn" onclick={loadSecurityApprovals} disabled={isLoading}>
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class={isLoading ? 'spin' : ''}>
				<polyline points="23 4 23 10 17 10"></polyline>
				<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
			</svg>
			<span>Refresh</span>
		</button>
	</div>

	<!-- Info Notice -->
	<div class="info-notice">
		<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
		</svg>
		<span>
			<strong>Security Protocol:</strong> An administrative <strong>Accept</strong> action resets the failed attempt lockout on the card so the customer can retry face verification at the ATM terminal. It does <em>not</em> bypass anti-spoofing or SFace biometric verification on subsequent login attempts.
		</span>
	</div>

	{#if successMessage}
		<div class="alert-success" role="alert">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<polyline points="20 6 9 17 4 12"></polyline>
			</svg>
			<span>{successMessage}</span>
		</div>
	{/if}

	{#if errorMessage}
		<div class="alert-error" role="alert">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="12" cy="12" r="10"></circle>
				<line x1="12" y1="8" x2="12" y2="12"></line>
				<line x1="12" y1="16" x2="12.01" y2="16"></line>
			</svg>
			<span>{errorMessage}</span>
		</div>
	{/if}

	<!-- Approvals Content -->
	{#if isLoading && approvals.length === 0}
		<div class="loading-state">
			<div class="spinner"></div>
			<p>Loading security approval records...</p>
		</div>
	{:else if approvals.length === 0}
		<div class="empty-state">
			<div class="empty-icon">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
					<polyline points="9 12 11 14 15 10"></polyline>
				</svg>
			</div>
			<h3>All Clear &bull; No Active Lockouts</h3>
			<p>There are currently no biometric lockout review requests pending administrator action.</p>
		</div>
	{:else}
		<div class="approvals-list">
			{#each approvals as item (item.id)}
				<div class="approval-card status-{item.status.toLowerCase()}">
					<div class="card-top">
						<div class="user-meta">
							<div class="user-avatar">{item.customerName?.charAt(0) || 'C'}</div>
							<div>
								<div class="customer-name">{item.customerName}</div>
								<div class="customer-email">{item.customerEmail}</div>
							</div>
						</div>
						<div class="status-badge {item.status.toLowerCase()}">
							{item.status}
						</div>
					</div>

					<!-- Comprehensive Incident & Lockout Details Grid -->
					<div class="card-details-grid">
						<div class="detail-item">
							<span class="detail-label">Masked Card</span>
							<span class="detail-val mono">{item.cardNumberMasked}</span>
						</div>
						<div class="detail-item">
							<span class="detail-label">Failed Attempts</span>
							<span class="detail-val badge-attempts">{item.failedAttempts} / 3</span>
						</div>
						<div class="detail-item">
							<span class="detail-label">Lockout Status</span>
							<span class="detail-val {item.isLocked ? 'text-locked' : 'text-unlocked'}">
								{#if item.isLocked}
									Locked ({Math.max(1, Math.ceil((item.lockoutRemainingSeconds || 0) / 60))}m left)
								{:else if item.status === 'ACCEPTED'}
									Lockout Lifted
								{:else if item.status === 'DENIED'}
									Lockout Preserved
								{:else}
									Lockout Expired
								{/if}
							</span>
						</div>
						<div class="detail-item">
							<span class="detail-label">Incident Timestamp</span>
							<span class="detail-val">
								{new Date(item.createdAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZoneName: 'short' })}
							</span>
						</div>
						<div class="detail-item full-width-sm">
							<span class="detail-label">Lockout Expiry</span>
							<span class="detail-val">
								{item.expiresAt ? new Date(item.expiresAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZoneName: 'short' }) : 'Expired'}
							</span>
						</div>
						<div class="detail-item full-width-sm">
							<span class="detail-label">Incident Reason</span>
							<span class="detail-val reason-text">{item.reason}</span>
						</div>
					</div>

					<!-- Incident Image Inspection Strip -->
					<div class="incident-media-section">
						<div class="media-header">
							<div class="media-title-group">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="camera-icon">
									<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
									<circle cx="12" cy="13" r="4"></circle>
								</svg>
								<span class="media-label">Failed Attempt Camera Capture</span>
							</div>
							{#if item.hasCapturedImage}
								<span class="secure-storage-badge">
									<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
										<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
										<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
									</svg>
									Secure Storage (Admin Only)
								</span>
							{/if}
						</div>

						<div class="media-content">
							{#if item.hasCapturedImage}
								<div class="image-preview-box">
									{#if incidentImageUrls[item.id]}
										<button class="image-thumbnail-btn" onclick={() => openZoomModal(item)} title="Click to view full-size captured attempt frame">
											<img src={incidentImageUrls[item.id]} alt="Captured failed attempt" class="incident-thumbnail" />
											<div class="zoom-overlay">
												<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
													<circle cx="11" cy="11" r="8"></circle>
													<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
													<line x1="11" y1="8" x2="11" y2="14"></line>
													<line x1="8" y1="11" x2="14" y2="11"></line>
												</svg>
												<span>Inspect Capture</span>
											</div>
										</button>
									{:else if imageLoadingStates[item.id]}
										<div class="media-loading">
											<div class="spinner-sm"></div>
											<span>Decrypting & loading frame...</span>
										</div>
									{:else}
										<button class="load-media-btn" onclick={() => fetchIncidentImage(item.id)}>
											<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
												<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
												<circle cx="12" cy="12" r="3"></circle>
											</svg>
											<span>Load Authenticated Frame</span>
										</button>
									{/if}
								</div>
							{:else}
								<div class="media-unavailable">
									<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
										<line x1="1" y1="1" x2="23" y2="23"></line>
										<path d="M21 21H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3m3-3h6l2 3h4a2 2 0 0 1 2 2v9.34"></path>
										<circle cx="12" cy="13" r="4"></circle>
									</svg>
									<span>No captured image recorded for this incident.</span>
								</div>
							{/if}
						</div>
					</div>

					<!-- Actions / Review Status -->
					{#if item.status === 'PENDING'}
						<div class="card-actions">
							<button class="action-btn deny" onclick={() => openDecisionDialog(item, 'DENY')}>
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<line x1="18" y1="6" x2="6" y2="18"></line>
									<line x1="6" y1="6" x2="18" y2="18"></line>
								</svg>
								<span>Deny (Maintain Lock)</span>
							</button>

							<button class="action-btn accept" onclick={() => openDecisionDialog(item, 'ACCEPT')}>
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<polyline points="20 6 9 17 4 12"></polyline>
								</svg>
								<span>Accept & Unlock Customer</span>
							</button>
						</div>
					{:else}
						<div class="review-meta">
							<span class="reviewed-by">
								Reviewed by: <strong>{item.reviewedBy || 'System'}</strong> on{' '}
								{item.reviewedAt ? new Date(item.reviewedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZoneName: 'short' }) : 'Expiry'}
							</span>
							{#if item.notes}
								<span class="review-notes">Notes: "{item.notes}"</span>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	<!-- ACTION CONFIRMATION MODAL -->
	{#if activeDialog}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="modal-backdrop" onclick={closeDialog}>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="modal-header">
					<h2>Confirm {activeDialog.decision === 'ACCEPT' ? 'Unlock Approval' : 'Rejection'}</h2>
					<button class="close-modal-btn" onclick={closeDialog}>&times;</button>
				</div>

				<div class="modal-body">
					<p class="modal-desc">
						{#if activeDialog.decision === 'ACCEPT'}
							You are approving an unlock request for <strong>{activeDialog.approval.customerName}</strong> ({activeDialog.approval.cardNumberMasked}).
							The customer's lockout will be lifted so they can retry biometric verification at the ATM terminal.
						{:else}
							You are denying the unlock request for <strong>{activeDialog.approval.customerName}</strong>.
							The account will remain locked according to policy for safety.
						{/if}
					</p>

					<div class="form-group">
						<label for="adminNotes">Review Notes (Optional)</label>
						<textarea
							id="adminNotes"
							rows="3"
							placeholder="e.g. Identity verified via branch telephone call."
							bind:value={adminNotes}
							maxlength="250"
						></textarea>
					</div>
				</div>

				<div class="modal-actions">
					<button class="btn-cancel" onclick={closeDialog} disabled={isActionLoading}>
						Cancel
					</button>

					<button
						class="btn-confirm {activeDialog.decision === 'ACCEPT' ? 'accept' : 'deny'}"
						onclick={submitDecision}
						disabled={isActionLoading}
					>
						{#if isActionLoading}
							<div class="spinner-sm"></div>
							<span>Recording Decision...</span>
						{:else}
							<span>Confirm {activeDialog.decision === 'ACCEPT' ? 'Acceptance' : 'Denial'}</span>
						{/if}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- IMAGE ZOOM INSPECTION MODAL -->
	{#if zoomedImage}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="modal-backdrop" onclick={closeZoomModal}>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div class="modal-dialog zoom-dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="modal-header">
					<div>
						<h2>Captured Attempt Biometric Frame</h2>
						<p class="zoom-subtitle">
							{zoomedImage.item.customerName} &bull; Card {zoomedImage.item.cardNumberMasked}
						</p>
					</div>
					<button class="close-modal-btn" onclick={closeZoomModal}>&times;</button>
				</div>

				<div class="zoom-body">
					{#if zoomedImage.url}
						<div class="zoom-image-wrapper">
							<img src={zoomedImage.url} alt="Full resolution biometric attempt frame" class="full-incident-image" />
						</div>
					{:else}
						<div class="media-unavailable">No image available to display.</div>
					{/if}

					<div class="zoom-meta-grid">
						<div class="zoom-meta-row">
							<span>Incident ID:</span>
							<span class="mono">{zoomedImage.item.id}</span>
						</div>
						<div class="zoom-meta-row">
							<span>Captured At:</span>
							<span>{new Date(zoomedImage.item.createdAt).toLocaleString('en-IN', { dateStyle: 'full', timeStyle: 'medium', timeZoneName: 'short' })}</span>
						</div>
						<div class="zoom-meta-row">
							<span>Lockout Expiry:</span>
							<span>{zoomedImage.item.expiresAt ? new Date(zoomedImage.item.expiresAt).toLocaleString('en-IN', { dateStyle: 'full', timeStyle: 'medium', timeZoneName: 'short' }) : 'Expired'}</span>
						</div>
					</div>
				</div>

				<div class="modal-actions">
					<button class="btn-cancel" onclick={closeZoomModal}>
						Close Inspector
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.approvals-page-wrapper {
		max-width: 1100px;
		margin: 0 auto;
	}

	.page-title-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1.5rem;
	}

	.page-title {
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--color-forest, #173f35);
		margin: 0 0 0.35rem;
	}

	.page-subtitle {
		font-size: 0.95rem;
		color: #6b7280;
		margin: 0;
	}

	.refresh-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background: #ffffff;
		border: 1px solid #d1d5db;
		color: #374151;
		padding: 0.55rem 1rem;
		border-radius: 8px;
		font-size: 0.88rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.2s;
	}

	.refresh-btn:hover:not(:disabled) {
		background: #f9fafb;
	}

	.refresh-btn svg {
		width: 16px;
		height: 16px;
	}

	.spin {
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.info-notice {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: #eef2ff;
		color: #312e81;
		border-left: 4px solid #4f46e5;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.5rem;
		font-size: 0.88rem;
		line-height: 1.4;
	}

	.info-notice svg {
		width: 22px;
		height: 22px;
		flex-shrink: 0;
		color: #4f46e5;
	}

	.alert-success {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		background: #d1fae5;
		color: #065f46;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.25rem;
		border-left: 4px solid #10b981;
	}

	.alert-error {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		background: #fee2e2;
		color: #991b1b;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.25rem;
		border-left: 4px solid #dc2626;
	}

	.loading-state,
	.empty-state {
		background: #ffffff;
		border-radius: 12px;
		border: 1px solid #e5e7eb;
		padding: 3.5rem 1.5rem;
		text-align: center;
	}

	.spinner {
		width: 40px;
		height: 40px;
		border: 4px solid rgba(23, 63, 53, 0.1);
		border-top-color: #173f35;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin: 0 auto 1rem;
	}

	.empty-icon {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		background: #ecfdf5;
		color: #059669;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 1rem;
	}

	.empty-icon svg {
		width: 28px;
		height: 28px;
	}

	.empty-state h3 {
		font-size: 1.2rem;
		color: #111827;
		margin: 0 0 0.4rem;
	}

	.empty-state p {
		color: #6b7280;
		font-size: 0.9rem;
		margin: 0;
	}

	/* Approvals List */
	.approvals-list {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.approval-card {
		background: #ffffff;
		border: 1px solid #e5e7eb;
		border-radius: 12px;
		padding: 1.5rem;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
		transition: border-color 0.2s;
	}

	.approval-card.status-pending {
		border-left: 5px solid #f59e0b;
	}

	.approval-card.status-accepted {
		border-left: 5px solid #10b981;
		opacity: 0.92;
	}

	.approval-card.status-denied {
		border-left: 5px solid #ef4444;
		opacity: 0.92;
	}

	.card-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.25rem;
	}

	.user-meta {
		display: flex;
		align-items: center;
		gap: 0.85rem;
	}

	.user-avatar {
		width: 42px;
		height: 42px;
		border-radius: 50%;
		background: #173f35;
		color: #ffffff;
		font-weight: 700;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.1rem;
	}

	.customer-name {
		font-weight: 700;
		font-size: 1.05rem;
		color: #111827;
	}

	.customer-email {
		font-size: 0.82rem;
		color: #6b7280;
	}

	.status-badge {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		padding: 4px 10px;
		border-radius: 999px;
	}

	.status-badge.pending {
		background: #fef3c7;
		color: #92400e;
	}

	.status-badge.accepted {
		background: #d1fae5;
		color: #065f46;
	}

	.status-badge.denied {
		background: #fee2e2;
		color: #991b1b;
	}

	.status-badge.expired {
		background: #f3f4f6;
		color: #6b7280;
	}

	.card-details-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.9rem;
		background: #f9fafb;
		padding: 1rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.25rem;
	}

	@media (max-width: 768px) {
		.card-details-grid {
			grid-template-columns: 1fr;
		}
	}

	.detail-item {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.detail-label {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: #6b7280;
		font-weight: 600;
	}

	.detail-val {
		font-size: 0.88rem;
		font-weight: 600;
		color: #111827;
	}

	.detail-val.mono {
		font-family: monospace;
	}

	.badge-attempts {
		color: #dc2626;
	}

	.text-locked {
		color: #b91c1c;
		font-weight: 700;
	}

	.text-unlocked {
		color: #047857;
		font-weight: 700;
	}

	.reason-text {
		color: #374151;
		font-weight: 500;
	}

	/* Incident Media Strip */
	.incident-media-section {
		border: 1px solid #e5e7eb;
		border-radius: 8px;
		background: #ffffff;
		padding: 0.9rem 1.1rem;
		margin-bottom: 1.25rem;
	}

	.media-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.media-title-group {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.camera-icon {
		width: 17px;
		height: 17px;
		color: #4b5563;
	}

	.media-label {
		font-size: 0.82rem;
		font-weight: 700;
		color: #374151;
		text-transform: uppercase;
		letter-spacing: 0.4px;
	}

	.secure-storage-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		background: #f0fdf4;
		border: 1px solid #bbf7d0;
		color: #166534;
		font-size: 0.72rem;
		font-weight: 600;
		padding: 2px 8px;
		border-radius: 6px;
	}

	.secure-storage-badge svg {
		width: 12px;
		height: 12px;
	}

	.media-content {
		display: flex;
		align-items: center;
	}

	.image-preview-box {
		display: inline-flex;
		align-items: center;
	}

	.image-thumbnail-btn {
		position: relative;
		border: 2px solid #e5e7eb;
		border-radius: 8px;
		overflow: hidden;
		background: #111827;
		padding: 0;
		cursor: pointer;
		line-height: 0;
		transition: transform 0.15s, border-color 0.15s;
	}

	.image-thumbnail-btn:hover {
		transform: scale(1.02);
		border-color: #173f35;
	}

	.incident-thumbnail {
		width: 120px;
		height: 90px;
		object-fit: cover;
		display: block;
	}

	.zoom-overlay {
		position: absolute;
		inset: 0;
		background: rgba(17, 24, 39, 0.6);
		color: #ffffff;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.25rem;
		opacity: 0;
		transition: opacity 0.2s;
		font-size: 0.72rem;
		font-weight: 600;
	}

	.zoom-overlay svg {
		width: 18px;
		height: 18px;
	}

	.image-thumbnail-btn:hover .zoom-overlay {
		opacity: 1;
	}

	.media-loading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.82rem;
		color: #6b7280;
	}

	.load-media-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		background: #f3f4f6;
		border: 1px solid #d1d5db;
		color: #374151;
		font-size: 0.82rem;
		font-weight: 600;
		padding: 0.45rem 0.85rem;
		border-radius: 6px;
		cursor: pointer;
	}

	.load-media-btn svg {
		width: 15px;
		height: 15px;
	}

	.media-unavailable {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: #9ca3af;
		font-size: 0.82rem;
		font-style: italic;
	}

	.media-unavailable svg {
		width: 18px;
		height: 18px;
		color: #9ca3af;
	}

	.card-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.action-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.6rem 1.1rem;
		border-radius: 8px;
		font-size: 0.88rem;
		font-weight: 600;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.action-btn svg {
		width: 16px;
		height: 16px;
	}

	.action-btn.accept {
		background: #10b981;
		color: #ffffff;
	}

	.action-btn.accept:hover {
		background: #059669;
	}

	.action-btn.deny {
		background: #fee2e2;
		color: #dc2626;
		border: 1px solid #fecaca;
	}

	.action-btn.deny:hover {
		background: #fecaca;
	}

	.review-meta {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.82rem;
		color: #6b7280;
	}

	.review-notes {
		font-style: italic;
		color: #4b5563;
	}

	/* Modals */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem;
		z-index: 200;
	}

	.modal-dialog {
		background: #ffffff;
		border-radius: 14px;
		max-width: 480px;
		width: 100%;
		padding: 1.75rem;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
	}

	.zoom-dialog {
		max-width: 580px;
	}

	.zoom-subtitle {
		font-size: 0.82rem;
		color: #6b7280;
		margin: 0.2rem 0 0;
	}

	.zoom-body {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin: 1rem 0;
	}

	.zoom-image-wrapper {
		background: #0f172a;
		border-radius: 10px;
		overflow: hidden;
		display: flex;
		justify-content: center;
		align-items: center;
		padding: 0.5rem;
		border: 1px solid #334155;
	}

	.full-incident-image {
		max-width: 100%;
		max-height: 380px;
		object-fit: contain;
		border-radius: 6px;
	}

	.zoom-meta-grid {
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 8px;
		padding: 0.75rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: 0.82rem;
	}

	.zoom-meta-row {
		display: flex;
		justify-content: space-between;
		color: #475569;
	}

	.zoom-meta-row span:last-child {
		font-weight: 600;
		color: #0f172a;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1rem;
	}

	.modal-header h2 {
		font-size: 1.25rem;
		margin: 0;
		color: #111827;
	}

	.close-modal-btn {
		background: none;
		border: none;
		font-size: 1.4rem;
		color: #9ca3af;
		cursor: pointer;
	}

	.modal-desc {
		font-size: 0.9rem;
		color: #4b5563;
		line-height: 1.5;
		margin: 0 0 1.25rem;
	}

	.form-group label {
		font-size: 0.85rem;
		font-weight: 600;
		color: #374151;
		display: block;
		margin-bottom: 0.4rem;
	}

	.form-group textarea {
		width: 100%;
		padding: 0.65rem 0.85rem;
		border: 1px solid #d1d5db;
		border-radius: 8px;
		font-size: 0.9rem;
		resize: vertical;
	}

	.form-group textarea:focus {
		outline: none;
		border-color: #173f35;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}

	.btn-cancel {
		background: #f3f4f6;
		color: #374151;
		border: 1px solid #d1d5db;
		padding: 0.65rem 1.15rem;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
	}

	.btn-confirm {
		color: #ffffff;
		border: none;
		padding: 0.65rem 1.25rem;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}

	.btn-confirm.accept {
		background: #10b981;
	}

	.btn-confirm.deny {
		background: #dc2626;
	}

	.spinner-sm {
		width: 14px;
		height: 14px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: #173f35;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
</style>
