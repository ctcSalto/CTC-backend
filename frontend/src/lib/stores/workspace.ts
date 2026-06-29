import { writable, get } from 'svelte/store';
import { listAccounts, listGroups } from '$lib/api';

export const accounts = writable<any[]>([]);
export const groups = writable<any[]>([]);
export const accountsLoaded = writable(false);
export const groupsLoaded = writable(false);

export async function loadAccounts(force = false) {
	if (get(accountsLoaded) && !force) return get(accounts);
	try {
		const res = await listAccounts(undefined, 500);
		const data = res.data as any;
		const list = data?.users || data || [];
		accounts.set(list);
		accountsLoaded.set(true);
		return list;
	} catch {
		return get(accounts);
	}
}

export async function loadGroups(force = false) {
	if (get(groupsLoaded) && !force) return get(groups);
	try {
		const res = await listGroups(200);
		const data = res.data as any;
		const list = data?.groups || data || [];
		groups.set(list);
		groupsLoaded.set(true);
		return list;
	} catch {
		return get(groups);
	}
}

export function invalidateAccounts() {
	accountsLoaded.set(false);
}

export function invalidateGroups() {
	groupsLoaded.set(false);
}
