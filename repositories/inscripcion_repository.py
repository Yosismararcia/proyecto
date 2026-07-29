import pymysql
from database import obtener_conexion

def registrar_inscripcion_segura(evento_id, usuario_id):
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. Verificar capacidad máxima y total de inscritos actuales
            cursor.execute("""
                SELECT 
                    e.estado,
                    esp.capacidad AS capacidad_maxima,
                    (SELECT COUNT(*) FROM inscripciones WHERE evento_id = %s) AS total_inscritos,
                    (SELECT COUNT(*) FROM inscripciones WHERE evento_id = %s AND usuario_id = %s) AS ya_inscrito
                FROM eventos e
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.id = %s;
            """, (evento_id, evento_id, usuario_id, evento_id))
            
            datos = cursor.fetchone()

            if not datos:
                return {"status": "error", "message": "El evento no existe."}

            if datos['ya_inscrito'] > 0:
                return {"status": "warning", "message": "Ya te encuentras inscrito en este evento."}

            if datos['total_inscritos'] >= datos['capacidad_maxima']:
                return {"status": "error", "message": "🚫 Capacidad agotada. No quedan cupos disponibles para este evento."}

            # 2. Registrar la inscripción
            cursor.execute("""
                INSERT INTO inscripciones (evento_id, usuario_id, fecha_inscripcion)
                VALUES (%s, %s, NOW());
            """, (evento_id, usuario_id))

        conexion.commit()
        return {"status": "success", "message": "¡Te has inscrito exitosamente al evento!"}

    except Exception as e:
        conexion.rollback()
        return {"status": "error", "message": f"Error al procesar la inscripción: {str(e)}"}
    finally:
        conexion.close()


def obtener_eventos_por_usuario(usuario_id):
    """Retorna la lista de eventos a los que se ha inscrito un usuario."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT e.*, esp.nombre as espacio_nombre, i.fecha_inscripcion 
                FROM inscripciones i
                JOIN eventos e ON i.evento_id = e.id
                JOIN espacios esp ON e.espacio_id = esp.id
                WHERE i.usuario_id = %s
                ORDER BY e.fecha DESC;
            """, (usuario_id,))
            return cursor.fetchall()
    finally:
        conexion.close()


def eliminar_propuesta_estudiante(propuesta_id):
    """Elimina permanentemente una propuesta de estudiante por su ID."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("DELETE FROM propuestas_estudiantes WHERE id = %s;", (propuesta_id,))
        conexion.commit()
        return True
    except pymysql.MySQLError as e:
        print(f"❌ Error al eliminar propuesta: {e}")
        return False
    finally:
        conexion.close()        