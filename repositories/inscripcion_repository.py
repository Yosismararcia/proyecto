import pymysql
from database import obtener_conexion


def registrar_inscripcion_segura(evento_id, usuario_id):
    """
    Registra a un usuario manejando bloqueo concurrente (FOR UPDATE)
    y control transaccional estricto.
    """
    conexion = obtener_conexion()
    
    try:
        conexion.begin()
        
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. Bloqueo pesimista sobre el evento
            cursor.execute("""
                SELECT e.id, esp.capacidad 
                FROM eventos e
                INNER JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.id = %s FOR UPDATE;
            """, (evento_id,))
            evento = cursor.fetchone()
            
            if not evento:
                conexion.rollback()
                return {"status": "error", "message": "El evento seleccionado no existe."}
                
            # 2. Contar inscritos activos en el momento
            cursor.execute("SELECT COUNT(*) as actuales FROM inscripciones WHERE evento_id = %s;", (evento_id,))
            res_conteo = cursor.fetchone()
            total_inscritos = res_conteo['actuales'] if res_conteo else 0
            capacidad_maxima = evento.get('capacidad', 0)
            
            if capacidad_maxima and total_inscritos >= capacidad_maxima:
                conexion.rollback()
                return {"status": "error", "message": "Los cupos para este evento se han agotado."}
                
            # 3. Validar duplicados
            cursor.execute(
                "SELECT id FROM inscripciones WHERE evento_id = %s AND usuario_id = %s;", 
                (evento_id, usuario_id)
            )
            if cursor.fetchone():
                conexion.rollback()
                return {"status": "warning", "message": "Ya te encuentras registrado en este evento."}
                
            # 4. Insertar inscripción
            cursor.execute(
                "INSERT INTO inscripciones (evento_id, usuario_id) VALUES (%s, %s);",
                (evento_id, usuario_id)
            )
            
        conexion.commit()
        return {"status": "success", "message": "🎉 ¡Inscripción realizada con éxito! Tu cupo ha sido reservado."}
        
    except Exception as e:
        conexion.rollback()
        return {"status": "error", "message": f"Falla en base de datos: {str(e)}"}
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


def obtener_inscritos_por_evento(evento_id):
    """Devuelve la lista de usuarios inscritos en un evento específico."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT u.id, u.nombre, u.cedula, u.correo, u.rol, i.fecha_inscripcion
                FROM inscripciones i
                JOIN usuarios u ON i.usuario_id = u.id
                WHERE i.evento_id = %s
                ORDER BY i.fecha_inscripcion ASC;
            """, (evento_id,))
            return cursor.fetchall()
    finally:
        conexion.close()