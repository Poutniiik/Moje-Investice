# Reporting service
from fpdf import FPDF
from datetime import datetime

def clean_text(text):
    replacements = {
        'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e', 'í': 'i', 'ň': 'n', 'ó': 'o', 'ř': 'r', 'š': 's', 'ť': 't', 'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
        'Á': 'A', 'Č': 'C', 'Ď': 'D', 'É': 'E', 'Ě': 'E', 'Í': 'I', 'Ň': 'N', 'Ó': 'O', 'Ř': 'R', 'Š': 'S', 'Ť': 'T', 'Ú': 'U', 'Ů': 'U', 'Ý': 'Y', 'Ž': 'Z'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def vytvor_pdf_report(user, total_czk, cash_usd, profit_czk, data_list):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(f"INVESTICNI REPORT: {user}"), ln=True, align='C')

    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "SOUHRN", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, clean_text(f"Celkove jmeni: {total_czk:,.0f} CZK"), ln=True)
    pdf.cell(0, 10, clean_text(f"Hotovost: {cash_usd:,.0f} USD"), ln=True)
    pdf.cell(0, 10, clean_text(f"Celkovy zisk/ztrata: {profit_czk:,.0f} CZK"), ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(30, 10, "Ticker", 1, 0, 'C', 1)
    pdf.cell(30, 10, "Kusy", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Cena (Avg)", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Hodnota (USD)", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Zisk (USD)", 1, 1, 'C', 1)

    pdf.set_font("Arial", size=10)
    for item in data_list:
        pdf.cell(30, 10, str(item['Ticker']), 1)
        pdf.cell(30, 10, f"{item['Kusy']:.2f}", 1)
        pdf.cell(40, 10, f"{item['Průměr']:.2f}", 1)
        pdf.cell(40, 10, f"{item['HodnotaUSD']:.0f}", 1)
        pdf.cell(40, 10, f"{item['Zisk']:.0f}", 1, 1)

    return pdf.output(dest='S').encode('latin-1', 'replace')
