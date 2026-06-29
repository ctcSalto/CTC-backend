<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/stores';

	const links = [
		{ href: `${base}/users`, label: 'Usuarios', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z' },
		{ href: `${base}/groups`, label: 'Grupos', icon: 'M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z' },
	];
</script>

<aside class="flex h-screen w-64 flex-col bg-slate-800 text-white">
	<div class="flex h-16 items-center gap-3 border-b border-slate-700 px-5">
		<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600">
			<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
			</svg>
		</div>
		<div>
			<h1 class="text-sm font-bold leading-tight">CTC Admin</h1>
			<p class="text-xs text-slate-400">Google Workspace</p>
		</div>
	</div>

	<nav class="mt-4 flex-1 space-y-1 px-3">
		{#each links as link}
			{@const active = $page.url.pathname.startsWith(link.href)}
			<a
				href={link.href}
				class="relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150
					{active
						? 'bg-blue-600/20 text-blue-400'
						: 'text-slate-300 hover:bg-slate-700/60 hover:text-white'}"
			>
				{#if active}
					<span class="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-blue-400"></span>
				{/if}
				<svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={link.icon} />
				</svg>
				{link.label}
			</a>
		{/each}
	</nav>

	<div class="border-t border-slate-700 p-4">
		<p class="text-xs text-slate-400">Panel de administración</p>
	</div>
</aside>
