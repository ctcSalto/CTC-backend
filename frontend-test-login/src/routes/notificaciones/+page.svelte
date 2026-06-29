<script>
	import { base } from '$app/paths';
	import { usuario, token, loading, apiFetch } from '$lib/auth.js';
	import { goto } from '$app/navigation';

	// Auth guard
	$effect(() => {
		if (!$loading && !$usuario && !$token) goto(`${base}/`);
	});

	// Estado - Pendientes
	let pendientes = $state([]);
	let seleccionados = $state(new Set());
	let cargandoPendientes = $state(false);

	// Estado - Historial
	let historial = $state([]);
	let historialPage = $state(1);
	let cargandoHistorial = $state(false);

	// Estado - Envio individual
	let indUsuarioId = $state('');
	let indAsunto = $state('');
	let indMensaje = $state('');

	// Estado - Envio masivo
	let masFiltro = $state('programa_id');
	let masFiltroValor = $state('');
	let masAsunto = $state('');
	let masMensaje = $state('');

	// Resultado de operaciones
	let resultado = $state(null);
	let error = $state('');

	// Cargar pendientes al montar
	$effect(() => {
		if ($usuario) cargarPendientes();
	});

	// ── Pendientes ──────────────────────────────────

	async function cargarPendientes() {
		cargandoPendientes = true;
		error = '';
		const res = await apiFetch('/v2/admin/notificaciones/pendientes');
		cargandoPendientes = false;
		if (res.ok) {
			pendientes = res.data;
			seleccionados = new Set();
		} else {
			error = res.error;
		}
	}

	function toggleSeleccion(id) {
		const nuevo = new Set(seleccionados);
		if (nuevo.has(id)) nuevo.delete(id);
		else nuevo.add(id);
		seleccionados = nuevo;
	}

	function seleccionarTodos() {
		if (seleccionados.size === pendientes.length) {
			seleccionados = new Set();
		} else {
			seleccionados = new Set(pendientes.map(p => p.inscripcion_id));
		}
	}

	async function enviarCalificacion(inscripcionId) {
		resultado = null;
		error = '';
		const res = await apiFetch(`/v2/admin/notificaciones/calificacion/${inscripcionId}`, { method: 'POST' });
		if (res.ok) {
			resultado = { tipo: 'exito', mensaje: `Notificacion enviada para inscripcion ${inscripcionId}` };
			await cargarPendientes();
		} else {
			resultado = { tipo: 'error', mensaje: res.error, status: res.status };
		}
	}

	async function enviarBatch() {
		if (seleccionados.size === 0) {
			error = 'Selecciona al menos una inscripcion';
			return;
		}
		resultado = null;
		error = '';
		const res = await apiFetch('/v2/admin/notificaciones/calificacion/batch', {
			method: 'POST',
			body: JSON.stringify({ inscripcion_ids: [...seleccionados] }),
		});
		if (res.ok) {
			resultado = {
				tipo: 'exito',
				mensaje: `Batch completado: ${res.data.enviados} enviados, ${res.data.errores?.length || 0} errores`,
				data: res.data,
			};
			await cargarPendientes();
		} else {
			resultado = { tipo: 'error', mensaje: res.error, status: res.status };
		}
	}

	// ── Historial ───────────────────────────────────

	async function cargarHistorial() {
		cargandoHistorial = true;
		const res = await apiFetch(`/v2/admin/notificaciones/historial?page=${historialPage}&per_page=20`);
		cargandoHistorial = false;
		if (res.ok) {
			historial = res.data;
		} else {
			error = res.error;
		}
	}

	// ── Envio individual ────────────────────────────

	async function enviarIndividual() {
		if (!indUsuarioId || !indAsunto || !indMensaje) {
			error = 'Completa todos los campos';
			return;
		}
		resultado = null;
		error = '';
		const res = await apiFetch('/v2/admin/notificaciones/individual', {
			method: 'POST',
			body: JSON.stringify({
				usuario_id: parseInt(indUsuarioId),
				asunto: indAsunto,
				mensaje: indMensaje,
			}),
		});
		if (res.ok) {
			resultado = { tipo: 'exito', mensaje: 'Email individual enviado correctamente' };
		} else {
			resultado = { tipo: 'error', mensaje: res.error, status: res.status };
		}
	}

	// ── Envio masivo ────────────────────────────────

	async function enviarMasivo() {
		if (!masFiltroValor || !masAsunto || !masMensaje) {
			error = 'Completa todos los campos';
			return;
		}
		resultado = null;
		error = '';
		const filtro = {};
		filtro[masFiltro] = parseInt(masFiltroValor);
		const res = await apiFetch('/v2/admin/notificaciones/masivo', {
			method: 'POST',
			body: JSON.stringify({ filtro, asunto: masAsunto, mensaje: masMensaje }),
		});
		if (res.ok) {
			resultado = {
				tipo: 'exito',
				mensaje: `Masivo completado: ${res.data.enviados} enviados, ${res.data.errores?.length || 0} errores`,
				data: res.data,
			};
		} else {
			resultado = { tipo: 'error', mensaje: res.error, status: res.status };
		}
	}
</script>

{#if $loading}
	<p>Cargando...</p>
{:else if $usuario}
	<h1>Test Notificaciones</h1>

	<!-- Resultado global -->
	{#if resultado}
		<div style="margin-bottom: 1rem; padding: 1rem; border-radius: 6px;
			background: {resultado.tipo === 'exito' ? '#e8f5e9' : '#ffebee'};
			border-left: 4px solid {resultado.tipo === 'exito' ? '#4caf50' : '#f44336'};">
			{#if resultado.tipo === 'exito'}
				<strong style="color: #2e7d32;">{resultado.mensaje}</strong>
				{#if resultado.data}
					<pre style="background: #f5f5f5; padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; overflow-x: auto; margin-top: 0.5rem;">{JSON.stringify(resultado.data, null, 2)}</pre>
				{/if}
			{:else}
				<strong style="color: #c62828;">Error {resultado.status}</strong>
				<p style="margin: 0.3rem 0 0; color: #b71c1c;">{resultado.mensaje}</p>
			{/if}
		</div>
	{/if}

	{#if error}
		<div style="background: #ffebee; border-left: 4px solid #f44336; padding: 1rem; border-radius: 0 6px 6px 0; margin-bottom: 1rem;">
			<strong style="color: #c62828;">Error:</strong>
			<span style="color: #b71c1c;">{error}</span>
		</div>
	{/if}

	<!-- Pendientes de calificacion -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<div style="display: flex; justify-content: space-between; align-items: center;">
			<h3 style="margin-top: 0;">Calificaciones pendientes de notificar</h3>
			<div style="display: flex; gap: 0.5rem;">
				<button onclick={cargarPendientes} disabled={cargandoPendientes}
					style="background: #1a1a2e; color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
					Recargar
				</button>
				{#if seleccionados.size > 0}
					<button onclick={enviarBatch}
						style="background: #e94560; color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
						Enviar seleccionados ({seleccionados.size})
					</button>
				{/if}
			</div>
		</div>

		{#if cargandoPendientes}
			<p style="color: #666;">Cargando...</p>
		{:else if pendientes.length === 0}
			<p style="color: #999;">No hay calificaciones pendientes de notificar.</p>
		{:else}
			<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
				<thead>
					<tr style="background: #f0f0f0;">
						<th style="padding: 0.4rem; border: 1px solid #ddd; width: 30px;">
							<input type="checkbox" checked={seleccionados.size === pendientes.length} onchange={seleccionarTodos} />
						</th>
						<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Insc. ID</th>
						<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Alumno</th>
						<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Materia</th>
						<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Estado</th>
						<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Accion</th>
					</tr>
				</thead>
				<tbody>
					{#each pendientes as pend}
						<tr>
							<td style="padding: 0.4rem; border: 1px solid #ddd; text-align: center;">
								<input type="checkbox" checked={seleccionados.has(pend.inscripcion_id)}
									onchange={() => toggleSeleccion(pend.inscripcion_id)} />
							</td>
							<td style="padding: 0.4rem; border: 1px solid #ddd; font-family: monospace;">{pend.inscripcion_id}</td>
							<td style="padding: 0.4rem; border: 1px solid #ddd;">{pend.alumno_nombre || pend.usuario_id || '-'}</td>
							<td style="padding: 0.4rem; border: 1px solid #ddd;">{pend.materia_nombre || '-'}</td>
							<td style="padding: 0.4rem; border: 1px solid #ddd;">
								<span style="padding: 0.1rem 0.5rem; border-radius: 3px; font-size: 0.8rem;
									background: {pend.estado === 'exonerado' || pend.estado === 'aprobado' ? '#e8f5e9' : '#ffebee'};
									color: {pend.estado === 'exonerado' || pend.estado === 'aprobado' ? '#2e7d32' : '#c62828'};">
									{pend.estado}
								</span>
							</td>
							<td style="padding: 0.4rem; border: 1px solid #ddd;">
								<button onclick={() => enviarCalificacion(pend.inscripcion_id)}
									style="background: #4caf50; color: white; border: none; padding: 0.2rem 0.5rem; border-radius: 3px; cursor: pointer; font-size: 0.8rem;">
									Enviar
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>

	<!-- Envio individual -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<h3 style="margin-top: 0;">Envio individual</h3>
		<div style="display: flex; flex-direction: column; gap: 0.5rem;">
			<div style="display: flex; gap: 0.5rem; align-items: center;">
				<label style="width: 100px; font-weight: bold; font-size: 0.85rem;">usuario_id:</label>
				<input type="number" bind:value={indUsuarioId} placeholder="ID del usuario"
					style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1;" />
			</div>
			<div style="display: flex; gap: 0.5rem; align-items: center;">
				<label style="width: 100px; font-weight: bold; font-size: 0.85rem;">Asunto:</label>
				<input type="text" bind:value={indAsunto} placeholder="Asunto del email"
					style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1;" />
			</div>
			<div style="display: flex; gap: 0.5rem; align-items: flex-start;">
				<label style="width: 100px; font-weight: bold; font-size: 0.85rem; padding-top: 0.5rem;">Mensaje:</label>
				<textarea bind:value={indMensaje} placeholder="Cuerpo del email (puede ser HTML)"
					rows="4" style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1; font-family: inherit;"></textarea>
			</div>
			<button onclick={enviarIndividual} disabled={!indUsuarioId || !indAsunto || !indMensaje}
				style="background: #1565c0; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; align-self: flex-end;">
				Enviar email individual
			</button>
		</div>
	</div>

	<!-- Envio masivo -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<h3 style="margin-top: 0;">Envio masivo</h3>
		<div style="display: flex; flex-direction: column; gap: 0.5rem;">
			<div style="display: flex; gap: 0.5rem; align-items: center;">
				<label style="width: 100px; font-weight: bold; font-size: 0.85rem;">Filtro:</label>
				<select bind:value={masFiltro} style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px;">
					<option value="programa_id">Por programa</option>
					<option value="instancia_cursado_id">Por instancia de cursado</option>
				</select>
				<input type="number" bind:value={masFiltroValor} placeholder="ID"
					style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; width: 100px;" />
			</div>
			<div style="display: flex; gap: 0.5rem; align-items: center;">
				<label style="width: 100px; font-weight: bold; font-size: 0.85rem;">Asunto:</label>
				<input type="text" bind:value={masAsunto} placeholder="Asunto del email masivo"
					style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1;" />
			</div>
			<div style="display: flex; gap: 0.5rem; align-items: flex-start;">
				<label style="width: 100px; font-weight: bold; font-size: 0.85rem; padding-top: 0.5rem;">Mensaje:</label>
				<textarea bind:value={masMensaje} placeholder="Cuerpo del email (puede ser HTML)"
					rows="4" style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1; font-family: inherit;"></textarea>
			</div>
			<button onclick={enviarMasivo} disabled={!masFiltroValor || !masAsunto || !masMensaje}
				style="background: #e94560; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; align-self: flex-end;">
				Enviar email masivo
			</button>
		</div>
	</div>

	<!-- Historial -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<div style="display: flex; justify-content: space-between; align-items: center;">
			<h3 style="margin-top: 0;">Historial de notificaciones</h3>
			<div style="display: flex; gap: 0.5rem; align-items: center;">
				<button onclick={() => { historialPage = Math.max(1, historialPage - 1); cargarHistorial(); }}
					disabled={historialPage <= 1 || cargandoHistorial}
					style="background: #eee; border: 1px solid #ccc; padding: 0.3rem 0.6rem; border-radius: 4px; cursor: pointer;">
					&lt;
				</button>
				<span style="font-size: 0.85rem;">Pagina {historialPage}</span>
				<button onclick={() => { historialPage++; cargarHistorial(); }}
					disabled={cargandoHistorial}
					style="background: #eee; border: 1px solid #ccc; padding: 0.3rem 0.6rem; border-radius: 4px; cursor: pointer;">
					&gt;
				</button>
				<button onclick={cargarHistorial} disabled={cargandoHistorial}
					style="background: #1a1a2e; color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
					Cargar
				</button>
			</div>
		</div>

		{#if cargandoHistorial}
			<p style="color: #666;">Cargando...</p>
		{:else if historial.length === 0}
			<p style="color: #999;">Sin registros. Presiona "Cargar" para ver el historial.</p>
		{:else}
			<table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
				<thead>
					<tr style="background: #f0f0f0;">
						<th style="padding: 0.3rem; text-align: left; border: 1px solid #ddd;">ID</th>
						<th style="padding: 0.3rem; text-align: left; border: 1px solid #ddd;">Tipo</th>
						<th style="padding: 0.3rem; text-align: left; border: 1px solid #ddd;">Destino</th>
						<th style="padding: 0.3rem; text-align: left; border: 1px solid #ddd;">Asunto</th>
						<th style="padding: 0.3rem; text-align: left; border: 1px solid #ddd;">Estado</th>
						<th style="padding: 0.3rem; text-align: left; border: 1px solid #ddd;">Fecha</th>
					</tr>
				</thead>
				<tbody>
					{#each historial as log}
						<tr>
							<td style="padding: 0.3rem; border: 1px solid #ddd; font-family: monospace;">{log.id}</td>
							<td style="padding: 0.3rem; border: 1px solid #ddd;">{log.tipo}</td>
							<td style="padding: 0.3rem; border: 1px solid #ddd;">{log.email_destino}</td>
							<td style="padding: 0.3rem; border: 1px solid #ddd;">{log.asunto}</td>
							<td style="padding: 0.3rem; border: 1px solid #ddd;">
								<span style="padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.75rem;
									background: {log.estado === 'enviada' ? '#e8f5e9' : '#ffebee'};
									color: {log.estado === 'enviada' ? '#2e7d32' : '#c62828'};">
									{log.estado}
								</span>
							</td>
							<td style="padding: 0.3rem; border: 1px solid #ddd; font-size: 0.75rem;">{log.fecha_envio || '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>
{/if}
