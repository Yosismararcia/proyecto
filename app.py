from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
import qrcode
import os
import io
from flask import send_file
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io
import os
from flask import render_template, redirect, url_for, flash, session, request, make_response
from werkzeug.utils import secure_filename

# 1. Importación de Repositorios
import repositories.evento_repository as evento_repo
import repositories.usuario_repository as usuario_repo

from repositories.inscripcion_repository import (
    registrar_inscripcion_segura,
    obtener_inscritos_por_evento  # 👈 Importar aquí
)
from repositories.evento_repository import (
    obtener_metricas_dashboard,
    obtener_solicitudes_totales_admin,
    obtener_propuestas_totales_admin,
    eliminar_propuesta_estudiante  # <--- Agrega la nueva función aquí
)
# 2. Importación de Módulos Core y Seguridad
from core.security import (
    hash_password, 
    verificar_password, 
    requerir_rol, 
    obtener_serializer,
    clean_input_strict
)

from core.validators import validar_cedula_format, validar_cedula_institucional
from repositories.evento_repository import obtener_evento_difusion  # Ajusta el nombre de la importación
#importacion de modulos de database por nuevas modificaciones
from database import (
    obtener_conexion,
    obtener_detalle_evento_bd,
    obtener_foro_discusiones_bd,
    obtener_tareas_voluntariado_bd,
    obtener_inscripcion_usuario_bd,
    insertar_mensaje_foro_bd,
    obtener_datos_certificado_bd,
    obtener_inscritos_evento_bd,
    cambiar_estado_asistencia_bd,
    registrar_postulacion_jurado_bd,
    obtener_perfil_jurado_bd,
    obtener_evaluacion_evento_bd,
    guardar_evaluacion_evento_bd,
    postular_voluntario_bd,
    crear_tarea_voluntariado_bd,
    cambiar_estado_postulacion_bd
)



app = Flask(__name__)
# Clave secreta para cifrar cookies de sesión y firmar tokens
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'clave_secreta_super_segura_facyt_2026')

# Instancia del Serializador para tokens temporales de recuperación
serializer = obtener_serializer(app.secret_key)
# --- RUTA 1: INICIO (DASHBOARD) ---
@app.route('/')
def inicio():
    # 1. Capturar la fecha de búsqueda ingresada por el usuario
    fecha_busqueda = request.args.get('fecha')

    if 'usuario_id' not in session:
        return render_template(
            'index.html', 
            anonimo=True, 
            metrics={}, 
            eventos=[], 
            eventos_cartelera=[],
            eventos_inscritos_ids=[],
            fecha_seleccionada=fecha_busqueda
        )
    
    usuario_id = session['usuario_id']
    
    try:
        # 2. Obtener la cartelera completa con el estado de inscripción del usuario
        eventos_cartelera = evento_repo.obtener_eventos_cartelera_publica(usuario_id) if hasattr(evento_repo, 'obtener_eventos_cartelera_publica') else []
        
        # 3. Extraer solo los IDs de los eventos donde el usuario ya está inscrito
        eventos_inscritos_ids = [
            ev['id'] for ev in eventos_cartelera if ev.get('esta_inscrito', 0) > 0
        ]

        # 4. FILTRAR POR FECHA (Si el usuario seleccionó una fecha en el buscador)
        if fecha_busqueda:
            eventos_cartelera = [
                ev for ev in eventos_cartelera 
                if str(ev.get('fecha')) == fecha_busqueda
            ]

        # 5. Métricas y Próximos eventos
        metrics = evento_repo.obtener_metricas_dashboard()  
        eventos_proximos = evento_repo.obtener_proximos_eventos(usuario_id) if hasattr(evento_repo, 'obtener_proximos_eventos') else []

    except Exception as e:
        print(f"Error al cargar métricas del inicio: {e}")
        metrics = {}
        eventos_proximos = []
        eventos_cartelera = []
        eventos_inscritos_ids = []
        
    return render_template(
        'index.html', 
        metrics=metrics, 
        eventos=eventos_proximos or eventos_cartelera, 
        eventos_cartelera=eventos_cartelera, 
        eventos_inscritos_ids=eventos_inscritos_ids,
        fecha_seleccionada=fecha_busqueda, # 👈 Se envía la fecha seleccionada a la plantilla
        anonimo=False
    )


# --- RUTA 2: REGISTRO DE USUARIOS ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        cedula = request.form.get('cedula', '').strip()
        correo = request.form.get('correo')
        password = request.form.get('contrasena')
        rol = request.form.get('rol')

        cedula_clean = clean_input_strict(cedula)
        nombre_clean = clean_input_strict(nombre)

        if not cedula_clean or not nombre_clean:
            flash("❌ Error: Se detectaron caracteres no permitidos en el formulario.", "error")
            return redirect(url_for('registro'))

        if rol in ['ponente', 'profesor', 'administrativo']:
            autorizado = validar_cedula_institucional(cedula_clean, rol)
            if not autorizado:
                flash(f"❌ Acceso Denegado: La cédula {cedula_clean} no está registrada en la nómina para el rol: {rol}.", "error")
                return redirect(url_for('registro'))

        password_hashed = hash_password(password)
        exito = usuario_repo.crear_usuario(nombre_clean, cedula_clean, correo, password_hashed, rol)
        
        if exito:
            flash("🎉 Cuenta creada con éxito. Ya puedes iniciar sesión.", "success")
            return redirect(url_for('login'))
        else:
            flash("❌ Error: La cédula o el correo ya se encuentran registrados.", "error")

    return render_template('registro.html')


# --- RUTA 3: LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        contrasena = request.form.get('contrasena')

        if not correo or not contrasena:
            flash("Error: Por favor rellene todos los campos.", "error")
            return redirect(url_for('login'))

        usuario = usuario_repo.obtener_usuario_por_correo(correo)

        if usuario and verificar_password(usuario['contrasena_hash'], contrasena):
            session['usuario_id'] = usuario['id']
            session['usuario_nombre'] = usuario['nombre']
            session['usuario_rol'] = usuario['rol']
            
            flash(f"¡Bienvenido de nuevo, {usuario['nombre']}! 👋", "success")
            return redirect(url_for('inicio'))
        else:
            flash("Error: Credenciales incorrectas.", "error")

    return render_template('login.html')


# --- RUTA 4: RECUPERACIÓN DE ACCESO ---

# 1. VERIFICAR CÉDULA Y CORREO
@app.route('/recuperar-acceso', methods=['GET', 'POST'])
def recuperar_acceso():
    if request.method == 'POST':
        cedula = request.form.get('cedula', '').strip()
        correo = request.form.get('correo', '').strip()

        conexion = obtener_conexion()
        try:
            with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
                # Validar que existan ambos datos en la BD
                cursor.execute(
                    "SELECT id FROM usuarios WHERE cedula = %s AND correo = %s;", 
                    (cedula, correo)
                )
                usuario = cursor.fetchone()
        finally:
            conexion.close()

        if usuario:
            # Guardamos la verificación en la sesión del servidor
            session['recuperar_usuario_id'] = usuario['id']
            
            # REDIRECCIÓN DIRECTA a la función redefinir_password
            return redirect(url_for('redefinir_password'))
        else:
            flash("❌ Cédula o correo electrónico incorrectos.", "error")
            return redirect(url_for('recuperar_acceso'))

    return render_template('recuperar.html')


# 2. CAMBIAR LA CONTRASEÑA DIRECTAMENTE
@app.route('/redefinir-clave', methods=['GET', 'POST'])
def redefinir_password():
    # Seguridad: solo se entra si pasó por el paso anterior
    usuario_id = session.get('recuperar_usuario_id')
    if not usuario_id:
        flash("Por favor verifica tus datos primero.", "warning")
        return redirect(url_for('recuperar_acceso'))

    if request.method == 'POST':
        nueva_clave = request.form.get('password', '').strip()
        
        # Encriptamos la clave nueva
        clave_hash = generate_password_hash(nueva_clave)

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "UPDATE usuarios SET contrasena_hash = %s WHERE id = %s;", 
                    (clave_hash, usuario_id)
                )
            conexion.commit()
        finally:
            conexion.close()

        # Limpiamos la variable de sesión
        session.pop('recuperar_usuario_id', None)

        flash("🎉 ¡Contraseña actualizada con éxito! Ya puedes iniciar sesión.", "success")
        return redirect(url_for('login'))

    return render_template('redefinir_password.html')

# --- RUTA 5: SOLICITAR ESPACIOS ---
@app.route('/solicitar', methods=['GET', 'POST'])
@requerir_rol(['ponente','profesor','administrativo'])
def solicitar():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        departamento = request.form.get('departamento')
        tipo_actividad = request.form.get('tipo_actividad')
        espacio_id = request.form.get('espacio_id')
        enlace_virtual = request.form.get('enlace_virtual', '')
        fecha = request.form.get('fecha')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        
        if not all([titulo, departamento, tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin]):
            flash("❌ Por favor complete todos los campos requeridos.", "error")
            return redirect(url_for('solicitar'))

        try:
            t_inicio = datetime.strptime(str(hora_inicio), "%H:%M").time()
            t_fin = datetime.strptime(str(hora_fin), "%H:%M").time()

            if t_inicio >= t_fin:
                flash("❌ La hora de inicio debe ser anterior a la hora de finalización.", "error")
                return redirect(url_for('solicitar'))

        except ValueError:
            flash("❌ Formato de hora inválido.", "error")
            return redirect(url_for('solicitar'))

        if evento_repo.validar_por_titulo(titulo):
            flash(f"❌ La idea '{titulo}' ya se encuentra registrada.", "error")
            return redirect(url_for('solicitar'))
        
        resultado = evento_repo.crear_solicitud_evento(
            titulo, session['usuario_id'], tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin, departamento, enlace_virtual
        )

        if resultado.get('exito'):
            flash("¡Solicitud registrada correctamente! Queda en espera de revisión.", "success")
            return redirect(url_for('inicio'))
        else:
            flash(f"❌ {resultado.get('mensaje', 'Error al procesar la solicitud.')}", "error")

    espacios = evento_repo.obtener_lista_espacios_formulario()
    return render_template('solicitar.html', espacios=espacios)


# --- APIS AUXILIARES ---
@app.route('/api/dias-ocupados')
def api_dias_ocupados():
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT DISTINCT DATE_FORMAT(fecha, '%%Y-%%m-%%d') as fecha 
                FROM eventos 
                WHERE estado IN ('aprobado', 'pendiente')
            """)
            resultados = cursor.fetchall()
            fechas = [row['fecha'] for row in resultados]
        return jsonify(fechas)
    except Exception as e:
        print(f"Error en API dias-ocupados: {e}")
        return jsonify([])
    finally:
        conexion.close()


@app.route('/api/disponibilidad-espacio')
def api_disponibilidad_espacio():
    espacio_id = request.args.get('espacio_id')
    fecha = request.args.get('fecha')

    if not espacio_id or not fecha:
        return jsonify([])

    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT titulo, 
                       TIME_FORMAT(hora_inicio, '%%H:%%i') as inicio, 
                       TIME_FORMAT(hora_fin, '%%H:%%i') as fin, 
                       estado
                FROM eventos 
                WHERE espacio_id = %s 
                  AND fecha = %s 
                  AND estado IN ('aprobado', 'pendiente')
                ORDER BY hora_inicio ASC
            """, (espacio_id, fecha))
            eventos_ocupados = cursor.fetchall()
        return jsonify(eventos_ocupados)
    except Exception as e:
        print(f"Error en API disponibilidad-espacio: {e}")
        return jsonify([])
    finally:
        conexion.close()


# --- PANEL ADMINISTRATIVO ---
@app.route('/admin')
@requerir_rol(['administrativo'])
def admin():
    solicitudes = evento_repo.obtener_solicitudes_totales_admin()
    propuestas = evento_repo.obtener_propuestas_totales_admin()
    top_espacios = evento_repo.obtener_top_espacios()
    conteo_estados = evento_repo.obtener_conteo_estados()
    metrics = evento_repo.obtener_metricas_dashboard()

    return render_template('admin.html', 
                           solicitudes=solicitudes, 
                           propuestas=propuestas, 
                           top_espacios=top_espacios, 
                           conteo_estados=conteo_estados,
                           metrics=metrics)


@app.route('/admin/actualizar-estado/<int:evento_id>', methods=['POST'])
@requerir_rol(['administrativo'])
def admin_actualizar_estado(evento_id):
    nuevo_estado = request.form.get('estado')
    
    if not nuevo_estado:
        flash("❌ Error: No se seleccionó un estado válido.", "error")
        return redirect(url_for('admin'))

    resultado = evento_repo.actualizar_estado_evento(evento_id, nuevo_estado)
    
    if resultado.get('status') == 'success':
        estado_texto = str(nuevo_estado).upper()
        flash(f"📢 El estado del evento ID {evento_id} se actualizó a '{estado_texto}'.", "success")
    else:
        flash(f"❌ Error: {resultado.get('message', 'No se pudo actualizar el estado.')}", "error")

    return redirect(url_for('admin'))


# --- DIFUSIÓN DE EVENTO ---
@app.route('/evento/difundir/<int:evento_id>')
def difundir_evento(evento_id):
    if not session.get('usuario_id'):
        flash('Debe iniciar sesión para acceder a esta función.', 'error')
        return redirect(url_for('login'))

    try:
        # 1. Consulta limpia a través del repositorio
        evento = obtener_evento_difusion(evento_id)
        print(evento)
        if not evento:
            flash('El evento solicitado no existe.', 'error')
            return redirect(url_for('inicio'))

        # 2. Formateo seguro de fechas y horas
        evento['inicio_formateado'] = str(evento['hora_inicio'])[:5] if evento.get('hora_inicio') else '--:--'
        evento['fin_formateado'] = str(evento['hora_fin'])[:5] if evento.get('hora_fin') else '--:--'
        evento['fecha_formateada'] = str(evento['fecha']) if evento.get('fecha') else 'Sin fecha'

        # 3. Verificación de la descripción
        desc = evento.get('descripcion')
        if desc and str(desc).strip():
            evento['descripcion'] = str(desc).strip()
        else:
            evento['descripcion'] = None

        return render_template('difundir_evento.html', evento=evento)

    except Exception as e:
        print(f"❌ ERROR EN DIFUSIÓN: {e}")
        flash('Error al generar la plantilla de difusión.', 'error')
        return redirect(url_for('inicio'))


# --- PROPUESTAS DE ESTUDIANTES ---
@app.route('/proponer', methods=['GET', 'POST'])
@requerir_rol(['estudiante'])
def proponer():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        tipo_actividad = request.form.get('tipo_actividad')
        descripcion = request.form.get('descripcion')

        if not all([titulo, tipo_actividad, descripcion]):
            flash("❌ Por favor complete todos los campos requeridos.", "error")
            return redirect(url_for('proponer'))
        
        if evento_repo.validar_por_titulo(titulo):
            flash(f"❌ La idea '{titulo}' ya se encuentra registrada en el buzón.", "error")
            return redirect(url_for('proponer'))            
        
        exito = evento_repo.crear_propuesta_estudiante(
            estudiante_id=session['usuario_id'],
            titulo=titulo,
            tipo_actividad=tipo_actividad,
            descripcion=descripcion
        )

        if exito:
            flash("💡 ¡Tu propuesta ha sido enviada al equipo administrativo!", "success")
            return redirect(url_for('mis_propuestas'))
        else:
            flash("❌ Ocurrió un error al guardar tu propuesta.", "error")
            return redirect(url_for('proponer'))

    return render_template('proponer.html')


@app.route('/mis_propuestas')
@requerir_rol(['estudiante'])
def mis_propuestas():
    mis_propuestas = evento_repo.obtener_mis_propuestas_estudiante(session['usuario_id'])
    return render_template('mis_propuestas.html', mis_propuestas=mis_propuestas)


@app.route('/mis_solicitudes')
@requerir_rol(['ponente','profesor','administrativo'])
def mis_solicitudes():
    solicitudes = evento_repo.obtener_mis_solicitudes(session.get('usuario_id'))
    return render_template('mis_solicitudes.html', solicitudes=solicitudes)


# --- ADMINISTRACIÓN DE ESPACIOS Y EVENTOS ---
@app.route('/admin/espacios/eliminar/<int:id>', methods=['POST'])
@requerir_rol(['administrativo'])
def eliminar_espacio(id):
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM espacios WHERE id = %s", (id,))
        conexion.commit()
        conexion.close()
        flash('🗑️ Espacio eliminado correctamente.', 'success')
    except Exception as e:
        flash(f'❌ No se pudo eliminar el espacio: {str(e)}', 'error')

    return redirect('/admin/espacios')


@app.route('/admin/eliminar-evento/<int:evento_id>', methods=['POST'])
@requerir_rol(['administrativo'])
def admin_eliminar_evento(evento_id):
    if evento_repo.eliminar_evento(evento_id):
        flash("🗑️ El evento ha sido eliminado permanentemente.", "success")
    else:
        flash("❌ No se pudo eliminar el evento.", "error")
    return redirect(url_for('admin'))


@app.route('/admin/editar-evento/<int:evento_id>', methods=['GET', 'POST'])
@requerir_rol(['administrativo'])
def admin_editar_evento(evento_id):
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        tipo_actividad = request.form.get('tipo_actividad')
        espacio_id = request.form.get('espacio_id')
        fecha = request.form.get('fecha')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        
        resultado = evento_repo.actualizar_evento_completo(
            evento_id, titulo, tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin
        )
        
        if resultado.get('exito'):
            flash("✏️ " + resultado['mensaje'], "success")
            return redirect(url_for('admin'))
        else:
            flash(resultado['mensaje'], "error")

    evento = evento_repo.obtener_evento_por_id(evento_id)
    espacios = evento_repo.obtener_lista_espacios_formulario()
    if not evento:
        flash("El evento no existe.", "error")
        return redirect(url_for('admin'))

    return render_template('editar_evento.html', evento=evento, espacios=espacios)


@app.route('/admin/espacios/nuevo', methods=['POST'])
@requerir_rol(['administrativo'])
def registrar_espacio():
    nombre = request.form.get('nombre')
    capacidad = request.form.get('capacidad')
    descripcion = request.form.get('descripcion')

    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            sql = "INSERT INTO espacios (nombre, capacidad, descripcion) VALUES (%s, %s, %s)"
            cursor.execute(sql, (nombre, capacidad, descripcion))
        conexion.commit()
        conexion.close()
        flash('✅ Espacio registrado exitosamente.', 'success')
    except Exception as e:
        flash(f'❌ Ocurrió un error al guardar el espacio: {str(e)}', 'error')

    return redirect('/admin/espacios')


@app.route('/admin/espacios')
@requerir_rol(['administrativo'])
def administrar_espacios():
    try:
        conexion = obtener_conexion()
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id, nombre, capacidad, descripcion FROM espacios")
            lista_espacios = cursor.fetchall()
        conexion.close()
    except Exception:
        lista_espacios = []

    return render_template('admin_espacios.html', espacios=lista_espacios)


# --- INSCRIPCIÓN Y VISTAS DE ASISTENCIA ---
@app.route('/inscribir-evento/<int:evento_id>', methods=['POST'])
def inscribir_evento(evento_id):
    if 'usuario_id' not in session:
        flash("Debe iniciar sesión para inscribirse a los eventos.", "warning")
        return redirect(url_for('login'))

    # 🛑 PROTECCIÓN: Consultar evento y bloquear si está cancelado
    evento = evento_repo.obtener_evento_por_id(evento_id)  # Ajusta al nombre de tu función que busca el evento
    if evento and str(evento.get('estado', '')).lower() == 'cancelado':
        flash("🚫 No es posible inscribirse: Este evento ha sido cancelado.", "warning")
        return redirect(request.referrer or url_for('inicio'))

    usuario_id = session['usuario_id']
    resultado = registrar_inscripcion_segura(evento_id, usuario_id)

    status = resultado.get('status', 'error')
    mensaje = str(resultado.get('message', 'Ocurrió un error inesperado.'))

    if status == 'success':
        flash(mensaje, "success")
    elif status == 'warning':
        flash(mensaje, "warning")
    else:
        flash(f"❌ {mensaje}", "error")

    return redirect(request.referrer or url_for('inicio'))


@app.route('/evento/<int:evento_id>/inscritos')
def ver_inscritos_evento(evento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para acceder.", "warning")
        return redirect(url_for('login'))

    # Se busca el rol en 'usuario_rol' o 'rol' para evitar incompatibilidades
    rol_actual = str(session.get('usuario_rol') or session.get('rol') or '').lower()
    
    # Incluimos 'administrativo' y 'admin' en los roles permitidos
    roles_autorizados = ['administrador', 'admin', 'administrativo', 'profesor', 'ponente']
    
    if rol_actual not in roles_autorizados:
        flash("⛔ No tienes permisos para ver esta lista.", "error")
        return redirect(url_for('inicio'))

    # Obtenemos evento e inscritos mediante database.py
    evento = obtener_detalle_evento_bd(evento_id)
    if not evento:
        flash("El evento solicitado no existe.", "error")
        return redirect(url_for('inicio'))

    inscritos = obtener_inscritos_evento_bd(evento_id) or []

    return render_template(
        'ver_inscritos.html', 
        evento=evento, 
        inscritos=inscritos,
        total_inscritos=len(inscritos)
    )

@app.route('/ponente/evento/<int:evento_id>/inscritos')
def ponente_ver_inscritos(evento_id):
    """Ruta directa para que el ponente/profesor consulte la lista de asistencia."""
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para acceder.", "warning")
        return redirect(url_for('login'))

    rol_actual = str(session.get('usuario_rol') or session.get('rol') or '').lower()
    if rol_actual not in ['ponente', 'profesor', 'administrativo', 'admin']:
        flash("Acceso denegado: Esta vista es solo para ponentes y profesores.", "error")
        return redirect(url_for('inicio'))

    evento = evento_repo.obtener_evento_por_id(evento_id)
    if not evento:
        flash("El evento solicitado no existe.", "error")
        return redirect(url_for('mis_solicitudes'))

    inscritos = obtener_inscritos_por_evento(evento_id) or []

    # Renderiza la vista consolidada de asistencia
    return render_template(
        'ver_inscritos.html', 
        evento=evento, 
        inscritos=inscritos,
        total_inscritos=len(inscritos)
    )

# ==========================================
# NUEVAS FUNCIONALIDADES: DETALLE, FORO Y REPOSITORIO
# ==========================================
# ==========================================
# RUTAS ACTUALIZADAS CON TU ESQUEMA ORIGINAL
# ==========================================

# ==========================================
# RUTAS DE VISTA DETALLADA Y FORO
# ==========================================

@app.route('/evento/<int:evento_id>')
def detalle_evento(evento_id):
    usuario_id = session.get('usuario_id')
    
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para consultar el detalle de un evento.", "warning")
        return redirect(url_for('login'))
        
    try:
        evento = obtener_detalle_evento_bd(evento_id)
        if not evento:
            flash("El evento solicitado no existe.", "error")
            return redirect(url_for('inicio'))

        preguntas = obtener_foro_discusiones_bd(evento_id)
        
        # --- AQUÍ OBTENEMOS LAS TAREAS DE VOLUNTARIADO ---
        tareas_voluntariado = obtener_tareas_voluntariado_bd(evento_id, usuario_id)
        
        inscripcion = obtener_inscripcion_usuario_bd(evento_id, session['usuario_id'])

        return render_template(
            'detalle_evento.html',
            evento=evento,
            preguntas=preguntas,
            tareas=tareas_voluntariado, # <-- SE ENVÍA LA VARIABLE A LA PLANTILLA
            inscripcion=inscripcion
        )
    except Exception as e:
        print(f"❌ Error en detalle_evento: {e}")
        flash("Error al cargar los detalles del evento.", "error")
        return redirect(url_for('inicio'))


@app.route('/evento/<int:evento_id>/foro/pregunta', methods=['POST'])
def agregar_pregunta_foro(evento_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    mensaje = clean_input_strict(request.form.get('pregunta', ''))
    if not mensaje:
        flash("❌ No puedes enviar un mensaje vacío.", "error")
        return redirect(url_for('detalle_evento', evento_id=evento_id))

    try:
        insertar_mensaje_foro_bd(evento_id, session['usuario_id'], mensaje)
        flash("💬 Tu mensaje ha sido publicado en el foro del evento.", "success")
    except Exception as e:
        flash(f"❌ Error al publicar en el foro: {e}", "error")

    return redirect(url_for('detalle_evento', evento_id=evento_id))

@app.route('/evento/<int:evento_id>/voluntariado/postular/<int:tarea_id>', methods=['POST'])
@requerir_rol(['estudiante'])
def postular_voluntariado(evento_id, tarea_id):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO voluntariado_postulaciones (tarea_id, estudiante_id, estado)
                VALUES (%s, %s, 'pendiente')
            """, (tarea_id, session['usuario_id']))
        conexion.commit()
        flash("🙋‍♂️ Te has postulado a la tarea de voluntariado. Pendiente de aprobación.", "success")
    except Exception as e:
        flash("⚠️ Ya estás postulado a esta tarea o se presentó un problema.", "warning")
    finally:
        conexion.close()

    return redirect(url_for('detalle_evento', evento_id=evento_id))


# ==========================================
# RUTAS DE CERTIFICACIÓN DIGITAL PDF + QR
# ==========================================

@app.route('/evento/<int:evento_id>/certificado')
def generar_certificado_pdf(evento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para descargar tu certificado.", "warning")
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    datos = obtener_datos_certificado_bd(evento_id, usuario_id)

    # Validar que exista la inscripción y la asistencia esté confirmada
    if not datos or not datos.get('asistio'):
        flash("⚠️ No tienes un certificado disponible para este evento (requiere asistencia confirmada).", "warning")
        return redirect(url_for('detalle_evento', evento_id=evento_id))

    # --- GENERACIÓN DEL PDF EN MEMORIA ---
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
    ancho, alto = landscape(letter)

    # Marco / Borde Institucional
    pdf.setStrokeColor(colors.HexColor("#002b49")) # Azul Institucional UC
    pdf.setLineWidth(5)
    pdf.rect(20, 20, ancho - 40, alto - 40)
    pdf.setLineWidth(1)
    pdf.rect(25, 25, ancho - 50, alto - 50)

    # Encabezado Institucional
    pdf.setFont("Helvetica-Bold", 14)
    pdf.setFillColor(colors.HexColor("#002b49"))
    pdf.drawCentredString(ancho / 2, alto - 70, "UNIVERSIDAD DE CARABOBO")
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawCentredString(ancho / 2, alto - 88, "FACULTAD EXPERIMENTAL DE CIENCIAS Y TECNOLOGÍA (FaCyT)")
    pdf.drawCentredString(ancho / 2, alto - 104, "SISTEMA DE GESTIÓN DE JORNADAS CIENTÍFICAS (SGJC)")

    # Título Principal
    pdf.setFont("Helvetica-Bold", 26)
    pdf.setFillColor(colors.HexColor("#002b49"))
    pdf.drawCentredString(ancho / 2, alto - 150, "OTORGA EL PRESENTE CERTIFICADO A:")

    # Nombre del Participante
    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawCentredString(ancho / 2, alto - 190, datos['usuario_nombre'].upper())

    # Cédula o Identificación
    cedula_txt = f"C.I. / Identificación: {datos['usuario_cedula']}" if datos.get('usuario_cedula') else ""
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawCentredString(ancho / 2, alto - 210, cedula_txt)

    # Texto de Acreditación
    rol_participacion = "ASISTENTE" if datos['usuario_rol'] in ['estudiante', 'profesor'] else datos['usuario_rol'].upper()
    cuerpo = f"Por su valiosa participación como {rol_participacion} en la actividad académica / científica:"
    pdf.drawCentredString(ancho / 2, alto - 245, cuerpo)

    # Nombre del Evento
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(colors.HexColor("#0284c7"))
    pdf.drawCentredString(ancho / 2, alto - 275, f'"{datos["evento_titulo"]}"')

    # Fecha
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.drawCentredString(ancho / 2, alto - 305, f"Realizado en fecha: {datos['evento_fecha']}")

    # --- GENERACIÓN Y EMBEBIDO DEL CÓDIGO QR ---
    url_validacion = request.host_url.rstrip('/') + f"/certificado/validar?ev={evento_id}&usr={usuario_id}"
    qr_img = qrcode.make(url_validacion)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, "PNG")
    qr_buffer.seek(0)

    # Dibujar QR en la esquina inferior izquierda
    from reportlab.lib.utils import ImageReader
    pdf.drawImage(ImageReader(qr_buffer), 50, 45, width=75, height=75)
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.drawString(50, 35, "Verificación Digital QR")

    # Firmas Autorizadas (Pie de Página)
    pdf.setStrokeColor(colors.HexColor("#94a3b8"))
    pdf.line(ancho / 2 - 120, 70, ancho / 2 + 120, 70)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawCentredString(ancho / 2, 55, "Comité Organizador / Decanato FaCyT")
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(ancho / 2, 42, "Universidad de Carabobo")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Certificado_{datos["usuario_nombre"].replace(" ", "_")}.pdf'
    )

@app.route('/certificado/validar')
def validar_certificado_qr():
    evento_id = request.args.get('ev', type=int)
    usuario_id = request.args.get('usr', type=int)

    if not evento_id or not usuario_id:
        return "❌ Código o enlace de verificación inválido.", 400

    datos = obtener_datos_certificado_bd(evento_id, usuario_id)

    if datos and datos.get('asistio'):
        return f"""
        <div style="font-family: sans-serif; text-align: center; padding: 40px; max-width: 500px; margin: auto; border: 2px solid #22c55e; border-radius: 12px; background: #f0fdf4;">
            <h2 style="color: #15803d;">✅ CERTIFICADO VÁLIDO</h2>
            <p><strong>Otorgado a:</strong> {datos['usuario_nombre']}</p>
            <p><strong>Cédula:</strong> {datos.get('usuario_cedula') or 'N/A'}</p>
            <p><strong>Evento:</strong> {datos['evento_titulo']}</p>
            <p><strong>Rol:</strong> {datos['usuario_rol'].capitalize()}</p>
            <p><strong>Fecha:</strong> {datos['evento_fecha']}</p>
            <hr style="border: 0.5px solid #bbf7d0;">
            <small style="color: #166534;">Documento verificado digitalmente por el Sistema SGJC - FaCyT UC</small>
        </div>
        """
    else:
        return """
        <div style="font-family: sans-serif; text-align: center; padding: 40px; max-width: 500px; margin: auto; border: 2px solid #ef4444; border-radius: 12px; background: #fef2f2;">
            <h2 style="color: #b91c1c;">❌ CERTIFICADO NO VÁLIDO</h2>
            <p>El documento consultado no figura en los registros de asistencia oficiales de la FaCyT.</p>
        </div>
        """, 404

@app.route('/evento/<int:evento_id>/asistencia/<int:usuario_id>', methods=['POST'])
def cambiar_asistencia(evento_id, usuario_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    rol_actual = str(session.get('usuario_rol') or session.get('rol') or '').lower()
    roles_autorizados = ['administrador', 'admin', 'administrativo', 'profesor', 'ponente']
    
    if rol_actual not in roles_autorizados:
        flash("⛔ No estás autorizado para realizar esta acción.", "error")
        return redirect(url_for('inicio'))

    nuevo_estado = request.form.get('asistio') == '1'

    try:
        cambiar_estado_asistencia_bd(evento_id, usuario_id, nuevo_estado)
        flash("✅ Estado de asistencia actualizado correctamente.", "success")
    except Exception as e:
        print(f"❌ Error al cambiar asistencia: {e}")
        flash("Error al modificar el estado de asistencia.", "error")

    return redirect(url_for('ver_inscritos_evento', evento_id=evento_id))

#NUEVAS MODIFICACIONES
# ==========================================
# RUTAS DE JURADOS Y MENTORES
# ==========================================

@app.route('/postular-jurado', methods=['GET', 'POST'])
def postular_jurado():
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para postularte como Jurado/Mentor.", "warning")
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']

    if request.method == 'POST':
        institucion = request.form.get('institucion_origen', '').strip()
        pais = request.form.get('pais', '').strip()
        especialidad = request.form.get('area_especialidad', '').strip()

        if not institucion or not pais or not especialidad:
            flash("Todos los campos son obligatorios.", "warning")
        else:
            try:
                registrar_postulacion_jurado_bd(usuario_id, institucion, pais, especialidad)
                flash("✅ Tu postulación como Jurado/Mentor ha sido enviada con éxito.", "success")
                return redirect(url_for('inicio'))
            except Exception as e:
                print(f"❌ Error al postular jurado: {e}")
                flash("Ocurrió un error al registrar la postulación.", "error")

    perfil_jurado = obtener_perfil_jurado_bd(usuario_id)
    return render_template('postular_jurado.html', perfil=perfil_jurado)


@app.route('/evento/<int:evento_id>/evaluar', methods=['GET', 'POST'])
def evaluar_evento(evento_id):
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para calificar este evento.", "warning")
        return redirect(url_for('login'))

    rol_actual = str(session.get('usuario_rol') or session.get('rol') or '').lower()
    roles_autorizados = ['profesor', 'ponente', 'administrador', 'admin', 'administrativo']

    if rol_actual not in roles_autorizados:
        flash("⛔ No estás autorizado como evaluador o mentor.", "error")
        return redirect(url_for('inicio'))

    evento = obtener_detalle_evento_bd(evento_id)
    if not evento:
        flash("El evento solicitado no existe.", "error")
        return redirect(url_for('inicio'))

    usuario_id = session['usuario_id']

    if request.method == 'POST':
        try:
            p_contenido = int(request.form.get('puntuacion_contenido', 1))
            p_dominio = int(request.form.get('puntuacion_dominio', 1))
            p_presentacion = int(request.form.get('puntuacion_presentacion', 1))
            observaciones = request.form.get('observaciones', '').strip()

            guardar_evaluacion_evento_bd(
                evento_id, usuario_id, p_contenido, p_dominio, p_presentacion, observaciones
            )
            flash("⭐ Evaluacion de Jurado registrada correctamente.", "success")
            return redirect(url_for('detalle_evento', evento_id=evento_id))
        except Exception as e:
            print(f"❌ Error al guardar evaluación: {e}")
            flash("Error al procesar la calificación.", "error")

    evaluacion_existente = obtener_evaluacion_evento_bd(evento_id, usuario_id)

    return render_template(
        'evaluar_evento.html',
        evento=evento,
        evaluacion=evaluacion_existente
    )


# =========================================================
# RUTAS DE VOLUNTARIADO 
# =========================================================

@app.route('/evento/<int:evento_id>/crear-tarea', methods=['POST'])
def crear_tarea_voluntariado(evento_id):
    # Validamos que sea un usuario con permisos
    if 'usuario_id' not in session or session.get('usuario_rol') not in ['administrativo', 'ponente', 'Admin', 'Profesor', 'Administrativo']:
        flash("Acceso denegado para crear tareas.", "error")
        return redirect(url_for('home')) # Cambia 'home' por el nombre de tu ruta principal si es diferente
    
    nombre = request.form.get('titulo_tarea')
    descripcion = request.form.get('descripcion')
    horas = int(request.form.get('horas_acreditadas', 0))
    cupos = int(request.form.get('cupos_disponibles', 1))
    
    crear_tarea_voluntariado_bd(evento_id, nombre, descripcion, horas, cupos)
    flash("✅ Oportunidad de voluntariado creada exitosamente.", "success")
    return redirect(url_for('detalle_evento', evento_id=evento_id)) # Asegúrate de que tu ruta de detalle se llama así


@app.route('/tarea/<int:tarea_id>/postular', methods=['POST'])
def postular_tarea(tarea_id):
    # Obtenemos el rol asegurando compatibilidad con 'usuario_rol' o 'rol'
    rol_actual = session.get('usuario_rol') or session.get('rol', '')

    # Validamos usando 'not in' en lugar de '!='
    if 'usuario_id' not in session or rol_actual not in ['Estudiante', 'estudiante', 'ESTUDIANTE']:
        flash("Solo los estudiantes pueden postularse al voluntariado.", "error")
        return redirect(request.referrer or url_for('inicio'))

    evento_id = request.form.get('evento_id')
    exito = postular_voluntario_bd(tarea_id, session['usuario_id'])
    
    if exito:
        flash("🙋‍♂️ Te has postulado correctamente. Espera la aprobación del coordinador.", "success")
    else:
        flash("⚠️ Ya te habías postulado a esta tarea anteriormente.", "error")
        
    return redirect(url_for('detalle_evento', evento_id=evento_id))

@app.route('/postulacion/<int:postulacion_id>/<string:accion>', methods=['POST'])
def gestionar_postulacion(postulacion_id, accion):
    rol_actual = str(session.get('usuario_rol') or session.get('rol') or '').lower()
    roles_permitidos = ['administrativo', 'administrador', 'admin', 'profesor', 'ponente']

    if 'usuario_id' not in session or rol_actual not in roles_permitidos:
        flash("No tienes permisos para realizar esta acción.", "error")
        return redirect(request.referrer or url_for('inicio'))
    
    evento_id = request.form.get('evento_id')
    nuevo_estado = 'aprobado' if accion == 'aprobar' else 'rechazado'
    
    exito = cambiar_estado_postulacion_bd(postulacion_id, nuevo_estado)
    if exito:
        msg = "✅ Postulación aprobada exitosamente." if nuevo_estado == 'aprobado' else "ℹ️ Postulación rechazada."
        flash(msg, "success" if nuevo_estado == 'aprobado' else "info")
    else:
        flash("Error al actualizar el estado de la postulación.", "error")
        
    return redirect(url_for('detalle_evento', evento_id=evento_id))

# --- RUTAS DE ADMINISTRACIÓN DE PROPUESTAS ---
# ==========================================
# GESTIÓN DE PROPUESTAS DE ESTUDIANTES
# ==========================================

# 1. EDITAR PROPUESTA (ESTUDIANTE)
@app.route('/editar_propuesta/<int:propuesta_id>', methods=['GET', 'POST'])
@requerir_rol(['estudiante'])
def editar_propuesta(propuesta_id):
    propuesta = evento_repo.obtener_propuesta_por_id(propuesta_id)
    if not propuesta:
        flash("❌ La propuesta solicitada no existe.", "error")
        return redirect(url_for('mis_propuestas'))
        
    # Verificar pertenencia del estudiante y que siga en estado pendiente
    if propuesta['estudiante_id'] != session['usuario_id']:
        flash("⛔ No tienes permisos para editar esta propuesta.", "error")
        return redirect(url_for('mis_propuestas'))

    if str(propuesta.get('estado', '')).lower() not in ['pendiente', 'en revision', 'en_revision']:
        flash("⚠️ Solo puedes editar propuestas que se encuentren en estado pendiente.", "warning")
        return redirect(url_for('mis_propuestas'))

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        departamento = request.form.get('departamento')
        tipo_actividad = request.form.get('tipo_actividad')
        descripcion = request.form.get('descripcion')

        exito = evento_repo.editar_propuesta_estudiante(
            propuesta_id=propuesta_id,
            estudiante_id=session['usuario_id'],
            titulo=titulo,
            departamento=departamento,
            tipo_actividad=tipo_actividad,
            descripcion=descripcion
        )

        if exito:
            flash("✏️ ¡Propuesta actualizada con éxito!", "success")
            return redirect(url_for('mis_propuestas'))
        else:
            flash("❌ No se pudieron guardar los cambios en la propuesta.", "error")

    return render_template('editar_propuesta.html', propuesta=propuesta)


# 2. APROBAR Y AGENDAR PROPUESTA (ADMINISTRATIVO)
@app.route('/admin/aprobar-propuesta/<int:propuesta_id>', methods=['GET', 'POST'])
@requerir_rol(['administrativo'])
def aprobar_propuesta(propuesta_id):
    propuesta = evento_repo.obtener_propuesta_por_id(propuesta_id)
    if not propuesta:
        flash("❌ La propuesta no existe.", "error")
        return redirect(url_for('admin'))

    if request.method == 'POST':
        espacio_id = request.form.get('espacio_id')
        fecha = request.form.get('fecha')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')

        if not all([espacio_id, fecha, hora_inicio, hora_fin]):
            flash("❌ Por favor asigne el espacio, la fecha y el horario completo.", "error")
            return redirect(url_for('aprobar_propuesta', propuesta_id=propuesta_id))

        resultado = evento_repo.aceptar_y_agendar_propuesta(
            propuesta_id=propuesta_id,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            espacio_id=espacio_id
        )

        if resultado.get('exito'):
            flash("🎉 " + resultado['mensaje'], "success")
            return redirect(url_for('admin'))
        else:
            flash(resultado.get('mensaje', 'Error al procesar la aprobación.'), "error")

    espacios = evento_repo.obtener_lista_espacios_formulario()
    return render_template('aprobar_propuesta_form.html', propuesta=propuesta, espacios=espacios)


# 3. RECHAZAR PROPUESTA (ADMINISTRATIVO)
@app.route('/admin/rechazar-propuesta/<int:propuesta_id>', methods=['POST'])
@requerir_rol(['administrativo'])
def rechazar_propuesta(propuesta_id):
    if evento_repo.rechazar_propuesta_estudiante(propuesta_id):
        flash("🚫 La propuesta ha sido rechazada correctamente.", "info")
    else:
        flash("❌ Ocurrió un error al intentar rechazar la propuesta.", "error")
    return redirect(url_for('admin'))

@app.route('/admin/propuesta/eliminar/<int:propuesta_id>', methods=['POST'])
def eliminar_propuesta(propuesta_id):
    if eliminar_propuesta_estudiante(propuesta_id):
        flash("Propuesta eliminada correctamente.", "success")
    else:
        flash("No se pudo eliminar la propuesta.", "danger")
        
    return redirect(url_for('admin'))  # Ajusta al nombre de tu vista admin

# --- SALIDA DEL SISTEMA ---
@app.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión de forma segura.", "success")
    return redirect(url_for('inicio'))


if __name__ == '__main__':
    app.run(debug=True)
