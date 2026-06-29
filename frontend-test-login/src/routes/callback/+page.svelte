<script>
	import { base } from '$app/paths';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { token, fetchMe } from '$lib/auth.js';

	let status = $state('Procesando login...');

	onMount(async () => {
		const urlToken = $page.url.searchParams.get('token');

		if (!urlToken) {
			status = 'Error: no se recibio token en la URL';
			return;
		}

		// Guardar token y obtener datos del usuario
		token.set(urlToken);
		await fetchMe(urlToken);

		// Limpiar el token de la URL y redirigir al dashboard
		status = 'Login exitoso, redirigiendo...';
		goto(`${base}/dashboard`, { replaceState: true });
	});
</script>

<div style="text-align: center; margin-top: 4rem;">
	<h2>{status}</h2>
</div>
