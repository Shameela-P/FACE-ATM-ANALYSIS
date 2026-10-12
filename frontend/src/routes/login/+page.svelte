<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { loginAdmin } from '#lib/firebase.js';
	import { adminUser, authLoading, authConfigured, getFriendlyAuthErrorMessage } from '#lib/auth.js';

	let email = $state('');
	let password = $state('');
	let showPassword = $state(false);
	let isSubmitting = $state(false);
	let errorMessage = $state('');
	let infoMessage = $state('');

	onMount(() => {
		const unsubscribe = adminUser.subscribe((user) => {
			if (user) {
				goto('/admin/dashboard', { replaceState: true });
			}
		});
		return () => unsubscribe();
	});

	function togglePasswordVisibility() {
		showPassword = !showPassword;
	}

	async function handleSubmit(event) {
		event.preventDefault();
		errorMessage = '';
		infoMessage = '';

		const trimmedEmail = email.trim();
		if (!trimmedEmail) {
			errorMessage = 'Please enter your administrator email address.';
			return;
		}

		if (!password) {
			errorMessage = 'Please enter your password.';
			return;
		}

		isSubmitting = true;

		try {
			await loginAdmin(trimmedEmail, password);
			// Successful login will trigger adminUser store and redirect to dashboard
			goto('/admin/dashboard', { replaceState: true });
		} catch (error) {
			console.error('Login error:', error);
			errorMessage = getFriendlyAuthErrorMessage(error);
		} finally {
			isSubmitting = false;
		}
	}
</script>

<svelte:head>
	<title>Admin Login | Face Authentication System</title>
</svelte:head>

<div class="login-wrapper">
	<div class="login-container">
		<!-- Brand Header -->
		<div class="brand-header">
			<div class="brand-icon">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
					<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
					<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
					<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
					<circle cx="12" cy="12" r="3"></circle>
					<path d="M16 16.5a5 5 0 0 0-8 0"></path>
				</svg>
			</div>
			<h1 class="project-title">Face Authentication System</h1>
			<p class="role-tag">Operational Administrator Portal</p>
		</div>

		<!-- Configuration Warning if Firebase is not yet configured -->
		{#if !$authConfigured}
			<div class="banner-notice" role="alert">
				<div class="notice-icon">⚠️</div>
				<div class="notice-content">
					<strong>Firebase Setup Required:</strong>
					<span>Update <code>frontend/.env</code> with your project's Firebase API credentials to enable live admin login.</span>
				</div>
			</div>
		{/if}

		<!-- Error Message Alert -->
		{#if errorMessage}
			<div class="alert-error" role="alert">
				<svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<circle cx="12" cy="12" r="10"></circle>
					<line x1="12" y1="8" x2="12" y2="12"></line>
					<line x1="12" y1="16" x2="12.01" y2="16"></line>
				</svg>
				<span>{errorMessage}</span>
			</div>
		{/if}

		<!-- Login Form -->
		<form onsubmit={handleSubmit} class="login-form" novalidate>
			<div class="form-group">
				<label for="admin-email">Admin Email Address</label>
				<div class="input-container">
					<svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="2" y="4" width="20" height="16" rx="2"></rect>
						<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path>
					</svg>
					<input
						id="admin-email"
						type="email"
						bind:value={email}
						placeholder="admin@faceatm.local"
						autocomplete="username"
						disabled={isSubmitting}
						required
					/>
				</div>
			</div>

			<div class="form-group">
				<label for="admin-password">Password</label>
				<div class="input-container">
					<svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
						<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
					</svg>
					<input
						id="admin-password"
						type={showPassword ? 'text' : 'password'}
						bind:value={password}
						placeholder="Enter your master password"
						autocomplete="current-password"
						disabled={isSubmitting}
						required
					/>
					<button
						type="button"
						class="toggle-password"
						onclick={togglePasswordVisibility}
						aria-label={showPassword ? 'Hide password' : 'Show password'}
						tabindex="-1"
					>
						{#if showPassword}
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
								<line x1="1" y1="1" x2="23" y2="23"></line>
							</svg>
						{:else}
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
								<circle cx="12" cy="12" r="3"></circle>
							</svg>
						{/if}
					</button>
				</div>
			</div>

			<button
				type="submit"
				class="btn-primary submit-btn"
				disabled={isSubmitting}
			>
				{#if isSubmitting}
					<span class="btn-spinner"></span>
					<span>Authenticating Admin...</span>
				{:else}
					<span>Sign In to Dashboard</span>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="arrow-icon">
						<line x1="5" y1="12" x2="19" y2="12"></line>
						<polyline points="12 5 19 12 12 19"></polyline>
					</svg>
				{/if}
			</button>
		</form>

		<!-- Security Notice Footer -->
		<div class="login-footer">
			<div class="lock-shield">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
				</svg>
				<span>Restricted System &bull; Single Admin Access Only</span>
			</div>
			<p class="provision-note">Public registration is prohibited. Authorized administrators only.</p>
			<a href="/" class="return-home-link">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<line x1="19" y1="12" x2="5" y2="12"></line>
					<polyline points="12 19 5 12 12 5"></polyline>
				</svg>
				<span>Back to Face ATM Home</span>
			</a>
		</div>
	</div>
</div>


<style>
	.login-wrapper {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		background: linear-gradient(135deg, var(--color-navy) 0%, #0c1a2e 50%, var(--color-navy-dark) 100%);
		padding: 1.5rem;
		position: relative;
		overflow: hidden;
	}

	.login-wrapper::before {
		content: '';
		position: absolute;
		width: 500px;
		height: 500px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(15, 118, 110, 0.2) 0%, transparent 70%);
		top: -150px;
		right: -100px;
		pointer-events: none;
	}

	.login-wrapper::after {
		content: '';
		position: absolute;
		width: 450px;
		height: 450px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(34, 197, 94, 0.08) 0%, transparent 70%);
		bottom: -150px;
		left: -100px;
		pointer-events: none;
	}

	.login-container {
		width: 100%;
		max-width: 460px;
		background-color: var(--color-white);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-lg);
		padding: 2.75rem 2.5rem;
		position: relative;
		z-index: 1;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.brand-header {
		text-align: center;
		margin-bottom: 2rem;
	}

	.brand-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 64px;
		height: 64px;
		border-radius: var(--radius-md);
		background-color: var(--color-forest);
		color: var(--color-cream);
		margin-bottom: 1.25rem;
		box-shadow: 0 8px 20px rgba(23, 63, 53, 0.25);
	}

	.brand-icon svg {
		width: 34px;
		height: 34px;
	}

	.project-title {
		font-size: 1.65rem;
		color: var(--color-forest);
		margin-bottom: 0.35rem;
		font-weight: 800;
	}

	.role-tag {
		font-size: 0.85rem;
		color: var(--color-terracotta);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.banner-notice {
		display: flex;
		gap: 0.75rem;
		background-color: rgba(217, 119, 69, 0.08);
		border: 1px solid rgba(217, 119, 69, 0.3);
		border-radius: var(--radius-md);
		padding: 0.85rem 1rem;
		margin-bottom: 1.5rem;
		font-size: 0.82rem;
		color: var(--color-forest);
		line-height: 1.4;
	}

	.notice-content code {
		background: rgba(23, 63, 53, 0.08);
		padding: 0.1rem 0.3rem;
		border-radius: 4px;
		font-family: monospace;
	}

	.alert-error {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background-color: #fdf2f2;
		border-left: 4px solid #dc2626;
		padding: 0.85rem 1rem;
		border-radius: var(--radius-sm);
		color: #991b1b;
		margin-bottom: 1.5rem;
		font-size: 0.875rem;
		font-weight: 500;
	}

	.alert-icon {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
	}

	.login-form {
		display: flex;
		flex-direction: column;
		gap: 1.35rem;
	}

	.form-group {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.form-group label {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-forest);
		letter-spacing: -0.01em;
	}

	.input-container {
		position: relative;
		display: flex;
		align-items: center;
	}

	.input-icon {
		position: absolute;
		left: 1rem;
		width: 18px;
		height: 18px;
		color: var(--color-gray);
		pointer-events: none;
	}

	.input-container input {
		width: 100%;
		padding: 0.85rem 1rem 0.85rem 2.75rem;
		background-color: var(--color-cream-light);
		border: 1.5px solid var(--color-gray-border);
		border-radius: var(--radius-md);
		color: var(--color-forest);
		font-family: var(--font-body);
		font-size: 0.95rem;
		transition: all var(--transition-fast);
	}

	.input-container input:focus {
		outline: none;
		border-color: var(--color-forest);
		background-color: var(--color-white);
		box-shadow: 0 0 0 3px rgba(23, 63, 53, 0.1);
	}

	.input-container input::placeholder {
		color: var(--color-gray-light);
	}

	.toggle-password {
		position: absolute;
		right: 0.75rem;
		padding: 0.4rem;
		display: flex;
		align-items: center;
		color: var(--color-gray);
		border-radius: 4px;
		transition: color var(--transition-fast);
	}

	.toggle-password:hover {
		color: var(--color-forest);
	}

	.toggle-password svg {
		width: 19px;
		height: 19px;
	}

	.submit-btn {
		width: 100%;
		margin-top: 0.5rem;
		padding: 0.95rem;
		font-size: 1rem;
	}

	.arrow-icon {
		width: 18px;
		height: 18px;
		transition: transform var(--transition-fast);
	}

	.submit-btn:hover:not(:disabled) .arrow-icon {
		transform: translateX(3px);
	}

	.btn-spinner {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: var(--color-white);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	.return-home-link {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 1rem;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-teal);
		padding: 0.4rem 0.8rem;
		border-radius: var(--radius-sm);
		transition: all var(--transition-fast);
	}

	.return-home-link:hover {
		color: var(--color-teal-hover);
		background-color: var(--color-teal-subtle);
		transform: translateX(-2px);
	}

	.return-home-link svg {
		width: 16px;
		height: 16px;
	}

	.login-footer {
		margin-top: 1.75rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--color-gray-border);
		text-align: center;
	}


	.lock-shield {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.78rem;
		font-weight: 600;
		color: var(--color-gray);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.lock-shield svg {
		width: 15px;
		height: 15px;
		color: var(--color-forest);
	}

	.provision-note {
		margin-top: 0.45rem;
		font-size: 0.75rem;
		color: var(--color-gray);
		line-height: 1.4;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 480px) {
		.login-container {
			padding: 2rem 1.5rem;
		}
	}
</style>
