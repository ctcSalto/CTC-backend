<script>
	import { base } from '$app/paths';
	import { token, usuario, loading, error, loginWithGoogle } from '$lib/auth.js';
	import { goto } from '$app/navigation';

	// Si ya esta autenticado, redirigir al dashboard
	$effect(() => {
		if ($usuario) {
			goto(`${base}/dashboard`);
		}
	});
</script>

<div style="text-align: center; margin-top: 4rem;">
	<h1>Portal Academico CTC</h1>
	<p style="color: #666; margin-bottom: 2rem;">Test de autenticacion Google OAuth 2.0</p>

	{#if $loading}
		<p>Cargando...</p>
	{:else if $error}
		<div style="background: #fee; border: 1px solid #fcc; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
			<p style="color: #c33; margin: 0;">Error: {$error}</p>
		</div>
		<button onclick={loginWithGoogle} style="padding: 0.8rem 2rem; font-size: 1rem; background: #4285f4; color: white; border: none; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem;">
			Reintentar con Google
		</button>
	{:else}
		<button onclick={loginWithGoogle} style="padding: 0.8rem 2rem; font-size: 1.1rem; background: #4285f4; color: white; border: none; border-radius: 8px; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem;">
			<svg width="20" height="20" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.9 33.6 29.4 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6 29.3 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.2-2.7-.4-3.9z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 15.1 18.8 12 24 12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.4 0-9.9-3.6-11.3-8.5l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.3 44 34 44 24c0-1.3-.2-2.7-.4-3.9z"/></svg>
			Iniciar sesion con Google
		</button>
		<p style="color: #999; margin-top: 1rem; font-size: 0.9rem;">Solo cuentas @ctcsalto.edu.uy</p>
	{/if}
</div>
