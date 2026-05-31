import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Loglama ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

izlenen_urunler = {}
urun_sayaci = 1

def trendyol_stok_kontrol(url):
    # Sistemi Googlebot olarak maskele. Hedef bizi arama motoru sanacak.
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Taktik 1: Googlebot'a özel sunulan Schema.org stok etiketini oku (En kesin yöntem)
            availability = soup.find('meta', {'itemprop': 'availability'})
            if availability and "InStock" in availability.get('href', ''):
                return True
                
            # Taktik 2: Etiket yoksa klasik kaba kuvvet HTML taraması yap
            butonlar = soup.find_all(class_=lambda c: c and 'add-to-basket' in c.lower())
            for b in butonlar:
                if b.text and "sepete ekle" in b.text.lower():
                    return True
                    
    except Exception as e:
        logging.error(f"Sızma Başarısız: {e}")
        
    return False

# --- KOMUTLAR ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "SBen StockFox.\n"
        "Kurallar basit, komutları eksiksiz gir:\n\n"
        "/ekle <link> - Takip edilecek hedefi belirle.\n"
        "/listem - Radarımızdaki hedefleri gör.\n"
        "/listedencikar <no> - Gereksiz hedefleri sistemden temizle.\n"
        "/kontrol - Aciliyet durumunda manuel tarama başlat.\n"
        "/rapor <link> - Hedef sayfanın arka plan analizini bana raporla."
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

async def rapor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Eksik parametre. Raporlanacak linki ver. Örnek: `/rapor https://...`")
        return
        
    url = context.args[0]
    await update.message.reply_text("📡 Hedefte derin tarama başlatıldı. Bekle...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept-Language": "tr-TR,tr;q=0.9"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        status = response.status_code
        
        soup = BeautifulSoup(response.text, 'html.parser')
        availability = soup.find('meta', {'itemprop': 'availability'})
        stok_durumu = availability.get('href', 'Bulunamadı') if availability else 'Etiket Yok'
        
        buton_text = "Bulunamadı"
        buton = soup.find(class_=lambda c: c and 'add-to-basket' in c.lower())
        if buton:
            buton_text = buton.text.strip()
            
        rapor_mesaji = (
            f"📄 **SİSTEM İSTİHBARAT RAPORU**\n\n"
            f"**HTTP Dönüş Kodu:** `{status}` (200 ise erişim temiz)\n"
            f"**Googlebot Stok Etiketi:** `{stok_durumu}`\n"
            f"**HTML Buton İçeriği:** `{buton_text}`\n"
            f"**Metin Analizi:** Sayfada 'Sepete Ekle' kelimesi `{response.text.lower().count('sepete ekle')}` kez geçiyor."
        )
        await update.message.reply_text(rapor_mesaji, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"HATA: Hedefe ulaşılamadı. Sebep: {e}")

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
    app.add_handler(CommandHandler("rapor", rapor)) 
    
    app.job_queue.run_repeating(periyodik_kontrol, interval=7200, first=10)
    
    logging.info("Sistem devrede. Veri akışı bekleniyor.")
    app.run_polling()

if __name__ == "__main__":
    main()
