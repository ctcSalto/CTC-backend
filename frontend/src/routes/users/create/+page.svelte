<script lang="ts">
	import { createAccountAndNotify } from '$lib/api';
	import { success, error } from '$lib/stores/toast';
	import { accounts, invalidateAccounts } from '$lib/stores/workspace';
	import { base } from '$app/paths';
	import Modal from '$lib/components/Modal.svelte';

	const DOMAIN = 'ctcsalto.edu.uy';
	const OU_OPTIONS = [
		{ value: '/Alumnos', label: 'Alumnos' },
		{ value: '/Equipo Docente', label: 'Equipo Docente' },
		{ value: '/Administración y Ventas', label: 'Administración y Ventas' },
	];

	let givenName = $state('');
	let familyName = $state('');
	let orgUnitPath = $state('/Alumnos');
	let notificationEmail = $state('');
	let autoPassword = $state(true);
	let customPassword = $state('');
	let loading = $state(false);

	let resultModal = $state({ show: false, password: '', email: '', notified: false, notifyError: '' });

	// Email auto-generado desde nombre.apellido (sin tildes, minúsculas)
	let emailUser = $derived.by(() => {
		if (!givenName.trim() || !familyName.trim()) return '';
		const first = givenName.trim().split(' ')[0].toLowerCase()
			.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
		const last = familyName.trim().split(' ')[0].toLowerCase()
			.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
		return `${first}.${last}`;
	});

	let generatedEmail = $derived(emailUser ? `${emailUser}@${DOMAIN}` : '');

	async function handleSubmit(e: Event) {
		e.preventDefault();
		loading = true;

		try {
			const res = await createAccountAndNotify({
				primaryEmail: generatedEmail,
				givenName: givenName.trim(),
				familyName: familyName.trim(),
				orgUnitPath,
				notificationEmail: notificationEmail.trim(),
				password: autoPassword ? undefined : customPassword,
			});

			resultModal = {
				show: true,
				password: res.temporaryPassword,
				email: generatedEmail,
				notified: res.notificationSent,
				notifyError: res.notificationError || '',
			};

			success('Cuenta creada exitosamente');

			// Agregar nuevo usuario a la lista local (sin recargar de Google)
			accounts.update(list => [...list, {
				primaryEmail: generatedEmail,
				name: { givenName: givenName.trim(), familyName: familyName.trim() },
				orgUnitPath,
				suspended: false,
			}]);
			invalidateAccounts();

			// Reset form
			givenName = '';
			familyName = '';
			notificationEmail = '';
			customPassword = '';
		} catch (err: any) {
			error(err.message);
		} finally {
			loading = false;
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
		success('Copiado al portapapeles');
	}
</script>

<div class="mx-auto max-w-lg space-y-4">
	<div class="flex items-center gap-3">
		<a href="{base}/users" class="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600">
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
		</a>
		<h2 class="text-xl font-bold text-gray-900">Crear usuario</h2>
	</div>

	<form onsubmit={handleSubmit} class="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
		<div class="grid grid-cols-2 gap-4">
			<div>
				<label for="givenName" class="mb-1 block text-sm font-medium text-gray-700">
					Nombre <span class="text-red-500">*</span>
				</label>
				<input
					id="givenName"
					type="text"
					bind:value={givenName}
					required
					placeholder="Juan"
					class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				/>
			</div>
			<div>
				<label for="familyName" class="mb-1 block text-sm font-medium text-gray-700">
					Apellido <span class="text-red-500">*</span>
				</label>
				<input
					id="familyName"
					type="text"
					bind:value={familyName}
					required
					placeholder="Pérez"
					class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				/>
			</div>
		</div>

		<div>
			<label for="emailUser" class="mb-1 block text-sm font-medium text-gray-700">Email de Workspace</label>
			<div class="flex">
				<input
					id="emailUser"
					type="text"
					value={emailUser}
					disabled
					class="w-full rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-500"
				/>
				<span class="flex items-center rounded-r-lg border border-gray-300 bg-gray-50 px-3 text-sm text-gray-500">
					@{DOMAIN}
				</span>
			</div>
			{#if !emailUser}
				<p class="mt-1 text-xs text-gray-400">Se genera automáticamente desde nombre y apellido</p>
			{/if}
		</div>

		<div>
			<label for="orgUnit" class="mb-1 block text-sm font-medium text-gray-700">Unidad organizativa</label>
			<select
				id="orgUnit"
				bind:value={orgUnitPath}
				class="w-full cursor-pointer rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
			>
				{#each OU_OPTIONS as ou}
					<option value={ou.value}>{ou.label}</option>
				{/each}
			</select>
		</div>

		<div>
			<label for="notifEmail" class="mb-1 block text-sm font-medium text-gray-700">
				Email personal <span class="text-red-500">*</span>
			</label>
			<input
				id="notifEmail"
				type="email"
				bind:value={notificationEmail}
				required
				placeholder="alumno@gmail.com"
				class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
			/>
			<p class="mt-1 text-xs text-gray-400">Se enviarán las credenciales a este correo</p>
		</div>

		<div>
			<div class="flex items-center gap-2">
				<input id="autoPass" type="checkbox" bind:checked={autoPassword} class="cursor-pointer rounded" />
				<label for="autoPass" class="cursor-pointer text-sm text-gray-700">Generar contraseña automáticamente</label>
			</div>
			{#if !autoPassword}
				<input
					type="text"
					bind:value={customPassword}
					required
					minlength="8"
					placeholder="Mínimo 8 caracteres"
					class="mt-2 w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
				/>
			{/if}
		</div>

		<button
			type="submit"
			disabled={loading}
			class="w-full cursor-pointer rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-blue-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
		>
			{loading ? 'Creando...' : 'Crear cuenta y notificar'}
		</button>
	</form>
</div>

<Modal show={resultModal.show} title="Cuenta creada" onclose={() => resultModal.show = false}>
	<div class="space-y-3">
		<div class="rounded-lg bg-gray-50 p-3">
			<p class="mb-1 text-xs font-medium text-gray-500">Email de Workspace</p>
			<div class="flex items-center justify-between">
				<p class="font-mono text-sm font-semibold text-gray-900">{resultModal.email}</p>
				<button
					onclick={() => copyToClipboard(resultModal.email)}
					class="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50"
				>
					Copiar
				</button>
			</div>
		</div>

		<div class="rounded-lg bg-gray-50 p-3">
			<p class="mb-1 text-xs font-medium text-gray-500">Contraseña</p>
			<div class="flex items-center justify-between">
				<p class="font-mono text-sm font-semibold text-gray-900">{resultModal.password}</p>
				<button
					onclick={() => copyToClipboard(resultModal.password)}
					class="cursor-pointer rounded-md px-2 py-1 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50"
				>
					Copiar
				</button>
			</div>
		</div>

		<div>
			{#if resultModal.notified}
				<div class="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2.5 text-sm text-green-700">
					<svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					Credenciales enviadas al email personal
				</div>
			{:else}
				<div class="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-700">
					<svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
					No se pudo enviar el email: {resultModal.notifyError}
				</div>
			{/if}
		</div>
	</div>

	<div class="mt-4 flex justify-end">
		<button
			onclick={() => resultModal.show = false}
			class="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
		>
			Cerrar
		</button>
	</div>
</Modal>
