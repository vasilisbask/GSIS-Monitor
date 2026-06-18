<script>
	import '../global.css';
	import { page } from '$app/state';

	let { children } = $props();

	// Live clock for header
	let now = $state(new Date());
	setInterval(() => { now = new Date(); }, 1000);

	function formatTime(d) {
		return d.toLocaleTimeString('el-GR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
	}
	function formatDate(d) {
		return d.toLocaleDateString('el-GR', { weekday: 'short', day: 'numeric', month: 'short' });
	}
</script>

<div class="app-layout">
	<header class="main-header">
		<div class="header-container">
			<div class="logo-area">
				<img src="/logo.png" alt="ΓΓΠΣΨΔ Logo" class="logo-img" />
				<div class="title-group">
					<h1 class="app-title">Σύστημα Παρακολούθησης Υπηρεσιών</h1>
				</div>
			</div>

			<div class="header-right">
				<div class="header-clock">
					<span class="clock-date">{formatDate(now)}</span>
					<span class="clock-time">{formatTime(now)}</span>
				</div>

				<nav class="main-nav">
					<a href="/" class="nav-link" class:active={page.url.pathname === '/'}>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect>
							<rect x="3" y="14" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect>
						</svg>
						Dashboard
					</a>
					<a href="/services" class="nav-link" class:active={page.url.pathname.startsWith('/services')}>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<circle cx="12" cy="12" r="10"></circle>
							<line x1="2" y1="12" x2="22" y2="12"></line>
							<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
						</svg>
						Υπηρεσίες
					</a>
					<a href="/alerts" class="nav-link" class:active={page.url.pathname.startsWith('/alerts')}>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
							<path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
						</svg>
						Ειδοποιήσεις
					</a>
				</nav>
			</div>
		</div>
	</header>

	<main class="main-content">
		{@render children()}
	</main>
	
</div>
