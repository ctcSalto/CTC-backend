<script>
	import { base } from '$app/paths';
	import { token, usuario, logout } from '$lib/auth.js';

	let { children } = $props();
</script>

<nav style="background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center;">
	<a href="{base}/" style="color: white; text-decoration: none; font-size: 1.2rem; font-weight: bold;">
		CTC - Test Login v2
	</a>

	{#if $usuario}
		<div style="display: flex; align-items: center; gap: 1rem;">
			<span style="background: #e94560; padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.85rem;">
				{$usuario.rol}
			</span>
			<span>{$usuario.nombre} {$usuario.apellido}</span>
			<a href="{base}/dashboard" style="color: #ccc; text-decoration: none;">Dashboard</a>
			{#if $usuario.rol === 'administrativo'}
				<a href="{base}/previaturas" style="color: #ccc; text-decoration: none;">Previaturas</a>
				<a href="{base}/notificaciones" style="color: #ccc; text-decoration: none;">Notificaciones</a>
			{/if}
			<button onclick={logout} style="background: none; border: 1px solid #ccc; color: #ccc; padding: 0.3rem 0.8rem; border-radius: 4px; cursor: pointer;">
				Cerrar sesion
			</button>
		</div>
	{/if}
</nav>

<main style="max-width: 900px; margin: 2rem auto; padding: 0 1rem;">
	{@render children()}
</main>

<style>
	:global(body) {
		margin: 0;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
		background: #f5f5f5;
		color: #333;
	}
</style>
