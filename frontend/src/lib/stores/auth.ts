import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export const token = writable<string | null>(
	browser ? localStorage.getItem('jwt_token') : null
);

export const user = writable<Record<string, unknown> | null>(null);

token.subscribe((value) => {
	if (browser) {
		if (value) {
			localStorage.setItem('jwt_token', value);
		} else {
			localStorage.removeItem('jwt_token');
		}
	}
});

export function logout() {
	token.set(null);
	user.set(null);
}
