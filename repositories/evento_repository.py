import pymysql
from database import obtener_conexion
from core.security import clean_input_strict, clean_html_entities


# --- METRICAS Y DASHBOARD ---

def obtener_metricas_dashboard():
    conexion = obtener_conexion()
    metrics = {'totales': 0, 'pendientes': 0, 'aprobados': 0, 'propuestas': 0}
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM eventos")
            res_totales = cursor.fetchone()
            metrics['totales'] = res_totales['total'] if res_totales else 0

            cursor.execute("""
                SELECT COUNT(*) AS pendientes 
                FROM eventos 
                WHERE LOWER(estado) IN ('revision', 'pendiente', 'solicitado', 'en revision')
            """)
            res_pendientes = cursor.fetchone()
            metrics['pendientes'] = res_pendientes['pendientes'] if res_pendientes else 0

            cursor.execute("""
                SELECT COUNT(*) AS aprobados 
                FROM eventos 
                WHERE LOWER(estado) IN ('aprobado', 'aprobada', 'confirmado')
            """)
            res_aprobados = cursor.fetchone()
            metrics['aprobados'] = res_aprobados['aprobados'] if res_aprobados else 0

            cursor.execute("SELECT COUNT(*) AS propuestas FROM propuestas_estudiantes")
            res_propuestas = cursor.fetchone()
            metrics['propuestas'] = res_propuestas['propuestas'] if res_propuestas else 0

    except Exception as e:
        print(f"⚠️ Error al obtener métricas del dashboard: {e}")
    finally:
        conexion.close()
        
    return metrics


def obtener_proximos_eventos(limite=5):
    """Retorna los próximos eventos para el panel público/dashboard."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                       esp.nombre AS espacio, u.nombre AS responsable
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                WHERE e.estado IN ('aprobado', 'programado')
                ORDER BY e.fecha ASC LIMIT %s;
            """, (limite,))
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_eventos_cartelera_publica(usuario_id=None):
    """Retorna los eventos aprobados para la cartelera pública con estados de cupo e inscripción."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    e.id, 
                    e.titulo, 
                    e.departamento,
                    e.tipo_actividad, 
                    e.fecha, 
                    e.hora_inicio, 
                    e.hora_fin, 
                    e.enlace_virtual,
                    esp.nombre AS espacio, 
                    esp.capacidad AS capacidad_maxima, 
                    u.nombre AS responsable,
                    (SELECT COUNT(*) FROM inscripciones i WHERE i.evento_id = e.id) AS total_inscritos,
                    (SELECT COUNT(*) FROM inscripciones i WHERE i.evento_id = e.id AND i.usuario_id = %s) AS esta_inscrito
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                WHERE e.estado IN ('aprobado', 'cancelado')
                ORDER BY e.fecha ASC;
            """, (usuario_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


# --- GESTIÓN Y VALIDACIÓN DE EVENTOS ---

def verificar_conflicto_horario(espacio_id, fecha, hora_inicio, hora_fin, evento_id_excluir=None):
    """Verifica si existe un traslape de horario en el mismo espacio y fecha."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
                SELECT id, titulo FROM eventos 
                WHERE espacio_id = %s 
                  AND fecha = %s 
                  AND estado NOT IN ('cancelado', 'rechazado')
                  AND (%s < hora_fin AND %s > hora_inicio)
            """
            params = [espacio_id, fecha, hora_inicio, hora_fin]
            
            if evento_id_excluir:
                sql += " AND id != %s"
                params.append(evento_id_excluir)
                
            cursor.execute(sql, tuple(params))
            return cursor.fetchone()
    finally:
        conexion.close()


def crear_solicitud_evento(titulo, responsable_id, tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin, departamento, enlace_virtual="", descripcion=""):
    """Inserta una solicitud formal de evento incluyendo su descripción."""
    conflicto = verificar_conflicto_horario(espacio_id, fecha, hora_inicio, hora_fin)
    if conflicto:
        return {
            "exito": False, 
            "mensaje": f"⚠️ El espacio ya está reservado en ese horario por '{conflicto['titulo']}'."
        }

    titulo_limpio = clean_input_strict(titulo)
    departamento_limpio = clean_input_strict(departamento)
    descripcion_limpia = clean_html_entities(descripcion) if descripcion else ""
    
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO eventos (titulo, departamento, tipo_actividad, fecha, hora_inicio, hora_fin, estado, espacio_id, enlace_virtual, responsable_id, descripcion)
                VALUES (%s, %s, %s, %s, %s, %s, 'pendiente', %s, %s, %s, %s);
            """, (
                titulo_limpio, 
                departamento_limpio, 
                tipo_actividad, 
                fecha, 
                hora_inicio, 
                hora_fin, 
                espacio_id, 
                enlace_virtual, 
                responsable_id,
                descripcion_limpia
            ))
        conexion.commit()
        return {"exito": True, "mensaje": "Solicitud creada exitosamente."}
        
    except pymysql.MySQLError as e:
        if e.args[0] == 45000:
            return {"exito": False, "mensaje": e.args[1]}
        return {"exito": False, "mensaje": f"Error de base de datos: {e}"}
        
    finally:
        conexion.close()


def obtener_solicitudes_totales_admin():
    """Retorna todas las solicitudes formales para el panel del administrador."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, e.estado, 
                       esp.nombre AS espacio, u.nombre AS solicitado_por
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                ORDER BY e.fecha ASC;
            """)
            return cursor.fetchall()
    finally:
        conexion.close()


def actualizar_estado_evento(evento_id, nuevo_estado):
    """Actualiza el estado de un evento."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.titulo, u.nombre AS solicitante FROM eventos e
                LEFT JOIN usuarios u ON e.responsable_id = u.id WHERE e.id = %s;
            """, (evento_id,))
            evento = cursor.fetchone()
            
            cursor.execute("UPDATE eventos SET estado = %s WHERE id = %s;", (nuevo_estado, evento_id))
        conexion.commit()
        return {"status": "success", "evento": evento}
    except pymysql.MySQLError as e:
        if e.args[0] == 45000:
            return {"status": "error", "message": f"Conflictivo: {e.args[1]}"}
        return {"status": "error", "message": "Error interno en la base de datos."}
    finally:
        conexion.close()


def eliminar_evento(evento_id):
    """Eliminación permanente de un evento."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM eventos WHERE id = %s;", (evento_id,))
        conexion.commit()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conexion.close()


def obtener_evento_por_id(evento_id):
    """Busca un evento específico para edición o detalle."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.id, e.titulo, e.descripcion, e.tipo_actividad, e.espacio_id, e.fecha, e.hora_inicio, e.hora_fin, e.estado,
                       esp.nombre AS espacio, u.nombre AS responsable
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                LEFT JOIN usuarios u ON e.responsable_id = u.id
                WHERE e.id = %s;
            """, (evento_id,))
            return cursor.fetchone()
    finally:
        conexion.close()


def actualizar_evento_basico(evento_id, titulo, tipo_actividad):
    """Modifica sólo título y tipo del evento."""
    titulo_limpio = clean_input_strict(titulo)
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE eventos SET titulo = %s, tipo_actividad = %s WHERE id = %s;",
                (titulo_limpio, tipo_actividad, evento_id)
            )
        conexion.commit()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conexion.close()


def actualizar_evento_completo(evento_id, titulo, tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin):
    """Actualiza un evento re-validando choques de horario."""
    conflicto = verificar_conflicto_horario(espacio_id, fecha, hora_inicio, hora_fin, evento_id_excluir=evento_id)
    if conflicto:
        return {
            "exito": False, 
            "mensaje": f"⚠️ El espacio ya se encuentra reservado por '{conflicto['titulo']}'."
        }

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            sql = """
                UPDATE eventos 
                SET titulo = %s, tipo_actividad = %s, espacio_id = %s, fecha = %s, hora_inicio = %s, hora_fin = %s 
                WHERE id = %s;
            """
            cursor.execute(sql, (clean_input_strict(titulo), tipo_actividad, espacio_id, fecha, hora_inicio, hora_fin, evento_id))
        conexion.commit()
        return {"exito": True, "mensaje": "Evento actualizado correctamente."}
    except Exception as e:
        return {"exito": False, "mensaje": f"Error al actualizar: {str(e)}"}
    finally:
        conexion.close()


def obtener_mis_solicitudes(responsable_id):
    """Historial específico de solicitudes de un ponente/profesor."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, e.estado, esp.nombre AS espacio
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.responsable_id = %s ORDER BY e.fecha DESC;
            """, (responsable_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_eventos_por_profesor(profesor_id):
    """Obtiene los eventos gestionados por un profesor específico."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.*, esp.nombre as espacio_nombre,
                       (SELECT COUNT(*) FROM inscripciones WHERE evento_id = e.id) as total_inscritos
                FROM eventos e
                JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.responsable_id = %s
                ORDER BY e.fecha DESC;
            """, (profesor_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


# --- PROPUESTAS DE ESTUDIANTES ---

def crear_propuesta_estudiante(estudiante_id, titulo, tipo_actividad, descripcion, departamento='General'):
    """Inserta una idea sugerida por los alumnos con estado 'pendiente' por defecto."""
    titulo_limpio = clean_input_strict(titulo)
    departamento_limpio = clean_input_strict(departamento)
    descripcion_segura = clean_html_entities(descripcion)
    
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO propuestas_estudiantes (estudiante_id, titulo, departamento, tipo_actividad, descripcion, estado)
                VALUES (%s, %s, %s, %s, %s, 'pendiente');
            """, (estudiante_id, titulo_limpio, departamento_limpio, tipo_actividad, descripcion_segura))
        conexion.commit()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conexion.close()


def obtener_propuesta_por_id(propuesta_id):
    """Obtiene una propuesta por su ID para formularios de edición o aprobación."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT p.*, u.nombre AS estudiante_nombre 
                FROM propuestas_estudiantes p
                JOIN usuarios u ON p.estudiante_id = u.id
                WHERE p.id = %s;
            """, (propuesta_id,))
            return cursor.fetchone()
    finally:
        conexion.close()


def obtener_propuestas_totales_admin():
    """Lista de propuestas estudiantiles para evaluar en el Panel Admin."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT p.id, p.titulo, p.tipo_actividad, p.descripcion, u.nombre AS estudiante
                FROM propuestas_estudiantes p
                JOIN usuarios u ON p.estudiante_id = u.id ORDER BY p.id DESC;
            """)
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_mis_propuestas_estudiante(estudiante_id):
    """Historial de propuestas enviadas por un estudiante específico con sus estados."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, titulo, departamento, tipo_actividad, descripcion, estado, fecha_propuesta_evento 
                FROM propuestas_estudiantes 
                WHERE estudiante_id = %s 
                ORDER BY id DESC;
            """, (estudiante_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


def rechazar_propuesta_estudiante(propuesta_id):
    """Cambia el estado de una propuesta a 'rechazado'."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE propuestas_estudiantes SET estado = 'rechazado' WHERE id = %s;",
                (propuesta_id,)
            )
        conexion.commit()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conexion.close()


def aceptar_y_agendar_propuesta(propuesta_id, fecha, hora_inicio, hora_fin, espacio_id):
    """
    Valida cruce de horario, crea el evento oficial con el estudiante de responsable
    y actualiza la propuesta a estado 'aceptado'.
    """
    propuesta = obtener_propuesta_por_id(propuesta_id)
    if not propuesta:
        return {"exito": False, "mensaje": "La propuesta solicitada no existe."}

    # 1. Validar choque de horarios en el espacio seleccionado
    conflicto = verificar_conflicto_horario(espacio_id, fecha, hora_inicio, hora_fin)
    if conflicto:
        return {"exito": False, "mensaje": f"⚠️ El espacio ya se encuentra reservado en ese horario por '{conflicto['titulo']}'."}

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # A) Crear evento en tabla oficial
            cursor.execute("""
                INSERT INTO eventos 
                (titulo, departamento, tipo_actividad, fecha, hora_inicio, hora_fin, estado, espacio_id, responsable_id, descripcion)
                VALUES (%s, %s, %s, %s, %s, %s, 'aprobado', %s, %s, %s);
            """, (
                propuesta['titulo'],
                propuesta['departamento'],
                propuesta['tipo_actividad'],
                fecha,
                hora_inicio,
                hora_fin,
                espacio_id,
                propuesta['estudiante_id'],
                propuesta['descripcion']
            ))

            # B) Actualizar propuesta
            cursor.execute("""
                UPDATE propuestas_estudiantes 
                SET estado = 'aceptado', 
                    fecha_propuesta_evento = %s, 
                    hora_inicio = %s, 
                    hora_fin = %s, 
                    espacio_id = %s
                WHERE id = %s;
            """, (fecha, hora_inicio, hora_fin, espacio_id, propuesta_id))

        conexion.commit()
        return {"exito": True, "mensaje": "¡Propuesta aceptada y agendada exitosamente!"}
    except Exception as e:
        conexion.rollback()
        return {"exito": False, "mensaje": f"Error al procesar propuesta: {str(e)}"}
    finally:
        conexion.close()


def editar_propuesta_estudiante(propuesta_id, estudiante_id, titulo, departamento, tipo_actividad, descripcion):
    """Permite al estudiante modificar su propuesta SOLO MIENTRAS esté 'pendiente' o 'en revisión'."""
    titulo_limpio = clean_input_strict(titulo) if titulo else ""
    departamento_limpio = clean_input_strict(departamento) if departamento else ""
    descripcion_segura = clean_html_entities(descripcion) if descripcion else ""

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                UPDATE propuestas_estudiantes 
                SET titulo = %s, departamento = %s, tipo_actividad = %s, descripcion = %s
                WHERE id = %s 
                  AND estudiante_id = %s 
                  AND LOWER(estado) IN ('pendiente', 'en revision', 'en_revision');
            """, (titulo_limpio, departamento_limpio, tipo_actividad, descripcion_segura, propuesta_id, estudiante_id))
            
        conexion.commit()
        
        # En MySQL/MariaDB la consulta se ejecuta con éxito aunque no haya cambios de texto.
        return True

    except Exception as e:
        # Imprime el detalle exacto en la terminal donde corre Flask
        print(f"❌ [ERROR DB] Falló editar_propuesta_estudiante: {e}")
        return False
    finally:
        conexion.close()

# --- ESTADÍSTICAS Y AUXILIARES ---

def obtener_top_espacios():
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT esp.nombre, COUNT(e.id) as total FROM eventos e
                JOIN espacios esp ON e.espacio_id = esp.id GROUP BY esp.nombre
                ORDER BY total DESC LIMIT 5;
            """)
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_conteo_estados():
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT estado, COUNT(*) as total FROM eventos GROUP BY estado;")
            return cursor.fetchall()
    finally:
        conexion.close()


def obtener_lista_espacios_formulario():
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT id, nombre, capacidad FROM espacios;")
            return cursor.fetchall()
    finally:
        conexion.close()


def validar_por_titulo(titulo):
    """Verifica si ya existe una propuesta de estudiante con el mismo título."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id FROM propuestas_estudiantes 
                WHERE LOWER(TRIM(titulo)) = LOWER(TRIM(%s));
            """, (titulo,))
            return cursor.fetchone() is not None
    finally:
        conexion.close()


def obtener_evento_difusion(evento_id):
    """Obtiene todos los datos de un evento para la plantilla de difusión."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    e.*, 
                    esp.nombre AS espacio_nombre
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.id = %s;
            """, (evento_id,))
            return cursor.fetchone()
    finally:
        conexion.close()