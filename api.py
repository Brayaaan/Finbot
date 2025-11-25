from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import os
import uuid
import re
from urllib.parse import unquote
import io
import traceback

# === ZMIANY NA OBSŁUGĘ POLSKICH ZNAKÓW ===
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# ==========================================

app = FastAPI(
    title="FinBot API (Rachunki Freelancerskie)",
    description="API do generowania Rachunków do Umowy PDF - wersja Hack Heroes",
    version="2.3.1"
)

# === KONFIGURACJA CZCIONKI DLA POLSKICH ZNAKÓW ===
try:
    # ⚠️ Wymagane: Pobierz plik 'DejaVuSans.ttf' i umieść go w tym samym katalogu co api.py
    # ZALECENIE: Stwórz podfolder 'fonts' i zmień ścieżkę na 'fonts/DejaVuSans.ttf'
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))
    POLISH_FONT_NAME = 'DejaVuSans'
    POLISH_FONT_BOLD = 'DejaVuSans-Bold'
    print("✅ ReportLab: Zarejestrowano czcionki DejaVuSans i DejaVuSans-Bold (PL support)")
except Exception:
    POLISH_FONT_NAME = 'Helvetica'
    POLISH_FONT_BOLD = 'Helvetica-Bold'
    print("⚠️ ReportLab: NIE ZNALEZIONO plików TTF dla DejaVu. Użyto domyślnej (BRAK PL support!).")
# =================================================

# POPRAWIONE CORS - pozwól na metodę OPTIONS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Przechowuj dane faktur w pamięci
invoice_store = {}

# Folder do przechowywania backupów - TYLKO PDF
BACKUP_DIR = os.path.join(os.getcwd(), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)
print(f"📁 Backup folder: {BACKUP_DIR}")

class InvoiceRequest(BaseModel):
    system_instruction: str
    invoice_data: dict

class PDFGenerator:
    @staticmethod
    def create_invoice_pdf(invoice_data: dict) -> bytes:
        """Tworzy PDF RACHUNKU z danych JSON - POPRAWIONA CZCIONKA"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            
            styles = getSampleStyleSheet()
            # Użyj nowej czcionki dla stylów
            styles['Normal'].fontName = POLISH_FONT_NAME
            styles['Normal'].fontSize = 10
            styles['Heading1'].fontName = POLISH_FONT_BOLD
            styles['Heading1'].fontSize = 16
            
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,
                fontName=POLISH_FONT_BOLD # Użycie PL czcionki
            )
            
            # NAGŁÓWEK DOKUMENTU
            title = Paragraph(f"RACHUNEK DO UMOWY {invoice_data.get('numer_faktury', 'BRAK')}", title_style)
            elements.append(title)
            
            # Dane sprzedawcy i nabywca
            sprzedawca = invoice_data.get('sprzedawca', {})
            nabywca = invoice_data.get('nabywca', {})
            
            seller_buyer_data = [
                ['SPRZEDAWCA (WYKONAWCA):', 'NABYWCA (ZLECENIODAWCA):'],
                [sprzedawca.get('nazwa', 'BRAK DANYCH'), nabywca.get('nazwa', 'BRAK DANYCH')],
                [f"NIP: {sprzedawca.get('nip', 'BRAK')}", f"NIP: {nabywca.get('nip', 'BRAK')}"],
                [sprzedawca.get('adres', 'BRAK'), nabywca.get('adres', 'BRAK')],
                [f"Konto: {sprzedawca.get('konto_bankowe', 'BRAK')}", ""]
            ]
            
            seller_buyer_table = Table(seller_buyer_data, colWidths=[250, 250])
            seller_buyer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), POLISH_FONT_BOLD), # Zmieniono
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), POLISH_FONT_NAME), # Zmieniono
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            elements.append(seller_buyer_table)
            elements.append(Spacer(1, 20))
            
            # Dane rachunku
            invoice_info_data = [
                ['Data wystawienia:', invoice_data.get('data_wystawienia', 'BRAK')],
                ['Data sprzedaży/usługi:', invoice_data.get('data_sprzedazy', 'BRAK')],
                ['Termin płatności:', invoice_data.get('termin_platnosci', 'BRAK')],
                ['Sposób płatności:', invoice_data.get('sposob_platnosci', 'BRAK')]
            ]
            
            invoice_info_table = Table(invoice_info_data, colWidths=[150, 150])
            invoice_info_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), POLISH_FONT_NAME), # Zmieniono
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            elements.append(invoice_info_table)
            elements.append(Spacer(1, 20))
            
            # Pozycje rachunku
            table_data = [['LP', 'NAZWA USŁUGI', 'ILOŚĆ', 'J.M.', 'CENA NETTO', 'WARTOŚĆ NETTO', 'VAT', 'KWOTA VAT', 'WARTOŚĆ BRUTTO']]
            
            pozycje = invoice_data.get('pozycje', [])
            for i, item in enumerate(pozycje, 1):
                table_data.append([
                    str(i),
                    item.get('nazwa', 'BRAK'),
                    str(item.get('ilosc', 0)),
                    item.get('jednostka', 'szt.'),
                    f"{float(item.get('cena_netto', 0)):.2f} zł",
                    f"{float(item.get('wartosc_netto', 0)):.2f} zł",
                    f"{float(item.get('stawka_vat', 0))}%",
                    f"{float(item.get('kwota_vat', 0)):.2f} zł",
                    f"{float(item.get('wartosc_brutto', 0)):.2f} zł"
                ])
            
            # Sumy
            table_data.append(['', '', '', '', 'RAZEM:', 
                              f"{float(invoice_data.get('suma_netto', 0)):.2f} zł",
                              '',
                              f"{float(invoice_data.get('suma_vat', 0)):.2f} zł",
                              f"{float(invoice_data.get('suma_brutto', 0)):.2f} zł"])
            
            items_table = Table(table_data, colWidths=[30, 150, 40, 40, 60, 70, 40, 60, 70])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), POLISH_FONT_BOLD), # Zmieniono
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('FONTNAME', (0, 1), (-1, -2), POLISH_FONT_NAME), # Zmieniono
                ('FONTSIZE', (0, 1), (-1, -2), 8),
                ('ALIGN', (2, 1), (8, -2), 'RIGHT'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), POLISH_FONT_BOLD), # Zmieniono
                ('FONTSIZE', (0, -1), (-1, -1), 9),
                ('ALIGN', (5, -1), (8, -1), 'RIGHT'),
            ]))
            
            elements.append(items_table)
            elements.append(Spacer(1, 30))
            
            # Uwagi z metadata
            metadata = invoice_data.get('metadata', {})
            uwagi = metadata.get('uwagi', [])
            if uwagi:
                # UWAGA: Użycie <br/> wymaga Paragraph, styles["Normal"] używa POLISH_FONT_NAME
                uwagi_text = "<b>Uwagi / Informacje Dodatkowe:</b><br/>" + "<br/>".join([f"• {uwaga}" for uwaga in uwagi])
                uwagi_paragraph = Paragraph(uwagi_text, styles["Normal"])
                elements.append(uwagi_paragraph)
                elements.append(Spacer(1, 15))
            
            # Podsumowanie
            suma_brutto = float(invoice_data.get('suma_brutto', 0))
            suma_netto = float(invoice_data.get('suma_netto', 0))
            suma_vat = float(invoice_data.get('suma_vat', 0))
            
            # UWAGA: Użycie <br/> wymaga Paragraph
            summary_text = f"""
            <b>KWOTA RACHUNKU (BRUTTO): {suma_brutto:.2f} zł</b><br/>
            <i>W tym: Netto: {suma_netto:.2f} zł, VAT: {suma_vat:.2f} zł</i>
            """
            summary = Paragraph(summary_text, styles["Normal"])
            elements.append(summary)
            
            # Generuj PDF
            doc.build(elements)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            return pdf_bytes
            
        except Exception as e:
            print(f"❌ Błąd przy generowaniu PDF: {e}")
            traceback.print_exc()
            raise

pdf_generator = PDFGenerator()

# FUNKCJE BACKUP (ZACHOWANA)
def sanitize_filename(filename):
    """Usuwa niebezpieczne znaki z nazw plików"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'_+', '_', filename)
    filename = filename.strip('_')
    return filename

def create_backup(invoice_data, pdf_bytes):
    """Tworzy automatyczny backup faktury - TYLKO PDF (ZACHOWANY)"""
    try:
        invoice_number = invoice_data.get('numer_faktury', 'unknown')
        
        # Sanityzuj numer faktury
        safe_invoice_number = sanitize_filename(invoice_number)
        
        # Unikalny ID i timestamp
        backup_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # TYLKO PDF - NIE TWORZYMY JSON
        pdf_filename = f"{timestamp}_{backup_id}_{safe_invoice_number}.pdf"
        pdf_path = os.path.join(BACKUP_DIR, pdf_filename)
        
        print(f"💾 Zapisuję backup PDF: {pdf_path}")
        
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✅ Backup utworzony: {invoice_number} (ID: {backup_id})")
        
        return {
            "backup_id": backup_id,
            "pdf_file": pdf_filename
        }
        
    except Exception as e:
        print(f"❌ Błąd tworzenia backupu: {e}")
        traceback.print_exc()
        return None

# --- NOWA FUNKCJA DO OBLICZEŃ PODSUMOWUJĄCYCH DLA DASHBOARDU ---
def calculate_financial_summary():
    """Oblicza sumy finansowe i przygotowuje listę Ostatnio Wygenerowanych Rachunków."""
    
    # 1. Agregacja danych
    total_brutto = 0.0
    total_invoices = len(invoice_store)
    
    # Sortowanie kluczy wg czasu utworzenia
    sorted_keys = sorted(invoice_store.keys(), key=lambda k: invoice_store[k]['created_at'], reverse=True)
    
    for key, value in invoice_store.items():
        # Używamy numeru rachunku jako klucza
        data = value['data']
        total_brutto += float(data.get('suma_brutto', 0))

    # 2. Logika "Ostatnio Wygenerowane Rachunki" (Tylko jeden)
    last_invoice_list = []
    
    if sorted_keys:
        # Zlokalizowanie ostatnio dodanego rachunku
        last_invoice_number = sorted_keys[0]
        last_invoice_data = invoice_store[last_invoice_number]['data']
        
        # Przygotowanie danych w formacie wyświetlanym w tabeli
        last_invoice_list.append({
            "Numer": last_invoice_number,
            "Data": last_invoice_data.get('data_wystawienia', 'BRAK'),
            "Kwota_Brutto": f"{float(last_invoice_data.get('suma_brutto', 0)):.2f} zł",
            "Klient": last_invoice_data.get('nabywca', {}).get('nazwa', 'BRAK'), 
            "Akcja": "Podgląd PDF",
            "download_url": f"/api/invoice/{last_invoice_number}/pdf"
        })

    # 3. Szacunkowa kwota do odłożenia (przykładowa prosta logika - np. 20% brutto)
    suggested_savings = total_brutto * 0.20
    
    # 4. Zwrot danych (Obsługa "0" zamiast "Błąd!")
    return {
        "przychód_brutto": f"{total_brutto:.2f} zł" if total_invoices > 0 else "0.00 zł",
        "sugerowana_kwota_do_odłożenia": f"{suggested_savings:.2f} zł" if total_invoices > 0 else "0.00 zł",
        "liczba_wygenerowanych_rachunków": total_invoices,
        "ostatnie_rachunki": last_invoice_list,
        "status": "OK"
    }

# Handler dla metody OPTIONS (Bez zmian)
@app.options("/api/invoice/generate")
async def options_generate():
    return JSONResponse(content={"message": "OK"})
@app.options("/api/invoice/{invoice_number}/pdf")
async def options_download(invoice_number: str):
    return JSONResponse(content={"message": "OK"})

@app.get("/")
async def root():
    return {"message": "FinBot API działa! - Wersja 2.3.1 RACHUNKI (PL Fix)"}

# --- ZMIANA NAZWY ENDPOINTU Z /api/health NA /api/dashboard ---
@app.get("/api/dashboard")
async def dashboard_summary():
    """Zwraca podsumowanie finansowe dla dashboardu i ostatnio wygenerowany rachunek."""
    pdf_files = []
    if os.path.exists(BACKUP_DIR):
        pdf_files = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.pdf')]
        
    summary = calculate_financial_summary()

    return {
        "status": "healthy",
        "service": "FinBot API (Rachunki)",
        "timestamp": datetime.now().isoformat(),
        "backups_count": len(pdf_files),
        "version": "2.3.1 - RACHUNEK PL Fix (Dashboard Fix)",
        "dashboard_data": summary
    }

@app.post("/api/invoice/generate")
async def generate_invoice(invoice_request: InvoiceRequest):
    """Generuje Rachunek PDF z danych formularza"""
    try:
        print(f"📨 Otrzymano żądanie generowania rachunku")
        
        # Używamy danych bezpośrednio z formularza
        invoice_data = invoice_request.invoice_data
        
        # Walidacja i poprawki danych
        invoice_data = validate_and_fix_invoice_data(invoice_data)
        
        # Generuj PDF
        pdf_bytes = pdf_generator.create_invoice_pdf(invoice_data)
        
        # AUTOMATYCZNY BACKUP - ZACHOWANY
        backup_result = create_backup(invoice_data, pdf_bytes)
        
        # Zapisz dane faktury w pamięci (do pobierania PDF)
        invoice_number = invoice_data.get('numer_faktury', 'unknown')
        invoice_store[invoice_number] = {
            'data': invoice_data,
            'pdf_bytes': pdf_bytes,
            # Dodajemy timestamp dla sortowania
            'created_at': datetime.now().isoformat() 
        }
        
        print(f"✅ Rachunek przetworzony: {invoice_number}")
        print(f"📦 Przechowywane rachunki: {list(invoice_store.keys())}")
        
        return {
            "status": "success",
            "message": "Rachunek przetworzony - gotowy do pobrania",
            "invoice_number": invoice_number,
            "totals": {
                "netto": invoice_data.get('suma_netto', 0),
                "vat": invoice_data.get('suma_vat', 0),
                "brutto": invoice_data.get('suma_brutto', 0)
            },
            "items_count": len(invoice_data.get('pozycje', [])),
            "download_url": f"/api/invoice/{invoice_number}/pdf",
            "backup_created": backup_result is not None,
            "backup_id": backup_result['backup_id'] if backup_result else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Błąd przetwarzania rachunku: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Błąd: {str(e)}")

# ZMIENIONY ENDPOINT: Użycie {invoice_number:path} pozwala na ukośniki w numerze rachunku!
@app.get("/api/invoice/{invoice_number:path}/pdf")
async def download_invoice_pdf(invoice_number: str):
    """Generuje i zwraca PDF rachunku do pobrania"""
    try:
        # DECODE URL - to naprawia problem z %2F
        decoded_invoice_number = unquote(invoice_number)
        print(f"📥 Żądanie PDF dla: {invoice_number} (decoded: {decoded_invoice_number})")
        print(f"📋 Dostępne rachunki w store: {list(invoice_store.keys())}")
        
        # Szukaj rachunku po zdecodowanym numerze
        if decoded_invoice_number not in invoice_store:
            # Spróbuj też po zakodowanym (dla kompatybilności)
            if invoice_number not in invoice_store:
                print(f"❌ Rachunek {decoded_invoice_number} nie znaleziony w store!")
                raise HTTPException(status_code=404, detail=f"Rachunek {decoded_invoice_number} nie znaleziony. Najpierw wygeneruj rachunek.")
            else:
                # Użyj zakodowanego numeru
                target_invoice_number = invoice_number
        else:
            # Użyj zdecodowanego numeru
            target_invoice_number = decoded_invoice_number
        
        invoice_data = invoice_store[target_invoice_number]
        pdf_bytes = invoice_data['pdf_bytes']
        
        print(f"✅ Znaleziono rachunek: {target_invoice_number}, rozmiar PDF: {len(pdf_bytes)} bajtów")
        
        # Zwróć PDF jako plik do pobrania
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=rachunek_{sanitize_filename(target_invoice_number)}.pdf",
                "Content-Type": "application/pdf"
            }
        )
        
    except Exception as e:
        print(f"❌ Błąd generowania PDF: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Błąd generowania PDF: {str(e)}")

# --- USUNIĘTO ENDPOINT '/api/backups' ABY ZABLOKOWAĆ WIDOK NA ARCHIWUM ---

# FUNKCJE WALIDACJI Z BOTA TELEGRAM (Bez zmian)
def validate_nip(nip):
    """Waliduje numer NIP zgodnie z polskim prawem"""
    if not nip or not isinstance(nip, str):
        return False
    
    nip = nip.replace(" ", "").replace("-", "")
    
    if len(nip) != 10 or not nip.isdigit():
        return False
    
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    
    try:
        checksum = sum(int(nip[i]) * weights[i] for i in range(9)) % 11
        return checksum == int(nip[9])
    except (ValueError, IndexError):
        return False

def validate_and_fix_invoice_data(invoice_data):
    """Waliduje i naprawia dane rachunku"""
    uwagi = []
    
    # Walidacja NIPów
    for podmiot in ['sprzedawca', 'nabywca']:
        if podmiot in invoice_data:
            nip = invoice_data[podmiot].get('nip', '').replace(" ", "").replace("-", "")
            if nip:
                if not validate_nip(nip):
                    uwagi.append(f"NIP {podmiot}a ({nip}) jest niepoprawny - wymaga weryfikacji")
            else:
                # NOWA UWAGA DLA SPRZEDAWCY (działalność nierejestrowana/osoba fizyczna)
                if podmiot == 'sprzedawca':
                    uwagi.append("Sprzedawca działa jako Osoba Fizyczna/Działalność Nierejestrowana (brak NIP/zwolnienie podmiotowe z VAT)")
    
    # Walidacja dat
    today = datetime.now().strftime('%d.%m.%Y')
    if not invoice_data.get('data_wystawienia'):
        invoice_data['data_wystawienia'] = today
        uwagi.append("Data wystawienia uzupełniona automatycznie")
    
    if not invoice_data.get('data_sprzedazy'):
        invoice_data['data_sprzedazy'] = invoice_data['data_wystawienia']
        uwagi.append("Data sprzedaży/wykonania usługi uzupełniona automatycznie")
    
    if not invoice_data.get('termin_platnosci'):
        try:
            wystawienia = datetime.strptime(invoice_data['data_wystawienia'], '%d.%m.%Y')
        except:
            wystawienia = datetime.now()
        
        termin = wystawienia + timedelta(days=14)
        invoice_data['termin_platnosci'] = termin.strftime('%d.%m.%Y')
        uwagi.append("Termin płatności uzupełniony automatycznie (14 dni)")
    
    # Walidacja pozycji
    for i, pozycja in enumerate(invoice_data.get('pozycje', [])):
        if not pozycja.get('jednostka'):
            nazwa = pozycja.get('nazwa', '').lower()
            if any(slowo in nazwa for slowo in ['usługa', 'consulting', 'konsultacja', 'programowanie']):
                pozycja['jednostka'] = 'usługa'
                uwagi.append(f"Pozycja {i+1}: jednostka uzupełniona jako 'usługa'")
            else:
                pozycja['jednostka'] = 'szt.'
                uwagi.append(f"Pozycja {i+1}: jednostka uzupełniona jako 'szt.'")
        
        # Uproszczenie dla FinBota - jeśli stawka nie jest podana, to 0% (zwolnienie podmiotowe)
        if pozycja.get('stawka_vat') is None:
            pozycja['stawka_vat'] = 0.0 # Domyślnie 0% dla rachunków freelancerskich
            uwagi.append(f"Pozycja {i+1}: stawka VAT uzupełniona jako 0% (Zwolnienie Podmiotowe)")
    
    # Dodaj uwagi do metadata
    if 'metadata' not in invoice_data:
        invoice_data['metadata'] = {}
    
    if 'uwagi' not in invoice_data['metadata']:
        invoice_data['metadata']['uwagi'] = []
    
    invoice_data['metadata']['uwagi'].extend(uwagi)
    invoice_data['metadata']['data_przetworzenia'] = datetime.now().strftime('%Y-%m-%d')
    invoice_data['metadata']['wersja_formatu'] = '2.3.1' # Zmieniona wersja formatu
    
    return invoice_data

if __name__ == "__main__":
    import uvicorn
    print("🚀 FinBot API uruchomione! - Wersja 2.3.1 RACHUNKI (PL Fix)")
    print("📊 Endpointy:")
    print("    POST /api/invoice/generate - Generowanie rachunku")
    print("    GET  /api/invoice/{nr}/pdf - Pobieranie PDF")
    print("    GET  /api/dashboard        - Dashboard Summary (NOWY!)") # NOWA WZMIANKA
    print("🔧 POPRAWKI w 2.3.1:")
    print("    ✅ Dodano obsługę polskich znaków w PDF (wymaga DejaVuSans.ttf).")
    print("    ✅ Użyto czcionki UNICODE dla wszystkich elementów PDF.")
    print("    ✅ Zmieniony typ dokumentu na RACHUNEK DO UMOWY.")
    print("    ✅ Poprawiony routing GET /api/invoice/{numer:path}/pdf - OBSŁUGA UKOŚNIKÓW!")
    print("    ✅ Zablokowano publiczny wgląd w listę backupów.")
    print("    ✅ Dodano endpoint /api/dashboard - Podsumowanie finansowe (0 zamiast błędu).")
    print("    ✅ Sekcja 'Ostatnio wygenerowane' pokazuje tylko OSTATNI rachunek.")
    print(f"💾 Backup folder: {BACKUP_DIR}")
    print("🔍 Sprawdź czy folder istnieje...")
    print(f"    📁 Folder exists: {os.path.exists(BACKUP_DIR)}")
    uvicorn.run(app, host="127.0.0.1", port=8000)