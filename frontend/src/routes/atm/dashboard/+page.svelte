<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { customerApiRequest, getCustomerSession, clearCustomerSession } from '#lib/api.js';

	let customer = $state(null);
	let balance = $state(0.0);
	let transactions = $state([]);
	let isLoading = $state(true);
	let isActionLoading = $state(false);
	let errorMessage = $state('');
	let successMessage = $state('');

	// Modals: null | 'WITHDRAW' | 'DEPOSIT' | 'BALANCE_RECEIPT'
	let activeModal = $state(null);
	let transactionAmount = $state('');
	let lastTransaction = $state(null);

	const quickAmounts = [500, 1000, 2000, 5000];

	onMount(() => {
		const session = getCustomerSession();
		if (!session) {
			goto('/atm', { replaceState: true });
			return;
		}
		customer = session;
		loadDashboard();
	});

	async function loadDashboard() {
		isLoading = true;
		errorMessage = '';
		try {
			const data = await customerApiRequest('/api/atm/dashboard');
			balance = data.balance;
			transactions = data.recentTransactions || [];
			customer = {
				...customer,
				fullName: data.fullName,
				cardNumberMasked: data.cardNumberMasked,
				bankName: data.bankName
			};
		} catch (err) {
			console.error('Failed to load dashboard:', err);
			errorMessage = err.message || 'Session expired. Please sign in again.';
			if (err.status === 401) {
				setTimeout(() => goto('/atm', { replaceState: true }), 1500);
			}
		} finally {
			isLoading = false;
		}
	}

	async function handleBalanceInquiry() {
		isActionLoading = true;
		errorMessage = '';
		successMessage = '';
		try {
			const res = await customerApiRequest('/api/atm/balance');
			balance = res.balance;
			lastTransaction = {
				type: 'BALANCE_INQUIRY',
				balance: res.balance,
				asOf: res.asOf
			};
			activeModal = 'BALANCE_RECEIPT';
		} catch (err) {
			errorMessage = err.message || 'Balance inquiry failed.';
		} finally {
			isActionLoading = false;
		}
	}

	function openTransactionModal(type) {
		errorMessage = '';
		successMessage = '';
		transactionAmount = '';
		activeModal = type;
	}

	function closeModal() {
		activeModal = null;
		transactionAmount = '';
	}

	function selectQuickAmount(amt) {
		transactionAmount = amt.toString();
	}

	async function submitTransaction() {
		errorMessage = '';
		successMessage = '';

		const numAmount = parseFloat(transactionAmount);
		if (isNaN(numAmount) || numAmount <= 0) {
			errorMessage = 'Please enter a valid amount greater than zero.';
			return;
		}

		if (numAmount > 20000) {
			errorMessage = 'Maximum ATM transaction limit is ₹20,000.';
			return;
		}

		if (numAmount % 100 !== 0) {
			errorMessage = 'Transaction amount must be in multiples of ₹100 notes (100, 200, 500, etc.).';
			return;
		}

		isActionLoading = true;
		const endpoint = activeModal === 'WITHDRAW' ? '/api/atm/withdraw' : '/api/atm/deposit';

		try {
			const res = await customerApiRequest(endpoint, {
				method: 'POST',
				body: JSON.stringify({ amount: numAmount })
			});

			balance = res.newBalance;
			successMessage = res.message;
			lastTransaction = res;

			// Refresh dashboard to pull fresh statement
			await loadDashboard();
			closeModal();
		} catch (err) {
			console.error('Transaction execution failed:', err);
			errorMessage = err.message || 'Transaction could not be completed.';
		} finally {
			isActionLoading = false;
		}
	}

	async function handleLogout() {
		try {
			await customerApiRequest('/api/atm/logout', { method: 'POST' });
		} catch {
			// Ignore network errors on logout
		} finally {
			clearCustomerSession();
			goto('/atm', { replaceState: true });
		}
	}
</script>

<svelte:head>
	<title>Customer Dashboard | Face ATM Terminal</title>
</svelte:head>

<div class="dashboard-wrapper">
	<!-- Top Navigation -->
	<header class="terminal-header">
		<div class="terminal-brand">
			<div class="brand-chip">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<rect x="2" y="5" width="20" height="14" rx="3"></rect>
					<line x1="2" y1="10" x2="22" y2="10"></line>
				</svg>
			</div>
			<div class="brand-info">
				<span class="brand-name">Face ATM</span>
				<span class="brand-status">Biometrically Authenticated &bull; Active Terminal</span>
			</div>
		</div>

		<div class="header-right">
			<div class="user-pill">
				<div class="auth-dot"></div>
				<span class="user-name">{customer?.fullName || 'Customer'}</span>
				<span class="card-num">{customer?.cardNumberMasked || ''}</span>
			</div>
			<button class="logout-btn" onclick={handleLogout} title="End Session">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
					<polyline points="16 17 21 12 16 7"></polyline>
					<line x1="21" y1="12" x2="9" y2="12"></line>
				</svg>
				<span>End Session</span>
			</button>
		</div>
	</header>

	<!-- Main Workspace -->
	<main class="dashboard-body">
		<!-- Disclaimer Banner -->
		<div class="simulation-banner">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="12" cy="12" r="10"></circle>
				<line x1="12" y1="8" x2="12" y2="12"></line>
				<line x1="12" y1="16" x2="12.01" y2="16"></line>
			</svg>
			<span>
				<strong>Simulated ATM Environment:</strong> Account balances and cash transactions are simulation-only demo records and do not connect to real banking networks.
			</span>
		</div>

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

		<!-- Grid Layout -->
		<div class="dashboard-grid">
			<!-- Left Column: Balance & Quick ATM Actions -->
			<div class="balance-column">
				<!-- Simulated Balance Card -->
				<div class="balance-card">
					<div class="bc-top">
						<div>
							<div class="bc-label">AVAILABLE SIMULATED BALANCE</div>
							<div class="bc-bank">{customer?.bankName || 'Face ATM Bank'}</div>
						</div>
						<span class="demo-tag">DEMO DATA</span>
					</div>

					<div class="bc-amount">
						<span class="currency-symbol">&#8377;</span>
						<span class="amount-digits">
							{isLoading ? '...' : balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
						</span>
					</div>

					<div class="bc-bottom">
						<span class="card-ref">{customer?.cardNumberMasked}</span>
						<button class="refresh-bal-btn" onclick={handleBalanceInquiry} disabled={isActionLoading}>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class={isActionLoading ? 'spin' : ''}>
								<polyline points="23 4 23 10 17 10"></polyline>
								<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
							</svg>
							<span>Balance Inquiry</span>
						</button>
					</div>
				</div>

				<!-- ATM Action Tiles -->
				<div class="atm-actions-grid">
					<button class="action-tile withdraw-tile" onclick={() => openTransactionModal('WITHDRAW')}>
						<div class="action-icon">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<line x1="12" y1="5" x2="12" y2="19"></line>
								<polyline points="19 12 12 19 5 12"></polyline>
							</svg>
						</div>
						<div class="action-text">
							<h3>Cash Withdrawal</h3>
							<p>Simulate cash dispensing</p>
						</div>
					</button>

					<button class="action-tile deposit-tile" onclick={() => openTransactionModal('DEPOSIT')}>
						<div class="action-icon">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<line x1="12" y1="19" x2="12" y2="5"></line>
								<polyline points="5 12 12 5 19 12"></polyline>
							</svg>
						</div>
						<div class="action-text">
							<h3>Cash Deposit</h3>
							<p>Simulate adding funds</p>
						</div>
					</button>
				</div>
			</div>

			<!-- Right Column: Recent Mini-Statement -->
			<div class="statement-column">
				<div class="statement-card">
					<div class="statement-header">
						<h3>Recent ATM Activity</h3>
						<span class="count-badge">{transactions.length} records</span>
					</div>

					{#if transactions.length === 0}
						<div class="empty-txns">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<rect x="2" y="5" width="20" height="14" rx="2"></rect>
								<line x1="2" y1="10" x2="22" y2="10"></line>
							</svg>
							<p>No recent transactions recorded yet.</p>
							<span>Use the withdrawal or deposit actions to record simulated ATM transactions.</span>
						</div>
					{:else}
						<div class="txns-list">
							{#each transactions as txn (txn.id)}
								<div class="txn-row">
									<div class="txn-icon-wrap {txn.type === 'DEPOSIT' ? 'deposit' : 'withdraw'}">
										{#if txn.type === 'DEPOSIT'}
											<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
												<polyline points="18 15 12 9 6 15"></polyline>
											</svg>
										{:else}
											<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
												<polyline points="6 9 12 15 18 9"></polyline>
											</svg>
										{/if}
									</div>
									<div class="txn-details">
										<div class="txn-title">{txn.description || txn.type}</div>
										<div class="txn-time">
											{new Date(txn.timestamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
										</div>
									</div>
									<div class="txn-amount-wrap">
										<div class="txn-val {txn.type === 'DEPOSIT' ? 'green' : 'red'}">
											{txn.type === 'DEPOSIT' ? '+' : '-'} &#8377;{txn.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
										</div>
										<div class="txn-balance">
											Bal: &#8377;{txn.newBalance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		</div>
	</main>

	<!-- TRANSACTION MODAL (WITHDRAW / DEPOSIT) -->
	{#if activeModal === 'WITHDRAW' || activeModal === 'DEPOSIT'}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="modal-backdrop" onclick={closeModal}>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div class="modal-dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="modal-header">
					<h2>{activeModal === 'WITHDRAW' ? 'Simulate Cash Withdrawal' : 'Simulate Cash Deposit'}</h2>
					<button class="close-modal-btn" onclick={closeModal}>&times;</button>
				</div>

				{#if errorMessage}
					<div class="error-banner in-modal" role="alert">
						<span>{errorMessage}</span>
					</div>
				{/if}

				<div class="modal-body">
					<p class="modal-note">
						{activeModal === 'WITHDRAW'
							? 'Select or enter the amount of simulated cash to withdraw. Multiples of ₹100 required.'
							: 'Select or enter the amount of simulated cash to deposit into your account.'}
					</p>

					<!-- Quick Select Buttons -->
					<div class="quick-amounts-grid">
						{#each quickAmounts as amt}
							<button
								type="button"
								class="quick-amt-btn {transactionAmount === amt.toString() ? 'selected' : ''}"
								onclick={() => selectQuickAmount(amt)}
							>
								&#8377;{amt.toLocaleString('en-IN')}
							</button>
						{/each}
					</div>

					<!-- Custom Amount Input -->
					<div class="form-group custom-amt">
						<label for="customAmount">Or Enter Amount (&#8377;)</label>
						<div class="input-wrap">
							<span class="currency-prefix">&#8377;</span>
							<input
								id="customAmount"
								type="number"
								inputmode="numeric"
								step="100"
								min="100"
								max="20000"
								placeholder="e.g. 1500"
								bind:value={transactionAmount}
							/>
						</div>
						<span class="input-hint">Max limit ₹20,000 per transaction &bull; Multiples of ₹100</span>
					</div>
				</div>

				<div class="modal-actions">
					<button class="cancel-modal-btn" onclick={closeModal} disabled={isActionLoading}>
						Cancel
					</button>
					<button class="confirm-modal-btn" onclick={submitTransaction} disabled={isActionLoading || !transactionAmount}>
						{#if isActionLoading}
							<div class="btn-spinner"></div>
							<span>Processing Transaction...</span>
						{:else}
							<span>Confirm {activeModal === 'WITHDRAW' ? 'Withdrawal' : 'Deposit'}</span>
						{/if}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- BALANCE RECEIPT MODAL -->
	{#if activeModal === 'BALANCE_RECEIPT'}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="modal-backdrop" onclick={closeModal}>
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<div class="modal-dialog receipt-dialog" onclick={(e) => e.stopPropagation()} role="dialog" tabindex="-1">
				<div class="receipt-header">
					<div class="receipt-icon">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<polyline points="20 6 9 17 4 12"></polyline>
						</svg>
					</div>
					<h2>Balance Inquiry Receipt</h2>
					<p class="receipt-sub">FACE ATM TERMINAL #01 &bull; SIMULATION</p>
				</div>

				<div class="receipt-card">
					<div class="receipt-row">
						<span>Customer:</span>
						<strong>{customer?.fullName}</strong>
					</div>
					<div class="receipt-row">
						<span>Card Number:</span>
						<strong>{customer?.cardNumberMasked}</strong>
					</div>
					<div class="receipt-row">
						<span>Bank:</span>
						<strong>{customer?.bankName || 'Face ATM Bank'}</strong>
					</div>
					<div class="receipt-row">
						<span>As of:</span>
						<span>{new Date().toLocaleString('en-IN')}</span>
					</div>
					<div class="receipt-divider"></div>
					<div class="receipt-row total">
						<span>Available Balance:</span>
						<strong class="receipt-amount">&#8377;{balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
					</div>
				</div>

				<div class="modal-actions receipt-actions">
					<button class="confirm-modal-btn" onclick={closeModal}>
						Done
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.dashboard-wrapper {
		min-height: 100vh;
		background: #fbf8f3;
		color: #173f35;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		display: flex;
		flex-direction: column;
	}

	.terminal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.25rem 2.5rem;
		background: var(--color-navy);
		color: #ffffff;
		box-shadow: var(--shadow-md);
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
		box-shadow: 0 4px 12px rgba(15, 118, 110, 0.3);
	}

	.brand-chip svg {
		width: 24px;
		height: 24px;
	}

	.brand-info {
		display: flex;
		flex-direction: column;
	}

	.brand-name {
		font-family: var(--font-heading);
		font-size: 1.25rem;
		font-weight: 700;
	}

	.brand-status {
		font-size: 0.78rem;
		color: #94a3b8;
	}

	.header-right {
		display: flex;
		align-items: center;
		gap: 1.25rem;
	}

	.user-pill {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		background: rgba(255, 255, 255, 0.1);
		padding: 0.5rem 1rem;
		border-radius: 999px;
		font-size: 0.88rem;
		border: 1px solid rgba(255, 255, 255, 0.15);
	}

	.auth-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--color-accent-green);
		box-shadow: 0 0 8px var(--color-accent-green);
	}

	.user-name {
		font-weight: 600;
	}

	.card-num {
		color: #94a3b8;
		font-family: monospace;
	}

	.logout-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		background: var(--color-teal);
		color: #ffffff;
		border: none;
		padding: 0.55rem 1.1rem;
		border-radius: var(--radius-md);
		font-size: 0.88rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 0 2px 8px rgba(15, 118, 110, 0.25);
		transition: all var(--transition-fast);
	}

	.logout-btn:hover {
		background: var(--color-teal-hover);
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(15, 118, 110, 0.35);
	}

	.logout-btn svg {
		width: 16px;
		height: 16px;
	}

	.dashboard-body {
		flex: 1;
		padding: 2rem 2.5rem;
		max-width: 1200px;
		margin: 0 auto;
		width: 100%;
	}

	.simulation-banner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: #e7dfd5;
		color: #173f35;
		border-left: 4px solid #d97745;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.5rem;
		font-size: 0.88rem;
	}

	.simulation-banner svg {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
		color: #d97745;
	}

	.success-banner {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		background: #d1fae5;
		color: #065f46;
		padding: 0.85rem 1.25rem;
		border-radius: 8px;
		margin-bottom: 1.25rem;
		border-left: 4px solid #10b981;
		font-weight: 500;
	}

	.success-banner svg {
		width: 18px;
		height: 18px;
	}

	.error-banner {
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

	.error-banner svg {
		width: 18px;
		height: 18px;
	}

	.dashboard-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 2rem;
	}

	@media (max-width: 900px) {
		.dashboard-grid {
			grid-template-columns: 1fr;
		}
	}

	/* Balance Card */
	.balance-card {
		background: linear-gradient(135deg, var(--color-navy) 0%, #0d1e2e 50%, var(--color-navy-dark) 100%);
		color: #ffffff;
		border-radius: var(--radius-lg);
		padding: 2.25rem 2rem;
		box-shadow: var(--shadow-lg);
		margin-bottom: 1.5rem;
		border: 1px solid rgba(255, 255, 255, 0.12);
		position: relative;
		overflow: hidden;
	}

	.balance-card::before {
		content: '';
		position: absolute;
		top: -50px;
		right: -50px;
		width: 160px;
		height: 160px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(15, 118, 110, 0.35) 0%, transparent 70%);
	}

	.bc-top {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1.25rem;
		position: relative;
		z-index: 1;
	}

	.bc-label {
		font-size: 0.75rem;
		letter-spacing: 1.5px;
		color: #94a3b8;
		font-weight: 600;
	}

	.bc-bank {
		font-size: 1.15rem;
		font-weight: 700;
		color: #ffffff;
		margin-top: 0.2rem;
	}

	.demo-tag {
		background: var(--color-teal-subtle);
		color: #5eead4;
		border: 1px solid rgba(15, 118, 110, 0.5);
		font-size: 0.7rem;
		font-weight: 700;
		padding: 3px 8px;
		border-radius: var(--radius-full);
	}

	.bc-amount {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
		margin-bottom: 1.5rem;
		position: relative;
		z-index: 1;
	}

	.currency-symbol {
		font-size: 1.8rem;
		font-weight: 600;
		color: #94a3b8;
	}

	.amount-digits {
		font-family: var(--font-heading);
		font-size: 2.75rem;
		font-weight: 800;
		letter-spacing: 1px;
		color: #ffffff;
	}

	.bc-bottom {
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
		padding-top: 1rem;
		position: relative;
		z-index: 1;
	}

	.card-ref {
		font-family: monospace;
		font-size: 0.95rem;
		color: #94a3b8;
	}

	.refresh-bal-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		background: rgba(255, 255, 255, 0.1);
		border: 1px solid rgba(255, 255, 255, 0.2);
		color: #ffffff;
		padding: 0.4rem 0.85rem;
		border-radius: var(--radius-sm);
		font-size: 0.82rem;
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.refresh-bal-btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.2);
		transform: translateY(-1px);
	}

	.refresh-bal-btn svg {
		width: 14px;
		height: 14px;
	}

	.spin {
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* ATM Action Tiles */
	.atm-actions-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}

	.action-tile {
		background: #ffffff;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		padding: 1.5rem 1.25rem;
		text-align: left;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		box-shadow: var(--shadow-sm);
		transition: all var(--transition-normal);
	}

	.action-tile:hover {
		transform: translateY(-3px);
		box-shadow: var(--shadow-hover);
		border-color: rgba(15, 118, 110, 0.3);
	}

	.action-icon {
		width: 44px;
		height: 44px;
		border-radius: 10px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.withdraw-tile .action-icon {
		background: #fee2e2;
		color: #dc2626;
	}

	.deposit-tile .action-icon {
		background: #d1fae5;
		color: #059669;
	}

	.action-icon svg {
		width: 22px;
		height: 22px;
	}

	.action-text h3 {
		font-size: 1.05rem;
		font-weight: 700;
		margin: 0 0 0.25rem;
	}

	.action-text p {
		font-size: 0.82rem;
		color: #6b7280;
		margin: 0;
	}

	/* Statement Card */
	.statement-card {
		background: #ffffff;
		border: 1px solid #e7dfd5;
		border-radius: 16px;
		padding: 1.75rem;
		box-shadow: 0 4px 12px rgba(23, 63, 53, 0.05);
	}

	.statement-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.25rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid #f0e9df;
	}

	.statement-header h3 {
		font-size: 1.15rem;
		font-weight: 700;
		margin: 0;
	}

	.count-badge {
		font-size: 0.75rem;
		background: #f3f4f6;
		padding: 3px 8px;
		border-radius: 999px;
		color: #4b5563;
		font-weight: 600;
	}

	.empty-txns {
		text-align: center;
		padding: 3rem 1rem;
		color: #6b7280;
	}

	.empty-txns svg {
		width: 40px;
		height: 40px;
		color: #9ca3af;
		margin-bottom: 0.75rem;
	}

	.empty-txns p {
		font-weight: 600;
		margin: 0 0 0.25rem;
	}

	.empty-txns span {
		font-size: 0.85rem;
	}

	.txns-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.txn-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid #f6f1e8;
	}

	.txn-row:last-child {
		border-bottom: none;
	}

	.txn-icon-wrap {
		width: 36px;
		height: 36px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.txn-icon-wrap.deposit {
		background: #d1fae5;
		color: #059669;
	}

	.txn-icon-wrap.withdraw {
		background: #fee2e2;
		color: #dc2626;
	}

	.txn-icon-wrap svg {
		width: 18px;
		height: 18px;
	}

	.txn-details {
		flex: 1;
	}

	.txn-title {
		font-size: 0.92rem;
		font-weight: 600;
		color: #111827;
	}

	.txn-time {
		font-size: 0.75rem;
		color: #6b7280;
		margin-top: 0.15rem;
	}

	.txn-amount-wrap {
		text-align: right;
	}

	.txn-val {
		font-size: 0.95rem;
		font-weight: 700;
	}

	.txn-val.green {
		color: #059669;
	}

	.txn-val.red {
		color: #dc2626;
	}

	.txn-balance {
		font-size: 0.75rem;
		color: #6b7280;
		font-family: monospace;
		margin-top: 0.15rem;
	}

	/* Modals */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(13, 40, 34, 0.7);
		backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem;
		z-index: 100;
	}

	.modal-dialog {
		background: #ffffff;
		border-radius: 16px;
		max-width: 500px;
		width: 100%;
		padding: 2rem;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.25rem;
	}

	.modal-header h2 {
		font-size: 1.35rem;
		font-weight: 700;
		margin: 0;
	}

	.close-modal-btn {
		background: none;
		border: none;
		font-size: 1.5rem;
		color: #9ca3af;
		cursor: pointer;
	}

	.modal-note {
		font-size: 0.9rem;
		color: #6b7280;
		margin: 0 0 1.25rem;
	}

	.quick-amounts-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.75rem;
		margin-bottom: 1.5rem;
	}

	.quick-amt-btn {
		background: #f3f4f6;
		border: 2px solid transparent;
		color: #1f2937;
		padding: 0.75rem 0.5rem;
		border-radius: 8px;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.2s;
	}

	.quick-amt-btn:hover {
		background: #e5e7eb;
	}

	.quick-amt-btn.selected {
		border-color: var(--color-teal);
		background: var(--color-teal-subtle);
		color: var(--color-teal);
	}

	.custom-amt {
		margin-bottom: 1.5rem;
	}

	.custom-amt label {
		font-size: 0.88rem;
		font-weight: 600;
		color: var(--color-text);
		display: block;
		margin-bottom: 0.4rem;
	}

	.input-wrap {
		position: relative;
		display: flex;
		align-items: center;
	}

	.currency-prefix {
		position: absolute;
		left: 1rem;
		font-size: 1.2rem;
		font-weight: 700;
		color: var(--color-text-light);
	}

	.input-wrap input {
		width: 100%;
		padding: 0.75rem 1rem 0.75rem 2.25rem;
		font-size: 1.2rem;
		font-weight: 700;
		border: 2px solid var(--color-border);
		border-radius: var(--radius-md);
		transition: border-color var(--transition-fast);
	}

	.input-wrap input:focus {
		outline: none;
		border-color: var(--color-teal);
		box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.15);
	}

	.input-hint {
		font-size: 0.78rem;
		color: var(--color-text-light);
		margin-top: 0.35rem;
		display: block;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}

	.cancel-modal-btn {
		background: #f3f4f6;
		border: 1px solid var(--color-border);
		color: var(--color-text);
		padding: 0.75rem 1.25rem;
		border-radius: var(--radius-md);
		font-weight: 600;
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.cancel-modal-btn:hover {
		background: #e5e7eb;
	}

	.confirm-modal-btn {
		background: var(--color-teal);
		color: #ffffff;
		border: none;
		padding: 0.75rem 1.5rem;
		border-radius: var(--radius-md);
		font-weight: 700;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		box-shadow: 0 2px 8px rgba(15, 118, 110, 0.25);
		transition: all var(--transition-fast);
	}

	.confirm-modal-btn:hover:not(:disabled) {
		background: var(--color-teal-hover);
		transform: translateY(-1px);
		box-shadow: 0 4px 14px rgba(15, 118, 110, 0.35);
	}

	.confirm-modal-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-spinner {
		width: 16px;
		height: 16px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: #ffffff;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	/* Receipt dialog */
	.receipt-header {
		text-align: center;
		margin-bottom: 1.5rem;
	}

	.receipt-icon {
		width: 48px;
		height: 48px;
		background: #d1fae5;
		color: #059669;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 0.75rem;
	}

	.receipt-icon svg {
		width: 24px;
		height: 24px;
	}

	.receipt-header h2 {
		margin: 0;
		font-size: 1.35rem;
	}

	.receipt-sub {
		font-size: 0.75rem;
		letter-spacing: 1px;
		color: #6b7280;
		margin: 0.25rem 0 0;
	}

	.receipt-card {
		background: #fdfaf6;
		border: 1px dashed #d1c7b8;
		border-radius: 10px;
		padding: 1.25rem;
		margin-bottom: 1.5rem;
	}

	.receipt-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.88rem;
		margin-bottom: 0.6rem;
	}

	.receipt-divider {
		border-top: 1px dashed #d1c7b8;
		margin: 0.75rem 0;
	}

	.receipt-row.total {
		font-size: 1.05rem;
		margin-bottom: 0;
	}

	.receipt-amount {
		color: #059669;
		font-size: 1.25rem;
	}

	.receipt-actions {
		justify-content: center;
	}
</style>
