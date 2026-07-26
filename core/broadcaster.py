# core/broadcaster.py
import urllib.parse
import io
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generar_ficha_difusion(evento):
    """
    Genera un bloque formateado en Markdown/Texto enriquecido para la divulgación 
    de eventos aprobados hacia la comunidad universitaria de FaCyT.
    """
    ubicacion = evento.get('enlace_virtual') if evento.get('modalidad') == 'virtual' else evento.get('espacio', 'Por asignar')
    
    plantilla = (
        "📢 *NUEVO EVENTO CIENTÍFICO EN FaCyT* 🔬\n\n"
        "🎓 *Actividad:* {titulo}\n"
        "🏛 *Departamento:* {departamento}\n"
        "📌 *Tipo:* {tipo} ({modalidad})\n"
        "📆 *Fecha:* {fecha}\n"
        "⏰ *Horario:* {hora_inicio} - {hora_fin}\n"
        "🏫 *Lugar / Enlace:* {ubicacion}\n"
        "👤 *Responsable:* {responsable}\n\n"
        "📝 *Descripción:* {descripcion}\n\n"
        "¡Asiste y expande tus conocimientos! _Plataforma SGJC-FaCyT 2026_"
    )
    
    return plantilla.format(
        titulo=evento.get('titulo', 'Sin título').upper(),
        departamento=evento.get('departamento', 'General'),
        tipo=evento.get('tipo_actividad', 'Conferencia'),
        modalidad=evento.get('modalidad', 'presencial').capitalize(),
        fecha=evento.get('fecha', ''),
        hora_inicio=evento.get('hora_inicio', ''),
        hora_fin=evento.get('hora_fin', ''),
        ubicacion=ubicacion,
        responsable=evento.get('responsable', 'Cuerpo Académico'),
        descripcion=evento.get('descripcion', 'Sin descripción adicional.')
    )

def generar_links_compartir(evento):
    """
    Genera URLs directas para reenviar el flyer de invitación hacia Telegram y WhatsApp.
    """
    texto_difusion = generar_ficha_difusion(evento)
    texto_encoded = urllib.parse.quote(texto_difusion)
    
    return {
        'telegram': f"https://t.me/share/url?url=&text={texto_encoded}",
        'whatsapp': f"https://api.whatsapp.com/send?text={texto_encoded}"
    }

def generar_pdf_reporte_inscritos(evento, lista_asistentes):
    """
    Genera un archivo PDF con el listado oficial de inscritos y asistencia del evento.
    Devuelve un buffer en memoria io.BytesIO listo para enviar vía Flask (send_file).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, alignment=1)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, leading=14, alignment=1)
    
    # Encabezado
    elements.append(Paragraph("<b>UNIVERSIDAD DE CARABOBO - FaCyT</b>", title_style))
    elements.append(Paragraph("Sistema de Gestión de Jornadas Científicas y Congresos", subtitle_style))
    elements.append(Spacer(1, 15))
    
    # Datos del Evento
    info_evento = f"""
    <b>Evento:</b> {evento.get('titulo')}<br/>
    <b>Departamento:</b> {evento.get('departamento')} | <b>Tipo:</b> {evento.get('tipo_actividad')}<br/>
    <b>Fecha:</b> {evento.get('fecha')} | <b>Horario:</b> {evento.get('hora_inicio')} - {evento.get('hora_fin')}<br/>
    <b>Espacio:</b> {evento.get('espacio')}
    """
    elements.append(Paragraph(info_evento, styles['Normal']))
    elements.append(Spacer(1, 15))
    
    # Tabla de Asistentes
    data_tabla = [["#", "Cédula", "Nombre y Apellido", "Correo Electrónico", "Rol", "Asistencia"]]
    for idx, usr in enumerate(lista_asistentes, start=1):
        asistencia = "Presente" if usr.get('asistio') else "Registrado"
        data_tabla.append([
            str(idx),
            usr.get('cedula', ''),
            usr.get('nombre', ''),
            usr.get('correo', ''),
            usr.get('rol', '').capitalize(),
            asistencia
        ])
        
    t = Table(data_tabla, colWidths=[25, 75, 160, 180, 65, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generar_pdf_certificado(nombre_usuario, cedula_usuario, titulo_evento, rol_participacion, codigo_verificacion):
    """
    Genera un Certificado Digital PDF con Código QR de Verificación (Módulo Cero Papel).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CertTitle', parent=styles['Heading1'], fontSize=22, leading=26, alignment=1, textColor=colors.HexColor('#1a365d'))
    sub_style = ParagraphStyle('CertSub', parent=styles['Normal'], fontSize=12, leading=16, alignment=1)
    name_style = ParagraphStyle('CertName', parent=styles['Heading2'], fontSize=18, leading=22, alignment=1, textColor=colors.HexColor('#0d6efd'))
    
    elements.append(Paragraph("<b>FACULTAD EXPERIMENTAL DE CIENCIAS Y TECNOLOGÍA</b>", title_style))
    elements.append(Paragraph("Otorga la presente constancia digital a:", sub_style))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph(f"<b>{nombre_usuario.upper()}</b>", name_style))
    elements.append(Paragraph(f"C.I.: {cedula_usuario}", sub_style))
    elements.append(Spacer(1, 15))
    
    desc_cert = f"Por su valiosa participación en calidad de <b>{rol_participacion.upper()}</b> en la actividad científica:<br/><br/><b>«{titulo_evento}»</b>"
    elements.append(Paragraph(desc_cert, sub_style))
    elements.append(Spacer(1, 20))
    
    # Generar QR en Memoria
    qr_img = qrcode.make(f"https://sgjc-facyt.uc.edu.ve/validar_certificado/{codigo_verificacion}")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, kind='PNG')
    qr_buffer.seek(0)
    
    img_qr = Image(qr_buffer, width=80, height=80)
    
    data_footer = [
        [Paragraph(f"<font size=8>Código de Verificación:<br/><b>{codigo_verificacion}</b><br/>Documento firmado digitalmente por FaCyT-UC</font>", styles['Normal']), img_qr]
    ]
    t_footer = Table(data_footer, colWidths=[400, 100])
    t_footer.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    
    elements.append(t_footer)
    doc.build(elements)
    buffer.seek(0)
    return buffer