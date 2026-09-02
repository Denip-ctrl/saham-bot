import json
import pandas as pd
import numpy as np

def hitung_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def proses_analisis_saham():
    try:
        with open('saham_history.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("File saham_history.json tidak ditemukan.")
        return

    if isinstance(data, dict):
        daftar_saham = [data]
    elif isinstance(data, list):
        daftar_saham = data
    else:
        print("Format JSON tidak dikenali.")
        return

    updated_data = []

    for saham in daftar_saham:
        if not isinstance(saham, dict):
            continue
            
        history = saham.get('history', [])
        if not history or len(history) < 20:
            updated_data.append(saham)
            continue

        df = pd.DataFrame(history)
        if 'close' not in df.columns or 'volume' not in df.columns:
            updated_data.append(saham)
            continue

        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['Volume_MA20'] = df['volume'].rolling(window=20).mean()
        df['RSI'] = hitung_rsi(df['close'], period=14)
        df['Volume_Spike'] = df['volume'] > (df['Volume_MA20'] * 2.0)

        last_close = df['close'].iloc[-1]
        last_sma20 = df['SMA_20'].iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        is_volume_spike = df['Volume_Spike'].iloc[-1]

        # Logika Sinyal
        if last_close > last_sma20 and last_rsi < 70 and is_volume_spike:
            sinyal = "Strong Bullish (Akumulasi Volume Tinggi)"
        elif last_close > last_sma20:
            sinyal = "Bullish Moderat"
        elif last_close < last_sma20 and is_volume_spike:
            sinyal = "Strong Bearish (Distribusi/Tekanan Jual Tinggi)"
        else:
            sinyal = "Bearish / Konsolidasi"

        # --- PERHITUNGAN PROYEKSI HARGA ---
        # Menghitung rata-rata return harian (persentase perubahan harian)
        df['daily_return'] = df['close'].pct_change()
        avg_daily_return = df['daily_return'].tail(30).mean() # Rata-rata 30 hari terakhir
        
        # Proyeksi 5 Hari ke Depan (Compound Daily Return sederhana)
        # Asumsi 5 hari perdagangan
        prediksi_5_hari = last_close * ((1 + avg_daily_return) ** 5)
        
        # Proyeksi 3 Bulan ke Depan (~60 hari bursa)
        prediksi_3_bulan = last_close * ((1 + avg_daily_return) ** 60)

        saham['analisis_terakhir'] = {
            "sinyal": sinyal,
            "harga_terakhir": round(float(last_close), 2),
            "rsi_terakhir": round(float(last_rsi), 2) if not pd.isna(last_rsi) else None,
            "sma_20": round(float(last_sma20), 2) if not pd.isna(last_sma20) else None,
            "volume_spike": bool(is_volume_spike),
            "proyeksi": {
                "target_5_hari": round(float(prediksi_5_hari), 2),
                "target_3_bulan": round(float(prediksi_3_bulan), 2)
            }
        }

        updated_data.append(saham)

    final_output = updated_data[0] if isinstance(data, dict) else updated_data

    with open('saham_history.json', 'w') as f:
        json.dump(final_output, f, indent=4)
    
    print("Analisis teknikal, volume, dan proyeksi harga berhasil diperbarui.")

if __name__ == "__main__":
    proses_analisis_saham()
