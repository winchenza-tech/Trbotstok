 import os
import logging
import cloudscraper
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Loglama ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

izlenen_urunler = {}
urun_sayaci = 1

def trendyol_stok_kontrol(url):
    scraper = cloudscraper.create_scraper(browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    })
    
    try:
        # allow_redirects=True ile ty.gl gibi kısa linkleri sonuna kadar takip et
        response = scraper.get(url, timeout=20, allow_redirects=True)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Sistem Trendyol güvenlik duvarına takıldıysa loglara yazdır
            if "Robot Değilim" in soup.text or "challengetitle" in response.text.lower():
                logging.warning(f"Güvenlik duvarına takıldık! URL: {url}")
                return False
                
            # Hedefi genişlet: Class isminin içinde 'add-to-basket' geçen tüm elementleri bul
            butonlar = soup.find_all(class_=lambda c: c and 'add-to-basket' in c.lower())
            
            for b in butonlar:
                if b.text and "sepete ekle" in b.text.lower():
                    return True
                    
    except Exception as e:
        logging.error(f"Tarama Hatası: {e}")
        
    return False

# --- KOMUTLAR ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "SBen StockFox.\n"
        "Kurallar basit, komutları eksiksiz gir:\n\n"
        "/ekle <link> - Takip edilecek hedefi belirle.\n"
        "/listem - Radarımızdaki hedefleri gör.\n"
        "/listedencikar <no> - Gereksiz hedefleri sistemden temizle.\n"
        "/kontrol - Aciliyet durumunda manuel tarama başlat."
    )
    await update.message.reply_text(mesaj)

async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global urun_sayaci
    chat_id = update.message.chat_id
    
    if not context.args:
        await update.message.reply_text("Eksik parametre. Bana net bir hedef linki ver.\nÖrnek: `/ekle https://trendyol.com/...`")
        return
        
    url = context.args[0]
    
    if chat_id not in izlenen_urunler:
        izlenen_urunler[chat_id] = {}
        
    izlenen_urunler[chat_id][urun_sayaci] = url
    await update.message.reply_text(f"✅ Hedef listeye eklendi. ID:{urun_sayaci}.\n bekle bakalım.")
    urun_sayaci += 1

async def listem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    urunler = izlenen_urunler.get(chat_id, {})
    
    if not urunler:
        await update.message.reply_text("Sistemde takip edilen hiçbir hedef yok. Önce bir görev ver.")
        return
        
    mesaj = "📦 **Radarımızdaki Aktif Hedefler:**\n\n"
    for uid, url in urunler.items():
        mesaj += f"• **ID: {uid}** | [Hedefe Git]({url})\n"
        
    await update.message.reply_text(mesaj, parse_mode="Markdown", disable_web_page_preview=True)

async def listedencikar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    
    if not context.args:
        await update.message.reply_text("Hatalı kullanım. İptal edilecek hedefin ID numarasını gir.\nÖrnek: `/listedencikar 1`")
        return
        
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Sadece rakam kullan. Basit komutları yanlış girme.")
        return

    if chat_id in izlenen_urunler and uid in izlenen_urunler[chat_id]:
        del izlenen_urunler[chat_id][uid]
        await update.message.reply_text(f"🗑️ ID {uid} sistemden kalıcı olarak silindi.")
    else:
        await update.message.reply_text("Böyle bir ID sistemde yok. Verilerini kontrol edip tekrar dene.")

# --- MANUEL KONTROL KOMUTU ---

async def manuel_kontrol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    urunler = izlenen_urunler.get(chat_id, {})
    
    if not urunler:
        await update.message.reply_text("Kontrol edilecek veri yok. Önce hedef ekle.")
        return
        
    await update.message.reply_text("⏳ Sistem taranıyor. Bekle.")
    
    silinecek_urunler = []
    stokta_bulunan = 0
    
    for uid, url in urunler.items():
        stokta_mi = trendyol_stok_kontrol(url)
        
        if stokta_mi:
            mesaj = f"🚨 **HEDEF TESPİT EDİLDİ** 🚨\n\nStok aktif. Koş harca paranı saçma şeylere.\n👉 [Satın Al]({url})"
            await context.bot.send_message(chat_id=chat_id, text=mesaj, parse_mode="Markdown")
            silinecek_urunler.append(uid)
            stokta_bulunan += 1
            
    for uid in silinecek_urunler:
        del izlenen_urunler[chat_id][uid]
        
    if stokta_bulunan == 0:
        await update.message.reply_text("Mevcut hedeflerde stok yok. Beklemeye devam et.")

# --- ZAMANLANMIŞ GÖREV (OTOMATİK KONTROL) ---

async def periyodik_kontrol(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, urunler in list(izlenen_urunler.items()):
        silinecek_urunler = []
        
        for uid, url in urunler.items():
            stokta_mi = trendyol_stok_kontrol(url)
            
            if stokta_mi:
                mesaj = f"🚨 **HEDEF TESPİT EDİLDİ** 🚨\n\nStok aktif. Koş harca paranı saçma şeylere.\n👉 [Satın Al]({url})"
                await context.bot.send_message(chat_id=chat_id, text=mesaj, parse_mode="Markdown")
                silinecek_urunler.append(uid)
                
        for uid in silinecek_urunler:
            del izlenen_urunler[chat_id][uid]

# --- ANA FONKSİYON ---

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN bulunamadı!")
        return
        
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ekle", ekle))
    app.add_handler(CommandHandler("listem", listem))
    app.add_handler(CommandHandler("listedencikar", listedencikar))
    app.add_handler(CommandHandler("kontrol", manuel_kontrol)) 
    
    app.job_queue.run_repeating(periyodik_kontrol, interval=7200, first=10)
    
    logging.info("Sistem devrede. Veri akışı bekleniyor.")
    app.run_polling()

if __name__ == "__main__":
    main()
