import os
import json
import time
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Konfigurasi Kredensial Fleksibel (GitHub Secrets vs Google Colab Lokal)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if "GCP_SA_KEY" in os.environ:
    # Jika berjalan di GitHub Actions, ambil dari Secret
    key_dict = json.loads(os.environ["GCP_SA_KEY"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
else:
    # Jika berjalan manual di Colab / Lokal (menggunakan file credentials.json)
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)

client = gspread.authorize(creds)

# Buka file Google Sheets utama
spreadsheet = client.open("DB_Master_Saham")

# Buka tab sumber ticker dan tab tujuan data
ticker_sheet = spreadsheet.worksheet("Daftar_Ticker")
target_sheet = spreadsheet.worksheet("Sheet1") # Atau ganti nama tab tujuan jika berbeda

# 2. Ambil seluruh daftar ticker dari tab 'Daftar_Ticker' (Kolom A)
# Mengabaikan baris pertama jika itu adalah header (misal: "Ticker")
raw_tickers = ticker_sheet.col_values(1)
daftar_ticker = [t.strip() for t in raw_tickers if t.strip() and t.strip().upper() != "TICKER"]

print(f"📋 Ditemukan {len(daftar_ticker)} emiten di dalam tab 'Daftar_Ticker'.")
print("🚀 Memulai proses pengunduhan dan perhitungan teknikal...\n")

# 3. Siapkan Header untuk Database
header = [
    "Ticker", "Nama_Emiten", "Sektor", "Harga_Terakhir", 
    "Market_Cap", "Div_Yield", "PBV", "MA50", "RSI", "MACD", "Signal_Line", "Last_Updated"
]
rows_to_insert = [header]
waktu_sekarang = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# 4. Looping untuk setiap emiten
sukses = 0
gagal = 0

for i, t in enumerate(daftar_ticker, start=1):
    try:
        stock = yf.Ticker(t)
        info = stock.info
        df = stock.history(period="1y")
        
        # Hitung Indikator Teknikal jika data historis tersedia
        if not df.empty:
            df['MA50'] = df['Close'].rolling(window=50).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

            ma50_val = df['MA50'].iloc[-1]
            rsi_val = df['RSI'].iloc[-1]
            macd_val = df['MACD'].iloc[-1]
            signal_val = df['Signal_Line'].iloc[-1]
        else:
            ma50_val, rsi_val, macd_val, signal_val = 0, 0, 0, 0

        # Ekstraksi Data Fundamental
        nama = info.get('longName', t)
        sektor = info.get('sector', 'N/A')
        harga = info.get('currentPrice', df['Close'].iloc[-1] if not df.empty else 0)
        market_cap = info.get('marketCap', 0)
        div_yield = info.get('dividendYield', 0)
        pbv = info.get('priceToBook', 0)
        
        # Normalisasi persentase dividend yield
        if div_yield and div_yield < 1.0:
            div_yield = div_yield * 100

        # Masukkan ke dalam baris data
        rows_to_insert.append([
            t, 
            nama, 
            sektor, 
            harga, 
            market_cap, 
            f"{div_yield:.2f}%" if div_yield else "0%", 
            pbv, 
            round(ma50_val, 2), 
            round(rsi_val, 2) if not np.isnan(rsi_val) else 0, 
            round(macd_val, 2) if not np.isnan(macd_val) else 0, 
            round(signal_val, 2) if not np.isnan(signal_val) else 0,
            waktu_sekarang
        ])
        
        print(f"[{i}/{len(daftar_ticker)}] Berhasil memproses: {t}")
        sukses += 1
        
    except Exception as e:
        print(f"[{i}/{len(daftar_ticker)}] Gagal memproses {t}: {e}")
        gagal += 1
    
    # Jeda 1 detik per emiten agar aman dari blokir Yahoo Finance (*rate limit*)
    time.sleep(1)

# 5. Tulis seluruh data ke Google Sheets secara massal (Bulk Update)
print("\n🔄 Sedang memperbarui data ke Google Sheets...")
target_sheet.clear()
target_sheet.update('A1', rows_to_insert)

print(f"\n🎉 Selesai! Total Berhasil: {sukses} emiten | Total Gagal: {gagal} emiten.")
print("📊 Database Google Sheets Anda kini sudah terisi penuh.")
