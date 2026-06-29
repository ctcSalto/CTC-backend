<script lang="ts">
	import { user, logout } from '$lib/stores/auth';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	let pageName = $derived.by(() => {
		const path = $page.url.pathname;
		if (path.includes('/users/create')) return 'Crear usuario';
		if (path.includes('/users/')) return 'Editar usuario';
		if (path.includes('/users')) return 'Usuarios';
		if (path.includes('/groups/create')) return 'Crear grupo';
		if (path.includes('/groups/')) return 'Editar grupo';
		if (path.includes('/groups')) return 'Grupos';
		return 'Inicio';
	});

	async function handleLogout() {
		logout();
		goto(`${base}/login`);
	}
</script>

<header class="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
	<h2 class="text-sm font-semibold text-gray-700">{pageName}</h2>
	<div class="flex items-center gap-3">
		{#if $user}
			<div class="flex items-center gap-2">
				<div class="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-600">
					{String($user.email || '').charAt(0).toUpperCase()}
				</div>
				<span class="text-sm text-gray-600">{$user.email}</span>
			</div>
		{/if}
		<button
			onclick={handleLogout}
			class="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
		>
			Cerrar sesión
		</button>
	</div>
</header>
