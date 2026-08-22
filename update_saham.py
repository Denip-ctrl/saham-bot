import os
import json
import time
import datetime
import subprocess
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Konfigurasi Kredensial Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if "GCP_SA_KEY" in os.environ:
    key_dict = json.loads(os.environ["GCP_SA_KEY"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)

client = gspread.authorize(creds)
spreadsheet = client.open("DB_Master_Saham")

ticker_sheet = spreadsheet.worksheet("Daftar_Ticker")
target_sheet = spreadsheet.worksheet("Sheet1") 

raw_tickers = ticker_sheet.col_values(1)
daftar_ticker = [t.strip() for t in raw_tickers if t.strip() and t.strip().upper() != "TICKER"]

print(f"📋 Ditemukan {len(daftar_ticker)} emiten di dalam tab 'Daftar_Ticker'.")
print("🚀 Memulai pengunduhan data historis 3 tahun & kalkulasi teknikal...\n", flush=True)

header = [
    "Ticker", "Nama_Emiten", "Sektor", "Harga_Terakhir", 
    "Market_Cap", "Div_Yield", "PBV", "MA50", "RSI", "MACD", "Signal_Line", "Last_Updated"
]
rows_to_insert = [header]
waktu_sekarang = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# Kamus besar untuk menampung data lengkap (Profil Fundamental + Histori) untuk file JSON
master_complete_json = {}

sukses = 0
gagal = 0

for i, t in enumerate(daftar_ticker, start=1):
    try:
        stock = yf.Ticker(t)
        info = stock.info
        # Tarik data historis 3 tahun
        df = stock.history(period="3y")
        
        ma50_val, rsi_val, macd_val, signal_val = 0, 0, 0, 0
        
        if not df.empty:
            # Hitung Indikator Teknikal
            df['MA50'] = df['Close'].rolling(window=50).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

            # Ambil nilai hari terakhir (baris paling ujung)
            if not pd.isna(df['MA50'].iloc[-1]): ma50_val = float(df['MA50'].iloc[-1])
            if not pd.isna(df['RSI'].iloc[-1]): rsi_val = float(df['RSI'].iloc[-1])
            if not pd.isna(df['MACD'].iloc[-1]): macd_val = float(df['MACD'].iloc[-1])
            if not pd.isna(df['Signal_Line'].iloc[-1]): signal_val = float(df['Signal_Line'].iloc[-1])

        nama = info.get('longName', t)
        sektor = info.get('sector', 'N/A')
        
        harga = info.get('currentPrice', None)
        if not harga and not df.empty:
            harga = float(df['Close'].iloc[-1])
        elif not harga:
            harga = 0.0

        market_cap = info.get('marketCap', 0)
        if not market_cap or pd.isna(market_cap): market_cap = 0

        div_yield = info.get('dividendYield', 0)
        if div_yield and div_yield < 1.0:
            div_yield = div_yield * 100
        if not div_yield or pd.isna(div_yield): div_yield = 0

        pbv = info.get('priceToBook', 0)
        if not pbv or pd.isna(pbv) or np.isinf(pbv): pbv = 0

        # Persiapkan data histori untuk JSON
        df_subset = []
        if not df.empty:
            df_clean = df.reset_index()
            cols_to_keep = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'MA50', 'MA20', 'RSI', 'MACD', 'Signal_Line']
            existing_cols = [c for c in cols_to_keep if c in df_clean.columns]
            df_subset_temp = df_clean[existing_cols].copy()
            
            df_subset_temp['Date'] = pd.to_datetime(df_subset_temp['Date']).dt.strftime('%Y-%m-%d')
            df_subset_temp = df_subset_temp.replace({np.nan: None, np.inf: None, -np.inf: None})
            df_subset = df_subset_temp.to_dict(orient='records')

        # --- PERUBAHAN UTAMA: Gabungkan Profile dan History ke dalam satu key Ticker ---
        master_complete_json[t] = {
            "profile": {
                "name": str(nama),
                "sector": str(sektor),
                "marketCap": int(market_cap),
                "divYield": f"{float(div_yield):.2f}%" if div_yield else "0%",
                "pbv": round(float(pbv), 2),
                "price": round(float(harga), 2)
            },
            "history": df_subset
        }

        # Data ringkasan untuk Google Sheets
        rows_to_insert.append([
            str(t), 
            str(nama), 
            str(sektor), 
            round(float(harga), 2), 
            int(market_cap), 
            f"{float(div_yield):.2f}%" if div_yield else "0%", 
            round(float(pbv), 2), 
            round(ma50_val, 2), 
            round(rsi_val, 2), 
            round(macd_val, 2), 
            round(signal_val, 2),
            str(waktu_sekarang)
        ])
        
        print(f"[{i}/{len(daftar_ticker)}] Sukses memproses: {t}", flush=True)
        sukses += 1
        
    except Exception as e:
        print(f"[{i}/{len(daftar_ticker)}] Gagal memproses {t}: {e}", flush=True)
        gagal += 1
    
    time.sleep(1)

# 2. Simpan Data Lengkap (Profil + Histori) ke File JSON
print("\n💾 Menyimpan data lengkap ke file 'saham_history.json'...", flush=True)
with open('saham_history.json', 'w') as f:
    json.dump(master_complete_json, f, indent=4)

# 3. Perbarui Google Sheets dengan Ringkasan Hari Terakhir
print("🔄 Sedang memperbarui ringkasan ke Google Sheets...", flush=True)
target_sheet.clear()
target_sheet.update(range_name='A1', values=rows_to_insert)

# 4. Otomatis Commit dan Push File JSON ke GitHub
try:
    print("🚀 Mengirim file JSON terbaru ke repositori GitHub...", flush=True)
    subprocess.run(["git", "config", "--global", "user.name", "GitHub Actions Bot"], check=True)
    subprocess.run(["git", "config", "--global", "user.email", "actions@github.com"], check=True)
    subprocess.run(["git", "add", "saham_history.json"], check=True)
    subprocess.run(["git", "commit", "-m", "Auto-update: Refresh profil fundamental dan data historis"], check=True)
    subprocess.run(["git", "push"], check=True)
    print("✅ Berhasil melakukan push ke GitHub!", flush=True)
except Exception as git_err:
    print(f"⚠️ Catatan Git Push: {git_err} (Abaikan jika dijalankan secara lokal di komputer pribadi).", flush=True)

print(f"\n🎉 Selesai! Total Berhasil: {sukses} emiten | Total Gagal: {gagal} emiten.", flush=True)
