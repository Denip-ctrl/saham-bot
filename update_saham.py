import os
import json
import time
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Konfigurasi Kredensial Fleksibel (GitHub Secrets vs Local File)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if "GCP_SA_KEY" in os.environ:
    # Jika berjalan di GitHub Actions, ambil dari Secret
    key_dict = json.loads(os.environ["GCP_SA_KEY"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
else:
    # Jika berjalan manual di Colab / Lokal (menggunakan file credentials.json)
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)

client = gspread.authorize(creds)
sheet = client.open("DB_Master_Saham").sheet1

# 2. Daftar Emiten (Contoh sampel, nanti bisa diperluas)
daftar_ticker = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ASII.JK", "TLKM.JK", "ICBP.JK"]

print("Sedang mengambil data & menghitung indikator teknikal...")

header = [
    "Ticker", "Nama_Emiten", "Sektor", "Harga_Terakhir", 
    "Market_Cap", "Div_Yield", "PBV", "MA50", "RSI", "MACD", "Signal_Line", "Last_Updated"
]
rows_to_insert = [header]
waktu_sekarang = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

for t in daftar_ticker:
    try:
        stock = yf.Ticker(t)
        info = stock.info
        df = stock.history(period="1y")
        
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

        nama = info.get('longName', t)
        sektor = info.get('sector', 'N/A')
        harga = info.get('currentPrice', df['Close'].iloc[-1] if not df.empty else 0)
        market_cap = info.get('marketCap', 0)
        div_yield = info.get('dividendYield', 0)
        pbv = info.get('priceToBook', 0)
        
        if div_yield and div_yield < 1.0:
            div_yield = div_yield * 100

        rows_to_insert.append([
            t, nama, sektor, harga, market_cap, 
            f"{div_yield:.2f}%" if div_yield else "0%", 
            pbv, 
            round(ma50_val, 2), 
            round(rsi_val, 2) if not np.isnan(rsi_val) else 0, 
            round(macd_val, 2) if not np.isnan(macd_val) else 0, 
            round(signal_val, 2) if not np.isnan(signal_val) else 0,
            waktu_sekarang
        ])
        print(f"Berhasil: {t}")
    except Exception as e:
        print(f"Gagal {t}: {e}")
    time.sleep(1)

# Tulis ke Google Sheets
sheet.clear()
sheet.update('A1', rows_to_insert)
print("\n🎉 Update Google Sheets Berhasil!")
