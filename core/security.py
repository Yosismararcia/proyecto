# core/security.py
import re
import html
import uuid
from functools import wraps
from flask import session, flash, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer

def obtener_serializer(secret_key):
    return URLSafeTimedSerializer(secret_key)

def hash_password(password):
    """Crea un hash seguro de la contraseña."""
    return generate_password_hash(password)

def verificar_password(password_hash, password):
    """Verifica si la contraseña coincide con el hash almacenado."""
    return check_password_hash(password_hash, password)

def generar_codigo_certificado():
    """Genera un token/código único para validación de certificados digitales."""
    return f"FACYT-CERT-{uuid.uuid4().hex[:10].upper()}"

def clean_input_strict(texto):
    """
    Bloquea y remueve símbolos peligrosos de inputs estrictos.
    Permite caracteres alfanuméricos, espacios, guiones y acentos.
    """
    if not texto:
        return ""
    limpio = re.sub(r'[^\w\s\-\u00C0-\u017F]', '', str(texto))
    return limpio.strip()

def clean_html_entities(texto):
    """
    Escapa código HTML para prevenir ataques XSS en descripciones largas.
    """
    if not texto:
        return ""
    return html.escape(str(texto).strip())

def requerir_rol(roles_permitidos):
    """
    Middleware RBAC para restringir el acceso a rutas según el rol del usuario.
    """
    def decorador(f):
        @wraps(f)
        def funcion_decorada(*args, **kwargs):
            if 'usuario_id' not in session:
                flash("🔒 Por favor, inicia sesión para acceder.", "warning")
                return redirect(url_for('login'))
            
            rol_actual = session.get('usuario_rol') or session.get('rol')
            if not rol_actual or rol_actual not in roles_permitidos:
                flash("🛑 No posees los permisos requeridos para acceder a esta función.", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return funcion_decorada
    return decorador