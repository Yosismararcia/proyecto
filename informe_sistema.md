# Informe del Sistema SGJC - FaCyT

## 1. Introducción

Este documento describe el funcionamiento del sistema SGJC - FaCyT, una plataforma web construida en Flask que gestiona eventos académicos y científicos, usuarios, solicitudes de espacios, propuestas estudiantiles, voluntariado, repositorio de materiales, certificados digitales y evaluaciones.

---

## 2. Objetivo del sistema

El sistema permite a la comunidad universitaria:

- Registrar y autenticar usuarios.
- Solicitar espacios para actividades académicas y culturales.
- Aprobar o rechazar eventos desde un panel administrativo.
- Administrar espacios y materiales asociados.
- Inscribir usuarios en eventos y supervisar la asistencia.
- Gestionar voluntariado ligado a eventos.
- Publicar y descargar materiales en un repositorio de evento.
- Emitir certificados en PDF con verificación por QR.
- Postular y evaluar eventos como jurado/mentor.

---

## 3. Roles y permisos

El sistema distingue varios roles con permisos específicos:

- **Estudiante**: proponer ideas, ver y editar sus propias propuestas, postularse a voluntariado, inscribirse en eventos.
- **Ponente / Profesor**: solicitar eventos, ver inscritos de sus eventos, evaluar eventos y gestionar voluntariado asociado.
- **Administrativo**: aprobar o rechazar eventos y propuestas, administrar espacios, gestionar solicitudes, subir materiales, exportar listas y controlar el panel administrativo.
- **Admin / Administrador**: acceso ampliado a panel y funciones administrativas.

---

## 4. Módulos principales

### 4.1 Autenticación y seguridad

- **Registro**: valida cédula institucional para roles de `ponente`, `profesor` y `administrativo`.
- **Login**: inicia sesión y guarda `usuario_id`, `usuario_nombre`, `usuario_rol` y `rol` en la sesión.
- **Recuperación de acceso**: verifica cédula y correo, luego permite redefinir contraseña.
- **Redefinición de contraseña**: actualiza el hash de la contraseña en la base de datos.

### 4.2 Dashboard e inicio

- Vista inicial para usuarios anónimos y autenticados.
- Muestra eventos disponibles, eventos en cartelera, eventos inscritos y métricas.
- Permite filtrar por fecha.

### 4.3 Solicitud de eventos/espacios

- Los roles autorizados pueden solicitar espacios.
- Verifica campos obligatorios, formato de hora y duplicidad de título.
- Envía solicitudes para revisión administrativa.

### 4.4 Panel administrativo

- Muestra solicitudes totales y propuestas de estudiantes.
- Lista de espacios más solicitados y conteo de estados de eventos.
- Permite cambiar estados de eventos a través de un formulario.
- Incluye opciones de edición, difusión y eliminación de eventos.

### 4.5 Administración de espacios

- Listado de espacios físicos.
- Creación de nuevos espacios.
- Eliminación de espacios existentes.

### 4.6 Inscripciones y asistencia

- Funcionalidad para inscribir usuarios en eventos.
- Evita inscribir en eventos cancelados.
- Visualización de la lista de inscritos con permisos de rol.
- Autorización para ver la lista basada en rol y propiedad del evento.
- Exportación de inscritos a CSV.
- Marcar asistencia desde la interfaz.

### 4.7 Detalle del evento

- Vista completa de un evento.
- Muestra información logística, voluntariado, repositorio y foro.
- Carga y descarga de materiales de repositorio.
- Muestra abstract/resumen y enlaces a documentos relevantes.

### 4.8 Foro de discusión

- Permite publicar mensajes en el foro del evento.
- Muestra discusiones asociadas al evento.

### 4.9 Voluntariado

- Crear tareas de voluntariado asociadas al evento.
- Postularse como voluntario.
- Administrar postulaciones: aprobar/rechazar y controlar cupos.

### 4.10 Propuestas estudiantiles

- Estudiantes envían propuestas de eventos o actividades.
- Pueden editar propuestas en estado pendiente.
- Administrativos pueden aprobar, agendar o rechazar propuestas.
- También pueden eliminar propuestas.

### 4.11 Difusión de evento

- Genera una plantilla para difundir la información del evento.
- Muestra datos formateados para compartir.

### 4.12 Evaluación de eventos

- Jurados, mentores y evaluadores califican eventos.
- Registra puntuaciones y observaciones.
- Presenta formulario de evaluación para usuarios autorizados.

### 4.13 Certificados digitales

- Generación de PDF de certificado para asistentes con asistencia confirmada.
- Crea un código QR que valida el certificado.
- Vista de validación de certificado online.

### 4.14 Repositorio de materiales

- Permite subir archivos para eventos.
- Guarda archivos en `static/uploads/repositorio`.
- Solo usuarios autorizados pueden subir materiales.
- Permite descargar materiales desde la vista del evento.

---

## 5. Estructura técnica

### 5.1 Backend

- `app.py`: controla todas las rutas y lógica de la aplicación.
- `database.py`: contiene funciones que acceden directamente a MySQL.
- `repositories/evento_repository.py`: encapsula consultas y operaciones importantes de eventos.
- `repositories/usuario_repository.py`: gestiona usuarios.
- `repositories/inscripcion_repository.py`: gestiona inscripciones.

### 5.2 Frontend y plantillas

- `templates/base.html`: estilos globales y estilos responsivos.
- `templates/index.html`: página principal y dashboard de eventos.
- `templates/detalle_evento.html`: vista de detalle de evento.
- `templates/admin.html`: panel administrativo.
- `templates/admin_espacios.html`: gestión de espacios.
- `templates/mis_solicitudes.html`, `templates/mis_propuestas.html`: vistas de usuario.
- `templates/ver_inscritos.html`: lista de inscritos.

### 5.3 Dependencias y utilidades

- `pymysql`: conexión y consultas MySQL.
- `reportlab`: generación de PDF.
- `qrcode`: generación de códigos QR.
- `werkzeug.security`: hash de contraseñas.
- `core.security` y `core.validators`: funciones de seguridad y validación.

---

## 6. Flujo típico de uso

1. Usuario se registra y hace login.
2. Usuario autorizado solicita un espacio para un evento.
3. El área administrativa revisa y cambia el estado del evento.
4. Estudiantes se inscriben o se postulan a tareas de voluntariado.
5. Organizadores consultan inscritos y marcan asistencia.
6. Los asistentes reciben certificados descargables.
7. Se suben materiales a un repositorio asociado al evento.
8. Evaluadores califican el evento.

---

## 7. Buenas prácticas recomendadas

- Mantener roles estrictos y validaciones de sesión antes de cada acción.
- Usar `secure_filename()` al subir archivos.
- Proteger rutas sensibles con `@requerir_rol` o validaciones manuales.
- Limitar el acceso de edición solo a propietarios y administradores.
- Validar y sanitizar entradas de formularios.

---

## 8. Posibles mejoras futuras

- Añadir notificaciones por email.
- Crear API REST separada para un frontend moderno.
- Separar los roles administrativos en permisos más finos.
- Integrar un sistema de comentarios mejorado.
- Añadir un módulo de reportes estadísticos avanzados.
- Implementar paginación en listas largas.

---

## 9. Conclusión

El sistema es una solución completa para gestionar eventos universitarios, desde la propuesta hasta la certificación. Está diseñado con roles diferenciados y cubre la mayoría de necesidades de gestión, seguimiento y publicación de materiales.
