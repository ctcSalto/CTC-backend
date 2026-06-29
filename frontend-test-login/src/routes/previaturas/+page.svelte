<script>
	import { base } from '$app/paths';
	import { usuario, token, loading, apiFetch } from '$lib/auth.js';
	import { goto } from '$app/navigation';

	// Auth guard
	$effect(() => {
		if (!$loading && !$usuario && !$token) goto(`${base}/`);
	});

	// Estado
	let programas = $state([]);
	let programaId = $state('');
	let malla = $state(null);
	let escolaridad = $state(null);
	let instancias = $state([]);
	let usuarioId = $state('');
	let instanciaCursadoId = $state('');
	let resultado = $state(null);
	let cargando = $state(false);
	let error = $state('');

	// Cargar programas al montar
	$effect(() => {
		if ($usuario) cargarProgramas();
	});

	async function cargarProgramas() {
		const res = await apiFetch('/v2/admin/programas?limit=100');
		if (res.ok) programas = res.data;
	}

	async function cargarMalla() {
		if (!programaId) return;
		cargando = true;
		error = '';
		malla = null;
		const res = await apiFetch(`/v2/admin/previaturas/malla/${programaId}`);
		cargando = false;
		if (res.ok) {
			// API returns {programa_id, semestres: {"1": [...], "2": [...]}}
			// Transform to array: [{semestre: 1, materias: [...]}, ...]
			const semestres = res.data.semestres || {};
			malla = Object.entries(semestres)
				.sort(([a], [b]) => Number(a) - Number(b))
				.map(([sem, materias]) => ({
					semestre: Number(sem),
					materias: materias.map(m => ({
						materia_id: m.id,
						materia_nombre: m.nombre,
						previaturas: (m.previaturas || []).map(p => ({
							materia_requerida_nombre: `${p.materia_previa_nombre} (${p.tipo_requerido})`
						}))
					}))
				}));
		} else {
			error = res.error;
		}
	}

	async function cargarEscolaridad() {
		if (!usuarioId || !programaId) {
			error = 'Selecciona un programa e ingresa un usuario_id';
			return;
		}
		cargando = true;
		error = '';
		escolaridad = null;
		const res = await apiFetch(`/v2/admin/inscripciones/escolaridad/${usuarioId}?programa_id=${programaId}`);
		cargando = false;
		if (res.ok) {
			escolaridad = res.data;
		} else {
			error = res.error;
		}
	}

	async function cargarInstancias() {
		if (!programaId || !malla) return;
		// Cargar instancias de cursado de todas las materias del programa
		let todas = [];
		for (const semestre of malla) {
			for (const materia of semestre.materias) {
				const res = await apiFetch(`/v2/admin/instancias-cursado/?materia_id=${materia.materia_id}`);
				if (res.ok && res.data.length > 0) {
					for (const inst of res.data) {
						todas.push({ ...inst, materia_nombre: materia.materia_nombre });
					}
				}
			}
		}
		instancias = todas;
	}

	async function inscribirManual() {
		if (!usuarioId || !instanciaCursadoId) {
			error = 'Completa usuario_id e instancia_cursado_id';
			return;
		}
		cargando = true;
		error = '';
		resultado = null;
		const res = await apiFetch('/v2/admin/inscripciones/inscribir', {
			method: 'POST',
			body: JSON.stringify({
				usuario_id: parseInt(usuarioId),
				instancia_cursado_id: parseInt(instanciaCursadoId),
			}),
		});
		cargando = false;
		if (res.ok) {
			resultado = { tipo: 'exito', data: res.data };
		} else {
			resultado = { tipo: 'error', mensaje: res.error, status: res.status };
		}
	}
</script>

{#if $loading}
	<p>Cargando...</p>
{:else if $usuario}
	<h1>Test Previaturas e Inscripcion</h1>

	<!-- Selector de programa -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<h3 style="margin-top: 0;">1. Seleccionar programa</h3>
		<div style="display: flex; gap: 0.5rem; align-items: center;">
			<select bind:value={programaId} style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1;">
				<option value="">-- Seleccionar programa --</option>
				{#each programas as prog}
					<option value={prog.id}>{prog.nombre} (ID: {prog.id})</option>
				{/each}
			</select>
			<button onclick={cargarMalla} disabled={!programaId || cargando}
				style="background: #1a1a2e; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
				Ver malla
			</button>
		</div>
	</div>

	<!-- Malla curricular -->
	{#if malla}
		<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
			<div style="display: flex; justify-content: space-between; align-items: center;">
				<h3 style="margin-top: 0;">Malla curricular</h3>
				<button onclick={cargarInstancias} disabled={cargando}
					style="background: #4caf50; color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
					Cargar instancias de cursado
				</button>
			</div>
			{#each malla as semestre}
				<div style="margin-bottom: 1rem;">
					<h4 style="color: #1565c0; margin-bottom: 0.5rem;">Semestre {semestre.semestre}</h4>
					<table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
						<thead>
							<tr style="background: #f0f0f0;">
								<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">ID</th>
								<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Materia</th>
								<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Previaturas</th>
							</tr>
						</thead>
						<tbody>
							{#each semestre.materias as materia}
								<tr>
									<td style="padding: 0.4rem; border: 1px solid #ddd; font-family: monospace;">{materia.materia_id}</td>
									<td style="padding: 0.4rem; border: 1px solid #ddd;">{materia.materia_nombre}</td>
									<td style="padding: 0.4rem; border: 1px solid #ddd;">
										{#if materia.previaturas && materia.previaturas.length > 0}
											{#each materia.previaturas as prev}
												<span style="background: #fff3e0; color: #e65100; padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.8rem; margin-right: 0.3rem;">
													{prev.materia_requerida_nombre}
												</span>
											{/each}
										{:else}
											<span style="color: #999;">Ninguna</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Escolaridad -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<h3 style="margin-top: 0;">2. Consultar escolaridad de un alumno</h3>
		<div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem;">
			<input type="number" bind:value={usuarioId} placeholder="usuario_id"
				style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; width: 120px;" />
			<span style="color: #666; font-size: 0.85rem;">Programa: {programaId || '(seleccionar arriba)'}</span>
			<button onclick={cargarEscolaridad} disabled={!usuarioId || !programaId || cargando}
				style="background: #1565c0; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
				Consultar
			</button>
		</div>
		{#if escolaridad}
			<div style="margin-top: 1rem;">
				<p style="margin: 0.3rem 0;"><strong>Alumno:</strong> {escolaridad.alumno?.nombre} {escolaridad.alumno?.apellido} (ID: {escolaridad.alumno?.id})</p>
				<p style="margin: 0.3rem 0;"><strong>Programa:</strong> {escolaridad.programa?.nombre}</p>
				{#if escolaridad.materias && escolaridad.materias.length > 0}
					<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 0.5rem;">
						<thead>
							<tr style="background: #f0f0f0;">
								<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Materia</th>
								<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Estado</th>
								<th style="padding: 0.4rem; text-align: left; border: 1px solid #ddd;">Nota final</th>
							</tr>
						</thead>
						<tbody>
							{#each escolaridad.materias as mat}
								<tr>
									<td style="padding: 0.4rem; border: 1px solid #ddd;">{mat.materia_nombre || mat.materia}</td>
									<td style="padding: 0.4rem; border: 1px solid #ddd;">
										<span style="padding: 0.1rem 0.5rem; border-radius: 3px; font-size: 0.8rem;
											background: {mat.estado === 'aprobado' || mat.estado === 'exonerado' ? '#e8f5e9' :
												mat.estado === 'cursando' ? '#e3f2fd' :
												mat.estado === 'reprobado' ? '#ffebee' : '#f5f5f5'};
											color: {mat.estado === 'aprobado' || mat.estado === 'exonerado' ? '#2e7d32' :
												mat.estado === 'cursando' ? '#1565c0' :
												mat.estado === 'reprobado' ? '#c62828' : '#666'};">
											{mat.estado}
										</span>
									</td>
									<td style="padding: 0.4rem; border: 1px solid #ddd;">{mat.nota_final ?? '-'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else}
					<p style="color: #999;">Sin inscripciones registradas.</p>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Inscripcion manual (test previaturas) -->
	<div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1.5rem;">
		<h3 style="margin-top: 0;">3. Inscripcion manual (test validacion previaturas)</h3>
		<p style="color: #666; font-size: 0.85rem; margin-top: 0;">
			Intenta inscribir un alumno a una instancia de cursado. Si la materia tiene previaturas no aprobadas, el backend rechazara la inscripcion.
		</p>
		<div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
			<input type="number" bind:value={usuarioId} placeholder="usuario_id"
				style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; width: 120px;" />
			{#if instancias.length > 0}
				<select bind:value={instanciaCursadoId} style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; flex: 1;">
					<option value="">-- Seleccionar instancia de cursado --</option>
					{#each instancias as inst}
						<option value={inst.id}>{inst.materia_nombre} - {inst.anio_lectivo} (IC ID: {inst.id})</option>
					{/each}
				</select>
			{:else}
				<input type="number" bind:value={instanciaCursadoId} placeholder="instancia_cursado_id"
					style="padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; width: 180px;" />
			{/if}
			<button onclick={inscribirManual} disabled={!usuarioId || !instanciaCursadoId || cargando}
				style="background: #e94560; color: white; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;">
				Inscribir
			</button>
		</div>

		{#if resultado}
			<div style="margin-top: 1rem; padding: 1rem; border-radius: 6px;
				background: {resultado.tipo === 'exito' ? '#e8f5e9' : '#ffebee'};
				border-left: 4px solid {resultado.tipo === 'exito' ? '#4caf50' : '#f44336'};">
				{#if resultado.tipo === 'exito'}
					<strong style="color: #2e7d32;">Inscripcion exitosa</strong>
					<pre style="background: #f5f5f5; padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; overflow-x: auto; margin-top: 0.5rem;">{JSON.stringify(resultado.data, null, 2)}</pre>
				{:else}
					<strong style="color: #c62828;">Error {resultado.status}</strong>
					<p style="margin: 0.3rem 0 0; color: #b71c1c;">{resultado.mensaje}</p>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Error global -->
	{#if error}
		<div style="background: #ffebee; border-left: 4px solid #f44336; padding: 1rem; border-radius: 0 6px 6px 0; margin-bottom: 1rem;">
			<strong style="color: #c62828;">Error:</strong>
			<span style="color: #b71c1c;">{error}</span>
		</div>
	{/if}
{/if}
