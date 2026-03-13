<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { suspendAccount, unsuspendAccount, deleteAccount } from '$lib/api';
	import { success, error } from '$lib/stores/toast';
	import { accounts, loadAccounts, invalidateAccounts } from '$lib/stores/workspace';
	import Modal from '$lib/components/Modal.svelte';

	let loading = $state(true);
	let searchQuery = $state('');
	let currentPage = $state(1);
	const PAGE_SIZE = 10;

	let confirmModal = $state({ show: false, email: '', action: '' as 'delete' | 'suspend' | 'unsuspend' });
	let actionLoading = $state(false);

	// Filtrado local instantáneo
	let filtered = $derived.by(() => {
		const q = searchQuery.toLowerCase().trim();
		if (!q) return $accounts;
		return $accounts.filter((a: any) => {
			const email = (a.primaryEmail || a.email || '').toLowerCase();
			const name = a.name
				? `${a.name.givenName || ''} ${a.name.familyName || ''}`.toLowerCase()
				: (a.fullName || '').toLowerCase();
			return email.includes(q) || name.includes(q);
		});
	});

	let totalPages = $derived(Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
	let paginated = $derived(filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE));

	// Reset page when search changes
	$effect(() => {
		void searchQuery;
		currentPage = 1;
	});

	async function handleConfirmAction() {
		const { email, action } = confirmModal;
		confirmModal = { show: false, email: '', action: '' as 'delete' };
		actionLoading = true;
		try {
			if (action === 'delete') {
				await deleteAccount(email);
				// Quitar inmediatamente de la lista local
				accounts.update(list => list.filter((a: any) => (a.primaryEmail || a.email) !== email));
				success('Usuario eliminado');
			} else if (action === 'suspend') {
				await suspendAccount(email);
				// Actualizar estado local inmediatamente
				accounts.update(list => list.map((a: any) =>
					(a.primaryEmail || a.email) === email ? { ...a, suspended: true } : a
				));
				success('Usuario suspendido');
			} else if (action === 'unsuspend') {
				await unsuspendAccount(email);
				accounts.update(list => list.map((a: any) =>
					(a.primaryEmail || a.email) === email ? { ...a, suspended: false } : a
				));
				success('Usuario reactivado');
			}
			// Marcar cache como stale para que la próxima navegación recargue
			invalidateAccounts();
		} catch (err: any) {
			error(err.message);
		} finally {
			actionLoading = false;
		}
	}

	onMount(async () => {
		await loadAccounts();
		loading = false;
	});
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h2 class="text-xl font-bold text-gray-900">Usuarios de Google Workspace</h2>
		<a
			href="{base}/users/create"
			class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
		>
			+ Crear usuario
		</a>
	</div>

	<div class="flex items-center gap-3">
		<input
			type="text"
			bind:value={searchQuery}
			placeholder="Buscar por nombre o email..."
			class="w-full max-w-md rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
		/>
		<button
			onclick={() => { invalidateAccounts(); loading = true; loadAccounts(true).then(() => loading = false); }}
			class="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
			title="Recargar"
		>
			<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
			</svg>
		</button>
	</div>

	{#if loading}
		<div class="flex justify-center py-12">
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
		</div>
	{:else if filtered.length === 0}
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
			{searchQuery ? 'No se encontraron resultados' : 'No se encontraron usuarios'}
		</div>
	{:else}
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
			<table class="w-full text-sm">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left font-medium text-gray-600">Nombre</th>
						<th class="px-4 py-3 text-left font-medium text-gray-600">Email</th>
						<th class="px-4 py-3 text-left font-medium text-gray-600">OU</th>
						<th class="px-4 py-3 text-left font-medium text-gray-600">Estado</th>
						<th class="px-4 py-3 text-right font-medium text-gray-600">Acciones</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-100">
					{#each paginated as account}
						{@const email = account.primaryEmail || account.email || ''}
						{@const name = account.name
							? `${account.name.givenName || ''} ${account.name.familyName || ''}`
							: account.fullName || email}
						{@const suspended = account.suspended}
						{@const ou = account.orgUnitPath || ''}
						<tr class="hover:bg-gray-50">
							<td class="px-4 py-3 font-medium text-gray-900">{name}</td>
							<td class="px-4 py-3 text-gray-600">{email}</td>
							<td class="px-4 py-3 text-gray-600">{ou}</td>
							<td class="px-4 py-3">
								{#if suspended}
									<span class="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">Suspendido</span>
								{:else}
									<span class="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">Activo</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-right">
								<div class="flex items-center justify-end gap-1">
									<a
										href="{base}/users/{encodeURIComponent(email)}"
										class="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
									>
										Editar
									</a>
									{#if suspended}
										<button
											onclick={() => confirmModal = { show: true, email, action: 'unsuspend' }}
											class="cursor-pointer rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50"
										>
											Reactivar
										</button>
									{:else}
										<button
											onclick={() => confirmModal = { show: true, email, action: 'suspend' }}
											class="cursor-pointer rounded px-2 py-1 text-xs font-medium text-amber-600 hover:bg-amber-50"
										>
											Suspender
										</button>
									{/if}
									<button
										onclick={() => confirmModal = { show: true, email, action: 'delete' }}
										class="cursor-pointer rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
									>
										Eliminar
									</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if actionLoading}
			<div class="flex items-center justify-center gap-2 py-2">
				<div class="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
				<span class="text-xs text-gray-500">Procesando...</span>
			</div>
		{/if}

		<!-- Paginación -->
		<div class="flex items-center justify-between">
			<p class="text-xs text-gray-400">{filtered.length} usuarios</p>
			{#if totalPages > 1}
				<div class="flex items-center gap-1">
					<button
						onclick={() => currentPage = Math.max(1, currentPage - 1)}
						disabled={currentPage === 1}
						class="cursor-pointer rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
					>
						Anterior
					</button>
					<span class="px-2 text-xs text-gray-500">
						{currentPage} / {totalPages}
					</span>
					<button
						onclick={() => currentPage = Math.min(totalPages, currentPage + 1)}
						disabled={currentPage === totalPages}
						class="cursor-pointer rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
					>
						Siguiente
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

<Modal show={confirmModal.show} title="Confirmar acción" onclose={() => confirmModal.show = false}>
	<p class="text-sm text-gray-600">
		{#if confirmModal.action === 'delete'}
			¿Estás seguro de <strong>eliminar permanentemente</strong> la cuenta <strong>{confirmModal.email}</strong>?
		{:else if confirmModal.action === 'suspend'}
			¿Estás seguro de <strong>suspender</strong> la cuenta <strong>{confirmModal.email}</strong>?
		{:else}
			¿Estás seguro de <strong>reactivar</strong> la cuenta <strong>{confirmModal.email}</strong>?
		{/if}
	</p>
	<div class="mt-4 flex justify-end gap-2">
		<button
			onclick={() => confirmModal.show = false}
			class="cursor-pointer rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
		>
			Cancelar
		</button>
		<button
			onclick={handleConfirmAction}
			class="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-white transition-colors
				{confirmModal.action === 'delete' ? 'bg-red-600 hover:bg-red-700' :
				 confirmModal.action === 'suspend' ? 'bg-amber-600 hover:bg-amber-700' :
				 'bg-green-600 hover:bg-green-700'}"
		>
			{confirmModal.action === 'delete' ? 'Eliminar' :
			 confirmModal.action === 'suspend' ? 'Suspender' : 'Reactivar'}
		</button>
	</div>
</Modal>
