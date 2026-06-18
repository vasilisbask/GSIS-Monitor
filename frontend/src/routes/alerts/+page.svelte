<script>
	import { onMount } from 'svelte';

	const API_BASE = 'http://localhost:8000';

	let alerts = $state([]);
	let rules = $state([]);
	let services = $state([]);

	let isLoadingAlerts = $state(false);
	let isLoadingRules = $state(false);
	let error = $state(null);

	let formServiceId = $state('');
	let formMetric = $state('latency');
	let formOperator = $state('>');
	let formValue = $state(2500);
	let isSubmitting = $state(false);

	// Active/all filter
	let alertFilter = $state('all'); // 'all' | 'active' | 'resolved'

	let filteredAlerts = $derived(
		alertFilter === 'all'
			? alerts
			: alerts.filter(a => a.status === alertFilter)
	);

	async function loadAlerts() {
		isLoadingAlerts = true;
		try {
			const res = await fetch(`${API_BASE}/api/alerts`);
			if (!res.ok) throw new Error('Failed to load alert logs');
			alerts = await res.json();
			error = null;
		} catch (e) {
			error = e.message;
		} finally {
			isLoadingAlerts = false;
		}
	}

	async function loadRules() {
		isLoadingRules = true;
		try {
			const res = await fetch(`${API_BASE}/api/rules`);
			if (!res.ok) throw new Error('Failed to load alert rules');
			rules = await res.json();
		} catch (e) {
			error = e.message;
		} finally {
			isLoadingRules = false;
		}
	}

	async function loadServices() {
		try {
			const res = await fetch(`${API_BASE}/api/services`);
			if (!res.ok) return;
			services = await res.json();
			if (services.length > 0 && !formServiceId) {
				formServiceId = services[0].id.toString();
			}
		} catch {}
	}

	async function resolveAlert(id) {
		try {
			const res = await fetch(`${API_BASE}/api/alerts/${id}/resolve`, { method: 'PUT' });
			if (!res.ok) throw new Error('Failed to resolve alert');
			await loadAlerts();
		} catch (e) {
			alert(`Σφάλμα: ${e.message}`);
		}
	}

	async function handleSubmitRule(e) {
		e.preventDefault();
		isSubmitting = true;
		const payload = {
			service_id: parseInt(formServiceId),
			metric: formMetric,
			operator: formOperator,
			value: parseFloat(formValue)
		};
		try {
			const res = await fetch(`${API_BASE}/api/rules`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (!res.ok) throw new Error('Failed to create rule');
			formValue = formMetric === 'ssl_expiry' ? 15 : formMetric === 'latency' ? 2500 : 200;
			await loadRules();
		} catch (e) {
			alert(`Σφάλμα: ${e.message}`);
		} finally {
			isSubmitting = false;
		}
	}

	async function handleDeleteRule(id) {
		if (!confirm('Θέλετε σίγουρα να διαγράψετε αυτόν τον κανόνα ειδοποίησης;')) return;
		try {
			const res = await fetch(`${API_BASE}/api/rules/${id}`, { method: 'DELETE' });
			if (!res.ok) throw new Error('Failed to delete rule');
			await loadRules();
		} catch (e) {
			alert(`Σφάλμα: ${e.message}`);
		}
	}

	function getServiceName(id) {
		const s = services.find(item => item.id === id);
		return s ? s.name : `Υπηρεσία #${id}`;
	}

	function formatMetric(m) {
		switch (m) {
			case 'latency':          return 'Καθυστέρηση';
			case 'ssl_expiry':       return 'Λήξη SSL';
			case 'status_code':      return 'HTTP Status';
			case 'content_verified': return 'Keyword Verify';
			default: return m;
		}
	}

	function metricUnit(m) {
		switch (m) {
			case 'latency':    return 'ms';
			case 'ssl_expiry': return 'ημ.';
			default: return '';
		}
	}

	function formatDateTime(str) {
		if (!str) return '—';
		return new Date(str).toLocaleString('el-GR', {
			day: '2-digit', month: '2-digit', year: 'numeric',
			hour: '2-digit', minute: '2-digit'
		});
	}

	function timeSince(str) {
		if (!str) return '';
		const diff = Date.now() - new Date(str).getTime();
		const mins  = Math.floor(diff / 60000);
		const hours = Math.floor(mins / 60);
		const days  = Math.floor(hours / 24);
		if (days > 0)  return `${days}ημ. πριν`;
		if (hours > 0) return `${hours}ω. πριν`;
		if (mins > 0)  return `${mins}λ. πριν`;
		return 'μόλις τώρα';
	}

	let activeCount   = $derived(alerts.filter(a => a.status === 'active').length);
	let resolvedCount = $derived(alerts.filter(a => a.status === 'resolved').length);

	onMount(() => {
		Promise.all([loadAlerts(), loadRules(), loadServices()]);
	});
</script>

<div class="container">
	<!-- Page Header -->
	<div class="page-header">
		<div>
			<h2 class="page-title">Ειδοποιήσεις &amp; Κανόνες</h2>
			<p class="page-subtitle">Ιστορικό σφαλμάτων και ρύθμιση κανόνων ορίων (thresholds).</p>
		</div>
		<div class="header-stats">
			<div class="stat-chip stat-chip--error">
				<span class="stat-num">{activeCount}</span>
				<span>Ενεργές</span>
			</div>
			<div class="stat-chip stat-chip--success">
				<span class="stat-num">{resolvedCount}</span>
				<span>Επιλύθηκαν</span>
			</div>
		</div>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<div class="alerts-layout">
		<!-- Left: Alert Logs -->
		<div class="history-col">
			<div class="section-card">
				<div class="section-header">
					<h3>Ιστορικό Καταγραφών</h3>
					<div class="section-header-actions">
						<div class="filter-tabs" role="tablist">
							{#each [['all','Όλα'],['active','Ενεργά'],['resolved','Επιλυμένα']] as [val, label]}
								<button
									class="filter-tab"
									class:active={alertFilter === val}
									onclick={() => alertFilter = val}
									role="tab"
									aria-selected={alertFilter === val}
								>{label}</button>
							{/each}
						</div>
						<button class="btn-refresh" onclick={loadAlerts} disabled={isLoadingAlerts} title="Ανανέωση">
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class:spinning={isLoadingAlerts}>
								<polyline points="23 4 23 10 17 10"></polyline>
								<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
							</svg>
						</button>
					</div>
				</div>

				{#if isLoadingAlerts}
					<div class="loading-state">
						<span class="spinner"></span>
						<span>Φόρτωση ειδοποιήσεων...</span>
					</div>
				{:else if filteredAlerts.length === 0}
					<div class="empty-state">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
							<path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
						</svg>
						<p>
							{alertFilter === 'all'
								? 'Δεν υπάρχουν καταγραφές ειδοποιήσεων.'
								: alertFilter === 'active'
								? 'Δεν υπάρχουν ενεργές ειδοποιήσεις.'
								: 'Δεν υπάρχουν επιλυμένες ειδοποιήσεις.'}
						</p>
					</div>
				{:else}
					<div class="alert-list">
						{#each filteredAlerts as alert (alert.id)}
							<div class="alert-row" class:alert-row--active={alert.status === 'active'}>
								<div class="alert-status-indicator" class:active={alert.status === 'active'} class:resolved={alert.status === 'resolved'}></div>
								<div class="alert-body">
									<div class="alert-top">
										<div class="alert-service">
											<span class="alert-service-name">{alert.service_name}</span>
											<span class="status-badge" class:unhealthy={alert.status === 'active'} class:healthy={alert.status === 'resolved'}>
												<span class="status-dot" class:unhealthy={alert.status === 'active'} class:healthy={alert.status === 'resolved'}></span>
												{alert.status === 'active' ? 'Ενεργό' : 'Επιλύθηκε'}
											</span>
										</div>
										{#if alert.status === 'active'}
											<button class="btn-resolve" onclick={() => resolveAlert(alert.id)} id="resolve-{alert.id}">
												<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
													<polyline points="20 6 9 17 4 12"></polyline>
												</svg>
												Επίλυση
											</button>
										{/if}
									</div>
									<p class="alert-message">{alert.message}</p>
									<div class="alert-times">
										<span title={formatDateTime(alert.triggered_at)}>
											<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
												<circle cx="12" cy="12" r="10"></circle>
												<polyline points="12 6 12 12 16 14"></polyline>
											</svg>
											Ενεργοποίηση: {timeSince(alert.triggered_at)} ({formatDateTime(alert.triggered_at)})
										</span>
										{#if alert.resolved_at}
											<span title={formatDateTime(alert.resolved_at)}>
												<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
													<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
													<polyline points="22 4 12 14.01 9 11.01"></polyline>
												</svg>
												Επίλυση: {formatDateTime(alert.resolved_at)}
											</span>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		<!-- Right: Rules -->
		<div class="rules-col">

			<!-- Add Rule Form -->
			<div class="section-card">
				<div class="section-header">
					<h3>Νέος Κανόνας Ειδοποίησης</h3>
				</div>
				<form class="rule-form" onsubmit={handleSubmitRule} id="rule-form">
					<div class="form-group">
						<label for="rule-service">Υπηρεσία</label>
						<select id="rule-service" bind:value={formServiceId} required>
							{#each services as svc}
								<option value={svc.id.toString()}>{svc.name}</option>
							{/each}
						</select>
					</div>

					<div class="form-row-3">
						<div class="form-group">
							<label for="rule-metric">Μετρικό</label>
							<select id="rule-metric" bind:value={formMetric} required>
								<option value="latency">Καθυστέρηση (ms)</option>
								<option value="ssl_expiry">Λήξη SSL (ημ.)</option>
								<option value="status_code">HTTP Status</option>
								<option value="content_verified">Keyword Verify</option>
							</select>
						</div>
						<div class="form-group">
							<label for="rule-op">Τελεστής</label>
							<select id="rule-op" bind:value={formOperator} required>
								<option value=">">&gt;</option>
								<option value="<">&lt;</option>
								<option value="=">=</option>
								<option value="!=">!=</option>
							</select>
						</div>
						<div class="form-group">
							<label for="rule-val">Τιμή</label>
							<input type="number" id="rule-val" bind:value={formValue} required step="any" />
						</div>
					</div>

					<div class="rule-hint">
						{#if formMetric === 'latency'}Τιμή σε milliseconds (π.χ. 2500ms = 2.5s){/if}
						{#if formMetric === 'ssl_expiry'}Τιμή σε ημέρες (π.χ. 15 = λιγότερες από 15 ημέρες){/if}
						{#if formMetric === 'status_code'}HTTP Status code (π.χ. 200, 404, 500){/if}
						{#if formMetric === 'content_verified'}1 = Επιτυχία Keyword, 0 = Αποτυχία{/if}
					</div>

					<button type="submit" class="btn btn-primary w-full" disabled={isSubmitting} id="add-rule-btn">
						{#if isSubmitting}
							<span class="btn-spinner"></span> Αποθήκευση...
						{:else}
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:0.9rem;height:0.9rem">
								<line x1="12" y1="5" x2="12" y2="19"></line>
								<line x1="5" y1="12" x2="19" y2="12"></line>
							</svg>
							Προσθήκη Κανόνα
						{/if}
					</button>
				</form>
			</div>

			<!-- Rules list -->
			<div class="section-card">
				<div class="section-header">
					<h3>Ενεργοί Κανόνες</h3>
					{#if rules.length > 0}
						<span class="count-chip">{rules.length}</span>
					{/if}
				</div>

				{#if isLoadingRules}
					<div class="loading-state">
						<span class="spinner"></span>
					</div>
				{:else if rules.length === 0}
					<div class="empty-state empty-state--sm">
						<p>Δεν υπάρχουν κανόνες ειδοποίησης.</p>
					</div>
				{:else}
					<div class="rules-list">
						{#each rules as rule (rule.id)}
							<div class="rule-row">
								<div class="rule-body">
									<div class="rule-service">{getServiceName(rule.service_id)}</div>
									<div class="rule-expr">
										<span class="rule-metric">{formatMetric(rule.metric)}</span>
										<span class="rule-op">{rule.operator}</span>
										<span class="rule-val">{rule.value}{metricUnit(rule.metric)}</span>
									</div>
								</div>
								<button class="btn-icon btn-icon--danger" onclick={() => handleDeleteRule(rule.id)} title="Διαγραφή κανόνα" id="delete-rule-{rule.id}">
									<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<polyline points="3 6 5 6 21 6"></polyline>
										<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
										<line x1="10" y1="11" x2="10" y2="17"></line>
										<line x1="14" y1="11" x2="14" y2="17"></line>
									</svg>
									<span class="sr-only">Διαγραφή κανόνα</span>
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>
