<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { logoutAdmin } from '#lib/firebase.js';
	import { adminUser, authLoading } from '#lib/auth.js';

	let { children } = $props();
	let isLoggingOut = $state(false);
	let mobileNavOpen = $state(false);

	onMount(() => {
		const unsubscribe = authLoading.subscribe((loading) => {
			if (!loading) {
				const userUnsub = adminUser.subscribe((user) => {
					if (!user) {
						goto('/login', { replaceState: true });
					}
				});
				userUnsub();
			}
		});

		return () => unsubscribe();
	});

	async function handleLogout() {
		isLoggingOut = true;
		try {
			await logoutAdmin();
			goto('/login', { replaceState: true });
		} catch (error) {
			console.error('Logout error:', error);
		} finally {
			isLoggingOut = false;
		}
	}

	function toggleMobileNav() {
		mobileNavOpen = !mobileNavOpen;
	}
</script>

{#if $authLoading}
	<div class="auth-loading-screen">
		<div class="loading-spinner"></div>
		<p>Verifying Administrator Session...</p>
	</div>
{:else if $adminUser}
	<div class="admin-layout">
		<!-- Sidebar Navigation -->
		<aside class="sidebar {mobileNavOpen ? 'mobile-open' : ''}">
			<div class="sidebar-brand">
				<div class="brand-badge">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
						<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
						<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
						<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
						<circle cx="12" cy="12" r="3"></circle>
						<path d="M16 16.5a5 5 0 0 0-8 0"></path>
					</svg>
				</div>
				<div class="brand-text">
					<div class="brand-name">Face ATM</div>
					<div class="brand-sub">Admin Portal</div>
				</div>
			</div>

			<nav class="sidebar-nav">
				<div class="nav-section-title">Navigation</div>
				<a href="/admin/dashboard" class="nav-item {page.url.pathname === '/admin/dashboard' ? 'active' : ''}">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="3" y="3" width="7" height="7"></rect>
						<rect x="14" y="3" width="7" height="7"></rect>
						<rect x="14" y="14" width="7" height="7"></rect>
						<rect x="3" y="14" width="7" height="7"></rect>
					</svg>
					<span>Dashboard</span>
				</a>

				<!-- Customer Registration (Phase 2 Active) -->
				<a href="/admin/register" class="nav-item {page.url.pathname.startsWith('/admin/register') ? 'active' : ''}">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
						<circle cx="9" cy="7" r="4"></circle>
						<line x1="19" y1="8" x2="19" y2="14"></line>
						<line x1="22" y1="11" x2="16" y2="11"></line>
					</svg>
					<span>Customer Registration</span>
				</a>

				<!-- Security Approvals (Phase 3 Active) -->
				<a href="/admin/security-approvals" class="nav-item {page.url.pathname.startsWith('/admin/security-approvals') ? 'active' : ''}">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
						<polyline points="9 12 11 14 15 10"></polyline>
					</svg>
					<span>Security Approvals</span>
				</a>
			</nav>

			<div class="sidebar-footer">
				<div class="admin-card">
					<div class="admin-avatar">A</div>
					<div class="admin-details">
						<div class="admin-role-badge">ADMIN</div>
						<div class="admin-email" title={$adminUser.email}>{$adminUser.email}</div>
					</div>
				</div>
				<button class="logout-btn" onclick={handleLogout} disabled={isLoggingOut}>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
						<polyline points="16 17 21 12 16 7"></polyline>
						<line x1="21" y1="12" x2="9" y2="12"></line>
					</svg>
					<span>{isLoggingOut ? 'Logging out...' : 'Sign Out'}</span>
				</button>
			</div>
		</aside>

		<!-- Main Workspace Area -->
		<div class="main-wrapper">
			<header class="topbar">
				<button class="mobile-toggle" onclick={toggleMobileNav} aria-label="Toggle Navigation">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="3" y1="12" x2="21" y2="12"></line>
						<line x1="3" y1="6" x2="21" y2="6"></line>
						<line x1="3" y1="18" x2="21" y2="18"></line>
					</svg>
				</button>
				<div class="system-status">
					<span class="status-indicator"></span>
					<span class="system-label">System Mode: <strong>Phase 2 Active</strong></span>
				</div>
				<div class="topbar-actions">
					<div class="admin-pill">
						<span class="badge badge-active">Admin Verified</span>
						<span class="pill-email">{$adminUser.email}</span>
					</div>
					<button class="topbar-logout" onclick={handleLogout} disabled={isLoggingOut} title="Sign Out">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
							<polyline points="16 17 21 12 16 7"></polyline>
							<line x1="21" y1="12" x2="9" y2="12"></line>
						</svg>
					</button>
				</div>
			</header>

			<main class="page-body">
				{@render children()}
			</main>
		</div>
	</div>
{/if}

<style>
	.auth-loading-screen {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		background-color: var(--color-cream);
		gap: 1.25rem;
		color: var(--color-forest);
	}

	.loading-spinner {
		width: 44px;
		height: 44px;
		border: 4px solid rgba(23, 63, 53, 0.15);
		border-top-color: var(--color-terracotta);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.admin-layout {
		display: flex;
		min-height: 100vh;
		background-color: var(--color-cream);
	}

	/* Sidebar Styles */
	.sidebar {
		width: 280px;
		background-color: var(--color-forest);
		color: var(--color-cream);
		display: flex;
		flex-direction: column;
		border-right: 1px solid rgba(255, 255, 255, 0.08);
		flex-shrink: 0;
		transition: transform var(--transition-normal);
		position: sticky;
		top: 0;
		height: 100vh;
	}

	.sidebar-brand {
		padding: 1.75rem 1.5rem;
		display: flex;
		align-items: center;
		gap: 0.85rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	}

	.brand-badge {
		width: 42px;
		height: 42px;
		background-color: var(--color-terracotta);
		border-radius: var(--radius-md);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-white);
		box-shadow: 0 4px 12px rgba(217, 119, 69, 0.3);
	}

	.brand-badge svg {
		width: 24px;
		height: 24px;
	}

	.brand-name {
		font-family: var(--font-heading);
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--color-white);
		line-height: 1.2;
	}

	.brand-sub {
		font-size: 0.75rem;
		color: var(--color-gray-light);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	.sidebar-nav {
		padding: 1.5rem 1rem;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.nav-section-title {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-gray-light);
		padding: 0 0.75rem 0.5rem;
		font-weight: 700;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		padding: 0.75rem 0.85rem;
		border-radius: var(--radius-md);
		color: var(--color-cream);
		font-size: 0.92rem;
		font-weight: 500;
		transition: all var(--transition-fast);
	}

	.nav-item svg {
		width: 20px;
		height: 20px;
		opacity: 0.8;
	}

	.nav-item.active {
		background-color: rgba(255, 255, 255, 0.12);
		color: var(--color-white);
		font-weight: 600;
	}

	.nav-item.active svg {
		opacity: 1;
		color: var(--color-teal);
	}

	.sidebar-footer {
		padding: 1.25rem;
		border-top: 1px solid rgba(255, 255, 255, 0.08);
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.admin-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background-color: rgba(0, 0, 0, 0.2);
		padding: 0.75rem;
		border-radius: var(--radius-md);
	}

	.admin-avatar {
		width: 36px;
		height: 36px;
		border-radius: 50%;
		background-color: var(--color-terracotta);
		color: var(--color-white);
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 700;
		font-size: 0.95rem;
	}

	.admin-details {
		overflow: hidden;
		flex: 1;
	}

	.admin-role-badge {
		font-size: 0.68rem;
		font-weight: 700;
		color: var(--color-terracotta);
		letter-spacing: 0.08em;
	}

	.admin-email {
		font-size: 0.8rem;
		color: var(--color-white);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.logout-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		width: 100%;
		padding: 0.75rem;
		border-radius: var(--radius-md);
		background-color: rgba(255, 255, 255, 0.08);
		color: var(--color-cream);
		font-size: 0.88rem;
		font-weight: 600;
		transition: all var(--transition-fast);
	}

	.logout-btn:hover:not(:disabled) {
		background-color: rgba(217, 119, 69, 0.25);
		color: var(--color-white);
	}

	.logout-btn svg {
		width: 18px;
		height: 18px;
	}

	/* Main Workspace Area */
	.main-wrapper {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.topbar {
		background-color: var(--color-white);
		padding: 1.1rem 2rem;
		border-bottom: 1px solid var(--color-gray-border);
		display: flex;
		align-items: center;
		justify-content: space-between;
		position: sticky;
		top: 0;
		z-index: 10;
	}

	.mobile-toggle {
		display: none;
		padding: 0.5rem;
		color: var(--color-forest);
	}

	.mobile-toggle svg {
		width: 24px;
		height: 24px;
	}

	.system-status {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.88rem;
		color: var(--color-forest);
	}

	.status-indicator {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background-color: #10b981;
		box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
	}

	.topbar-actions {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.admin-pill {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		background-color: var(--color-cream-light);
		border: 1px solid var(--color-gray-border);
		padding: 0.35rem 0.75rem;
		border-radius: var(--radius-full);
	}

	.pill-email {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-forest);
	}

	.topbar-logout {
		display: flex;
		align-items: center;
		padding: 0.5rem;
		border-radius: var(--radius-md);
		color: var(--color-gray);
		border: 1px solid var(--color-gray-border);
		transition: all var(--transition-fast);
	}

	.topbar-logout:hover {
		color: var(--color-terracotta);
		border-color: var(--color-terracotta);
		background-color: var(--color-terracotta-subtle);
	}

	.topbar-logout svg {
		width: 18px;
		height: 18px;
	}

	.page-body {
		padding: 2.25rem 2.5rem;
		flex: 1;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 900px) {
		.mobile-toggle {
			display: block;
		}

		.sidebar {
			position: fixed;
			left: 0;
			top: 0;
			bottom: 0;
			z-index: 100;
			transform: translateX(-100%);
		}

		.sidebar.mobile-open {
			transform: translateX(0);
		}

		.page-body {
			padding: 1.5rem;
		}
	}
</style>
