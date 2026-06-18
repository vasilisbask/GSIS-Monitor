<script>
	import { onMount, onDestroy } from 'svelte';
	import Chart from 'chart.js/auto';

	const API_BASE = 'http://localhost:8000';

	let summary = $state({
		total_services: 0,
		active_services: 0,
		healthy_services: 0,
		unhealthy_services: 0,
		active_alerts: 0,
		average_response_time_ms: 0.0,
		services: []
	});

	let selectedService = $state(null);
	let selectedRange = $state('24h');
	let serviceLogs = $state([]);
	let isLoadingLogs = $state(false);
	let isLoadingSummary = $state(true);
	let logsError = $state(null);
	let lastRefreshed = $state(null);

	let chartCanvas = $state(null);
	let chartInstance = null;
	let pollInterval = null;

	async function loadSummary() {
		try {
			const res = await fetch(`${API_BASE}/api/dashboard/summary`);
			if (!res.ok) throw new Error('Failed to load summary');
			summary = await res.json();
			lastRefreshed = new Date();
			if (summary.services.length > 0 && !selectedService) {
				selectService(summary.services[0]);
			} else if (selectedService) {
				const updated = summary.services.find(s => s.id === selectedService.id);
				if (updated) selectedService = updated;
			}
		} catch (e) {
			console.error(e);
		} finally {
			isLoadingSummary = false;
		}
	}

	function selectService(service) {
		selectedService = service;
		loadLogs();
	}

	function changeRange(range) {
		selectedRange = range;
		loadLogs();
	}

	async function loadLogs() {
		if (!selectedService) return;
		isLoadingLogs = true;
		logsError = null;
		try {
			const res = await fetch(`${API_BASE}/api/services/${selectedService.id}/logs?range=${selectedRange}`);
			if (!res.ok) throw new Error('Failed to load logs');
			serviceLogs = await res.json();
			renderChart();
		} catch (e) {
			logsError = e.message;
		} finally {
			isLoadingLogs = false;
		}
	}

	async function manualRefresh() {
		isLoadingSummary = true;
		await Promise.all([loadSummary(), loadLogs()]);
	}

	function formatLabel(timeStr) {
		const d = new Date(timeStr);
		const now = new Date();
		const isToday = d.toDateString() === now.toDateString();
		const timePart = d.toLocaleTimeString('el-GR', { hour: '2-digit', minute: '2-digit' });
		if (selectedRange === '1h' || selectedRange === '6h' || isToday) return timePart;
		return `${d.getDate()}/${d.getMonth() + 1} ${timePart}`;
	}

	function formatLastRefreshed(d) {
		if (!d) return '';
		return d.toLocaleTimeString('el-GR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
	}

	// Uptime percentage from logs
	function uptimePercent(logs) {
		if (!logs || logs.length === 0) return null;
		const healthy = logs.filter(l => l.is_healthy).length;
		return ((healthy / logs.length) * 100).toFixed(1);
	}

	function renderChart() {
		if (!chartCanvas) return;
		if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
		if (serviceLogs.length === 0) return;

		let sampled = [...serviceLogs];
		const maxBars = 60;
		if (sampled.length > maxBars) {
			const step = Math.ceil(sampled.length / maxBars);
			sampled = sampled.filter((_, i) => i % step === 0);
		}

		const labels  = sampled.map(l => formatLabel(l.time));
		const dnsData  = sampled.map(l => l.dns_lookup_ms  || 0);
		const tcpData  = sampled.map(l => l.tcp_connect_ms || 0);
		const tlsData  = sampled.map(l => l.tls_handshake_ms || 0);
		const ttfbData = sampled.map(l => {
			const ttfb = l.ttfb_ms || 0;
			const base = (l.dns_lookup_ms || 0) + (l.tcp_connect_ms || 0) + (l.tls_handshake_ms || 0);
			const rem  = ttfb - base;
			return rem > 0 ? rem : ttfb;
		});

		chartInstance = new Chart(chartCanvas, {
			type: 'bar',
			data: {
				labels,
				datasets: [
					{ label: 'DNS Lookup (ms)',      data: dnsData,  backgroundColor: '#0188ca', borderWidth: 0 },
					{ label: 'TCP Connect (ms)',      data: tcpData,  backgroundColor: '#6b7280', borderWidth: 0 },
					{ label: 'TLS Handshake (ms)',    data: tlsData,  backgroundColor: '#ed5929', borderWidth: 0 },
					{ label: 'TTFB / Processing (ms)',data: ttfbData, backgroundColor: '#9ca3af', borderWidth: 0 }
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				scales: {
					x: {
						stacked: true,
						grid: { display: false },
						ticks: { font: { size: 10, family: 'Inter' }, color: '#9ca3af', maxTicksLimit: 12 }
					},
					y: {
						stacked: true,
						title: { display: true, text: 'ms', font: { size: 11, weight: '600' }, color: '#6b7280' },
						ticks: { font: { size: 10 }, color: '#9ca3af' },
						grid: { color: '#f3f4f6' }
					}
				},
				plugins: {
					legend: {
						position: 'bottom',
						labels: { boxWidth: 10, boxHeight: 10, font: { size: 11 }, padding: 16, color: '#4b5563' }
					},
					tooltip: {
						mode: 'index',
						intersect: false,
						backgroundColor: '#111827',
						titleColor: '#f9fafb',
						bodyColor: '#d1d5db',
						borderColor: '#374151',
						borderWidth: 1,
						padding: 12,
						callbacks: {
							label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)} ms`
						}
					}
				},
				animation: { duration: 300 }
			}
		});
	}

	onMount(() => {
		loadSummary();
		pollInterval = setInterval(loadSummary, 15000);
	});

	onDestroy(() => {
		if (pollInterval) clearInterval(pollInterval);
		if (chartInstance) chartInstance.destroy();
	});

	$effect(() => {
		if (chartCanvas && serviceLogs.length > 0) {
			selectedRange;
			renderChart();
		}
	});

	// Compute total uptime across logs (for selected service)
	let uptimePct = $derived(uptimePercent(serviceLogs));

	// Health class for response time coloring
	function latencyClass(ms) {
		if (ms === null || ms === undefined) return '';
		if (ms < 500)  return 'latency-good';
		if (ms < 2000) return 'latency-warn';
		return 'latency-bad';
	}
</script>

<div class="container">

	<!-- Page Header -->
	<div class="page-header">
		<div>
			<h2 class="page-title">Επισκόπηση Διαθεσιμότητας</h2>
			<p class="page-subtitle">Ζωντανή παρακολούθηση και τηλεμετρία υπηρεσιών σε πραγματικό χρόνο.</p>
		</div>
		<button class="refresh-btn" onclick={manualRefresh} disabled={isLoadingSummary || isLoadingLogs} title="Χειροκίνητη Ανανέωση">
			<svg class={isLoadingSummary || isLoadingLogs ? 'spinning' : ''} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<polyline points="23 4 23 10 17 10"></polyline>
				<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
			</svg>
			{#if isLoadingSummary || isLoadingLogs}
				Ανανέωση...
			{:else if lastRefreshed}
				Ανανεώθηκε {formatLastRefreshed(lastRefreshed)}
			{:else}
				Ανανέωση
			{/if}
		</button>
	</div>

	<!-- KPI Cards -->
	<div class="metrics-grid">

		<div class="metric-card">
			<div class="metric-icon-wrap icon-blue">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect>
					<rect x="3" y="14" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect>
				</svg>
			</div>
			<div class="metric-body">
				<span class="metric-label">ΣΥΝΟΛΟ ΠΥΛΩΝ</span>
				<span class="metric-value">{isLoadingSummary ? '—' : summary.total_services}</span>
				<span class="metric-sub">Ενεργές: <strong>{summary.active_services}</strong></span>
			</div>
		</div>

		<div class="metric-card metric-card--success">
			<div class="metric-icon-wrap icon-green">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
					<polyline points="22 4 12 14.01 9 11.01"></polyline>
				</svg>
			</div>
			<div class="metric-body">
				<span class="metric-label">ΛΕΙΤΟΥΡΓΟΥΝ</span>
				<span class="metric-value text-success">{isLoadingSummary ? '—' : summary.healthy_services}</span>
				<span class="metric-sub">Υγιείς πύλες</span>
			</div>
		</div>

		<div class="metric-card" class:metric-card--error={summary.unhealthy_services > 0}>
			<div class="metric-icon-wrap icon-red">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="12" cy="12" r="10"></circle>
					<line x1="15" y1="9" x2="9" y2="15"></line>
					<line x1="9" y1="9" x2="15" y2="15"></line>
				</svg>
			</div>
			<div class="metric-body">
				<span class="metric-label">ΕΚΤΟΣ ΛΕΙΤΟΥΡΓΙΑΣ</span>
				<span class="metric-value" class:text-error={summary.unhealthy_services > 0} class:text-muted={summary.unhealthy_services === 0}>
					{isLoadingSummary ? '—' : summary.unhealthy_services}
				</span>
				<span class="metric-sub">Απαιτούν προσοχή</span>
			</div>
		</div>

		<div class="metric-card" class:metric-card--warning={summary.active_alerts > 0}>
			<div class="metric-icon-wrap icon-orange">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
					<path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
				</svg>
			</div>
			<div class="metric-body">
				<span class="metric-label">ΕΝΕΡΓΕΣ ΕΙΔΟΠΟΙΗΣΕΙΣ</span>
				<span class="metric-value" class:text-warning={summary.active_alerts > 0} class:text-muted={summary.active_alerts === 0}>
					{isLoadingSummary ? '—' : summary.active_alerts}
				</span>
				<span class="metric-sub">Alert logs</span>
			</div>
		</div>

		<div class="metric-card">
			<div class="metric-icon-wrap icon-blue">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="12" cy="12" r="10"></circle>
					<polyline points="12 6 12 12 16 14"></polyline>
				</svg>
			</div>
			<div class="metric-body">
				<span class="metric-label">Μέση Απόκριση</span>
				<span class="metric-value text-primary">{isLoadingSummary ? '—' : summary.average_response_time_ms} <span class="metric-unit">ms</span></span>
				<span class="metric-sub">Τελευταίο 24h</span>
			</div>
		</div>

	</div>

	<!-- Dashboard body -->
	<div class="dashboard-layout">

		<!-- Services list -->
		<div class="services-column">
			<div class="column-header">
				<h3 class="column-title">Κατάσταση Υπηρεσιών</h3>
				{#if summary.services.length > 0}
					<span class="count-badge">{summary.services.length}</span>
				{/if}
			</div>

			{#if isLoadingSummary}
				<div class="services-list">
					{#each {length: 3} as _}
						<div class="service-card skeleton-card">
							<div class="skeleton" style="height:1rem;width:60%;margin-bottom:0.5rem"></div>
							<div class="skeleton" style="height:0.75rem;width:80%"></div>
						</div>
					{/each}
				</div>
			{:else if summary.services.length === 0}
				<div class="empty-services">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<circle cx="12" cy="12" r="10"></circle>
						<line x1="12" y1="8" x2="12" y2="12"></line>
						<line x1="12" y1="16" x2="12.01" y2="16"></line>
					</svg>
					<p>Δεν υπάρχουν καταχωρημένες υπηρεσίες.</p>
					<a href="/services" class="empty-link">Προσθήκη υπηρεσίας</a>
				</div>
			{:else}
				<div class="services-list">
					{#each summary.services as service (service.id)}
						<button
							class="service-card"
							class:active={selectedService && selectedService.id === service.id}
							class:unhealthy={!service.is_healthy && service.is_active}
							onclick={() => selectService(service)}
						>
							<div class="service-card-header">
								<span class="service-name">{service.name}</span>
								<span class="status-badge" class:healthy={service.is_healthy} class:unhealthy={!service.is_healthy && service.is_active} class:inactive={!service.is_active}>
									<span class="status-dot" class:healthy={service.is_healthy} class:unhealthy={!service.is_healthy && service.is_active} class:inactive={!service.is_active}></span>
									{#if !service.is_active}ΑΝΕΝΕΡΓΗ{:else if service.is_healthy}ONLINE{:else}OFFLINE{/if}
								</span>
							</div>

							<div class="service-url">{service.url}</div>

							<div class="service-metrics">
								<div class="svc-metric">
									<span class="svc-metric-label">Απόκριση</span>
									<span class="svc-metric-val {latencyClass(service.last_response_time_ms)}">
										{service.last_response_time_ms ? `${service.last_response_time_ms.toFixed(0)} ms` : '—'}
									</span>
								</div>
								<div class="svc-metric">
									<span class="svc-metric-label">HTTP</span>
									<span class="svc-metric-val">{service.last_status_code ?? '—'}</span>
								</div>
								{#if service.ssl_expiry_days !== null}
									<div class="svc-metric">
										<span class="svc-metric-label">SSL</span>
										<span class="svc-metric-val" class:text-error={service.ssl_expiry_days < 15} class:text-warning={service.ssl_expiry_days < 30 && service.ssl_expiry_days >= 15}>
											{service.ssl_expiry_days}ημ.
										</span>
									</div>
								{/if}
							</div>

							{#if service.active_alerts_count > 0}
								<div class="alert-pill">
									{service.active_alerts_count} ενεργ{service.active_alerts_count === 1 ? 'ή' : 'ές'} ειδοποίηση
								</div>
							{/if}
						</button>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Chart panel -->
		<div class="chart-column">
			<div class="chart-card">
				{#if selectedService}
					<div class="chart-header">
						<div class="chart-title-group">
							<h3 class="chart-title">Ανάλυση Καθυστέρησης</h3>
							<p class="chart-subtitle">
								<strong>{selectedService.name}</strong>
								&mdash; DNS · TCP · TLS · TTFB (ms)
								{#if uptimePct !== null}
									<span class="uptime-tag" class:uptime-ok={uptimePct >= 99} class:uptime-warn={uptimePct < 99 && uptimePct >= 90} class:uptime-bad={uptimePct < 90}>
										Uptime {uptimePct}%
									</span>
								{/if}
							</p>
						</div>
						<div class="range-selector" role="group" aria-label="Εύρος χρόνου">
							{#each ['1h','6h','24h','7d'] as r}
								<button
									class:active={selectedRange === r}
									onclick={() => changeRange(r)}
									aria-pressed={selectedRange === r}
								>{r}</button>
							{/each}
						</div>
					</div>

					<div class="chart-wrapper">
						{#if isLoadingLogs}
							<div class="chart-overlay">
								<span class="spinner"></span>
								<span>Φόρτωση δεδομένων...</span>
							</div>
						{/if}
						{#if logsError}
							<div class="chart-overlay error">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:2rem;height:2rem">
									<circle cx="12" cy="12" r="10"></circle>
									<line x1="12" y1="8" x2="12" y2="12"></line>
									<line x1="12" y1="16" x2="12.01" y2="16"></line>
								</svg>
								Σφάλμα: {logsError}
							</div>
						{/if}
						{#if !isLoadingLogs && !logsError && serviceLogs.length === 0}
							<div class="chart-overlay">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:2.5rem;height:2.5rem;color:var(--text-muted)">
									<line x1="18" y1="20" x2="18" y2="10"></line>
									<line x1="12" y1="20" x2="12" y2="4"></line>
									<line x1="6"  y1="20" x2="6"  y2="14"></line>
								</svg>
								Δεν βρέθηκαν δεδομένα για αυτή την περίοδο.
							</div>
						{/if}
						<canvas bind:this={chartCanvas}></canvas>
					</div>

				{:else}
					<div class="no-selection">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
						</svg>
						<p>Επιλέξτε υπηρεσία για να δείτε τα γραφήματα τηλεμετρίας.</p>
					</div>
				{/if}
			</div>
		</div>

	</div>
</div>
