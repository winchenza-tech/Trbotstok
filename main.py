import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Loglama ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- VERİ TUTMA ---
izlenen_urunler = {}
urun_sayaci = 1

def trendyol_stok_kontrol(url):
    """Trendyol linkini kontrol eder, 'Sepete Ekle' butonu varsa True döner."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            buton = soup.find('div', class_='add-to-basket-button-text')
            
            # .lower() kullanarak büyük/küçük harf sorununu ortadan kaldırıyoruz
            if buton and "sepete ekle" in buton.text.lower():
                return True
    except Exception as e:
        logging.error(f"Stok kontrol hatası: {e}")
        
    return False

# --- KOMUTLAR ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "Zenithstok kontrol botuna hoş geldiniz! 🛒\n\n"
        "Komutlar:\n"
        "/ekle <link> - Kontrol listesine ürğn ekler.\n"
        "/listem - Takipteki ürünleri gösterir.\n"
        "/listedencikar <numara> - Ürünü takipten çıkarır."
    )
    await update.message.reply_text(mesaj)

async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global urun_sayaci
    chat_id = update.message.chat_id
    
    if not context.args:
        await update.message.reply_text("Lütfen bir link girin.\nDoğru kullanım: `/ekle https://trendyol.com/...`")
        return
        
    url = context.args[0]
    
    if chat_id not in izlenen_urunler:
        izlenen_urunler[chat_id] = {}
        
    izlenen_urunler[chat_id][urun_sayaci] = url
    await update.message.reply_text(f"✅ Ürün takibe alındı!\nÜrün Numarası: {urun_sayaci}\n2 saatte bir stok kontrolü yapılacaktır.")
    urun_sayaci += 1

async def listem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    urunler = izlenen_urunler.get(chat_id, {})
    
    if not urunler:
        await update.message.reply_text("Şu anda takip ettiğiniz bir ürün bulunmuyor.")
        return
        
    mesaj = "📦 Stoğa girmesi beklenen ürünler:\n\n"
    for uid, url in urunler.items():
        mesaj += f"• No: {uid} | [Ürün Linki]({url})\n"
        
    await update.message.reply_text(mesaj, parse_mode="Markdown", disable_web_page_preview=True)

async def listedencikar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    
    if not context.args:
        await update.message.reply_text("çıkarmak istediğiniz ürünün numarasını gir.\nMal olma doğru kullanım: `/listedencikar 1`")
        return
        
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Ürün numarası sadece sayılardan oluşmalıdır!")
        return

    if chat_id in izlenen_urunler and uid in izlenen_urunler[chat_id]:
        del izlenen_urunler[chat_id][uid]
        await update.message.reply_text(f"🗑️ {uid} numaralı ürün listeden çıkarıldı.")
    else:
        await update.message.reply_text("Bu numaraya ait takip edilen bir ürün bulunamadı.")

# --- ZAMANLANMIŞ GÖREV ---

async def periyodik_kontrol(context: ContextTypes.DEFAULT_TYPE):
    """Her 2 saatte bir çalışacak kontrol fonksiyonu."""
    for chat_id, urunler in list(izlenen_urunler.items()):
        silinecek_urunler = []
        
        for uid, url in urunler.items():
            stokta_mi = trendyol_stok_kontrol(url)
            
            if stokta_mi:
                mesaj = f"🚨 KOŞ KOŞ KOŞ STOKLARDA!🚨\n\nBeklediğiniz ürün stoklara girdi. Hemen tükenmeden kap!\n👉 [Ürüne Git]({url})"
                await context.bot.send_message(chat_id=chat_id, text=mesaj, parse_mode="Markdown")
                silinecek_urunler.append(uid)
                
        for uid in silinecek_urunler:
            del izlenen_urunler[chat_id][uid]

# --- ANA FONKSİYON ---

def main():
    # Railway'deki Environment Variables kısmında TELEGRAM_BOT_TOKEN tanımlı olmalıdır.
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN bulunamadı! Lütfen çevre değişkenlerini kontrol edin.")
        return
        
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ekle", ekle))
    app.add_handler(CommandHandler("listem", listem))
    app.add_handler(CommandHandler("listedencikar", listedencikar))
    
    # interval=7200 saniye (2 Saat) demektir. 
    app.job_queue.run_repeating(periyodik_kontrol, interval=7200, first=10)
    
    logging.info("Bot başarıyla başlatıldı.")
    app.run_polling()

if __name__ == "__main__":
    main()
