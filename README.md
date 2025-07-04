# AI AntiSpam Bot for Telegram

Telegram grubu için Gemini AI ve veri seti tabanlı spam koruma botu.

## Özellikler

- **Hibrit Spam Algılama**: Veri seti kalıpları + Gemini AI analizi
- **Otomatik Spam Silme**: Spam mesajları otomatik siler
- **Kullanıcı Uyarı Sistemi**: Spam gönderen kullanıcılara uyarı mesajı
- **Detaylı Loglama**: Tüm aktiviteler loglanır

## Bot Nasıl Çalışır?

Bot otomatik olarak gruplardaki mesajları izler:

1. **Mesaj Alındığında**: Her mesaj otomatik analiz edilir
2. **İki Aşamalı Kontrol**: 
   - Önce veri setindeki kalıplarla kontrol
   - Sonra Gemini AI ile derin analiz
3. **Spam Tespit Edilirse**:
   - Mesaj otomatik silinir
   - Kullanıcıya uyarı mesajı gönderilir
   - Log kaydı tutulur

## Kurulum

1. **Virtual Environment Oluştur**:
```bash
python3 -m venv antispam_env
source antispam_env/bin/activate
```

2. **Paketleri Yükle**:
```bash
pip install -r requirements.txt
```

3. **Bot Tokenini Al**:
   - @BotFather'dan yeni bot oluştur
   - Token'ı `antispam_bot.py` dosyasına ekle

4. **Gemini API Key Al**:
   - Google AI Studio'dan API key al
   - API key'i `antispam_bot.py` dosyasına ekle

## Kullanım

### Test Modu
```bash
python test_bot.py
```

### Canlı Bot
```bash
python antispam_bot.py
# veya
./run_bot.sh
```

### Gruba Ekleme

1. Bot tokenini al
2. Botu gruba ekle
3. Bota admin yetkisi ver (mesaj silme yetkisi gerekli)
4. Bot otomatik olarak mesajları izlemeye başlar

## Spam Kategorileri

Bot şu türlerde spam'ları tespit eder:

- **Forbidden Links**: Yasak linkler (google.com, test.com vs.)
- **Forbidden Tags**: Yasak kullanıcı etiketleri (@spam_user vs.)
- **Crypto Addresses**: Kripto para adresleri (0x...)
- **Flood Messages**: Aynı mesajı tekrar tekrar gönderme
- **Forward Spam**: Spam forward mesajları
- **Banned Words**: Yasaklı kelimeler
- **AI Detection**: Gemini AI'ın tespit ettiği diğer spam türleri

## Konfigürasyon

`antispam_bot.py` dosyasında:

```python
# Bot ayarları
BOT_TOKEN = "your_bot_token"
GEMINI_API_KEY = "your_gemini_api_key"

# Spam tespit eşiği (0.0-1.0)
SPAM_THRESHOLD = 0.7
```

## Komutlar

Bot komut gerektirmez, otomatik çalışır. Admin kullanıcıları için:

- Botun durumunu kontrol etmek için loglara bakın
- Bot manuel olarak durdurulabilir (Ctrl+C)

## Log Örnekleri

```
INFO:__main__:Message from John (123456): {
  'is_spam': True, 
  'confidence': 0.95, 
  'method': 'pattern_matching', 
  'details': ['Forbidden link: google.com']
}

INFO:__main__:Message from Jane (789012): {
  'is_spam': False, 
  'confidence': 0.1, 
  'method': 'ai_analysis'
}
```

## Sorun Giderme

1. **Bot mesajlara cevap vermiyor**:
   - Token'ı kontrol edin
   - Bot gruba admin olarak eklenmiş mi?

2. **Spam tespit edilmiyor**:
   - Gemini API key'i doğru mu?
   - Veri seti doğru yüklendi mi?

3. **Mesajlar silinmiyor**:
   - Botun mesaj silme yetkisi var mı?
   - Bot admin yetkisine sahip mi?