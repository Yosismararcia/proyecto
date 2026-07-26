import pymysql
from database import obtener_conexion
from core.security import clean_input_strict


def obtener_usuario_por_correo(correo):
    """Busca un usuario por su correo electrónico institucional."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE correo = %s;", (correo,))
            return cursor.fetchone()
    finally:
        conexion.close()


def obtener_usuario_por_cedula_y_correo(cedula, correo):
    """Busca coincidencia exacta para el proceso de recuperación de acceso."""
    cedula_limpia = clean_input_strict(cedula)
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE cedula = %s AND correo = %s;",
                (cedula_limpia, correo)
            )
            return cursor.fetchone()
    finally:
        conexion.close()


def crear_usuario(nombre, cedula, correo, password_hashed, rol):
    """Registra un nuevo usuario en el sistema."""
    nombre_limpio = clean_input_strict(nombre)
    cedula_limpia = clean_input_strict(cedula)
    
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("""
                INSERT INTO usuarios (nombre, cedula, correo, contrasena_hash, rol)
                VALUES (%s, %s, %s, %s, %s);
            """, (nombre_limpio, cedula_limpia, correo, password_hashed, rol))
        conexion.commit()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conexion.close()


def actualizar_contrasena_por_id(usuario_id, nueva_password_hashed):
    """Modifica de forma segura el hash de la contraseña de un usuario."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE usuarios SET contrasena_hash = %s WHERE id = %s;",
                (nueva_password_hashed, usuario_id)
            )
        conexion.commit()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conexion.close()


def obtener_todos_los_usuarios():
    """Obtiene la lista de todos los usuarios registrados para el administrador."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT id, nombre, cedula, correo, rol FROM usuarios ORDER BY nombre ASC;")
            return cursor.fetchall()
    finally:
        conexion.close()

def es_cedula_autorizada_nomina(cedula: str, rol: str) -> bool:
    """
    Verifica si una cédula existe en la tabla de personal autorizado de MariaDB.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor(pymysql.cursors.DictCursor) as cursor:
            # según el nombre real que le diste en tu esquema.
            rol_limpio = rol.lower().strip()
            cursor.execute("""
                SELECT 1 FROM personal_autorizado 
                WHERE UPPER(cedula) = %s 
                  AND (
                      LOWER(rol_permitido) = %s 
                      OR (LOWER(rol_permitido) = 'profesor' AND %s IN ('ponente', 'profesor'))
                  );
            """, (cedula.upper(), rol_limpio, rol_limpio)) #con esto comparo los roles y  si es ponente o profesor se aceptan
            
            resultado = cursor.fetchone()
            return bool(resultado)
    except Exception as e:
        print(f"⚠️ Error al verificar personal autorizado: {e}")
        return False
    finally:
        conexion.close()        