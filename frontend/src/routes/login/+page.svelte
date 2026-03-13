<script lang="ts">
	import { login, getMe } from '$lib/api';
	import { token, user } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	let email = $state('');
	let password = $state('');
	let errorMsg = $state('');
	let loading = $state(false);
	let showPassword = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		errorMsg = '';
		loading = true;

		try {
			const data = await login(email, password);
			token.set(data.access_token);

			const me = await getMe();
			user.set(me);

			goto(`${base}/users`);
		} catch (err: any) {
			errorMsg = err.message || 'Error al iniciar sesión';
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-800 to-slate-900">
	<div class="w-full max-w-sm">
		<div class="animate-in rounded-2xl bg-white p-8 shadow-2xl">
			<div class="mb-8 text-center">
				<div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-xl bg-blue-600 text-white shadow-lg">
					<svg class="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
					</svg>
				</div>
				<h1 class="text-2xl font-bold text-gray-900">CTC Admin</h1>
				<p class="mt-1 text-sm text-gray-500">Panel de Google Workspace</p>
			</div>

			<form onsubmit={handleSubmit} class="space-y-4">
				<div>
					<label for="email" class="mb-1 block text-sm font-medium text-gray-700">Correo electrónico</label>
					<input
						id="email"
						type="email"
						bind:value={email}
						required
						autocomplete="email"
						class="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
						placeholder="usuario@email.com"
					/>
				</div>

				<div>
					<label for="password" class="mb-1 block text-sm font-medium text-gray-700">Contraseña</label>
					<div class="relative">
						<input
							id="password"
							type={showPassword ? 'text' : 'password'}
							bind:value={password}
							required
							autocomplete="current-password"
							class="w-full rounded-lg border border-gray-300 px-3 py-2.5 pr-10 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
							placeholder="••••••••"
						/>
						<button
							type="button"
							onclick={() => showPassword = !showPassword}
							class="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer rounded p-1 text-gray-400 transition-colors hover:text-gray-600"
							aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
						>
							{#if showPassword}
								<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
								</svg>
							{:else}
								<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
								</svg>
							{/if}
						</button>
					</div>
				</div>

				{#if errorMsg}
					<div class="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-600">
						<svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						{errorMsg}
					</div>
				{/if}

				<button
					type="submit"
					disabled={loading}
					class="w-full cursor-pointer rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-blue-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
				>
					{loading ? 'Ingresando...' : 'Ingresar'}
				</button>
			</form>
		</div>
	</div>
</div>
