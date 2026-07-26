# core/validators.py
from core.security import clean_input_strict
from repositories.usuario_repository import es_cedula_autorizada_nomina
import re 

def validar_cedula_format(cedula):
    """
    Valida que la cédula tenga un formato venezolano válido (Ej: V-12345678 o E-87654321).
    """
    cedula_limpia = clean_input_strict(cedula).upper()
    patron = r'^(V|E|J|G)-\d{5,9}$'
    return bool(re.match(patron, cedula_limpia)) if 're' in globals() else True

def puede_editar_propuesta(estado_solicitud):
    """
    REGLA DE NEGOCIO: Estudiantes y profesores SÓLO pueden editar o eliminar
    sus propuestas/solicitudes mientras estén en estado 'pendiente'.
    Si ha sido 'aceptado', 'aprobado' o 'rechazado', se bloquea la modificación.
    """
    if not estado_solicitud:
        return False
    return str(estado_solicitud).lower() == 'pendiente'

def validar_campos_evento(datos):
    """
    Valida que los datos mínimos para la creación/edición de un evento estén presentes.
    """
    campos_requeridos = ['titulo', 'tipo_actividad', 'fecha', 'hora_inicio', 'hora_fin', 'espacio_id']
    errores = []
    
    for campo in campos_requeridos:
        if not datos.get(campo):
            errores.append(f"El campo '{campo}' es obligatorio.")
            
    if datos.get('hora_inicio') and datos.get('hora_fin'):
        if datos['hora_inicio'] >= datos['hora_fin']:
            errores.append("La hora de inicio debe ser anterior a la hora de finalización.")
            
    return errores


def validar_cedula_institucional(cedula, rol):
    """
    REGLA DE NEGOCIO: Verifica si la cédula pertenece a la nómina autorizada 
    para registrarse con rol 'ponente' o 'administrativo'.
    Si el formato es correcto y la cédula está en la nómina (o en la lista blanca), permite el registro.
    """
    if not validar_cedula_format(cedula):
        return False
        
    cedula_limpia = clean_input_strict(cedula).upper()
    rol_limpio = str(rol).lower().strip()
    
    # Si el rol es estudiante, no requiere validación de nómina
    if rol_limpio == 'estudiante':
        return True
        
    # Retorna True si la cédula está autorizada en la nómina
    return es_cedula_autorizada_nomina(cedula, rol_limpio)