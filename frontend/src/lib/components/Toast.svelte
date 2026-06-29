<script lang="ts">
	import { toasts, removeToast } from '$lib/stores/toast';
</script>

<div class="fixed top-4 right-4 z-[60] flex flex-col gap-2">
	{#each $toasts as toast (toast.id)}
		<div
			class="flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg transition-all duration-300 animate-in"
			class:bg-green-600={toast.type === 'success'}
			class:bg-red-600={toast.type === 'error'}
			class:bg-blue-600={toast.type === 'info'}
			role="alert"
			aria-live="polite"
		>
			{#if toast.type === 'success'}
				<svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
			{:else if toast.type === 'error'}
				<svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
			{:else}
				<svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>
			{/if}
			<span class="flex-1">{toast.message}</span>
			<button
				onclick={() => removeToast(toast.id)}
				class="cursor-pointer rounded p-0.5 transition-colors hover:bg-white/20"
				aria-label="Cerrar notificacion"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
	{/each}
</div>
