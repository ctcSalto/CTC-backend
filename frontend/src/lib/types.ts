export interface ApiResponse<T = unknown> {
	status: string;
	message?: string;
	data?: T;
}

export interface CreateAccountRequest {
	primaryEmail: string;
	givenName: string;
	familyName: string;
	orgUnitPath: string;
	notificationEmail: string;
	password?: string;
}

export interface UpdateAccountRequest {
	primaryEmail: string;
	givenName?: string;
	familyName?: string;
	orgUnitPath?: string;
	suspended?: boolean;
	password?: string;
}

export interface CreateAccountResponse {
	status: string;
	message: string;
	data: unknown;
	temporaryPassword: string;
	notificationSent: boolean;
	notificationError: string | null;
}

export interface UserEmailRequest {
	primaryEmail: string;
}

export interface CreateGroupRequest {
	groupEmail: string;
	groupName: string;
	description?: string;
}

export interface UpdateGroupRequest {
	groupId: string;
	name?: string;
	description?: string;
	email?: string;
}

export interface AddToGroupRequest {
	primaryEmail: string;
	groupId: string;
}

export interface PasswordResponse {
	status: string;
	password: string;
	length: number;
}

export interface Toast {
	id: number;
	type: 'success' | 'error' | 'info';
	message: string;
}
