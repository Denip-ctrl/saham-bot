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
    # 1. Baca data mentah dari saham_history.json
    try:
        with open('saham_history.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("File saham_history.json tidak ditemukan.")
        return

    # Pastikan data berupa dictionary atau list tergantung struktur JSON Anda
    # Asumsi struktur: list dari objek saham atau dictionary berkunci kode saham
    updated_data = []

    # Jika formatnya list per saham
    for saham in data:
        kode = saham.get('kode', 'UNKNOWN')
        history = saham.get('history', [])
        
        if not history or len(history) < 20:
            updated_data.append(saham)
            continue

        df = pd.DataFrame(history)
        # Pastikan kolom standar tersedia: date, close, volume
        if 'close' not in df.columns or 'volume' not in df.columns:
            updated_data.append(saham)
            continue

        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        # 2. Perhitungan Indikator Teknikal & Volume
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['Volume_MA20'] = df['volume'].rolling(window=20).mean()
        df['RSI'] = hitung_rsi(df['close'], period=14)
        
        # Analisis Volume Spike (Volume hari ini > 2x rata-rata volume 20 hari)
        df['Volume_Spike'] = df['volume'] > (df['Volume_MA20'] * 2.0)

        # 3. Logika Prediksi Sederhana Berbasis Tren & Volume
        last_close = df['close'].iloc[-1]
        last_sma20 = df['SMA_20'].iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        is_volume_spike = df['Volume_Spike'].iloc[-1]

        # Menentukan sinyal tren
        if last_close > last_sma20 and last_rsi < 70 and is_volume_spike:
            sinyal = "Strong Bullish (Akumulasi Volume Tinggi)"
        elif last_close > last_sma20:
            sinyal = "Bullish Moderat"
        elif last_close < last_sma20 and is_volume_spike:
            sinyal = "Strong Bearish (Distribusi/Tekanan Jual Tinggi)"
        else:
            sinyal = "Bearish / Konsolidasi"

        # Simpan hasil analisis ke dalam objek saham
        saham['analisis_terakhir'] = {
            "sinyal": sinyal,
            "rsi_terakhir": round(float(last_rsi), 2) if not pd.isna(last_rsi) else None,
            "sma_20": round(float(last_sma20), 2) if not pd.isna(last_sma20) else None,
            "volume_spike": bool(is_volume_spike),
            "keterangan_volume": "Volume di atas rata-rata 20 hari" if is_volume_spike else "Volume normal"
        }

        updated_data.append(saham)

    # 4. Tulis ulang hasil ke file JSON (bisa ditimpa atau dibuat file baru misal: saham_analisis.json)
    with open('saham_history.json', 'w') as f:
        json.dump(updated_data, f, indent=4)
    
    print("Analisis teknikal dan volume berhasil diperbarui ke JSON.")

if __name__ == "__main__":
    proses_analisis_saham()
