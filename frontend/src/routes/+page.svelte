<script>
	// Public Customer Landing Page
	// SvelteKit JavaScript only - No TypeScript
</script>

<svelte:head>
	<title>Face ATM — Next-Gen Biometric Banking & Customer Terminal</title>
	<meta
		name="description"
		content="Next-generation cardless Face ATM banking powered by YuNet facial landmark detection and SFace 128-dimensional biometric authentication."
	/>
</svelte:head>

<div class="landing-page">
	<!-- Public Navigation Bar -->
	<header class="navbar">
		<div class="nav-container">
			<a href="/" class="brand-group" aria-label="Face ATM Home">
				<div class="brand-icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<rect x="2" y="5" width="20" height="14" rx="3"></rect>
						<circle cx="12" cy="12" r="3.5"></circle>
						<path d="M12 2v3"></path>
						<path d="M12 19v3"></path>
					</svg>
				</div>
				<div class="brand-info">
					<span class="brand-title">Face ATM</span>
					<span class="brand-tag">Biometric Banking</span>
				</div>
			</a>

			<nav class="nav-links" aria-label="Main Navigation">
				<a href="#features" class="nav-link">Features</a>
				<a href="#how-it-works" class="nav-link">How It Works</a>
				<a href="#security" class="nav-link">Security</a>
			</nav>

			<div class="nav-actions">
				<a href="/login" class="btn-admin" title="Administrator Control Portal">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
						<circle cx="9" cy="7" r="4"></circle>
						<polyline points="16 11 18 13 22 9"></polyline>
					</svg>
					<span>Admin Portal</span>
				</a>
				<a href="/atm" class="btn-start-nav">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="3"></circle>
						<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
						<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
						<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
						<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
					</svg>
					<span>Start ATM</span>
				</a>
			</div>
		</div>
	</header>

	<!-- Hero Section -->
	<section class="hero-section">
		<div class="hero-container">
			<div class="hero-content">
				<div class="hero-badge">
					<span class="pulse-dot"></span>
					<span>LIVE BIOMETRIC TERMINAL &bull; YUNET + SFACE ONNX</span>
				</div>

				<h1 class="hero-title">
					Cardless Biometric <br />
					<span class="highlight-teal">Face ATM Banking</span>
				</h1>

				<p class="hero-description">
					Experience frictionless ATM banking. Authenticate in sub-seconds using AI-driven
					3D facial geometry and anti-spoofing defense. Step up to the terminal, verify your face,
					and securely withdraw or deposit funds.
				</p>

				<!-- Clear Customer Start Button as explicitly requested -->
				<div class="hero-cta-group">
					<a href="/atm" class="btn-customer-start" id="customer-start-btn">
						<div class="btn-icon-wrapper">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
								<circle cx="12" cy="12" r="3.2"></circle>
								<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
								<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
								<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
								<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
							</svg>
						</div>
						<div class="btn-text-wrapper">
							<span class="btn-primary-text">Start ATM / Customer Login</span>
							<span class="btn-sub-text">Card Number &amp; Face Authentication &rarr;</span>
						</div>
					</a>

					<a href="/login" class="btn-secondary-hero">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
							<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
						</svg>
						<span>Admin Login</span>
					</a>
				</div>

				<div class="hero-trust-bar">
					<div class="trust-item">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
							<polyline points="9 12 11 14 15 10"></polyline>
						</svg>
						<span>MiniFASNetV2 Anti-Spoofing</span>
					</div>
					<div class="trust-item">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
							<polyline points="22 4 12 14.01 9 11.01"></polyline>
						</svg>
						<span>128-D Biometric Embeddings</span>
					</div>
					<div class="trust-item">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
							<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
						</svg>
						<span>AES-256 PII Encryption</span>
					</div>
				</div>
			</div>

			<!-- Hero Interactive Card Preview -->
			<div class="hero-visual">
				<div class="terminal-preview-card">
					<div class="tpc-header">
						<div class="tpc-badge">FACE ATM TERMINAL #01</div>
						<div class="tpc-status">
							<span class="status-live-dot"></span>
							<span>SENSOR READY</span>
						</div>
					</div>

					<div class="smart-card-mockup">
						<div class="scm-top">
							<span class="scm-chip-text">FACE ATM SMART</span>
							<div class="scm-nfc">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M5 8.5a8 8 0 0 1 14 0"></path>
									<path d="M8 12a4 4 0 0 1 8 0"></path>
								</svg>
							</div>
						</div>
						<div class="scm-emv-chip"></div>
						<div class="scm-card-number">5049 &bull;&bull;&bull;&bull; &bull;&bull;&bull;&bull; 8920</div>
						<div class="scm-bottom">
							<div>
								<div class="scm-label">CARDHOLDER</div>
								<div class="scm-val">VERIFIED CUSTOMER</div>
							</div>
							<div class="scm-biometric-flag">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<circle cx="12" cy="12" r="3"></circle>
									<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
									<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
								</svg>
								<span>BIOMETRIC ENROLLED</span>
							</div>
						</div>
					</div>

					<div class="scanner-status-box">
						<div class="radar-circle">
							<div class="radar-ping"></div>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<circle cx="12" cy="12" r="3.5"></circle>
								<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
								<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
								<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
								<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
							</svg>
						</div>
						<div class="scanner-text">
							<div class="scanner-title">Face Verification Pipeline</div>
							<div class="scanner-sub">YuNet Face Alignment &bull; SFace Matcher &bull; MiniFASNet</div>
						</div>
					</div>

					<a href="/atm" class="tpc-direct-btn">
						<span>Launch Terminal Interface</span>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<polyline points="9 18 15 12 9 6"></polyline>
						</svg>
					</a>
				</div>
			</div>
		</div>
	</section>

	<!-- Metric Highlights Bar -->
	<section class="metrics-bar">
		<div class="metrics-container">
			<div class="metric-block">
				<div class="metric-number">&lt; 1.2s</div>
				<div class="metric-label">Biometric Verification</div>
			</div>
			<div class="metric-divider"></div>
			<div class="metric-block">
				<div class="metric-number">128-D</div>
				<div class="metric-label">SFace Facial Embeddings</div>
			</div>
			<div class="metric-divider"></div>
			<div class="metric-block">
				<div class="metric-number">100%</div>
				<div class="metric-label">Cardless Convenience</div>
			</div>
			<div class="metric-divider"></div>
			<div class="metric-block">
				<div class="metric-number">AES-256</div>
				<div class="metric-label">Encrypted PII Storage</div>
			</div>
		</div>
	</section>

	<!-- How It Works Section -->
	<section class="how-it-works-section" id="how-it-works">
		<div class="section-container">
			<div class="section-header">
				<span class="section-tag">Frictionless 3-Step Flow</span>
				<h2 class="section-heading">How Customer Face ATM Works</h2>
				<p class="section-description">
					Banking made as simple as looking into a screen. Zero physical cards to swipe, no PINs to leak.
				</p>
			</div>

			<div class="steps-grid">
				<div class="step-card">
					<div class="step-number">01</div>
					<div class="step-icon">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="2" y="5" width="20" height="14" rx="2"></rect>
							<line x1="2" y1="10" x2="22" y2="10"></line>
						</svg>
					</div>
					<h3 class="step-title">Enter Card Number</h3>
					<p class="step-text">
						Type your unique 16-digit Face ATM card identifier received during biometric registration.
					</p>
				</div>

				<div class="step-card">
					<div class="step-number">02</div>
					<div class="step-icon">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="3.2"></circle>
							<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
							<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
							<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
							<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
						</svg>
					</div>
					<h3 class="step-title">Face Biometric Scan</h3>
					<p class="step-text">
						Align your face inside the camera frame. YuNet detects landmarks and SFace compares feature embeddings.
					</p>
				</div>

				<div class="step-card">
					<div class="step-number">03</div>
					<div class="step-icon">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<line x1="12" y1="1" x2="12" y2="23"></line>
							<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
						</svg>
					</div>
					<h3 class="step-title">Instant Transactions</h3>
					<p class="step-text">
						View real-time account balance, execute cash withdrawals, or deposit funds with immediate receipt receipts.
					</p>
				</div>
			</div>
		</div>
	</section>

	<!-- Features Grid Section -->
	<section class="features-section" id="features">
		<div class="section-container">
			<div class="section-header">
				<span class="section-tag">Modern Banking Standards</span>
				<h2 class="section-heading">Engineered for Maximum Security &amp; Speed</h2>
				<p class="section-description">
					A complete biometric authentication infrastructure designed to protect customers against fraud.
				</p>
			</div>

			<div class="features-grid">
				<div class="feature-card">
					<div class="feature-icon teal">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
							<polyline points="9 12 11 14 15 10"></polyline>
						</svg>
					</div>
					<h3 class="feature-title">MiniFASNet Liveness Defense</h3>
					<p class="feature-text">
						Deep convolutional neural anti-spoofing rejects photo cutouts, tablet playback, and 3D silicone mask impersonations.
					</p>
				</div>

				<div class="feature-card">
					<div class="feature-icon navy">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="3"></circle>
							<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
							<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
							<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
							<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
						</svg>
					</div>
					<h3 class="feature-title">YuNet + SFace ONNX Engine</h3>
					<p class="feature-text">
						Sub-millisecond facial landmark extraction coupled with 128-dimensional cosine feature comparison.
					</p>
				</div>

				<div class="feature-card">
					<div class="feature-icon green">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
							<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
						</svg>
					</div>
					<h3 class="feature-title">AES-256-GCM Encryption</h3>
					<p class="feature-text">
						All Aadhaar numbers, phone records, and bank accounts are encrypted with authenticated AES-256 ciphers.
					</p>
				</div>

				<div class="feature-card">
					<div class="feature-icon teal">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="10"></circle>
							<line x1="12" y1="8" x2="12" y2="12"></line>
							<line x1="12" y1="16" x2="12.01" y2="16"></line>
						</svg>
					</div>
					<h3 class="feature-title">Automated Lockout &amp; Fraud Rules</h3>
					<p class="feature-text">
						Consecutive failed biometric attempts trigger instantaneous session lockouts and administrator review alerts.
					</p>
				</div>

				<div class="feature-card">
					<div class="feature-icon navy">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
							<polyline points="22,6 12,13 2,6"></polyline>
						</svg>
					</div>
					<h3 class="feature-title">SMTP Automated Dispatch</h3>
					<p class="feature-text">
						Cryptographic 6-digit OTP verification and automated card delivery directly through secure Gmail SMTP channels.
					</p>
				</div>

				<div class="feature-card">
					<div class="feature-icon green">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
						</svg>
					</div>
					<h3 class="feature-title">Dual-Tier Security Approvals</h3>
					<p class="feature-text">
						Marginal biometric match scores require explicit supervisor clearance from the admin security console.
					</p>
				</div>
			</div>
		</div>
	</section>

	<!-- Ready to Start CTA Banner -->
	<section class="cta-banner-section" id="security">
		<div class="cta-banner-container">
			<div class="cta-banner-content">
				<h2 class="cta-banner-title">Ready to Experience Face ATM?</h2>
				<p class="cta-banner-subtitle">
					Click below to start your customer ATM session. Zero cards required.
				</p>
				<div class="cta-banner-actions">
					<a href="/atm" class="btn-primary cta-action-btn">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<circle cx="12" cy="12" r="3"></circle>
							<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
							<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
							<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
							<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
						</svg>
						<span>Start ATM / Customer Login</span>
					</a>
					<a href="/login" class="btn-secondary cta-admin-btn">
						<span>Administrator Access</span>
					</a>
				</div>
			</div>
		</div>
	</section>

	<!-- Public Footer -->
	<footer class="footer">
		<div class="footer-container">
			<div class="footer-col brand-col">
				<div class="brand-group">
					<div class="brand-icon small">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="2" y="5" width="20" height="14" rx="3"></rect>
							<circle cx="12" cy="12" r="3.5"></circle>
						</svg>
					</div>
					<span class="brand-title">Face ATM</span>
				</div>
				<p class="footer-desc">
					Secure face authentication and customer banking transaction system. Powered by OpenCV YuNet and SFace.
				</p>
			</div>

			<div class="footer-col">
				<h4 class="footer-heading">Customer Services</h4>
				<ul class="footer-links">
					<li><a href="/atm">Launch Customer ATM</a></li>
					<li><a href="#how-it-works">How Biometrics Work</a></li>
					<li><a href="#features">Security Specifications</a></li>
				</ul>
			</div>

			<div class="footer-col">
				<h4 class="footer-heading">Administrative</h4>
				<ul class="footer-links">
					<li><a href="/login">Admin Sign In</a></li>
					<li><a href="/admin/dashboard">System Dashboard</a></li>
					<li><a href="/admin/register">Customer Registration</a></li>
				</ul>
			</div>
		</div>

		<div class="footer-bottom">
			<div class="footer-bottom-container">
				<p>&copy; 2026 Face ATM Biometric Banking System. Built with FastAPI, SFace, and SvelteKit.</p>
				<div class="footer-compliance">
					<span class="compliance-badge">AES-256 Protected</span>
					<span class="compliance-badge">YuNet 0.40 Threshold</span>
				</div>
			</div>
		</div>
	</footer>
</div>

<style>
	/* Landing Page Layout and Modern Banking Styles */
	.landing-page {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		background-color: var(--color-bg-light);
		color: var(--color-text);
		animation: fadeIn 0.4s ease-out;
	}

	/* Top Navigation Bar */
	.navbar {
		position: sticky;
		top: 0;
		z-index: 100;
		background: rgba(255, 255, 255, 0.92);
		backdrop-filter: blur(12px);
		border-bottom: 1px solid var(--color-border);
		transition: all var(--transition-normal);
	}

	.nav-container {
		max-width: 1240px;
		margin: 0 auto;
		padding: 1rem 1.75rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.5rem;
	}

	.brand-group {
		display: flex;
		align-items: center;
		gap: 0.85rem;
	}

	.brand-icon {
		width: 44px;
		height: 44px;
		background: linear-gradient(135deg, var(--color-navy) 0%, var(--color-teal) 100%);
		border-radius: var(--radius-md);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-white);
		box-shadow: 0 4px 12px rgba(16, 24, 40, 0.15);
	}

	.brand-icon svg {
		width: 24px;
		height: 24px;
	}

	.brand-icon.small {
		width: 32px;
		height: 32px;
	}

	.brand-icon.small svg {
		width: 18px;
		height: 18px;
	}

	.brand-info {
		display: flex;
		flex-direction: column;
	}

	.brand-title {
		font-family: var(--font-heading);
		font-size: 1.3rem;
		font-weight: 800;
		color: var(--color-navy);
		line-height: 1.2;
	}

	.brand-tag {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-weight: 700;
		color: var(--color-teal);
	}

	.nav-links {
		display: flex;
		align-items: center;
		gap: 2rem;
	}

	.nav-link {
		font-size: 0.92rem;
		font-weight: 600;
		color: var(--color-text-muted);
		transition: color var(--transition-fast);
	}

	.nav-link:hover {
		color: var(--color-teal);
	}

	.nav-actions {
		display: flex;
		align-items: center;
		gap: 0.85rem;
	}

	.btn-admin {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text-muted);
		padding: 0.55rem 0.95rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-white);
		transition: all var(--transition-fast);
	}

	.btn-admin:hover {
		color: var(--color-navy);
		border-color: var(--color-navy);
		transform: translateY(-1px);
	}

	.btn-admin svg {
		width: 15px;
		height: 15px;
	}

	.btn-start-nav {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.88rem;
		font-weight: 700;
		color: var(--color-white);
		background-color: var(--color-teal);
		padding: 0.55rem 1.15rem;
		border-radius: var(--radius-md);
		box-shadow: 0 2px 8px rgba(15, 118, 110, 0.25);
		transition: all var(--transition-fast);
	}

	.btn-start-nav:hover {
		background-color: var(--color-teal-hover);
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(15, 118, 110, 0.35);
	}

	.btn-start-nav svg {
		width: 16px;
		height: 16px;
	}

	/* Hero Section */
	.hero-section {
		padding: 4.5rem 1.75rem 4rem;
		position: relative;
		overflow: hidden;
	}

	.hero-container {
		max-width: 1240px;
		margin: 0 auto;
		display: grid;
		grid-template-columns: 1.15fr 0.85fr;
		gap: 3.5rem;
		align-items: center;
	}

	.hero-content {
		animation: slideUp 0.5s ease-out;
	}

	.hero-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		background: var(--color-teal-subtle);
		color: var(--color-teal);
		padding: 0.4rem 0.9rem;
		border-radius: var(--radius-full);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		margin-bottom: 1.25rem;
		border: 1px solid rgba(15, 118, 110, 0.2);
	}

	.pulse-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background-color: var(--color-accent-green);
		animation: pulseGlow 2s infinite;
	}

	.hero-title {
		font-size: 3.25rem;
		line-height: 1.15;
		color: var(--color-navy);
		margin-bottom: 1.25rem;
		letter-spacing: -0.03em;
	}

	.highlight-teal {
		color: var(--color-teal);
		background: linear-gradient(135deg, var(--color-teal) 0%, #14b8a6 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
	}

	.hero-description {
		font-size: 1.12rem;
		color: var(--color-text-muted);
		line-height: 1.65;
		margin-bottom: 2.25rem;
		max-width: 580px;
	}

	/* Hero CTA Group */
	.hero-cta-group {
		display: flex;
		align-items: center;
		gap: 1.25rem;
		flex-wrap: wrap;
		margin-bottom: 2.5rem;
	}

	/* Prominent Start ATM / Customer Login Button */
	.btn-customer-start {
		display: inline-flex;
		align-items: center;
		gap: 1rem;
		background: linear-gradient(135deg, var(--color-teal) 0%, #0d655e 100%);
		color: var(--color-white);
		padding: 1.05rem 1.85rem;
		border-radius: var(--radius-lg);
		box-shadow: 0 8px 24px rgba(15, 118, 110, 0.35);
		transition: all var(--transition-normal);
		text-decoration: none;
		position: relative;
	}

	.btn-customer-start:hover {
		transform: translateY(-3px);
		box-shadow: 0 12px 32px rgba(15, 118, 110, 0.45);
		background: linear-gradient(135deg, #115e59 0%, #0a4f49 100%);
	}

	.btn-customer-start:active {
		transform: translateY(0);
	}

	.btn-icon-wrapper {
		width: 44px;
		height: 44px;
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.16);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--color-white);
		flex-shrink: 0;
	}

	.btn-icon-wrapper svg {
		width: 24px;
		height: 24px;
	}

	.btn-text-wrapper {
		display: flex;
		flex-direction: column;
		text-align: left;
	}

	.btn-primary-text {
		font-size: 1.1rem;
		font-weight: 700;
		letter-spacing: -0.01em;
	}

	.btn-sub-text {
		font-size: 0.78rem;
		opacity: 0.9;
		font-weight: 500;
	}

	.btn-secondary-hero {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		background: var(--color-white);
		color: var(--color-navy);
		border: 1.5px solid var(--color-border);
		padding: 1.15rem 1.65rem;
		border-radius: var(--radius-lg);
		font-weight: 600;
		font-size: 1rem;
		box-shadow: var(--shadow-sm);
		transition: all var(--transition-normal);
	}

	.btn-secondary-hero:hover {
		border-color: var(--color-navy);
		color: var(--color-navy);
		transform: translateY(-2px);
		box-shadow: var(--shadow-md);
	}

	.btn-secondary-hero svg {
		width: 18px;
		height: 18px;
	}

	.hero-trust-bar {
		display: flex;
		align-items: center;
		gap: 1.75rem;
		flex-wrap: wrap;
		padding-top: 1.5rem;
		border-top: 1px solid var(--color-border);
	}

	.trust-item {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.trust-item svg {
		width: 16px;
		height: 16px;
		color: var(--color-teal);
	}

	/* Hero Visual Mockup */
	.hero-visual {
		animation: slideUp 0.6s ease-out;
	}

	.terminal-preview-card {
		background: var(--color-white);
		border: 1px solid var(--color-border);
		border-radius: 24px;
		padding: 2rem;
		box-shadow: var(--shadow-lg);
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		transition: transform var(--transition-normal), box-shadow var(--transition-normal);
	}

	.terminal-preview-card:hover {
		transform: translateY(-4px);
		box-shadow: var(--shadow-hover);
	}

	.tpc-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.tpc-badge {
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.08em;
		color: var(--color-navy);
	}

	.tpc-status {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.75rem;
		font-weight: 700;
		color: #15803d;
		background: var(--color-accent-green-subtle);
		padding: 0.25rem 0.65rem;
		border-radius: var(--radius-full);
	}

	.status-live-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background-color: var(--color-accent-green);
	}

	/* Smart Card Styling */
	.smart-card-mockup {
		background: linear-gradient(135deg, var(--color-navy) 0%, #0d1e2e 100%);
		color: var(--color-white);
		border-radius: 16px;
		padding: 1.75rem 1.85rem;
		box-shadow: 0 10px 24px rgba(16, 24, 40, 0.25);
		border: 1px solid rgba(255, 255, 255, 0.12);
		position: relative;
		overflow: hidden;
	}

	.smart-card-mockup::before {
		content: '';
		position: absolute;
		top: -40px;
		right: -40px;
		width: 140px;
		height: 140px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(15, 118, 110, 0.4) 0%, transparent 70%);
	}

	.scm-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.scm-chip-text {
		font-size: 0.88rem;
		font-weight: 800;
		letter-spacing: 1.5px;
		color: #e2e8f0;
	}

	.scm-nfc svg {
		width: 22px;
		height: 22px;
		color: #94a3b8;
	}

	.scm-emv-chip {
		width: 38px;
		height: 28px;
		background: linear-gradient(135deg, #e2b755, #c29528);
		border-radius: 6px;
		margin: 1.25rem 0;
		box-shadow: inset 0 1px 2px rgba(255, 255, 255, 0.4);
	}

	.scm-card-number {
		font-family: monospace;
		font-size: 1.25rem;
		letter-spacing: 2px;
		font-weight: 600;
		margin-bottom: 1.25rem;
		color: #ffffff;
	}

	.scm-bottom {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
	}

	.scm-label {
		font-size: 0.65rem;
		color: #94a3b8;
		letter-spacing: 0.08em;
	}

	.scm-val {
		font-size: 0.85rem;
		font-weight: 700;
		color: #f1f5f9;
	}

	.scm-biometric-flag {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		background: rgba(15, 118, 110, 0.35);
		border: 1px solid rgba(15, 118, 110, 0.6);
		padding: 0.25rem 0.6rem;
		border-radius: 6px;
		font-size: 0.68rem;
		font-weight: 700;
		color: #a7f3d0;
	}

	.scm-biometric-flag svg {
		width: 14px;
		height: 14px;
	}

	/* Radar Scanner Box */
	.scanner-status-box {
		display: flex;
		align-items: center;
		gap: 1rem;
		background: var(--color-surface-subtle);
		border: 1px solid var(--color-border);
		padding: 1rem 1.25rem;
		border-radius: var(--radius-md);
	}

	.radar-circle {
		width: 44px;
		height: 44px;
		border-radius: 50%;
		background: var(--color-teal-subtle);
		color: var(--color-teal);
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		flex-shrink: 0;
	}

	.radar-ping {
		position: absolute;
		width: 100%;
		height: 100%;
		border-radius: 50%;
		border: 2px solid var(--color-teal);
		opacity: 0.6;
		animation: pulseGlow 2.5s infinite;
	}

	.radar-circle svg {
		width: 22px;
		height: 22px;
	}

	.scanner-text {
		display: flex;
		flex-direction: column;
	}

	.scanner-title {
		font-size: 0.92rem;
		font-weight: 700;
		color: var(--color-navy);
	}

	.scanner-sub {
		font-size: 0.78rem;
		color: var(--color-text-muted);
	}

	.tpc-direct-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		background: var(--color-navy);
		color: var(--color-white);
		padding: 0.85rem;
		border-radius: var(--radius-md);
		font-size: 0.92rem;
		font-weight: 600;
		text-decoration: none;
		transition: all var(--transition-fast);
	}

	.tpc-direct-btn:hover {
		background: #1e293b;
		transform: translateY(-1px);
	}

	.tpc-direct-btn svg {
		width: 16px;
		height: 16px;
	}

	/* Metrics Bar */
	.metrics-bar {
		background: var(--color-white);
		border-top: 1px solid var(--color-border);
		border-bottom: 1px solid var(--color-border);
		padding: 2.25rem 1.75rem;
	}

	.metrics-container {
		max-width: 1240px;
		margin: 0 auto;
		display: flex;
		align-items: center;
		justify-content: space-around;
		gap: 1.5rem;
		flex-wrap: wrap;
	}

	.metric-block {
		text-align: center;
	}

	.metric-number {
		font-family: var(--font-heading);
		font-size: 2.25rem;
		font-weight: 800;
		color: var(--color-navy);
		line-height: 1.1;
		margin-bottom: 0.25rem;
	}

	.metric-label {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.metric-divider {
		width: 1px;
		height: 48px;
		background: var(--color-border);
	}

	/* Steps Section */
	.how-it-works-section {
		padding: 5rem 1.75rem;
		background: var(--color-surface-subtle);
	}

	.section-container {
		max-width: 1240px;
		margin: 0 auto;
	}

	.section-header {
		text-align: center;
		max-width: 680px;
		margin: 0 auto 3.5rem;
	}

	.section-tag {
		display: inline-block;
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-teal);
		margin-bottom: 0.6rem;
	}

	.section-heading {
		font-size: 2.35rem;
		color: var(--color-navy);
		margin-bottom: 0.85rem;
		letter-spacing: -0.02em;
	}

	.section-description {
		font-size: 1.05rem;
		color: var(--color-text-muted);
		line-height: 1.6;
	}

	.steps-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 2rem;
	}

	.step-card {
		background: var(--color-white);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		padding: 2.25rem 2rem;
		box-shadow: var(--shadow-sm);
		position: relative;
		transition: all var(--transition-normal);
		display: flex;
		flex-direction: column;
	}

	.step-card:hover {
		transform: translateY(-4px);
		box-shadow: var(--shadow-md);
		border-color: rgba(15, 118, 110, 0.3);
	}

	.step-number {
		position: absolute;
		top: 1.5rem;
		right: 1.75rem;
		font-family: var(--font-heading);
		font-size: 2.25rem;
		font-weight: 800;
		color: #e2e8f0;
	}

	.step-icon {
		width: 52px;
		height: 52px;
		border-radius: var(--radius-md);
		background: var(--color-teal-subtle);
		color: var(--color-teal);
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 1.5rem;
	}

	.step-icon svg {
		width: 26px;
		height: 26px;
	}

	.step-title {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-navy);
		margin-bottom: 0.5rem;
	}

	.step-text {
		font-size: 0.95rem;
		color: var(--color-text-muted);
		line-height: 1.55;
	}

	/* Features Section */
	.features-section {
		padding: 5rem 1.75rem;
		background: var(--color-white);
	}

	.features-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
		gap: 2rem;
	}

	.feature-card {
		background: var(--color-bg-light);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-lg);
		padding: 2rem;
		transition: all var(--transition-normal);
	}

	.feature-card:hover {
		transform: translateY(-3px);
		box-shadow: var(--shadow-md);
		border-color: rgba(15, 118, 110, 0.3);
		background: var(--color-white);
	}

	.feature-icon {
		width: 48px;
		height: 48px;
		border-radius: var(--radius-md);
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 1.25rem;
	}

	.feature-icon.teal {
		background: var(--color-teal-subtle);
		color: var(--color-teal);
	}

	.feature-icon.navy {
		background: rgba(16, 24, 40, 0.08);
		color: var(--color-navy);
	}

	.feature-icon.green {
		background: var(--color-accent-green-subtle);
		color: #15803d;
	}

	.feature-icon svg {
		width: 24px;
		height: 24px;
	}

	.feature-title {
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--color-navy);
		margin-bottom: 0.5rem;
	}

	.feature-text {
		font-size: 0.92rem;
		color: var(--color-text-muted);
		line-height: 1.55;
	}

	/* CTA Banner Section */
	.cta-banner-section {
		padding: 4rem 1.75rem;
		background: var(--color-bg-light);
	}

	.cta-banner-container {
		max-width: 1240px;
		margin: 0 auto;
		background: linear-gradient(135deg, var(--color-navy) 0%, #0d1e2e 50%, var(--color-teal-dark) 100%);
		border-radius: 24px;
		padding: 3.5rem 3rem;
		color: var(--color-white);
		box-shadow: var(--shadow-lg);
		text-align: center;
		position: relative;
		overflow: hidden;
	}

	.cta-banner-container::before {
		content: '';
		position: absolute;
		top: -50px;
		right: -50px;
		width: 250px;
		height: 250px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(15, 118, 110, 0.3) 0%, transparent 70%);
	}

	.cta-banner-content {
		max-width: 650px;
		margin: 0 auto;
		position: relative;
		z-index: 1;
	}

	.cta-banner-title {
		font-size: 2.4rem;
		font-weight: 800;
		color: var(--color-white);
		margin-bottom: 0.85rem;
	}

	.cta-banner-subtitle {
		font-size: 1.1rem;
		color: #cbd5e1;
		margin-bottom: 2rem;
		line-height: 1.6;
	}

	.cta-banner-actions {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.cta-action-btn {
		font-size: 1.05rem;
		padding: 1rem 2rem;
		box-shadow: 0 4px 16px rgba(15, 118, 110, 0.4);
	}

	.cta-action-btn svg {
		width: 20px;
		height: 20px;
	}

	.cta-admin-btn {
		background: rgba(255, 255, 255, 0.12);
		color: var(--color-white);
		border-color: rgba(255, 255, 255, 0.25);
		font-size: 1.05rem;
		padding: 1rem 1.85rem;
	}

	.cta-admin-btn:hover {
		background: rgba(255, 255, 255, 0.2);
		border-color: var(--color-white);
		color: var(--color-white);
	}

	/* Footer */
	.footer {
		background: var(--color-white);
		border-top: 1px solid var(--color-border);
		padding-top: 4rem;
	}

	.footer-container {
		max-width: 1240px;
		margin: 0 auto;
		padding: 0 1.75rem 3rem;
		display: grid;
		grid-template-columns: 1.6fr 1fr 1fr;
		gap: 3rem;
	}

	.brand-col .footer-desc {
		font-size: 0.9rem;
		color: var(--color-text-muted);
		margin-top: 1rem;
		line-height: 1.6;
		max-width: 380px;
	}

	.footer-heading {
		font-size: 0.92rem;
		font-weight: 700;
		color: var(--color-navy);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		margin-bottom: 1.25rem;
	}

	.footer-links {
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.footer-links a {
		font-size: 0.9rem;
		color: var(--color-text-muted);
		transition: color var(--transition-fast);
	}

	.footer-links a:hover {
		color: var(--color-teal);
	}

	.footer-bottom {
		border-top: 1px solid var(--color-border);
		padding: 1.5rem 1.75rem;
	}

	.footer-bottom-container {
		max-width: 1240px;
		margin: 0 auto;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.5rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
		color: var(--color-text-light);
	}

	.footer-compliance {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.compliance-badge {
		background: var(--color-bg-light);
		padding: 0.25rem 0.6rem;
		border-radius: var(--radius-sm);
		border: 1px solid var(--color-border);
		font-weight: 600;
		font-size: 0.75rem;
	}

	/* Responsive Media Queries */
	@media (max-width: 1024px) {
		.hero-container {
			grid-template-columns: 1fr;
			text-align: center;
		}

		.hero-content {
			display: flex;
			flex-direction: column;
			align-items: center;
		}

		.hero-description {
			max-width: 100%;
		}

		.hero-cta-group {
			justify-content: center;
		}

		.hero-trust-bar {
			justify-content: center;
		}

		.steps-grid {
			grid-template-columns: 1fr;
		}

		.footer-container {
			grid-template-columns: 1fr;
			gap: 2rem;
		}
	}

	@media (max-width: 768px) {
		.nav-links {
			display: none;
		}

		.hero-title {
			font-size: 2.35rem;
		}

		.metric-divider {
			display: none;
		}

		.metrics-container {
			display: grid;
			grid-template-columns: 1fr 1fr;
		}

		.cta-banner-container {
			padding: 2.5rem 1.5rem;
		}

		.cta-banner-title {
			font-size: 1.85rem;
		}
	}
</style>
