import { writable } from 'svelte/store';
import { base } from '$app/paths';

// Estado de autenticacion
export const token = writable(null);
export const usuario = writable(null);
export const loading = writable(false);
export const error = writable(null);

// Inicializar desde localStorage
if (typeof window !== 'undefined') {
	const saved = localStorage.getItem('v2_token');
	if (saved) {
		token.set(saved);
		fetchMe(saved);
	}
}

// Guardar token en localStorage cuando cambia
token.subscribe((value) => {
	if (typeof window !== 'undefined') {
		if (value) {
			localStorage.setItem('v2_token', value);
		} else {
			localStorage.removeItem('v2_token');
		}
	}
});

/**
 * Inicia el flujo OAuth redirigiendo al backend.
 * Como el frontend esta en el mismo origen que el backend,
 * el callback vuelve a /test-login/callback en el mismo puerto.
 */
export function loginWithGoogle() {
	const callbackUrl = `${window.location.origin}${base}/callback`;
	const loginUrl = `/v2/auth/google/login?redirect_to=${encodeURIComponent(callbackUrl)}`;
	window.location.href = loginUrl;
}

/**
 * Pide los datos del usuario autenticado al endpoint /v2/auth/me.
 */
export async function fetchMe(jwt) {
	loading.set(true);
	error.set(null);
	try {
		const res = await fetch('/v2/auth/me', {
			headers: { Authorization: `Bearer ${jwt}` }
		});
		if (!res.ok) {
			const data = await res.json().catch(() => ({}));
			throw new Error(data.detail || `Error ${res.status}`);
		}
		const data = await res.json();
		usuario.set(data);
	} catch (err) {
		error.set(err.message);
		token.set(null);
		usuario.set(null);
	} finally {
		loading.set(false);
	}
}

/**
 * Cierra sesion: llama al endpoint de logout y limpia el estado local.
 */
export async function logout() {
	const currentToken = getTokenValue();
	if (currentToken) {
		try {
			await fetch('/v2/auth/logout', {
				method: 'POST',
				headers: { Authorization: `Bearer ${currentToken}` }
			});
		} catch {
			// Si falla el logout remoto, igual limpiamos local
		}
	}
	token.set(null);
	usuario.set(null);
}

function getTokenValue() {
	let value = null;
	token.subscribe((v) => (value = v))();
	return value;
}

/**
 * Helper para llamadas autenticadas a la API.
 * Retorna {ok, data, error, status}.
 */
export async function apiFetch(url, options = {}) {
	const jwt = getTokenValue();
	const headers = {
		Authorization: `Bearer ${jwt}`,
		'Content-Type': 'application/json',
		...options.headers,
	};
	try {
		const res = await fetch(url, { ...options, headers });
		const data = await res.json().catch(() => null);
		if (!res.ok) {
			return { ok: false, data: null, error: data?.detail || `Error ${res.status}`, status: res.status };
		}
		return { ok: true, data, error: null, status: res.status };
	} catch (err) {
		return { ok: false, data: null, error: err.message, status: 0 };
	}
}
