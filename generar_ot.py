# -*- coding: utf-8 -*-
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

NEGRO = colors.black
GRIS_CLARO = colors.HexColor("#f2f2f2")
GRIS_LINEA = colors.HexColor("#999999")
BLANCO = colors.white

W, H = letter

LM = 15 * mm
RM = 15 * mm
TM = 12 * mm
BM = 15 * mm
TW = W - LM - RM

BASE = os.path.dirname(os.path.abspath(__file__))

LOGO_PATH = os.path.join(BASE, "static", "logo_eshen.jpg")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(BASE, "logo_eshen.jpg")


def ps(name, font="Helvetica", size=8, leading=10, color=NEGRO, align=TA_LEFT):
    return ParagraphStyle(
        name,
        fontName=font,
        fontSize=size,
        leading=leading,
        textColor=color,
        alignment=align
    )


styles = {
    "n": ps("n"),
    "b": ps("b", font="Helvetica-Bold"),
    "titulo": ps("titulo", font="Helvetica-Bold", size=15, leading=18, align=TA_CENTER),
    "sub": ps("sub", font="Helvetica", size=8, leading=10, align=TA_CENTER),
    "h": ps("h", font="Helvetica-Bold", size=8, leading=10, align=TA_CENTER),
    "c": ps("c", size=8, leading=10, align=TA_CENTER),
    "cb": ps("cb", font="Helvetica-Bold", size=8, leading=10, align=TA_CENTER),
    "firma": ps("firma", font="Helvetica-Bold", size=8, leading=12, align=TA_CENTER),
}


def p(text, style="n"):
    if text is None:
        text = ""
    return Paragraph(str(text).replace("\n", "<br/>"), styles[style])


def generar_ot_pdf(data, out_path):
    story = []

    # =========================
    # HEADER BAJO CONSUMO
    # =========================

    try:
        from reportlab.platypus import Image
        logo = Image(LOGO_PATH, width=18 * mm, height=18 * mm)
    except Exception:
        logo = ""

    header_text = Table([
        [p("ORDEN DE TRABAJO", "titulo")],
        [p("CONTROL DE MANTENIMIENTO / SERVICIO", "sub")]
    ], colWidths=[TW - 25 * mm])

    header_text.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    header = Table([[header_text, logo]], colWidths=[TW - 25 * mm, 25 * mm])
    header.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),
        ("LINEBELOW", (0, 0), (-1, -1), 0.8, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(header)
    story.append(Spacer(1, 5))

    folio = data.get("folio", "")
    fecha_hora = data.get("fecha_hora", "")
    solicitante = data.get("solicitante", "")
    asignado = data.get("asignado_nombre", "")
    area = data.get("area", "")
    codigo_equipo = data.get("codigo_equipo", "")
    estado = data.get("estado", "")

    # =========================
    # DATOS GENERALES
    # =========================

    datos = Table([
        [p("FOLIO", "h"), p("FECHA / HORA", "h"), p("ESTADO", "h")],
        [p(folio, "cb"), p(fecha_hora, "c"), p(estado.upper(), "cb")],

        [p("SOLICITANTE", "h"), p("ASIGNADO A", "h"), p("ÁREA", "h")],
        [p(solicitante, "c"), p(asignado, "c"), p(area, "c")],

        [p("CÓDIGO / EQUIPO", "h"), p("", "h"), p("", "h")],
        [p(codigo_equipo, "c"), "", ""],
    ], colWidths=[TW / 3, TW / 3, TW / 3])

    datos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CLARO),
        ("BACKGROUND", (0, 2), (-1, 2), GRIS_CLARO),
        ("BACKGROUND", (0, 4), (-1, 4), GRIS_CLARO),

        ("SPAN", (0, 5), (-1, 5)),

        ("GRID", (0, 0), (-1, -1), 0.3, GRIS_LINEA),
        ("BOX", (0, 0), (-1, -1), 0.7, NEGRO),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    story.append(datos)
    story.append(Spacer(1, 6))

    # =========================
    # DESCRIPCIONES
    # =========================

    descripcion_servicio = data.get("descripcion_servicio", "")
    trabajos_efectuados = data.get("trabajos_efectuados", "")
    observaciones = data.get("observaciones", "")

    bloques = Table([
        [p("DESCRIPCIÓN DEL SERVICIO", "h")],
        [p(descripcion_servicio, "n")],

        [p("TRABAJOS EFECTUADOS", "h")],
        [p(trabajos_efectuados, "n")],

        [p("OBSERVACIONES", "h")],
        [p(observaciones, "n")],
    ], colWidths=[TW])

    bloques.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), GRIS_CLARO),
        ("BACKGROUND", (0, 2), (0, 2), GRIS_CLARO),
        ("BACKGROUND", (0, 4), (0, 4), GRIS_CLARO),

        ("GRID", (0, 0), (-1, -1), 0.3, GRIS_LINEA),
        ("BOX", (0, 0), (-1, -1), 0.7, NEGRO),

        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(bloques)
    story.append(Spacer(1, 6))

    # =========================
    # REFACCIONES
    # =========================

    refacciones = data.get("refacciones", [])

    rows = [[
        p("CANT.", "h"),
        p("UNIDAD", "h"),
        p("DESCRIPCIÓN", "h"),
        p("SERIE / NO. PARTE", "h"),
        p("TIPO", "h")
    ]]

    if refacciones:
        for ref in refacciones:
            rows.append([
                p(ref.get("cantidad", ""), "c"),
                p(ref.get("unidad", ""), "c"),
                p(ref.get("descripcion", ""), "n"),
                p(ref.get("serie_no_parte", ""), "c"),
                p(ref.get("tipo", ""), "c"),
            ])
    else:
        rows.append([
            p("", "c"),
            p("", "c"),
            p("Sin refacciones registradas", "c"),
            p("", "c"),
            p("", "c"),
        ])

    refs_tbl = Table(
        rows,
        colWidths=[
            16 * mm,
            22 * mm,
            TW - 16 * mm - 22 * mm - 42 * mm - 25 * mm,
            42 * mm,
            25 * mm
        ]
    )

    refs_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CLARO),

        ("GRID", (0, 0), (-1, -1), 0.3, GRIS_LINEA),
        ("BOX", (0, 0), (-1, -1), 0.7, NEGRO),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    story.append(refs_tbl)
    story.append(Spacer(1, 22))

    # =========================
    # FIRMAS
    # =========================

    firmas = Table([
        ["", ""],
        [p("REALIZÓ", "firma"), p("RECIBIÓ / AUTORIZÓ", "firma")]
    ], colWidths=[TW / 2, TW / 2])

    firmas.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.8, NEGRO),
        ("LINEABOVE", (1, 1), (1, 1), 0.8, NEGRO),
        ("TOPPADDING", (0, 0), (-1, 0), 35),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    story.append(firmas)

    # =========================
    # BORDE EXTERIOR LIGERO
    # =========================

    def on_page(canv, doc):
        canv.saveState()
        canv.setStrokeColor(GRIS_LINEA)
        canv.setLineWidth(0.5)
        canv.rect(LM - 3, BM - 3, W - LM - RM + 6, H - TM - BM + 6)
        canv.restoreState()

    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=LM,
        rightMargin=RM,
        topMargin=TM,
        bottomMargin=BM
    )

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
