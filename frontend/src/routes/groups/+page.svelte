<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { deleteGroup } from '$lib/api';
	import { success, error } from '$lib/stores/toast';
	import { groups, loadGroups, invalidateGroups } from '$lib/stores/workspace';
	import Modal from '$lib/components/Modal.svelte';

	let loading = $state(true);
	let searchQuery = $state('');
	let deleteModal = $state({ show: false, groupId: '', name: '' });

	let filtered = $derived.by(() => {
		const q = searchQuery.toLowerCase().trim();
		if (!q) return $groups;
		return $groups.filter((g: any) => {
			const email = (g.email || '').toLowerCase();
			const name = (g.name || '').toLowerCase();
			const desc = (g.description || '').toLowerCase();
			return email.includes(q) || name.includes(q) || desc.includes(q);
		});
	});

	async function handleDelete() {
		const { groupId } = deleteModal;
		deleteModal = { show: false, groupId: '', name: '' };
		try {
			await deleteGroup(groupId);
			invalidateGroups();
			await loadGroups(true);
			success('Grupo eliminado');
		} catch (err: any) {
			error(err.message);
		}
	}

	onMount(async () => {
		await loadGroups();
		loading = false;
	});
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h2 class="text-xl font-bold text-gray-900">Grupos de Google Workspace</h2>
		<a
			href="{base}/groups/create"
			class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
		>
			+ Crear grupo
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
			onclick={() => { invalidateGroups(); loading = true; loadGroups(true).then(() => loading = false); }}
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
			{searchQuery ? 'No se encontraron resultados' : 'No se encontraron grupos'}
		</div>
	{:else}
		<div class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
			<table class="w-full text-sm">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-4 py-3 text-left font-medium text-gray-600">Nombre</th>
						<th class="px-4 py-3 text-left font-medium text-gray-600">Email</th>
						<th class="px-4 py-3 text-left font-medium text-gray-600">Descripcion</th>
						<th class="px-4 py-3 text-right font-medium text-gray-600">Acciones</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-100">
					{#each filtered as group}
						{@const email = group.email || ''}
						{@const name = group.name || email}
						{@const desc = group.description || '-'}
						{@const id = group.id || email}
						<tr class="hover:bg-gray-50">
							<td class="px-4 py-3 font-medium text-gray-900">{name}</td>
							<td class="px-4 py-3 text-gray-600">{email}</td>
							<td class="max-w-xs truncate px-4 py-3 text-gray-600">{desc}</td>
							<td class="px-4 py-3 text-right">
								<div class="flex items-center justify-end gap-1">
									<a
										href="{base}/groups/{encodeURIComponent(id)}"
										class="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
									>
										Editar
									</a>
									<button
										onclick={() => deleteModal = { show: true, groupId: id, name }}
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
		<p class="text-xs text-gray-400">{filtered.length} grupos</p>
	{/if}
</div>

<Modal show={deleteModal.show} title="Eliminar grupo" onclose={() => deleteModal.show = false}>
	<p class="text-sm text-gray-600">
		¿Estás seguro de <strong>eliminar permanentemente</strong> el grupo <strong>{deleteModal.name}</strong>?
	</p>
	<div class="mt-4 flex justify-end gap-2">
		<button onclick={() => deleteModal.show = false} class="cursor-pointer rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50">Cancelar</button>
		<button onclick={handleDelete} class="cursor-pointer rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700">Eliminar</button>
	</div>
</Modal>
