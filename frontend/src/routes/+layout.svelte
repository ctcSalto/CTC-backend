<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import { token, user } from '$lib/stores/auth';
	import { getMe } from '$lib/api';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import Topbar from '$lib/components/Topbar.svelte';
	import Toast from '$lib/components/Toast.svelte';

	let { children } = $props();

	let loading = $state(true);

	$effect(() => {
		const isLogin = $page.url.pathname === `${base}/login`;
		if (!$token && !isLogin) {
			goto(`${base}/login`);
		}
	});

	onMount(async () => {
		if ($token) {
			try {
				const me = await getMe();
				user.set(me);
			} catch {
				token.set(null);
				goto(`${base}/login`);
			}
		}
		loading = false;
	});

	let isLoginPage = $derived($page.url.pathname === `${base}/login`);
</script>

<Toast />

{#if loading}
	<div class="flex h-screen items-center justify-center bg-gray-50">
		<div class="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
	</div>
{:else if isLoginPage}
	{@render children()}
{:else}
	<div class="flex h-screen bg-gray-50">
		<Sidebar />
		<div class="flex flex-1 flex-col overflow-hidden">
			<Topbar />
			<main class="flex-1 overflow-auto p-6">
				{@render children()}
			</main>
		</div>
	</div>
{/if}
