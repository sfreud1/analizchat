import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any
import google.generativeai as genai

class DataCategorizer:
    def __init__(self, gemini_api_key: str, input_file: str = "captcha.json", output_file: str = "categorized_data.json"):
        self.gemini_api_key = gemini_api_key
        self.input_file = input_file
        self.output_file = output_file
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Initialize categories
        self.categories = {
            "spam": {
                "crypto_trading": [],
                "phishing": [],
                "promotional": [],
                "forward_spam": [],
                "flood": [],
                "suspicious_links": [],
                "banned_content": [],
                "other_spam": []
            },
            "legitimate": {
                "normal_conversation": [],
                "questions": [],
                "announcements": [],
                "other_legitimate": []
            },
            "unclear": []
        }
        
        print("🤖 Veri Kategorileme Sistemi başlatıldı")
        print(f"📄 Giriş dosyası: {input_file}")
        print(f"📝 Çıkış dosyası: {output_file}")

    def load_data(self) -> List[Dict]:
        """Load data from JSON file"""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Find the data array in the JSON structure
            dataset = None
            for item in data:
                if isinstance(item, dict) and item.get("type") == "table" and "data" in item:
                    dataset = item["data"]
                    break
            
            if not dataset:
                print("❌ JSON dosyasında veri seti bulunamadı")
                return []
            
            # Extract messages
            messages = []
            for entry in dataset:
                if "chat_reasons" in entry and entry["chat_reasons"]:
                    try:
                        # Handle nested JSON strings
                        chat_reasons = entry["chat_reasons"]
                        if isinstance(chat_reasons, str):
                            chat_reasons = chat_reasons.strip('"')
                            reasons = json.loads(chat_reasons)
                        else:
                            reasons = chat_reasons
                        
                        for reason in reasons:
                            if "message" in reason and reason["message"]:
                                messages.append({
                                    "message": str(reason["message"]),
                                    "original_reason": reason.get("reason", ""),
                                    "user_id": entry.get("user_id", ""),
                                    "chat_id": entry.get("chat_id", ""),
                                    "timestamp": entry.get("timestamp", "")
                                })
                    except (json.JSONDecodeError, KeyError) as e:
                        continue
            
            print(f"✅ {len(messages)} mesaj yüklendi")
            return messages
            
        except Exception as e:
            print(f"❌ Veri yükleme hatası: {e}")
            return []

    async def categorize_message(self, message_data: Dict) -> Dict:
        """Categorize a single message using Gemini AI"""
        try:
            # Rate limiting: wait 4 seconds between requests (15 requests/minute = 1 request/4 seconds)
            await asyncio.sleep(4)
            
            message = message_data["message"]
            original_reason = message_data["original_reason"]
            
            prompt = f"""
            Bu mesajı analiz et ve kategorize et. Mesaj spam mi, meşru mu yoksa belirsiz mi?
            
            Mesaj: "{message}"
            Orijinal etiket: "{original_reason}"
            
            Kategoriler:
            
            SPAM kategorileri:
            - crypto_trading: Kripto para, trading bot reklamları
            - phishing: Sahte linkler, dolandırıcılık
            - promotional: Ürün/hizmet reklamları
            - forward_spam: Toplu forward mesajlar
            - flood: Tekrarlayan, spam içerik
            - suspicious_links: Şüpheli linkler
            - banned_content: Yasak içerik
            - other_spam: Diğer spam türleri
            
            LEGİTİMATE kategorileri:
            - normal_conversation: Normal sohbet
            - questions: Sorular
            - announcements: Duyurular
            - other_legitimate: Diğer meşru içerik
            
            JSON formatında yanıt ver:
            {{
                "is_spam": true/false,
                "category": "kategori_adı",
                "main_type": "spam/legitimate/unclear",
                "confidence": 0.0-1.0,
                "reason": "kısa açıklama",
                "keywords": ["anahtar", "kelimeler"]
            }}
            """
            
            # Retry mechanism for rate limits
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await asyncio.to_thread(self.model.generate_content, prompt)
                    break
                except Exception as api_error:
                    if "429" in str(api_error) and attempt < max_retries - 1:
                        wait_time = 10 * (attempt + 1)  # Exponential backoff
                        print(f"   ⏳ Rate limit, {wait_time}s bekleniyor... (deneme {attempt + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise api_error
            
            try:
                result = json.loads(response.text.strip())
                result["original_message"] = message
                result["original_reason"] = original_reason
                result["user_id"] = message_data.get("user_id", "")
                result["chat_id"] = message_data.get("chat_id", "")
                result["timestamp"] = message_data.get("timestamp", "")
                return result
                
            except json.JSONDecodeError:
                # Fallback parsing
                text = response.text.lower()
                is_spam = "spam" in text and ("true" in text or "is_spam" in text)
                
                return {
                    "is_spam": is_spam,
                    "category": "other_spam" if is_spam else "unclear",
                    "main_type": "spam" if is_spam else "unclear",
                    "confidence": 0.5,
                    "reason": "AI parsing failed",
                    "keywords": [],
                    "original_message": message,
                    "original_reason": original_reason,
                    "user_id": message_data.get("user_id", ""),
                    "chat_id": message_data.get("chat_id", ""),
                    "timestamp": message_data.get("timestamp", "")
                }
                
        except Exception as e:
            print(f"❌ Mesaj kategorileme hatası: {e}")
            return {
                "is_spam": False,
                "category": "unclear",
                "main_type": "unclear",
                "confidence": 0.0,
                "reason": f"Error: {str(e)}",
                "keywords": [],
                "original_message": message_data.get("message", ""),
                "original_reason": message_data.get("original_reason", ""),
                "user_id": message_data.get("user_id", ""),
                "chat_id": message_data.get("chat_id", ""),
                "timestamp": message_data.get("timestamp", "")
            }

    async def process_all_messages(self, messages: List[Dict]) -> Dict:
        """Process all messages and categorize them"""
        print(f"\n🔄 {len(messages)} mesaj işleniyor...")
        
        categorized_data = {
            "metadata": {
                "total_messages": len(messages),
                "processed_at": datetime.now().isoformat(),
                "categories": {}
            },
            "spam": {
                "crypto_trading": [],
                "phishing": [],
                "promotional": [],
                "forward_spam": [],
                "flood": [],
                "suspicious_links": [],
                "banned_content": [],
                "other_spam": []
            },
            "legitimate": {
                "normal_conversation": [],
                "questions": [],
                "announcements": [],
                "other_legitimate": []
            },
            "unclear": []
        }
        
        processed = 0
        for message_data in messages:
            try:
                result = await self.categorize_message(message_data)
                
                # Categorize based on result
                main_type = result.get("main_type", "unclear")
                category = result.get("category", "unclear")
                
                if main_type == "spam" and category in categorized_data["spam"]:
                    categorized_data["spam"][category].append(result)
                elif main_type == "legitimate" and category in categorized_data["legitimate"]:
                    categorized_data["legitimate"][category].append(result)
                else:
                    categorized_data["unclear"].append(result)
                
                processed += 1
                if processed % 10 == 0:
                    print(f"   ✅ {processed}/{len(messages)} mesaj işlendi")
                    
            except Exception as e:
                print(f"   ❌ Mesaj işleme hatası: {e}")
                continue
        
        # Update metadata
        for main_cat in ["spam", "legitimate"]:
            for sub_cat in categorized_data[main_cat]:
                count = len(categorized_data[main_cat][sub_cat])
                categorized_data["metadata"]["categories"][f"{main_cat}_{sub_cat}"] = count
        
        categorized_data["metadata"]["categories"]["unclear"] = len(categorized_data["unclear"])
        
        print(f"\n📊 İşlem tamamlandı!")
        print(f"   📈 Toplam işlenen: {processed}")
        
        return categorized_data

    def save_categorized_data(self, categorized_data: Dict):
        """Save categorized data to JSON file"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(categorized_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Kategorilere ayrılmış veri kaydedildi: {self.output_file}")
            
            # Print summary
            print(f"\n📋 ÖZET:")
            metadata = categorized_data["metadata"]
            print(f"   📄 Toplam mesaj: {metadata['total_messages']}")
            
            for category, count in metadata["categories"].items():
                if count > 0:
                    print(f"   📁 {category}: {count}")
                    
        except Exception as e:
            print(f"❌ Veri kaydetme hatası: {e}")

    async def run(self):
        """Main execution function"""
        print("\n🚀 Veri kategorileme başlatılıyor...")
        
        # Load data
        messages = self.load_data()
        if not messages:
            print("❌ İşlenecek veri bulunamadı")
            return
        
        # Process messages
        categorized_data = await self.process_all_messages(messages)
        
        # Save results
        self.save_categorized_data(categorized_data)
        
        print("\n🎉 Veri kategorileme tamamlandı!")

# Usage
if __name__ == "__main__":
    # Gemini API key (same as bot)
    GEMINI_API_KEY = "AIzaSyCnKJ6IVDQKumbTp-9mJoHxh7fPyOgDFH0"
    
    # Create categorizer
    categorizer = DataCategorizer(
        gemini_api_key=GEMINI_API_KEY,
        input_file="captcha.json",
        output_file="categorized_spam_data.json"
    )
    
    # Run categorization
    try:
        asyncio.run(categorizer.run())
    except KeyboardInterrupt:
        print("\n🛑 İşlem kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n❌ Hata: {e}")