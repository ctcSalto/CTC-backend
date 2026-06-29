<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { getGroup, updateGroup, deleteGroup, listGroupMembers, addToGroup, removeFromGroup } from '$lib/api';
	import { success, error } from '$lib/stores/toast';
	import { invalidateGroups } from '$lib/stores/workspace';
	import { goto } from '$app/navigation';
	import Modal from '$lib/components/Modal.svelte';

	let groupId = $derived(decodeURIComponent($page.params.groupId ?? ''));
	let group: any = $state(null);
	let members: any[] = $state([]);
	let loading = $state(true);
	let saving = $state(false);

	let editName = $state('');
	let editDescription = $state('');

	let addMemberEmail = $state('');
	let addingMember = $state(false);

	let removeModal = $state({ show: false, email: '' });
	let deleteModal = $state(false);

	async function loadGroup() {
		loading = true;
		try {
			const res = await getGroup(groupId);
			group = res.data;
			editName = group?.name || '';
			editDescription = group?.description || '';

			const groupEmail = group?.email || groupId;
			try {
				const membersRes = await listGroupMembers(groupEmail);
				const data = membersRes.data as any;
				members = data?.members || data || [];
			} catch {
				members = [];
			}
		} catch (err: any) {
			error(err.message);
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		saving = true;
		try {
			await updateGroup({
				groupId,
				name: editName,
				description: editDescription,
			});
			invalidateGroups();
			success('Grupo actualizado');
		} catch (err: any) {
			error(err.message);
		} finally {
			saving = false;
		}
	}

	async function handleAddMember() {
		if (!addMemberEmail.trim()) return;
		addingMember = true;
		try {
			await addToGroup(addMemberEmail.trim(), groupId);
			success(`${addMemberEmail} agregado al grupo`);
			addMemberEmail = '';
			await loadGroup();
		} catch (err: any) {
			error(err.message);
		} finally {
			addingMember = false;
		}
	}

	async function handleRemoveMember() {
		const { email } = removeModal;
		removeModal = { show: false, email: '' };
		try {
			await removeFromGroup(email, groupId);
			success(`${email} removido del grupo`);
			members = members.filter(m => m.email !== email);
		} catch (err: any) {
			error(err.message);
		}
	}

	async function handleDelete() {
		deleteModal = false;
		try {
			await deleteGroup(groupId);
			invalidateGroups();
			success('Grupo eliminado');
			goto(`${base}/groups`);
		} catch (err: any) {
			error(err.message);
		}
	}

	onMount(loadGroup);
</script>

<div class="mx-auto max-w-lg space-y-4">
	<div class="flex items-center gap-3">
		<a href="{base}/groups" class="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
		</a>
		<h2 class="text-xl font-bold text-gray-900">{group?.name || groupId}</h2>
	</div>

	{#if loading}
		<div class="flex justify-center py-12">
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
		</div>
	{:else if group}
		<div class="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
			<h3 class="font-medium text-gray-900">Información del grupo</h3>

			<div>
				<label for="editName" class="mb-1 block text-sm font-medium text-gray-700">Nombre</label>
				<input
					id="editName"
					type="text"
					bind:value={editName}
					class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				/>
			</div>

			<div>
				<label for="editDesc" class="mb-1 block text-sm font-medium text-gray-700">Descripción</label>
				<textarea
					id="editDesc"
					bind:value={editDescription}
					rows="2"
					class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				></textarea>
			</div>

			<div class="flex gap-2">
				<button
					onclick={handleSave}
					disabled={saving}
					class="flex-1 cursor-pointer rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-blue-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
				>
					{saving ? 'Guardando...' : 'Guardar'}
				</button>
				<button
					onclick={() => deleteModal = true}
					class="cursor-pointer rounded-lg border border-red-300 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-100"
				>
					Eliminar grupo
				</button>
			</div>
		</div>

		<div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
			<h3 class="mb-3 font-medium text-gray-900">Miembros ({members.length})</h3>

			<div class="mb-4 flex gap-2">
				<input
					type="email"
					bind:value={addMemberEmail}
					placeholder="email@ctcsalto.edu.uy"
					class="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				/>
				<button
					onclick={handleAddMember}
					disabled={addingMember}
					class="cursor-pointer rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
				>
					{addingMember ? '...' : 'Agregar'}
				</button>
			</div>

			{#if members.length === 0}
				<div class="rounded-lg border border-dashed border-gray-200 py-6 text-center text-sm text-gray-400">
					No hay miembros en este grupo
				</div>
			{:else}
				<div class="divide-y divide-gray-100">
					{#each members as member}
						{@const memberEmail = member.email || ''}
						{@const role = member.role || 'MEMBER'}
						<div class="flex items-center justify-between py-2.5">
							<div>
								<p class="text-sm font-medium text-gray-900">{memberEmail}</p>
								<p class="text-xs text-gray-400">{role}</p>
							</div>
							<button
								onclick={() => removeModal = { show: true, email: memberEmail }}
								class="cursor-pointer rounded px-2 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
							>
								Remover
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
			No se encontró el grupo
		</div>
	{/if}
</div>

<Modal show={removeModal.show} title="Remover miembro" onclose={() => removeModal.show = false}>
	<p class="text-sm text-gray-600">
		¿Estás seguro de remover <strong>{removeModal.email}</strong> del grupo?
	</p>
	<div class="mt-4 flex justify-end gap-2">
		<button onclick={() => removeModal.show = false} class="cursor-pointer rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50">Cancelar</button>
		<button onclick={handleRemoveMember} class="cursor-pointer rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700">Remover</button>
	</div>
</Modal>

<Modal show={deleteModal} title="Eliminar grupo" onclose={() => deleteModal = false}>
	<p class="text-sm text-gray-600">
		¿Estás seguro de <strong>eliminar permanentemente</strong> este grupo? Esta acción no se puede deshacer.
	</p>
	<div class="mt-4 flex justify-end gap-2">
		<button onclick={() => deleteModal = false} class="cursor-pointer rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50">Cancelar</button>
		<button onclick={handleDelete} class="cursor-pointer rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700">Eliminar</button>
	</div>
</Modal>
