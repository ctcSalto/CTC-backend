import { get } from 'svelte/store';
import { token, logout } from '$lib/stores/auth';
import { base } from '$app/paths';

class ApiError extends Error {
	status: number;
	constructor(message: string, status: number) {
		super(message);
		this.status = status;
	}
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
	const currentToken = get(token);
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {})
	};

	const res = await fetch(path, { ...options, headers });

	if (res.status === 401 || res.status === 403) {
		logout();
		window.location.href = `${base}/login`;
		throw new ApiError('No autorizado', res.status);
	}

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new ApiError(err.detail || 'Error en la API', res.status);
	}

	return res.json();
}

// ── Auth ──
export async function login(email: string, password: string) {
	const res = await fetch('/auth/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ email, password })
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: 'Error de autenticación' }));
		const detail = typeof err.detail === 'string' ? err.detail : 'Credenciales inválidas';
		throw new ApiError(detail, res.status);
	}

	return res.json();
}

export async function getMe() {
	return apiFetch<Record<string, unknown>>('/auth/me');
}

// ── Users ──
export async function listAccounts(query?: string, maxResults = 100) {
	const params = new URLSearchParams({ max_results: String(maxResults) });
	if (query) params.set('query', query);
	return apiFetch<{ status: string; data: unknown }>(`/google/test/list-accounts?${params}`);
}

export async function getAccount(email: string) {
	return apiFetch<{ status: string; data: unknown }>('/google/test/get-account', {
		method: 'POST',
		body: JSON.stringify({ primaryEmail: email })
	});
}

export async function createAccountAndNotify(data: {
	primaryEmail: string;
	givenName: string;
	familyName: string;
	orgUnitPath: string;
	notificationEmail: string;
	password?: string;
}) {
	return apiFetch<{
		status: string;
		message: string;
		data: unknown;
		temporaryPassword: string;
		notificationSent: boolean;
		notificationError: string | null;
	}>('/google/test/create-account-and-notify', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateAccount(data: {
	primaryEmail: string;
	givenName?: string;
	familyName?: string;
	orgUnitPath?: string;
	suspended?: boolean;
	password?: string;
}) {
	return apiFetch<{ status: string; message: string }>('/google/test/update-account', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function deleteAccount(email: string) {
	return apiFetch<{ status: string; message: string }>('/google/test/delete-account', {
		method: 'POST',
		body: JSON.stringify({ primaryEmail: email })
	});
}

export async function suspendAccount(email: string) {
	return apiFetch<{ status: string; message: string }>('/google/test/suspend-account', {
		method: 'POST',
		body: JSON.stringify({ primaryEmail: email })
	});
}

export async function unsuspendAccount(email: string) {
	return apiFetch<{ status: string; message: string }>('/google/test/unsuspend-account', {
		method: 'POST',
		body: JSON.stringify({ primaryEmail: email })
	});
}

export async function generatePassword(length = 16) {
	return apiFetch<{ status: string; password: string }>(`/google/test/generate-password?length=${length}`);
}

// ── Groups ──
export async function listGroups(maxResults = 100) {
	return apiFetch<{ status: string; data: unknown }>(`/google/test/list-groups?max_results=${maxResults}`);
}

export async function getGroup(groupId: string) {
	return apiFetch<{ status: string; data: unknown }>('/google/test/get-group', {
		method: 'POST',
		body: JSON.stringify({ groupId })
	});
}

export async function createGroup(data: { groupEmail: string; groupName: string; description?: string }) {
	return apiFetch<{ status: string; message: string }>('/google/test/create-group', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function updateGroup(data: {
	groupId: string;
	name?: string;
	description?: string;
	email?: string;
}) {
	return apiFetch<{ status: string; message: string }>('/google/test/update-group', {
		method: 'POST',
		body: JSON.stringify(data)
	});
}

export async function deleteGroup(groupId: string) {
	return apiFetch<{ status: string; message: string }>('/google/test/delete-group', {
		method: 'POST',
		body: JSON.stringify({ groupId })
	});
}

export async function listGroupMembers(groupEmail: string) {
	return apiFetch<{ status: string; data: unknown }>('/google/test/list-group-members', {
		method: 'POST',
		body: JSON.stringify({ groupEmail })
	});
}

export async function addToGroup(primaryEmail: string, groupId: string) {
	return apiFetch<{ status: string; message: string }>('/google/test/add-to-group', {
		method: 'POST',
		body: JSON.stringify({ primaryEmail, groupId })
	});
}

export async function removeFromGroup(primaryEmail: string, groupId: string) {
	return apiFetch<{ status: string; message: string }>('/google/test/remove-from-group', {
		method: 'POST',
		body: JSON.stringify({ primaryEmail, groupId })
	});
}
