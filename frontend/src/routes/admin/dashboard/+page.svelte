<script>
	import { onMount } from 'svelte';
	import { adminUser } from '#lib/auth.js';
	import { getAdminToken } from '#lib/firebase.js';
	import { apiRequest } from '#lib/api.js';

	let summaryCounts = $state({
		customers: 0,
		verifications: 0,
		transactions: 0,
		loaded: false
	});

	let recentCustomers = $state([]);
	let loadingCustomers = $state(true);

	let backendStatus = $state({
		loading: true,
		checked: false,
		online: false,
		details: null,
		error: null
	});

	const backendApiUrl = import.meta.env.VITE_BACKEND_API_URL || 'http://127.0.0.1:8000';

	async function checkBackendHealth() {
		backendStatus.loading = true;
		backendStatus.error = null;

		const candidateUrls = [backendApiUrl];
		if (backendApiUrl.includes('localhost')) {
			candidateUrls.push(backendApiUrl.replace('localhost', '127.0.0.1'));
		} else if (backendApiUrl.includes('127.0.0.1')) {
			candidateUrls.push(backendApiUrl.replace('127.0.0.1', 'localhost'));
		}

		let connected = false;
		let lastError = null;

		for (const baseUrl of candidateUrls) {
			try {
				const res = await fetch(`${baseUrl}/api/health`, {
					method: 'GET',
					headers: { Accept: 'application/json' },
					cache: 'no-store'
				});
				if (res.ok) {
					const data = await res.json();
					if (data && (data.status === 'healthy' || data.status === 'ok')) {
						backendStatus.online = true;
						backendStatus.details = data;
						backendStatus.error = null;
						connected = true;
						break;
					} else {
						lastError = `Backend returned unexpected status: ${JSON.stringify(data.status)}`;
					}
				} else {
					lastError = `Backend responded with HTTP ${res.status}`;
				}
			} catch (err) {
				lastError = `Cannot connect to FastAPI server at ${baseUrl}`;
			}
		}

		if (!connected) {
			backendStatus.online = false;
			backendStatus.details = null;
			backendStatus.error = lastError || `Cannot connect to FastAPI server at ${backendApiUrl}`;
		}

		backendStatus.loading = false;
		backendStatus.checked = true;
	}

	async function loadDashboardData() {
		try {
			const summary = await apiRequest('/api/admin/summary');
			if (summary) {
				summaryCounts.customers = summary.customers_count || 0;
				summaryCounts.verifications = summary.verifications_count || 0;
				summaryCounts.transactions = summary.transactions_count || 0;
				summaryCounts.loaded = true;
			}
		} catch (err) {
			console.warn('Could not load summary counts:', err);
		}

		try {
			loadingCustomers = true;
			const customers = await apiRequest('/api/customers?limit=10');
			if (Array.isArray(customers)) {
				recentCustomers = customers;
			}
		} catch (err) {
			console.warn('Could not load recent customers:', err);
		} finally {
			loadingCustomers = false;
		}
	}

	onMount(async () => {
		await checkBackendHealth();
		if (backendStatus.online) {
			await loadDashboardData();
		}
	});
</script>

<svelte:head>
	<title>Admin Dashboard | Face Authentication System</title>
</svelte:head>

<div class="dashboard-container">
	<!-- Welcome Heading & Header Banner -->
	<div class="welcome-header">
		<div class="welcome-text">
			<div class="role-pill">
				<span class="status-dot"></span>
				<span>ADMINISTRATOR SESSION ACTIVE</span>
			</div>
			<h1 class="welcome-title">Welcome, Administrator</h1>
			<p class="welcome-subtitle">
				Operational control portal for the Face Authentication & Customer Transaction System.
			</p>
		</div>

		<div class="header-actions">
			<a href="/admin/register" class="btn-primary cta-register-btn">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
					<circle cx="9" cy="7" r="4" />
					<line x1="19" y1="8" x2="19" y2="14" />
					<line x1="22" y1="11" x2="16" y2="11" />
				</svg>
				<span>Register Customer</span>
			</a>

			<div class="admin-badge-card">
				<div class="badge-row">
					<span class="badge-label">Active Role:</span>
					<span class="badge-value role-highlight">ADMIN</span>
				</div>
				<div class="badge-row">
					<span class="badge-label">Admin Email:</span>
					<span class="badge-value">{$adminUser?.email}</span>
				</div>
			</div>
		</div>
	</div>

	<!-- Phase 2 Active Notice Alert -->
	<div class="phase2-alert">
		<div class="alert-icon">✨</div>
		<div class="alert-text">
			<strong>Phase 2 Biometric Registration Active:</strong>
			Customer registration with AES-256 encrypted storage, Gmail SMTP email OTP verification, OpenCV YuNet face geometry detection, and SFace 128-dimensional embedding enrollment is operational.
		</div>
	</div>

	<!-- Dashboard Summary Cards -->
	<section class="metrics-grid" aria-label="System Metrics">
		<!-- Card 1: Registered Customers -->
		<div class="metric-card">
			<div class="card-top">
				<div class="card-icon customers">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
						<circle cx="9" cy="7" r="4" />
						<path d="M23 21v-2a4 4 0 0 0-3-3.87" />
						<path d="M16 3.13a4 4 0 0 1 0 7.75" />
					</svg>
				</div>
				<span class="phase-badge active">Phase 2 Active</span>
			</div>
			<div class="card-body">
				<div class="metric-value">{summaryCounts.customers}</div>
				<h3 class="metric-title">Registered Customers</h3>
				<p class="metric-caption">Enrolled with AES-encrypted PII and unique card numbers</p>
			</div>
			<div class="card-footer">
				<a href="/admin/register" class="card-action-link">+ Register New Customer &rarr;</a>
			</div>
		</div>

		<!-- Card 2: Face Verifications -->
		<div class="metric-card">
			<div class="card-top">
				<div class="card-icon verifications">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M3 7V5a2 2 0 0 1 2-2h2" />
						<path d="M17 3h2a2 2 0 0 1 2 2v2" />
						<path d="M21 17v2a2 2 0 0 1-2 2h-2" />
						<path d="M7 21H5a2 2 0 0 1-2-2v-2" />
						<circle cx="12" cy="12" r="3" />
					</svg>
				</div>
				<span class="phase-badge active">Phase 2 Active</span>
			</div>
			<div class="card-body">
				<div class="metric-value">{summaryCounts.verifications}</div>
				<h3 class="metric-title">Biometric Face Enrollments</h3>
				<p class="metric-caption">128-dimensional normalized SFace feature embeddings stored</p>
			</div>
			<div class="card-footer">
				<span class="footer-badge">SFace ONNX Pipeline Operational</span>
			</div>
		</div>

		<!-- Card 3: Completed Transactions -->
		<div class="metric-card">
			<div class="card-top">
				<div class="card-icon transactions">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="2" y="5" width="20" height="14" rx="2" />
						<line x1="2" y1="10" x2="22" y2="10" />
					</svg>
				</div>
				<span class="phase-badge pending">Phase 3 Pending</span>
			</div>
			<div class="card-body">
				<div class="metric-value">0</div>
				<h3 class="metric-title">Completed Transactions</h3>
				<p class="metric-caption">Transaction ledger & ATM withdrawal pipeline scheduled for Phase 3</p>
			</div>
			<div class="card-footer">
				<span class="footer-badge pending">Phase 3 Implementation</span>
			</div>
		</div>
	</section>

	<!-- Recent Registered Customers Table Section -->
	<section class="customers-section">
		<div class="card customer-table-card">
			<div class="section-header">
				<div>
					<h2 class="section-title">Recent Customer Registrations</h2>
					<p class="section-subtitle">Real-time enrolled customer records with data minimization</p>
				</div>
				<a href="/admin/register" class="btn-secondary btn-sm">
					+ Enroll Customer
				</a>
			</div>

			{#if loadingCustomers}
				<div class="table-loading">
					<div class="table-spinner"></div>
					<p>Loading registered customers...</p>
				</div>
			{:else if recentCustomers.length === 0}
				<div class="table-empty">
					<div class="empty-icon">👥</div>
					<h3>No Customers Registered Yet</h3>
					<p>Begin by registering your first customer through the biometric enrollment flow.</p>
					<a href="/admin/register" class="btn-primary btn-sm">
						Start Customer Registration &rarr;
					</a>
				</div>
			{:else}
				<div class="table-responsive">
					<table class="data-table">
						<thead>
							<tr>
								<th>Customer Name</th>
								<th>Email</th>
								<th>Phone</th>
								<th>Card Number</th>
								<th>Bank</th>
								<th>Status</th>
								<th>Face Enrolled</th>
							</tr>
						</thead>
						<tbody>
							{#each recentCustomers as c}
								<tr>
									<td>
										<div class="cust-name-cell">
											<div class="cust-avatar">{c.fullName?.charAt(0) || 'C'}</div>
											<span class="cust-name">{c.fullName}</span>
										</div>
									</td>
									<td class="cust-email">{c.email}</td>
									<td class="cust-phone mono">{c.phoneMasked}</td>
									<td class="cust-card mono">{c.cardNumberMasked}</td>
									<td>{c.bankName}</td>
									<td>
										<span class="badge badge-active">{c.status}</span>
									</td>
									<td>
										{#if c.faceEnrolled}
											<span class="badge badge-biometric">✓ Enrolled (128-dim)</span>
										{:else}
											<span class="badge badge-pending">Pending</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</section>

	<!-- System Architecture & Phase Roadmap Overview -->
	<section class="system-section">
		<div class="card system-overview-card">
			<div class="section-header">
				<h2 class="section-title">System Infrastructure Status</h2>
				<span class="badge badge-active">Phase 2 Operational</span>
			</div>

			<div class="component-grid">
				<div class="component-box">
					<div class="comp-header">
						<span class="comp-title">Firebase Authentication</span>
						<span class="badge badge-active">Operational</span>
					</div>
					<p class="comp-desc">
						Strict single-admin role authentication with persistent browser session handling.
					</p>
				</div>

				<div class="component-box">
					<div class="comp-header">
						<span class="comp-title">Cloud Firestore & AES Encryption</span>
						<span class="badge badge-active">Secured</span>
					</div>
					<p class="comp-desc">
						Privileged server-side Firestore client. Aadhaar and Bank Accounts protected via AES-256-GCM.
					</p>
				</div>

				<div class="component-box">
					<div class="comp-header">
						<span class="comp-title">FastAPI Backend</span>
						{#if backendStatus.loading}
							<span class="badge badge-coming-soon">Checking...</span>
						{:else if backendStatus.online}
							<span class="badge badge-active">Online</span>
						{:else}
							<button type="button" class="badge badge-terracotta badge-retry" onclick={checkBackendHealth} title="Click to re-check backend connection">Offline &bull; Re-check</button>
						{/if}
					</div>
					<p class="comp-desc">
						Protected administrative API endpoints with Bearer token authentication and CORS enabled.
					</p>
					{#if backendStatus.error}
						<div class="backend-warn">{backendStatus.error}</div>
					{/if}
				</div>

				<div class="component-box">
					<div class="comp-header">
						<span class="comp-title">Biometric Face Engine</span>
						<span class="badge badge-active">YuNet + SFace</span>
					</div>
					<p class="comp-desc">
						OpenCV YuNet facial detector and SFace 128-dimensional embedding model loaded and active.
					</p>
				</div>

				<div class="component-box">
					<div class="comp-header">
						<span class="comp-title">Gmail SMTP Email Service</span>
						<span class="badge badge-active">Active</span>
					</div>
					<p class="comp-desc">
						Cryptographic 6-digit OTP delivery and automated card number dispatch upon face enrollment.
					</p>
				</div>

				<div class="component-box">
					<div class="comp-header">
						<span class="comp-title">Phase 3 ATM Engine</span>
						<span class="badge badge-coming-soon">Next Phase</span>
					</div>
					<p class="comp-desc">
						Face login terminal, customer balance checks, and ATM withdrawal transactions scheduled.
					</p>
				</div>
			</div>
		</div>
	</section>
</div>

<style>
	.dashboard-container {
		display: flex;
		flex-direction: column;
		gap: 2rem;
		max-width: 1200px;
		margin: 0 auto;
	}

	.welcome-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 2rem;
		flex-wrap: wrap;
	}

	.role-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background-color: rgba(23, 63, 53, 0.08);
		color: var(--color-forest);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		padding: 0.35rem 0.85rem;
		border-radius: var(--radius-full);
		margin-bottom: 0.75rem;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background-color: #10b981;
	}

	.welcome-title {
		font-size: 2.1rem;
		color: var(--color-forest);
		margin-bottom: 0.4rem;
	}

	.welcome-subtitle {
		font-size: 1rem;
		color: var(--color-gray);
		max-width: 580px;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.cta-register-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.95rem;
		padding: 0.9rem 1.6rem;
		box-shadow: 0 4px 14px rgba(217, 119, 69, 0.35);
	}

	.cta-register-btn svg {
		width: 20px;
		height: 20px;
	}

	.admin-badge-card {
		background-color: var(--color-white);
		border: 1px solid var(--color-gray-border);
		padding: 0.85rem 1.25rem;
		border-radius: var(--radius-md);
		box-shadow: var(--shadow-sm);
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		min-width: 220px;
	}

	.badge-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.82rem;
	}

	.badge-label {
		color: var(--color-gray);
	}

	.badge-value {
		font-weight: 600;
		color: var(--color-forest);
	}

	.role-highlight {
		background-color: var(--color-forest);
		color: var(--color-cream);
		padding: 1px 6px;
		border-radius: 4px;
		font-size: 0.72rem;
		letter-spacing: 0.05em;
	}

	/* Phase 2 Alert */
	.phase2-alert {
		display: flex;
		align-items: center;
		gap: 1rem;
		background: rgba(35, 92, 78, 0.08);
		border: 1px solid rgba(35, 92, 78, 0.25);
		border-radius: var(--radius-md);
		padding: 1rem 1.4rem;
		color: var(--color-forest);
	}

	.alert-icon {
		font-size: 1.4rem;
		flex-shrink: 0;
	}

	.alert-text {
		font-size: 0.9rem;
		line-height: 1.5;
	}

	/* Metrics Grid */
	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
		gap: 1.5rem;
	}

	.metric-card {
		background-color: var(--color-white);
		border: 1px solid var(--color-gray-border);
		border-radius: var(--radius-lg);
		padding: 1.75rem;
		box-shadow: var(--shadow-md);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		transition: transform var(--transition-normal), box-shadow var(--transition-normal);
	}

	.metric-card:hover {
		transform: translateY(-2px);
		box-shadow: var(--shadow-hover);
	}

	.card-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1.25rem;
	}

	.card-icon {
		width: 48px;
		height: 48px;
		border-radius: var(--radius-md);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.card-icon svg {
		width: 24px;
		height: 24px;
	}

	.card-icon.customers {
		background-color: rgba(35, 92, 78, 0.12);
		color: var(--color-forest);
	}

	.card-icon.verifications {
		background-color: rgba(217, 119, 69, 0.12);
		color: var(--color-terracotta);
	}

	.card-icon.transactions {
		background-color: rgba(102, 115, 111, 0.12);
		color: var(--color-gray);
	}

	.phase-badge {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 0.25rem 0.65rem;
		border-radius: var(--radius-full);
	}

	.phase-badge.active {
		background-color: rgba(35, 92, 78, 0.15);
		color: var(--color-forest);
	}

	.phase-badge.pending {
		background-color: rgba(102, 115, 111, 0.15);
		color: var(--color-gray);
	}

	.metric-value {
		font-size: 2.75rem;
		font-weight: 800;
		color: var(--color-forest);
		line-height: 1;
		margin-bottom: 0.5rem;
	}

	.metric-title {
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--color-forest);
		margin-bottom: 0.35rem;
	}

	.metric-caption {
		font-size: 0.88rem;
		color: var(--color-gray);
		line-height: 1.4;
	}

	.card-footer {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(102, 115, 111, 0.1);
	}

	.card-action-link {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--color-terracotta);
		transition: color var(--transition-fast);
	}

	.card-action-link:hover {
		color: var(--color-terracotta-hover);
		text-decoration: underline;
	}

	.footer-badge {
		font-size: 0.8rem;
		color: var(--color-forest);
		font-weight: 600;
	}

	.footer-badge.pending {
		color: var(--color-gray);
	}

	/* Customers Table Section */
	.customer-table-card {
		background: var(--color-white);
		border: 1px solid var(--color-gray-border);
		border-radius: var(--radius-lg);
		padding: 1.75rem;
		box-shadow: var(--shadow-md);
	}

	.section-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		margin-bottom: 1.5rem;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.section-title {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-forest);
	}

	.section-subtitle {
		font-size: 0.85rem;
		color: var(--color-gray);
		margin-top: 0.2rem;
	}

	.btn-sm {
		padding: 0.45rem 1rem;
		font-size: 0.85rem;
	}

	.table-loading,
	.table-empty {
		text-align: center;
		padding: 3rem 1.5rem;
		color: var(--color-gray);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
	}

	.empty-icon {
		font-size: 2.5rem;
	}

	.table-spinner {
		width: 32px;
		height: 32px;
		border: 3px solid rgba(23, 63, 53, 0.15);
		border-top-color: var(--color-terracotta);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.table-responsive {
		overflow-x: auto;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		text-align: left;
		font-size: 0.88rem;
	}

	.data-table th {
		padding: 0.75rem 1rem;
		background: var(--color-cream-light);
		color: var(--color-gray);
		font-weight: 700;
		text-transform: uppercase;
		font-size: 0.75rem;
		letter-spacing: 0.05em;
		border-bottom: 1.5px solid var(--color-gray-border);
	}

	.data-table td {
		padding: 0.9rem 1rem;
		border-bottom: 1px solid var(--color-gray-border);
		color: var(--color-forest);
	}

	.cust-name-cell {
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}

	.cust-avatar {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		background: rgba(23, 63, 53, 0.1);
		color: var(--color-forest);
		font-weight: 700;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.82rem;
	}

	.cust-name {
		font-weight: 600;
	}

	.cust-email {
		color: var(--color-gray);
	}

	.mono {
		font-family: monospace;
	}

	.badge-biometric {
		background-color: rgba(35, 92, 78, 0.15);
		color: var(--color-forest);
		font-weight: 700;
	}

	/* Component Grid */
	.system-overview-card {
		background: var(--color-white);
		border: 1px solid var(--color-gray-border);
		border-radius: var(--radius-lg);
		padding: 1.75rem;
		box-shadow: var(--shadow-md);
	}

	.component-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 1.25rem;
	}

	.component-box {
		background: var(--color-cream-light);
		border: 1px solid var(--color-gray-border);
		border-radius: var(--radius-md);
		padding: 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.comp-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.comp-title {
		font-weight: 700;
		font-size: 0.95rem;
		color: var(--color-forest);
	}

	.comp-desc {
		font-size: 0.82rem;
		color: var(--color-gray);
		line-height: 1.45;
	}

	.backend-warn {
		font-size: 0.75rem;
		color: #e53e3e;
		background: #fff5f5;
		padding: 4px 8px;
		border-radius: 4px;
	}

	.badge-retry {
		cursor: pointer;
	}

	@media (max-width: 768px) {
		.welcome-header {
			flex-direction: column;
		}

		.header-actions {
			width: 100%;
			flex-direction: column;
			align-items: stretch;
		}

		.metrics-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
