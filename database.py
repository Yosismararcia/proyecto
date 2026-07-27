import os
from dotenv import load_dotenv
import pymysql
import pymysql.cursors

load_dotenv()

def obtener_conexion():
    """Establece y retorna una conexión a la base de datos MySQL con dict cursors."""
    host = os.getenv('DB_HOST', 'localhost')
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    database = os.getenv('DB_NAME', 'facyt_eventos_v2')
    
    try:
        port = int(os.getenv('DB_PORT', 3306))
    except (ValueError, TypeError):
        port = 3306

    # Configuración de certificado SSL opcional para Aiven u otros servicios secure
    ssl_ca = os.getenv('DB_SSL_CA')
    ssl_cert = os.getenv('DB_SSL_CERT')
    ssl_key = os.getenv('DB_SSL_KEY')
    ssl_verify = os.getenv('DB_SSL_VERIFY', 'true').lower() not in ('0', 'false', 'no')

    ssl_config = None
    if ssl_ca or ssl_cert or ssl_key:
        ssl_config = {}
        if ssl_ca:
            ssl_config['ca'] = ssl_ca
        if ssl_cert:
            ssl_config['cert'] = ssl_cert
        if ssl_key:
            ssl_config['key'] = ssl_key
        ssl_config['check_hostname'] = ssl_verify

    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        port=port,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        ssl=ssl_config,
        autocommit=True
    )

# =========================================================
# FUNCIONES DE BASE DE DATOS PARA DETALLE, FORO Y VOLUNTARIADO
# =========================================================

def obtener_detalle_evento_bd(evento_id):
    """Obtiene los datos de un evento y su espacio."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.*, esp.nombre AS espacio_nombre
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.id = %s
            """, (evento_id,))
            evento = cursor.fetchone()
            
            if evento:
                # Normalización del nombre del ponente u organizador
                evento['ponente_nombre'] = (
                    evento.get('ponente') or 
                    evento.get('organizador') or 
                    'Comité FaCyT'
                )
            return evento
    finally:
        conexion.close()


def obtener_foro_discusiones_bd(evento_id):
    """Obtiene los mensajes del foro con los datos del usuario."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT f.*, u.nombre AS usuario_nombre, u.rol AS usuario_rol
                FROM foro_discusiones f
                JOIN usuarios u ON f.usuario_id = u.id
                WHERE f.evento_id = %s
                ORDER BY f.fecha_publicacion DESC
            """, (evento_id,))
            return cursor.fetchall()
    finally:
        conexion.close()

def obtener_inscripcion_usuario_bd(evento_id, usuario_id):
    """Verifica el estado de inscripción y asistencia de un usuario en un evento."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM inscripciones WHERE evento_id = %s AND usuario_id = %s
            """, (evento_id, usuario_id))
            return cursor.fetchone()
    finally:
        conexion.close()


def insertar_mensaje_foro_bd(evento_id, usuario_id, mensaje):
    """Inserta una nueva intervención en el foro de discusión."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO foro_discusiones (evento_id, usuario_id, mensaje)
                VALUES (%s, %s, %s)
            """, (evento_id, usuario_id, mensaje))
        conexion.commit()
        return True
    finally:
        conexion.close()

def obtener_datos_certificado_bd(evento_id, usuario_id):
    """Obtiene los datos del usuario y del evento para la emisión del certificado."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    u.nombre AS usuario_nombre,
                    u.cedula AS usuario_cedula,
                    u.rol AS usuario_rol,
                    e.titulo AS evento_titulo,
                    e.fecha AS evento_fecha,
                    i.asistio AS asistio
                FROM inscripciones i
                JOIN usuarios u ON i.usuario_id = u.id
                JOIN eventos e ON i.evento_id = e.id
                WHERE i.evento_id = %s AND i.usuario_id = %s
            """, (evento_id, usuario_id))
            return cursor.fetchone()
    finally:
        conexion.close()        

# =========================================================
# FUNCIONES PARA GESTIÓN DE ASISTENCIA E INSCRITOS
# =========================================================

def obtener_inscritos_evento_bd(evento_id):
    """Obtiene el listado de participantes con alias compatibles con la plantilla."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    i.id AS inscripcion_id,
                    i.usuario_id,
                    i.fecha_inscripcion,
                    i.asistio AS asistio,
                    i.estado,
                    u.nombre,
                    u.correo,
                    u.cedula,
                    u.rol
                FROM inscripciones i
                JOIN usuarios u ON i.usuario_id = u.id
                WHERE i.evento_id = %s
                ORDER BY u.nombre ASC
            """, (evento_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


def cambiar_estado_asistencia_bd(evento_id, usuario_id, estado_asistencia):
    """Actualiza la asistencia de un usuario en un evento (1 = asistió, 0 = no asistió)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE inscripciones 
                SET asistio = %s 
                WHERE evento_id = %s AND usuario_id = %s
            """, (1 if estado_asistencia else 0, evento_id, usuario_id))
        conexion.commit()
        return True
    finally:
        conexion.close()

# NUEVAS MODIFICACIONES

# =========================================================
# MÓDULO DE JURADOS Y MENTORÍA GLOBAL (jurados_evaluadores)
# =========================================================

def registrar_postulacion_jurado_bd(usuario_id, institucion_origen, pais, area_especialidad):
    """Registra o actualiza la postulación de un usuario como jurado o mentor."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO jurados_evaluadores (usuario_id, institucion_origen, pais, area_especialidad, estado)
                VALUES (%s, %s, %s, %s, 'postulado')
                ON DUPLICATE KEY UPDATE
                    institucion_origen = VALUES(institucion_origen),
                    pais = VALUES(pais),
                    area_especialidad = VALUES(area_especialidad)
            """, (usuario_id, institucion_origen, pais, area_especialidad))
        conexion.commit()
        return True
    finally:
        conexion.close()


def obtener_perfil_jurado_bd(usuario_id):
    """Obtiene los datos de perfil y estado del jurado en la plataforma."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT j.*, u.nombre, u.correo, u.rol
                FROM jurados_evaluadores j
                JOIN usuarios u ON j.usuario_id = u.id
                WHERE j.usuario_id = %s
            """, (usuario_id,))
            return cursor.fetchone()
    finally:
        conexion.close()


def cambiar_estado_jurado_bd(jurado_tabla_id, nuevo_estado):
    """Actualiza el estado de un jurado ('postulado', 'activo', 'inactivo')."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE jurados_evaluadores 
                SET estado = %s 
                WHERE id = %s
            """, (nuevo_estado, jurado_tabla_id))
        conexion.commit()
        return True
    finally:
        conexion.close()


def obtener_evaluacion_evento_bd(evento_id, jurado_id):
    """Obtiene la calificación realizada por un jurado en un evento determinado."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM evaluaciones_eventos 
                WHERE evento_id = %s AND jurado_id = %s
            """, (evento_id, jurado_id))
            return cursor.fetchone()
    finally:
        conexion.close()


def guardar_evaluacion_evento_bd(evento_id, jurado_id, p_contenido, p_dominio, p_presentacion, observaciones):
    """Guarda o actualiza la rúbrica del jurado para un evento."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO evaluaciones_eventos 
                    (evento_id, jurado_id, puntuacion_contenido, puntuacion_dominio, puntuacion_presentacion, observaciones)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    puntuacion_contenido = VALUES(puntuacion_contenido),
                    puntuacion_dominio = VALUES(puntuacion_dominio),
                    puntuacion_presentacion = VALUES(puntuacion_presentacion),
                    observaciones = VALUES(observaciones),
                    fecha_evaluacion = CURRENT_TIMESTAMP
            """, (evento_id, jurado_id, p_contenido, p_dominio, p_presentacion, observaciones))
        conexion.commit()
        return True
    finally:
        conexion.close()


# =========================================================
# MÓDULO DE VOLUNTARIADO (Agrega estas funciones a database.py)
# =========================================================

def crear_tarea_voluntariado_bd(evento_id, nombre, descripcion, horas, cupos):
    """Crea una nueva necesidad de staff/voluntarios para un evento."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO voluntariado_tareas (evento_id, titulo_tarea, descripcion, horas_acreditadas, cupos_disponibles)
                VALUES (%s, %s, %s, %s, %s)
            """, (evento_id, nombre, descripcion, horas, cupos))
        conexion.commit()
        return True
    finally:
        conexion.close()

def postular_voluntario_bd(tarea_id, usuario_id):
    """Registra a un estudiante como postulante en inscripciones_voluntarios."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # 1. Verificamos si el usuario ya se había postulado a esta tarea
            cursor.execute("SELECT id FROM inscripciones_voluntarios WHERE tarea_id = %s AND estudiante_id = %s", (tarea_id, usuario_id))
            if cursor.fetchone():
                return False # Ya está postulado
                
            # 2. Si no está postulado, lo insertamos
            cursor.execute("""
                INSERT INTO inscripciones_voluntarios (tarea_id, estudiante_id, estado)
                VALUES (%s, %s, 'postulado')
            """, (tarea_id, usuario_id))
        conexion.commit()
        return True
    finally:
        conexion.close()

def obtener_tareas_voluntariado_bd(evento_id, usuario_id=None):
    """
    Obtiene las tareas de un evento, calcula cupos ocupados (solo aprobados),
    revisa el estado de postulación del usuario actual y lista los postulantes para el docente/admin.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            sql = "SELECT id, evento_id, titulo_tarea, descripcion, horas_acreditadas, cupos_disponibles FROM voluntariado_tareas WHERE evento_id = %s"
            cursor.execute(sql, (evento_id,))
            tareas = cursor.fetchall()
            
            for tarea in tareas:
                # 1. Contar cupos ocupados considerando únicamente las solicitudes aprobadas
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM inscripciones_voluntarios WHERE tarea_id = %s AND estado = 'aprobado'",
                    (tarea['id'],)
                )
                res_ocupados = cursor.fetchone()
                tarea['ocupados'] = res_ocupados['total'] if res_ocupados else 0

                # 2. Obtener el estado del estudiante actual si está conectado
                tarea['mi_estado'] = None
                if usuario_id:
                    cursor.execute(
                        "SELECT estado FROM inscripciones_voluntarios WHERE tarea_id = %s AND estudiante_id = %s",
                        (tarea['id'], usuario_id)
                    )
                    res_mi_post = cursor.fetchone()
                    if res_mi_post:
                        tarea['mi_estado'] = res_mi_post['estado']

                # 3. Obtener la lista de postulantes con sus datos para gestión del coordinador
                cursor.execute("""
                    SELECT iv.id AS postulacion_id, iv.estudiante_id, iv.estado, u.nombre AS estudiante_nombre
                    FROM inscripciones_voluntarios iv
                    JOIN usuarios u ON iv.estudiante_id = u.id
                    WHERE iv.tarea_id = %s
                    ORDER BY iv.id DESC
                """, (tarea['id'],))
                tarea['postulaciones'] = cursor.fetchall()

            return tareas
    finally:
        conexion.close()


def cambiar_estado_postulacion_bd(postulacion_id, nuevo_estado):
    """Actualiza el estado de una postulación a 'aprobado' o 'rechazado'."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE inscripciones_voluntarios SET estado = %s WHERE id = %s",
                (nuevo_estado, postulacion_id)
            )
        conexion.commit()
        return True
    except Exception as e:
        print(f"Error al cambiar estado de postulación: {e}")
        return False
    finally:
        conexion.close()