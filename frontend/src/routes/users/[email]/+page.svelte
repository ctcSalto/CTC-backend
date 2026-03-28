<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { getAccount, updateAccount, deleteAccount, generatePassword } from '$lib/api';
	import { success, error } from '$lib/stores/toast';
	import { accounts, invalidateAccounts } from '$lib/stores/workspace';
	import { goto } from '$app/navigation';
	import { get } from 'svelte/store';
	import Modal from '$lib/components/Modal.svelte';

	let userEmail = $derived(decodeURIComponent($page.params.email ?? ''));
	let account: any = $state(null);
	let loading = $state(true);
	let saving = $state(false);

	let editName = $state('');
	let editLastName = $state('');
	let editOU = $state('');

	let passwordModal = $state({ show: false, password: '', loading: false });
	let deleteModal = $state(false);

	const OU_OPTIONS = [
		{ value: '/Alumnos', label: 'Alumnos' },
		{ value: '/Equipo Docente', label: 'Equipo Docente' },
		{ value: '/Administración y Ventas', label: 'Administración y Ventas' },
	];

	function setFieldsFromAccount(acc: any) {
		account = acc;
		editName = acc?.name?.givenName || acc?.givenName || '';
		editLastName = acc?.name?.familyName || acc?.familyName || '';
		editOU = acc?.orgUnitPath || '/Alumnos';
	}

	async function loadAccount() {
		const cached = get(accounts).find(
			(a: any) => (a.primaryEmail || a.email) === userEmail
		);
		if (cached) {
			setFieldsFromAccount(cached);
			loading = false;
		}

		try {
			const res = await getAccount(userEmail);
			const accountData = res?.data?.user || res?.data;
			if (accountData) {
				setFieldsFromAccount(accountData);
			} else if (!cached) {
				error('No se pudo obtener la cuenta');
			}
		} catch (err: any) {
			error(err.message || 'Error al cargar la cuenta');
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		const originalName = account?.name?.givenName || account?.givenName || '';
		const originalLastName = account?.name?.familyName || account?.familyName || '';

		const finalName = editName.trim() || originalName;
		const finalLastName = editLastName.trim() || originalLastName;

		if (!finalName || !finalLastName) {
			error('Nombre y apellido son obligatorios');
			return;
		}

		saving = true;
		try {
			await updateAccount({
				primaryEmail: userEmail,
				givenName: finalName,
				familyName: finalLastName,
				orgUnitPath: editOU,
			});
			success('Usuario actualizado. Redirigiendo...');

			editName = finalName;
			editLastName = finalLastName;

			accounts.update(list => list.map((a: any) => {
				if ((a.primaryEmail || a.email) === userEmail) {
					return {
						...a,
						name: { ...a.name, givenName: finalName, familyName: finalLastName },
						orgUnitPath: editOU,
					};
				}
				return a;
			}));

			invalidateAccounts();

			setTimeout(() => {
				goto(`${base}/users`);
			}, 3000);
		} catch (err: any) {
			error(err.message || 'Error al guardar los cambios');
		} finally {
			saving = false;
		}
	}

	async function handleResetPassword() {
		passwordModal = { show: true, password: '', loading: true };
		try {
			const gen = await generatePassword(16);
			const newPass = gen.password;

			await updateAccount({
				primaryEmail: userEmail,
				password: newPass,
			});

			passwordModal = { show: true, password: newPass, loading: false };
			success('Contraseña actualizada');
		} catch (err: any) {
			passwordModal = { show: false, password: '', loading: false };
			error(err.message || 'Error al resetear la contraseña');
		}
	}

	async function handleDelete() {
		deleteModal = false;
		try {
			await deleteAccount(userEmail);
			accounts.update(list => list.filter((a: any) => (a.primaryEmail || a.email) !== userEmail));
			invalidateAccounts();
			success('Usuario eliminado');
			goto(`${base}/users`);
		} catch (err: any) {
			error(err.message || 'Error al eliminar la cuenta');
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
		success('Copiado al portapapeles');
	}

	onMount(loadAccount);
</script>

<div class="mx-auto max-w-lg space-y-4">
	<div class="flex items-center gap-3">
		<a href="{base}/users" class="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
		</a>
		<h2 class="text-xl font-bold text-gray-900">{userEmail}</h2>
	</div>

	{#if loading}
		<div class="flex justify-center py-12">
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
		</div>
	{:else if account}
		<div class="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
			<div class="flex items-center justify-between">
				<h3 class="font-medium text-gray-900">Información de la cuenta</h3>
				{#if account.suspended}
					<span class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
						<span class="h-1.5 w-1.5 rounded-full bg-red-500"></span>
						Suspendido
					</span>
				{:else}
					<span class="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
						<span class="h-1.5 w-1.5 rounded-full bg-green-500"></span>
						Activo
					</span>
				{/if}
			</div>

			<div class="grid grid-cols-2 gap-4">
				<div>
					<label for="editName" class="mb-1 block text-sm font-medium text-gray-700">Nombre <span class="text-red-500">*</span></label>
					<input
						id="editName"
						type="text"
						required
						bind:value={editName}
						class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
					/>
				</div>
				<div>
					<label for="editLastName" class="mb-1 block text-sm font-medium text-gray-700">Apellido <span class="text-red-500">*</span></label>
					<input
						id="editLastName"
						type="text"
						required
						bind:value={editLastName}
						class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
					/>
				</div>
			</div>

			<div>
				<label for="editOU" class="mb-1 block text-sm font-medium text-gray-700">Unidad organizativa</label>
				<select
					id="editOU"
					bind:value={editOU}
					class="w-full cursor-pointer rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				>
					{#each OU_OPTIONS as ou}
						<option value={ou.value}>{ou.label}</option>
					{/each}
				</select>
			</div>

			<button
				onclick={handleSave}
				disabled={saving}
				class="w-full cursor-pointer rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-blue-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
			>
				{saving ? 'Guardando...' : 'Guardar cambios'}
			</button>
		</div>

		<div class="flex gap-3">
			<button
				onclick={handleResetPassword}
				class="flex-1 cursor-pointer rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100"
			>
				Resetear contraseña
			</button>
			<button
				onclick={() => deleteModal = true}
				class="flex-1 cursor-pointer rounded-lg border border-red-300 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-100"
			>
				Eliminar cuenta
			</button>
		</div>
	{:else}
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
			No se encontró la cuenta
		</div>
	{/if}
</div>

<Modal show={passwordModal.show} title="Nueva contraseña" onclose={() => passwordModal.show = false}>
	{#if passwordModal.loading}
		<div class="flex items-center justify-center gap-3 py-6">
			<div class="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
			<span class="text-sm text-gray-500">Generando contraseña...</span>
		</div>
	{:else}
		<div class="space-y-3">
			<p class="text-sm text-gray-600">La contraseña ha sido actualizada para <strong>{userEmail}</strong>:</p>
			<div class="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2.5">
				<p class="flex-1 font-mono text-sm font-semibold text-gray-900">{passwordModal.password}</p>
				<button
					onclick={() => copyToClipboard(passwordModal.password)}
					class="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50"
				>
					Copiar
				</button>
			</div>
		</div>
		<div class="mt-4 flex justify-end">
			<button
				onclick={() => passwordModal.show = false}
				class="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
			>
				Cerrar
			</button>
		</div>
	{/if}
</Modal>

<Modal show={deleteModal} title="Eliminar cuenta" onclose={() => deleteModal = false}>
	<p class="text-sm text-gray-600">
		¿Estás seguro de <strong>eliminar permanentemente</strong> la cuenta <strong>{userEmail}</strong>? Esta acción no se puede deshacer.
	</p>
	<div class="mt-4 flex justify-end gap-2">
		<button
			onclick={() => deleteModal = false}
			class="cursor-pointer rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
		>
			Cancelar
		</button>
		<button
			onclick={handleDelete}
			class="cursor-pointer rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700"
		>
			Eliminar
		</button>
	</div>
</Modal>
