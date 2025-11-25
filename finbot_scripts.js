// Konfiguracja API - taka sama jak w bocie Telegram
const API_CONFIG = {
    baseUrl: 'http://127.0.0.1:8000',
    endpoint: '/api/invoice/generate'
};

// ZMIENIONE: SYSTEM INSTRUCTION - USUNIĘTO SUGEROWANIE FORMATOWANIA CZCIONEK
const SYSTEM_INSTRUCTION = `
Jesteś specjalistą od rachunków i rozliczeń uproszczonych. Na podstawie podanych danych utwórz **Rachunek do Umowy** w formacie JSON, idealny dla młodego freelancera (osoba fizyczna).

OCZEKIWANY FORMAT JSON:
{
    "typ_dokumentu": "Rachunek do Umowy",
    "numer_faktury": "string",
    "data_wystawienia": "DD.MM.RRRR",
    "data_sprzedazy": "DD.MM.RRRR", 
    "termin_platnosci": "DD.MM.RRRR",
    "sprzedawca": {
        "nazwa": "string",
        "nip": "string", 
        "adres": "string",
        "konto_bankowe": "string"
    },
    "nabywca": {
        "nazwa": "string",
        "nip": "string",
        "adres": "string"
    },
    "pozycje": [
        {
            "nazwa": "string",
            "ilosc": number,
            "jednostka": "string",
            "cena_netto": number,
            "stawka_vat": number,
            "wartosc_netto": number,
            "kwota_vat": number,
            "wartosc_brutto": number
        }
    ],
    "suma_netto": number,
    "suma_vat": number,
    "suma_brutto": number,
    "sposob_platnosci": "string",
    "metadata": {
        "data_przetworzenia": "RRRR-MM-DD",
        "wersja_formatu": "1.4",
        "uwagi": ["string"]
    }
}

ZASADY PRZETWARZANIA:
- Obliczaj automatycznie wartości netto, VAT, brutto.
- Format liczb: użyj kropek dziesiętnych, bez "zł" w wartościach.
- Format dat: DD.MM.RRRR w JSON.

Zwróć TYLKO JSON, bez dodatkowego tekstu.
`;

// Walidacja NIP - pozostawiona, ale luźniejsza dla sprzedawcy
function validateNip(nip) {
    if (!nip || typeof nip !== 'string') return false;
    
    nip = nip.replace(/[\s-]/g, '');
    
    if (nip.length !== 10 || !/^\d+$/.test(nip)) return false;
    
    const weights = [6, 5, 7, 2, 3, 4, 5, 6, 7];
    
    try {
        let checksum = 0;
        for (let i = 0; i < 9; i++) {
            checksum += parseInt(nip[i]) * weights[i];
        }
        checksum = checksum % 11;
        
        return checksum === parseInt(nip[9]);
    } catch (error) {
        return false;
    }
}

// Funkcje walidacji NIP
function setupNipValidation() {
    const buyerNipInput = document.getElementById('buyer_nip');
    
    // Walidacja tylko dla Nabywcy (wymagany dla firm)
    [buyerNipInput].forEach(input => {
        input.addEventListener('blur', function() {
            const nip = this.value;
            
            if (validateNip(nip)) {
                document.getElementById('buyerNipError').style.display = 'none';
                document.getElementById('buyerNipSuccess').style.display = 'block';
            } else if (nip.trim() !== '') {
                document.getElementById('buyerNipError').style.display = 'block';
                document.getElementById('buyerNipSuccess').style.display = 'none';
            } else {
                document.getElementById('buyerNipError').style.display = 'none';
                document.getElementById('buyerNipSuccess').style.display = 'none';
            }
        });
    });
}

// Obliczanie sum
function calculateItemTotals() {
    const rows = document.querySelectorAll('#itemsTable tbody tr');
    let totalNetto = 0;
    let totalVat = 0;
    let totalBrutto = 0;
    
    rows.forEach(row => {
        const qty = parseFloat(row.querySelector('.item_qty').value) || 0;
        const price = parseFloat(row.querySelector('.item_price').value) || 0;
        const vatRate = parseFloat(row.querySelector('.item_vat').value) || 0;
        
        const netValue = qty * price;
        const vatAmount = netValue * (vatRate / 100);
        const grossValue = netValue + vatAmount;
        
        row.querySelector('.item_net_value').textContent = netValue.toFixed(2);
        row.querySelector('.item_gross_value').textContent = grossValue.toFixed(2);
        
        totalNetto += netValue;
        totalVat += vatAmount;
        totalBrutto += grossValue;
    });
    
    document.getElementById('totalNetto').textContent = totalNetto.toFixed(2);
    document.getElementById('totalVat').textContent = totalVat.toFixed(2);
    document.getElementById('totalBrutto').textContent = totalBrutto.toFixed(2);
}

// USUNIĘTO FUNKCJĘ checkApiStatus() - jej funkcjonalność przejmuje loadDashboardData()

// Funkcje do pokazywania/ukrywania komunikatów (bez zmian)
function showLoading() {
    hideAllMessages();
    document.getElementById('loadingMessage').style.display = 'block';
}

function showSuccess(apiResult) {
    hideAllMessages();
    
    const successDiv = document.getElementById('successMessage');
    const successDetails = document.getElementById('successDetails');
    const downloadSection = document.getElementById('downloadSection');
    
    // Upewniamy się, że result ma wymagane pola
    const invoiceTotals = apiResult.totals || { brutto: 0 }; 
    const itemsCount = apiResult.items_count || 0;
    const invoiceNumber = apiResult.invoice_number || "BRAK";

    successDetails.innerHTML = `
        Suma: <strong>${invoiceTotals.brutto.toFixed(2)} zł</strong> | 
        Pozycji: <strong>${itemsCount}</strong> |
        Numer: <strong>${invoiceNumber}</strong>
    `;
    
    // Przycisk pobierania PDF
    downloadSection.innerHTML = `
        <button onclick="downloadPDF('${invoiceNumber}')" style="background: #3498db; padding: 10px 20px;">
            📥 Pobierz PDF Rachunku
        </button>
    `;
    
    successDiv.style.display = 'block';
    loadDashboardData(); // Odśwież dashboard po udanym zapisie
}

function showError(message = 'Spróbuj ponownie za chwilę.') {
    hideAllMessages();
    document.getElementById('errorText').textContent = message;
    document.getElementById('errorMessage').style.display = 'block';
}

function hideAllMessages() {
    document.getElementById('loadingMessage').style.display = 'none';
    document.getElementById('successMessage').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';
}

// Funkcja do tworzenia promptu (bez zmian logiki, tylko typ dokumentu)
function createInvoicePrompt(formData) {
    const promptData = {
        typ_dokumentu: "Rachunek do Umowy",
        numer_faktury: formData.number,
        data_wystawienia: formatDate(formData.issue_date),
        data_sprzedazy: formatDate(formData.sale_date),
        termin_platnosci: calculateDueDate(formData.issue_date), // Użycie poprawnej funkcji
        sprzedawca: {
            nazwa: formData.seller.company,
            nip: formData.seller.nip || "Brak (Osoba Fizyczna)",
            adres: `${formData.seller.street}, ${formData.seller.postal} ${formData.seller.city}`,
            konto_bankowe: formData.seller.account
        },
        nabywca: {
            nazwa: formData.buyer.company,
            nip: formData.buyer.nip,
            adres: `${formData.buyer.street}, ${formData.buyer.postal} ${formData.buyer.city}`
        },
        pozycje: formData.items.map(item => {
            const netValue = item.quantity * item.price_net;
            const vatAmount = netValue * (item.vat / 100);
            const grossValue = netValue + vatAmount;
            
            return {
                nazwa: item.name,
                ilosc: item.quantity,
                jednostka: item.unit,
                cena_netto: item.price_net,
                stawka_vat: item.vat,
                wartosc_netto: Math.round(netValue * 100) / 100,
                kwota_vat: Math.round(vatAmount * 100) / 100,
                wartosc_brutto: Math.round(grossValue * 100) / 100
            };
        }),
        suma_netto: Math.round(formData.items.reduce((sum, item) => sum + (item.quantity * item.price_net), 0) * 100) / 100,
        suma_vat: Math.round(formData.items.reduce((sum, item) => sum + (item.quantity * item.price_net * item.vat / 100), 0) * 100) / 100,
        suma_brutto: Math.round(formData.items.reduce((sum, item) => sum + (item.quantity * item.price_net * (1 + item.vat / 100)), 0) * 100) / 100,
        sposob_platnosci: document.getElementById("payment_method").value, // Użyj wartości z DOM
        metadata: {
            data_przetworzenia: new Date().toISOString().split('T')[0],
            wersja_formatu: "1.4",
            uwagi: [formData.notes]
        }
    };

    return {
        system_instruction: SYSTEM_INSTRUCTION,
        invoice_data: promptData
    };
}

// Funkcje pomocnicze do dat
function formatDate(dateString) {
    const date = new Date(dateString);
    // Używamy formatu YYYY-MM-DD do tworzenia obiektu Date, a następnie PL formatu
    return date.toLocaleDateString('pl-PL');
}

// ZMIENIONE: Poprawna funkcja obliczająca termin płatności (+14 dni)
function calculateDueDate(issueDate) {
    // issueDate jest w formacie YYYY-MM-DD z inputu
    const date = new Date(issueDate);
    // Dodajemy 14 dni
    date.setDate(date.getDate() + 14);
    // Zwracamy w formacie PL, jak oczekuje JSON
    return date.toLocaleDateString('pl-PL');
}

// Funkcja do pobierania PDF (bez zmian)
async function downloadPDF(invoiceNumber) {
    try {
        showLoading();
        
        const response = await fetch(`${API_CONFIG.baseUrl}/api/invoice/${encodeURIComponent(invoiceNumber)}/pdf`);
        
        if (response.ok) {
            const pdfBlob = await response.blob();
            
            if (pdfBlob.type === 'application/pdf') {
                const url = window.URL.createObjectURL(pdfBlob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `rachunek_${invoiceNumber}.pdf`;
                
                document.body.appendChild(a);
                a.click();
                
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                hideAllMessages();
            } else {
                // Jeśli serwer zwróci błąd jako JSON/tekst zamiast PDF
                const responseText = await response.text();
                console.error("❌ Błąd serwera (nie PDF):", responseText);
                throw new Error('Otrzymano nieprawidłowy typ pliku lub błąd serwera.');
            }
        } else {
            const errorText = await response.text();
            throw new Error(`Błąd serwera: ${response.status} - ${errorText}`);
        }
    } catch (error) {
        console.error("❌ Błąd pobierania PDF:", error);
        showError('Błąd pobierania PDF: ' + error.message);
    }
}

// ======================================================================
// ZAKTUALIZOWANA FUNKCJA - Ładowanie Danych do Dashboardu
// Odpytuje /api/dashboard, wyświetla kafelki i tylko OSTATNI rachunek
// ======================================================================
async function loadDashboardData() {
    const apiURL = `${API_CONFIG.baseUrl}/api/dashboard`;
    const statusElement = document.getElementById('apiStatus');
    const historyTableBody = document.querySelector('#historyTable tbody');
    
    // Reset kafelków na ładowanie
    document.getElementById('monthlyRevenue').textContent = 'Ładuję...';
    document.getElementById('simulatedTax').textContent = '...';
    document.getElementById('jobsCount').textContent = '...';
    historyTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Ładowanie danych...</td></tr>';
    
    try {
        const response = await fetch(apiURL);
        
        if (!response.ok) {
            statusElement.innerHTML = `❌ <strong>API nie odpowiada</strong> - uruchom api.py na localhost:8000 (Status: ${response.status})`;
            // Ustawienie wartości na 0, jeśli API nie działa
            document.getElementById('monthlyRevenue').textContent = '0.00 zł';
            document.getElementById('simulatedTax').textContent = '0.00 zł';
            document.getElementById('jobsCount').textContent = 0;
            historyTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Błąd ładowania danych.</td></tr>';
            
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const dashboardData = data.dashboard_data;

        // 1. Aktualizacja statusu API
        statusElement.innerHTML = 
            `✅ <strong>API FinBot działa</strong> | Status: ${data.status} | Backupów: ${data.backups_count}`;

        // 2. Aktualizacja kafelków podsumowujących (dane z API, 0 przy braku rachunków)
        document.getElementById('monthlyRevenue').textContent = dashboardData.przychód_brutto;
        document.getElementById('simulatedTax').textContent = dashboardData.sugerowana_kwota_do_odłożenia;
        document.getElementById('jobsCount').textContent = dashboardData.liczba_wygenerowanych_rachunków;
        
        // 3. Aktualizacja sekcji 'Ostatnio Wygenerowane Rachunki'
        historyTableBody.innerHTML = '';
        
        if (dashboardData.ostatnie_rachunki && dashboardData.ostatnie_rachunki.length > 0) {
            // Zwracany jest tylko JEDEN OSTATNI element
            const lastInvoice = dashboardData.ostatnie_rachunki[0]; 
            
            const row = historyTableBody.insertRow();
            row.innerHTML = `
                <td>${lastInvoice.Numer}</td>
                <td>${lastInvoice.Data}</td>
                <td><strong>${lastInvoice.Kwota_Brutto}</strong></td>
                <td>${lastInvoice.Klient}</td>
                <td>
                    <button onclick="downloadPDF('${lastInvoice.Numer}')" style="padding: 5px; background: #3498db; margin: 0;">
                        ${lastInvoice.Akcja}
                    </button>
                </td>
            `;
        } else {
            // Komunikat, gdy nie ma rachunków
            const row = historyTableBody.insertRow();
            row.innerHTML = `<td colspan="5" style="text-align: center;">Nie wygenerowano jeszcze żadnego rachunku.</td>`;
        }
        
    } catch (error) {
        // Logowanie błędu, ale nie zmieniamy już wartości na 'Błąd!', 
        // bo zostały ustawione na '0.00 zł' w sekcji if (!response.ok)
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            console.error("❌ Błąd połączenia z API (NetworkError)");
        } else {
            console.error("❌ Błąd ładowania dashboardu:", error);
        }
        
    }
}


// Dodawanie/usuwanie pozycji rachunku
document.getElementById("addItem").addEventListener("click", function(){
    const tbody = document.querySelector("#itemsTable tbody");
    const row = document.createElement("tr");
    row.innerHTML = `
        <td><input type="text" class="item_name" placeholder="Nazwa usługi/towaru" required></td>
        <td><input type="text" class="item_unit" value="szt." required></td>
        <td><input type="number" class="item_qty" value="1" min="0" step="0.5" required></td>
        <td><input type="number" class="item_price" value="0" min="0" step="0.01" required></td>
        <td><input type="number" class="item_vat" value="0" min="0" max="23" required></td>
        <td><span class="item_net_value">0.00</span> zł</td>
        <td><span class="item_gross_value">0.00</span> zł</td>
        <td><button type="button" class="removeItem">❌</button></td>`;
    tbody.appendChild(row);
    
    addItemEventListeners(row);
    calculateItemTotals();
});

// Obsługa usuwania pozycji (bez zmian)
document.addEventListener("click", function(e){
    if(e.target.classList.contains("removeItem")){
        if(document.querySelectorAll("#itemsTable tbody tr").length > 1) {
            e.target.closest("tr").remove();
            calculateItemTotals();
        } else {
            alert("Rachunek musi mieć przynajmniej jedną pozycję!");
        }
    }
});

// Dodaj event listeners do pól w wierszach (bez zmian)
function addItemEventListeners(row) {
    const inputs = row.querySelectorAll('.item_qty, .item_price, .item_vat');
    inputs.forEach(input => {
        input.addEventListener('input', calculateItemTotals);
    });
}

// Główna obsługa formularza (bez zmian w logice, tylko zmiana komunikatów)
document.getElementById("invoiceForm").addEventListener("submit", async function(e){
    e.preventDefault();
    
    // Walidacja NIP nabywcy przed wysłaniem
    const buyerNip = document.getElementById('buyer_nip').value;
    
    if (buyerNip && !validateNip(buyerNip)) {
        showError('Proszę poprawić niepoprawny numer NIP Nabywcy (Klienta).');
        return;
    }
    
    showLoading();

    const invoice = {
        number: document.getElementById("invoice_number").value,
        issue_date: document.getElementById("issue_date").value,
        sale_date: document.getElementById("sale_date").value,
        place: document.getElementById("place").value,
        seller: {
            company: document.getElementById("seller_company").value,
            nip: document.getElementById("seller_nip").value,
            street: document.getElementById("seller_street").value,
            postal: document.getElementById("seller_postal").value,
            city: document.getElementById("seller_city").value,
            account: document.getElementById("bank_account").value
        },
        buyer: {
            company: document.getElementById("buyer_company").value,
            nip: document.getElementById("buyer_nip").value,
            street: document.getElementById("buyer_street").value,
            postal: document.getElementById("buyer_postal").value,
            city: document.getElementById("buyer_city").value,
        },
        items: [],
        payment_method: document.getElementById("payment_method").value,
        notes: document.getElementById("notes").value
    };

    // Zbierz pozycje z tabeli
    const rows = document.querySelectorAll("#itemsTable tbody tr");
    rows.forEach(r => {
        invoice.items.push({
            name: r.querySelector(".item_name").value,
            unit: r.querySelector(".item_unit").value,
            quantity: parseFloat(r.querySelector(".item_qty").value),
            price_net: parseFloat(r.querySelector(".item_price").value),
            vat: parseFloat(r.querySelector(".item_vat").value)
        });
    });

    try {
        const promptData = createInvoicePrompt(invoice);
        
        const response = await fetch(`${API_CONFIG.baseUrl}/api/invoice/generate`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(promptData)
        });

        if (response.ok) {
            const result = await response.json();
            showSuccess(result);
        } else {
            const errorText = await response.text();
            throw new Error(`Błąd serwera: ${response.status} - ${errorText}`);
        }
        
    } catch (error) {
        console.error("❌ Błąd:", error);
        
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            showError('Brak połączenia z API. Uruchom plik api.py na localhost:8000');
        } else {
            showError(error.message);
        }
    }
});

// Inicjalizacja
document.addEventListener('DOMContentLoaded', function() {
    // Ustawienie aktualnej daty
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('issue_date').value = today;
    document.getElementById('sale_date').value = today;

    document.querySelectorAll('#itemsTable tbody tr').forEach(row => {
        addItemEventListeners(row);
    });
    
    setupNipValidation();
    
    // Uruchamia ładowanie danych, status API oraz wyświetlanie ostatniego rachunku
    loadDashboardData(); 
});