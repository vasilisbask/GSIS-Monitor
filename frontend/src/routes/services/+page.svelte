<script>
	import { onMount } from 'svelte';

	const API_BASE = 'http://localhost:8000';

	let services = $state([]);
	let error = $state(null);
	let isLoading = $state(true);
	let saveError = $state(null);
	let isSaving = $state(false);

	let isDialogOpen = $state(false);
	let isEditMode = $state(false);
	let currentServiceId = $state(null);

	let formName = $state('');
	let formUrl = $state('');
	let formVerificationKeyword = $state('');
	let formExclusionKeyword = $state('');
	let formSkipTlsVerify = $state(false);
	let formIsActive = $state(true);

	async function loadServices() {
		isLoading = true;
		try {
			const res = await fetch(`${API_BASE}/api/services`);
			if (!res.ok) throw new Error('Failed to load services');
			services = await res.json();
			error = null;
		} catch (e) {
			error = e.message;
		} finally {
			isLoading = false;
		}
	}

	function openAddDialog() {
		isEditMode = false;
		currentServiceId = null;
		formName = '';
		formUrl = '';
		formVerificationKeyword = '';
		formExclusionKeyword = '';
		formSkipTlsVerify = false;
		formIsActive = true;
		saveError = null;
		isDialogOpen = true;
	}

	function openEditDialog(service) {
		isEditMode = true;
		currentServiceId = service.id;
		formName = service.name;
		formUrl = service.url;
		formVerificationKeyword = service.verification_keyword || '';
		formExclusionKeyword = service.exclusion_keyword || '';
		formSkipTlsVerify = service.skip_tls_verify;
		formIsActive = service.is_active;
		saveError = null;
		isDialogOpen = true;
	}

	function closeDialog() {
		isDialogOpen = false;
		saveError = null;
	}

	async function handleSubmit(e) {
		e.preventDefault();
		isSaving = true;
		saveError = null;
		const payload = {
			name: formName,
			url: formUrl,
			verification_keyword: formVerificationKeyword || null,
			exclusion_keyword: formExclusionKeyword || null,
			skip_tls_verify: formSkipTlsVerify,
			is_active: formIsActive
		};

		try {
			let res;
			if (isEditMode) {
				res = await fetch(`${API_BASE}/api/services/${currentServiceId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(payload)
				});
			} else {
				res = await fetch(`${API_BASE}/api/services`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(payload)
				});
			}

			if (!res.ok) {
				const d = await res.json();
				throw new Error(d.detail || 'Αποτυχία αποθήκευσης');
			}

			closeDialog();
			await loadServices();
		} catch (e) {
			saveError = e.message;
		} finally {
			isSaving = false;
		}
	}

	async function handleDelete(id, name) {
		if (!confirm(`Είστε σίγουροι ότι θέλετε να διαγράψετε την υπηρεσία "${name}";`)) return;
		try {
			const res = await fetch(`${API_BASE}/api/services/${id}`, { method: 'DELETE' });
			if (!res.ok) throw new Error('Delete failed');
			await loadServices();
		} catch (e) {
			alert(`Σφάλμα: ${e.message}`);
		}
	}

	onMount(loadServices);
</script>

<div class="container">
	<!-- Header -->
	<div class="page-header">
		<div>
			<h2 class="page-title">Διαχείριση Ψηφιακών Πυλών</h2>
			<p class="page-subtitle">Προσθέστε, επεξεργαστείτε ή απενεργοποιήστε πύλες ελέγχου.</p>
		</div>
		<button class="btn btn-primary" onclick={openAddDialog} id="add-service-btn">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<line x1="12" y1="5" x2="12" y2="19"></line>
				<line x1="5" y1="12" x2="19" y2="12"></line>
			</svg>
			Νέα Υπηρεσία
		</button>
	</div>

	{#if error}
		<div class="error-banner" role="alert">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<circle cx="12" cy="12" r="10"></circle>
				<line x1="12" y1="8" x2="12" y2="12"></line>
				<line x1="12" y1="16" x2="12.01" y2="16"></line>
			</svg>
			Σφάλμα επικοινωνίας: {error}
		</div>
	{/if}

	<!-- Table -->
	<div class="table-card">
		{#if isLoading}
			<div class="loading-rows">
				{#each {length: 4} as _}
					<div class="loading-row">
						<div class="skeleton" style="height:0.875rem;width:30%"></div>
						<div class="skeleton" style="height:0.875rem;width:45%"></div>
						<div class="skeleton" style="height:1.375rem;width:5rem;border-radius:9999px"></div>
					</div>
				{/each}
			</div>
		{:else if services.length === 0}
			<div class="empty-state">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
					<circle cx="12" cy="12" r="10"></circle>
					<line x1="2" y1="12" x2="22" y2="12"></line>
					<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
				</svg>
				<p>Δεν υπάρχουν καταχωρημένες υπηρεσίες.</p>
				<button class="btn btn-primary btn-sm" onclick={openAddDialog}>Προσθήκη πρώτης υπηρεσίας</button>
			</div>
		{:else}
			<div class="table-overflow">
				<table>
					<thead>
						<tr>
							<th>#</th>
							<th>Όνομα</th>
							<th>Διεύθυνση (URL)</th>
							<th>Keyword Επαλήθευσης</th>
							<th>Keyword Αποκλεισμού</th>
							<th class="text-center">TLS Bypass</th>
							<th class="text-center">Κατάσταση</th>
							<th class="text-right">Ενέργειες</th>
						</tr>
					</thead>
					<tbody>
						{#each services as service (service.id)}
							<tr>
								<td class="id-col">{service.id}</td>
								<td class="name-col">{service.name}</td>
								<td>
									<a href={service.url} target="_blank" rel="noopener noreferrer" class="url-link" title={service.url}>
										{service.url}
									</a>
								</td>
								<td>
									{#if service.verification_keyword}
										<code class="kw-chip kw-verify">{service.verification_keyword}</code>
									{:else}
										<span class="none-label">—</span>
									{/if}
								</td>
								<td>
									{#if service.exclusion_keyword}
										<code class="kw-chip kw-exclude">{service.exclusion_keyword}</code>
									{:else}
										<span class="none-label">—</span>
									{/if}
								</td>
								<td class="text-center">
									<span class="badge" class:badge-warning={service.skip_tls_verify} class:badge-secondary={!service.skip_tls_verify}>
										{service.skip_tls_verify ? 'ΝΑΙ' : 'ΟΧΙ'}
									</span>
								</td>
								<td class="text-center">
									<span class="status-badge" class:healthy={service.is_active} class:inactive={!service.is_active}>
										<span class="status-dot" class:healthy={service.is_active} class:inactive={!service.is_active}></span>
										{service.is_active ? 'ΕΝΕΡΓΗ' : 'ΑΝΕΝΕΡΓΗ'}
									</span>
								</td>
								<td class="text-right">
									<div class="actions-wrap">
										<button class="btn-icon" onclick={() => openEditDialog(service)} title="Επεξεργασία" id="edit-{service.id}">
											<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
												<path d="M11 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5"></path>
												<path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
											</svg>
											<span class="sr-only">Επεξεργασία</span>
										</button>
										<button class="btn-icon btn-icon--danger" onclick={() => handleDelete(service.id, service.name)} title="Διαγραφή" id="delete-{service.id}">
											<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
												<polyline points="3 6 5 6 21 6"></polyline>
												<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
												<line x1="10" y1="11" x2="10" y2="17"></line>
												<line x1="14" y1="11" x2="14" y2="17"></line>
											</svg>
											<span class="sr-only">Διαγραφή</span>
										</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<div class="table-footer">
				<span>{services.length} υπηρεσ{services.length === 1 ? 'ία' : 'ίες'} καταχωρημέν{services.length === 1 ? 'η' : 'ες'}</span>
			</div>
		{/if}
	</div>
</div>

<!-- Modal -->
{#if isDialogOpen}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Φόρμα Υπηρεσίας" onclick={(e) => e.target === e.currentTarget && closeDialog()}>
		<div class="modal-card">
			<div class="modal-header">
				<h3>{isEditMode ? 'Επεξεργασία Υπηρεσίας' : 'Προσθήκη Νέας Υπηρεσίας'}</h3>
				<button class="btn-close" onclick={closeDialog} aria-label="Κλείσιμο">&times;</button>
			</div>

			<form onsubmit={handleSubmit} id="service-form">
				<div class="form-section">
					<div class="form-group">
						<label for="svc-name">Όνομα Υπηρεσίας <span class="required">*</span></label>
						<input type="text" id="svc-name" bind:value={formName} required placeholder="π.χ. e-Paravolo" autocomplete="off" />
					</div>
					<div class="form-group">
						<label for="svc-url">Διεύθυνση (URL) <span class="required">*</span></label>
						<input type="url" id="svc-url" bind:value={formUrl} required placeholder="https://example.gov.gr" autocomplete="off" />
					</div>
				</div>

				<div class="form-divider">
					<span>Επαλήθευση Περιεχομένου</span>
				</div>

				<div class="form-section">
					<div class="form-row">
						<div class="form-group">
							<label for="svc-verify">Keyword Επαλήθευσης</label>
							<input type="text" id="svc-verify" bind:value={formVerificationKeyword} placeholder="Πρέπει να υπάρχει στο HTML" autocomplete="off" />
							<span class="field-hint">Εάν οριστεί, το keyword πρέπει να βρεθεί στο σώμα της απόκρισης.</span>
						</div>
						<div class="form-group">
							<label for="svc-exclude">Keyword Αποκλεισμού</label>
							<input type="text" id="svc-exclude" bind:value={formExclusionKeyword} placeholder="π.χ. maintenance" autocomplete="off" />
							<span class="field-hint">Εάν το keyword βρεθεί, η υπηρεσία θεωρείται OFFLINE.</span>
						</div>
					</div>
				</div>

				<div class="form-divider">
					<span>Ρυθμίσεις</span>
				</div>

				<div class="form-section">
					<div class="checkbox-group">
						<label class="checkbox-label" for="svc-tls">
							<input type="checkbox" id="svc-tls" bind:checked={formSkipTlsVerify} />
							<span class="checkbox-custom"></span>
							<span>
								<strong>Παράκαμψη ελέγχου TLS/SSL</strong>
								<small>InsecureSkipVerify — χρήση μόνο για εσωτερικά endpoints</small>
							</span>
						</label>
						<label class="checkbox-label" for="svc-active">
							<input type="checkbox" id="svc-active" bind:checked={formIsActive} />
							<span class="checkbox-custom"></span>
							<span>
								<strong>Ενεργή παρακολούθηση</strong>
								<small>Ο pinger θα ελέγχει αυτή την υπηρεσία</small>
							</span>
						</label>
					</div>
				</div>

				{#if saveError}
					<div class="form-error" role="alert">{saveError}</div>
				{/if}

				<div class="modal-actions">
					<button type="button" class="btn btn-secondary" onclick={closeDialog} disabled={isSaving}>Ακύρωση</button>
					<button type="submit" class="btn btn-primary" disabled={isSaving} id="save-service-btn">
						{#if isSaving}
							<span class="btn-spinner"></span> Αποθήκευση...
						{:else}
							{isEditMode ? 'Αποθήκευση Αλλαγών' : 'Προσθήκη Υπηρεσίας'}
						{/if}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
