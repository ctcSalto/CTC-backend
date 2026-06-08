<script>
	import { base } from '$app/paths';
	import { usuario, token, loading } from '$lib/auth.js';
	import { goto } from '$app/navigation';

	// Si no esta autenticado, volver al login
	$effect(() => {
		if (!$loading && !$usuario && !$token) {
			goto(`${base}/`);
		}
	});
</script>

{#if $loading}
	<p>Cargando datos del usuario...</p>
{:else if $usuario}
	<div style="margin-bottom: 2rem;">
		<h1>Dashboard</h1>
		<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
			<h3 style="margin-top: 0;">Datos del usuario</h3>
			<table style="width: 100%; border-collapse: collapse;">
				<tbody>
					<tr><td style="padding: 0.5rem; font-weight: bold; width: 160px;">Nombre</td><td>{$usuario.nombre} {$usuario.apellido}</td></tr>
					<tr style="background: #f9f9f9;"><td style="padding: 0.5rem; font-weight: bold;">Email</td><td>{$usuario.email}</td></tr>
					<tr><td style="padding: 0.5rem; font-weight: bold;">Rol</td><td><span style="background: #e94560; color: white; padding: 0.2rem 0.6rem; border-radius: 1rem; font-size: 0.85rem;">{$usuario.rol}</span></td></tr>
					<tr style="background: #f9f9f9;"><td style="padding: 0.5rem; font-weight: bold;">Google ID</td><td style="font-family: monospace; font-size: 0.85rem;">{$usuario.google_id}</td></tr>
					{#if $usuario.moodle_id}
						<tr><td style="padding: 0.5rem; font-weight: bold;">Moodle ID</td><td>{$usuario.moodle_id}</td></tr>
					{/if}
					{#if $usuario.ou_google}
						<tr style="background: #f9f9f9;"><td style="padding: 0.5rem; font-weight: bold;">OU Google</td><td style="font-family: monospace; font-size: 0.85rem;">{$usuario.ou_google}</td></tr>
					{/if}
					<tr><td style="padding: 0.5rem; font-weight: bold;">Activo</td><td>{$usuario.activo ? 'Si' : 'No'}</td></tr>
				</tbody>
			</table>
		</div>
	</div>

	<!-- Panel segun rol -->
	{#if $usuario.rol === 'estudiante'}
		<div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 1.5rem; border-radius: 0 8px 8px 0;">
			<h2 style="margin-top: 0; color: #1565c0;">Panel Estudiante</h2>
			<p>Bienvenido/a al portal de estudiantes.</p>
			<ul>
				<li>Consultar inscripciones</li>
				<li>Ver calificaciones</li>
				<li>Inscripcion a examenes</li>
				<li>Escolaridad</li>
			</ul>
		</div>
	{:else if $usuario.rol === 'docente'}
		<div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 1.5rem; border-radius: 0 8px 8px 0;">
			<h2 style="margin-top: 0; color: #2e7d32;">Panel Docente</h2>
			<p>Bienvenido/a al portal de docentes.</p>
			<ul>
				<li>Gestionar calificaciones</li>
				<li>Ver listado de alumnos</li>
				<li>Instancias de evaluacion</li>
			</ul>
		</div>
	{:else if $usuario.rol === 'administrativo'}
		<div style="background: #fce4ec; border-left: 4px solid #e91e63; padding: 1.5rem; border-radius: 0 8px 8px 0;">
			<h2 style="margin-top: 0; color: #ad1457;">Panel Administrativo</h2>
			<p>Bienvenido/a al panel de administracion.</p>
			<ul>
				<li>Gestion de programas y materias</li>
				<li>Administrar inscripciones</li>
				<li>Gestion de usuarios</li>
				<li>Politicas de calificacion</li>
				<li>Previaturas</li>
			</ul>
		</div>
	{:else}
		<div style="background: #fff3e0; border-left: 4px solid #ff9800; padding: 1.5rem; border-radius: 0 8px 8px 0;">
			<h2 style="margin-top: 0; color: #e65100;">Rol desconocido: {$usuario.rol}</h2>
			<p>Tu rol no tiene un panel asignado todavia.</p>
		</div>
	{/if}

	<!-- Token JWT (debug) -->
	<details style="margin-top: 2rem;">
		<summary style="cursor: pointer; color: #666;">Ver JWT token (debug)</summary>
		<pre style="background: #1a1a2e; color: #0f0; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.8rem; word-break: break-all; white-space: pre-wrap;">{$token}</pre>
	</details>
{/if}
