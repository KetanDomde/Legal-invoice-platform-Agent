from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_dummy_invoice(filename="test_invoice.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    # Header layout
    header_data = [
        [Paragraph("<b>LexCorp Legal LLP</b><br/><font size=9 color=gray>450 Legal Avenue, Suite 1200<br/>New York, NY 10001</font>", styles['Normal']),
         Paragraph("<b>INVOICE</b><br/><b>Invoice Number:</b> INV-2026-089<br/><b>Invoice Date:</b> August 4, 2026", styles['Normal'])]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    story.append(header_table)
    story.append(Spacer(1, 20))

    # Client & Matter info
    client_text = "<b>CLIENT:</b><br/>Acme Corporation<br/>Attn: Legal Department<br/>100 Innovation Way, Silicon Valley, CA 94025"
    matter_text = "<b>MATTER DESCRIPTION:</b><br/>Series B Preferred Stock Financing and Corporate Restructuring"
    story.append(Paragraph(client_text, styles['Normal']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(matter_text, styles['Normal']))
    story.append(Spacer(1, 15))

    # Line items table
    table_data = [
        ["Date", "Timekeeper & Description", "Hours", "Rate", "Total"],
        ["08/01/2026", "Sarah Jenkins (Partner)\nReviewed draft term sheet.", "2.5", "$650.00", "$1,625.00"],
        ["08/02/2026", "Michael Ross (Associate)\nDrafted definitive agreements.", "6.0", "$400.00", "$2,400.00"],
        ["08/03/2026", "Sarah Jenkins (Partner)\nNegotiated provisions.", "1.5", "$650.00", "$975.00"],
    ]
    
    t = Table(table_data, colWidths=[70, 250, 50, 70, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))

    # Totals
    totals_data = [
        ["Subtotal:", "$5,000.00"],
        ["Disbursements:", "$150.00"],
        ["Total Amount Due:", "$5,150.00"]
    ]
    t_tot = Table(totals_data, colWidths=[400, 140])
    t_tot.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(t_tot)

    doc.build(story)
    print(f"Generated pure Python PDF: {filename}")

if __name__ == "__main__":
    generate_dummy_invoice()