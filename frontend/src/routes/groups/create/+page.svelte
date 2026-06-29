<script lang="ts">
	import { createGroup } from '$lib/api';
	import { success, error } from '$lib/stores/toast';
	import { invalidateGroups } from '$lib/stores/workspace';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	const DOMAIN = 'ctcsalto.edu.uy';

	let groupUser = $state('');
	let groupName = $state('');
	let description = $state('');
	let loading = $state(false);

	let generatedEmail = $derived(groupUser ? `${groupUser}@${DOMAIN}` : '');

	async function handleSubmit(e: Event) {
		e.preventDefault();
		loading = true;

		try {
			await createGroup({
				groupEmail: generatedEmail,
				groupName: groupName.trim(),
				description: description.trim() || undefined,
			});
			invalidateGroups();
			success('Grupo creado exitosamente');
			goto(`${base}/groups`);
		} catch (err: any) {
			error(err.message);
		} finally {
			loading = false;
		}
	}
</script>

<div class="mx-auto max-w-lg space-y-4">
	<div class="flex items-center gap-3">
		<a href="{base}/groups" class="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
		</a>
		<h2 class="text-xl font-bold text-gray-900">Crear grupo</h2>
	</div>

	<form onsubmit={handleSubmit} class="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
		<div>
			<label for="groupName" class="mb-1 block text-sm font-medium text-gray-700">
				Nombre del grupo <span class="text-red-500">*</span>
			</label>
			<input
				id="groupName"
				type="text"
				bind:value={groupName}
				required
				placeholder="Ej: Docentes 2026"
				class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
			/>
		</div>

		<div>
			<label for="groupEmail" class="mb-1 block text-sm font-medium text-gray-700">
				Email del grupo <span class="text-red-500">*</span>
			</label>
			<div class="flex">
				<input
					id="groupEmail"
					type="text"
					bind:value={groupUser}
					required
					placeholder="docentes-2026"
					class="w-full rounded-l-lg border border-r-0 border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				/>
				<span class="flex items-center rounded-r-lg border border-gray-300 bg-gray-50 px-3 text-sm text-gray-500">
					@{DOMAIN}
				</span>
			</div>
			<p class="mt-1 text-xs text-gray-400">Sin espacios, minúsculas, puede usar guiones</p>
		</div>

		<div>
			<label for="description" class="mb-1 block text-sm font-medium text-gray-700">
				Descripción <span class="text-xs font-normal text-gray-400">(opcional)</span>
			</label>
			<textarea
				id="description"
				bind:value={description}
				rows="3"
				placeholder="Descripción del grupo..."
				class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
			></textarea>
		</div>

		<button
			type="submit"
			disabled={loading}
			class="w-full cursor-pointer rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-blue-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
		>
			{loading ? 'Creando...' : 'Crear grupo'}
		</button>
	</form>
</div>
