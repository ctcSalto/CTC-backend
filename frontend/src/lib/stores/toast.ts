import { writable } from 'svelte/store';
import type { Toast } from '$lib/types';

let nextId = 0;

export const toasts = writable<Toast[]>([]);

export function addToast(type: Toast['type'], message: string, duration = 4000) {
	const id = nextId++;
	toasts.update((t) => [...t, { id, type, message }]);
	setTimeout(() => {
		toasts.update((t) => t.filter((toast) => toast.id !== id));
	}, duration);
}

export function success(message: string) {
	addToast('success', message);
}

export function error(message: string) {
	addToast('error', message, 6000);
}

export function removeToast(id: number) {
	toasts.update((t) => t.filter((toast) => toast.id !== id));
}
