<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		show: boolean;
		title: string;
		onclose: () => void;
	}

	let { show, title, onclose, children } = $props<Props & { children: any }>();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && show) onclose();
	}

	onMount(() => {
		document.addEventListener('keydown', handleKeydown);
		return () => document.removeEventListener('keydown', handleKeydown);
	});
</script>

{#if show}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm transition-opacity duration-200"
		role="dialog"
		aria-modal="true"
		aria-labelledby="modal-title"
		onclick={onclose}
		onkeydown={(e) => e.key === 'Escape' && onclose()}
		tabindex="-1"
	>
		<div
			class="mx-4 w-full max-w-md animate-in rounded-2xl bg-white p-6 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="mb-4 flex items-center justify-between">
				<h3 id="modal-title" class="text-lg font-semibold text-gray-900">{title}</h3>
				<button
					onclick={onclose}
					class="cursor-pointer rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
					aria-label="Cerrar"
				>
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
			{@render children()}
		</div>
	</div>
{/if}
