import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any
import asyncio
import logging

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import google.generativeai as genai

logging.basicConfig(level=logging.WARNING)  # Reduce log spam
logger = logging.getLogger(__name__)

class AntiSpamBot:
    def __init__(self, bot_token: str, gemini_api_key: str, dataset_path: str = "captcha.json"):
        self.bot_token = bot_token
        self.gemini_api_key = gemini_api_key
        self.dataset_path = dataset_path
        
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        print("🤖 AntiSpam Bot başlatılıyor...")
        self.spam_patterns = self._load_spam_patterns()
        self.application = None
        
    def _load_spam_patterns(self) -> Dict[str, List[str]]:
        """Load spam patterns from dataset"""
        try:
            with open(self.dataset_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            patterns = {
                "forbidden_links": [],
                "forbidden_tags": [],
                "crypto_addresses": [],
                "flood_patterns": [],
                "forward_spam": [],
                "banned_words": []
            }
            
            # Find the data array in the JSON structure
            dataset = None
            for item in data:
                if isinstance(item, dict) and item.get("type") == "table" and "data" in item:
                    dataset = item["data"]
                    break
            
            if not dataset:
                print("⚠️ JSON dosyasında veri seti bulunamadı")
                return patterns
            
            # Extract patterns from dataset
            for entry in dataset:
                if "chat_reasons" in entry and entry["chat_reasons"]:
                    try:
                        # Handle nested JSON strings
                        chat_reasons = entry["chat_reasons"]
                        if isinstance(chat_reasons, str):
                            # Remove extra quotes and parse
                            chat_reasons = chat_reasons.strip('"')
                            reasons = json.loads(chat_reasons)
                        else:
                            reasons = chat_reasons
                        
                        for reason in reasons:
                            if "reason" in reason and "message" in reason and reason["message"]:
                                msg = str(reason["message"]).lower()
                                
                                if "forbidden link" in reason["reason"].lower():
                                    links = re.findall(r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', msg)
                                    patterns["forbidden_links"].extend(links)
                                
                                elif "forbidden tag" in reason["reason"].lower():
                                    tags = re.findall(r'@\w+', msg)
                                    patterns["forbidden_tags"].extend(tags)
                                
                                elif "ca" in reason["reason"].lower() or "crypto" in reason["reason"].lower():
                                    crypto_addr = re.findall(r'0x[a-fA-F0-9]{40}', msg)
                                    patterns["crypto_addresses"].extend(crypto_addr)
                                
                                elif "flood" in reason["reason"].lower():
                                    patterns["flood_patterns"].append(msg)
                                
                                elif "forward" in reason["reason"].lower():
                                    patterns["forward_spam"].append(msg)
                                
                                elif "banned word" in reason["reason"].lower():
                                    patterns["banned_words"].append(msg)
                    except json.JSONDecodeError:
                        continue
            
            # Remove duplicates
            for key in patterns:
                patterns[key] = list(set(patterns[key]))
            
            print(f"✅ Spam kalıpları yüklendi:")
            print(f"   📎 {len(patterns['forbidden_links'])} yasak link")
            print(f"   🏷️ {len(patterns['forbidden_tags'])} yasak tag")
            print(f"   💰 {len(patterns['crypto_addresses'])} kripto adresi")
            print(f"   💬 {len(patterns['flood_patterns'])} flood pattern")
            print(f"   📤 {len(patterns['forward_spam'])} forward spam")
            print(f"   🚫 {len(patterns['banned_words'])} yasaklı kelime")
            return patterns
            
        except Exception as e:
            print(f"❌ Spam kalıpları yüklenirken hata: {e}")
            return {}

    def _basic_spam_check(self, message: str) -> Dict[str, Any]:
        """Basic pattern matching before AI analysis"""
        message_lower = message.lower()
        violations = []
        
        print(f"🔍 Kalıp kontrolü başlatılıyor...")
        
        # Check for forbidden links
        for link in self.spam_patterns.get("forbidden_links", []):
            if link.lower() in message_lower:
                violations.append(f"Yasak link: {link}")
                print(f"   ❌ Yasak link bulundu: {link}")
        
        # Check for forbidden tags
        for tag in self.spam_patterns.get("forbidden_tags", []):
            if tag.lower() in message_lower:
                violations.append(f"Yasak tag: {tag}")
                print(f"   ❌ Yasak tag bulundu: {tag}")
        
        # Check for crypto addresses
        crypto_addresses = re.findall(r'0x[a-fA-F0-9]{40}', message)
        if crypto_addresses:
            violations.append(f"Kripto adres: {crypto_addresses[0]}")
            print(f"   ❌ Kripto adres bulundu: {crypto_addresses[0]}")
        
        # Check for banned words
        for word in self.spam_patterns.get("banned_words", []):
            if word.lower() in message_lower:
                violations.append(f"Yasaklı kelime: {word}")
                print(f"   ❌ Yasaklı kelime bulundu: {word}")
        
        if not violations:
            print(f"   ✅ Kalıp kontrolünde spam bulunamadı")
        
        return {
            "is_spam": len(violations) > 0,
            "violations": violations,
            "confidence": 0.9 if violations else 0.0
        }

    async def _ai_spam_analysis(self, message: str) -> Dict[str, Any]:
        """Use Gemini AI to analyze message for spam"""
        try:
            print(f"🧠 Gemini AI analizi başlatılıyor...")
            
            prompt = f"""
            You are an expert anti-spam filter for Telegram groups. Analyze this message and determine if it's spam.

            Message: "{message}"

            Consider these spam indicators:
            - Promotional content for crypto/trading bots
            - Phishing links or suspicious URLs
            - Forward spam or copy-paste content
            - Excessive use of emojis or caps
            - Investment/trading promotions
            - Referral links or affiliate marketing
            - Repetitive content or flooding
            - Suspicious usernames or tags

            Respond with JSON format:
            {{
                "is_spam": true/false,
                "confidence": 0.0-1.0,
                "reason": "brief explanation",
                "category": "type of spam if detected"
            }}
            """
            
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            
            # Parse JSON response
            try:
                result = json.loads(response.text.strip())
                if result["is_spam"]:
                    print(f"   🤖 AI spam tespit etti: {result['reason']}")
                    print(f"   📊 Güven: {result['confidence']:.2f}")
                else:
                    print(f"   ✅ AI spam bulamadı: {result['reason']}")
                return result
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                text = response.text.lower()
                is_spam = "true" in text and "is_spam" in text
                print(f"   ⚠️ AI yanıtı ayrıştırılamadı, fallback kullanılıyor")
                return {
                    "is_spam": is_spam,
                    "confidence": 0.8 if is_spam else 0.2,
                    "reason": "AI analysis completed",
                    "category": "unknown"
                }
                
        except Exception as e:
            print(f"   ❌ AI analiz hatası: {e}")
            return {
                "is_spam": False,
                "confidence": 0.0,
                "reason": "AI analysis failed",
                "category": "error"
            }

    async def analyze_message(self, message: str) -> Dict[str, Any]:
        """Complete spam analysis combining patterns and AI"""
        print(f"\n📝 Mesaj analizi başlatılıyor...")
        print(f"   Mesaj: '{message[:100]}{'...' if len(message) > 100 else ''}'")
        
        # Basic pattern check first
        basic_result = self._basic_spam_check(message)
        
        # If basic check finds spam, return immediately
        if basic_result["is_spam"]:
            print(f"✅ Kalıp eşleşmesi ile spam tespit edildi!")
            return {
                "is_spam": True,
                "confidence": basic_result["confidence"],
                "method": "pattern_matching",
                "details": basic_result["violations"]
            }
        
        # Use AI for deeper analysis
        ai_result = await self._ai_spam_analysis(message)
        
        final_decision = "🚫 SPAM" if ai_result["is_spam"] else "✅ TEMİZ"
        print(f"🏁 Final Karar: {final_decision}")
        
        return {
            "is_spam": ai_result["is_spam"],
            "confidence": ai_result["confidence"],
            "method": "ai_analysis",
            "details": {
                "reason": ai_result.get("reason", ""),
                "category": ai_result.get("category", "")
            }
        }

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        try:
            message = update.message
            if not message or not message.text:
                return
            
            user = message.from_user
            chat = message.chat
            
            print(f"\n" + "="*60)
            print(f"📨 YENİ MESAJ GELDİ!")
            print(f"👤 Kullanıcı: {user.first_name} ({user.id})")
            print(f"💬 Grup: {chat.title if chat.title else 'Private'} ({chat.id})")
            print(f"📄 Mesaj ID: {message.message_id}")
            print(f"⏰ Zaman: {datetime.now().strftime('%H:%M:%S')}")
            
            # Analyze message
            result = await self.analyze_message(message.text)
            
            # Take action if spam detected
            if result["is_spam"] and result["confidence"] >= 0.6:
                print(f"\n🚨 SPAM TESPİT EDİLDİ - AKSIYON ALINIYOR!")
                try:
                    # Delete spam message first
                    print(f"   🗑️ Spam mesaj siliniyor... (ID: {message.message_id})")
                    await message.delete()
                    print(f"   ✅ Spam mesaj başarıyla silindi")
                    
                    # Send warning to user
                    warning_msg = f"⚠️ {user.first_name}, spam tespit edildi ve mesajınız silindi!\n"
                    warning_msg += f"📝 Sebep: {result['details']}\n"
                    warning_msg += f"🔍 Yöntem: {result['method']}\n"
                    warning_msg += f"📊 Güven: {result['confidence']:.2f}"
                    
                    warn_message = await context.bot.send_message(
                        chat_id=chat.id,
                        text=warning_msg
                    )
                    print(f"   📢 Uyarı mesajı gönderildi")
                    
                    # Auto-delete warning after 10 seconds
                    await asyncio.sleep(10)
                    try:
                        await warn_message.delete()
                        print(f"   🧹 Uyarı mesajı 10 saniye sonra silindi")
                    except Exception as warn_del_error:
                        print(f"   ⚠️ Uyarı mesajı silinirken hata: {warn_del_error}")
                    
                except Exception as e:
                    print(f"   ❌ Spam mesaj silme hatası: {e}")
                    print(f"   ❌ Hata tipi: {type(e).__name__}")
                    # Still try to send warning even if deletion fails
                    try:
                        warning_msg = f"⚠️ {user.first_name}, spam tespit edildi!\n"
                        warning_msg += f"📝 Sebep: {result['details']}\n"
                        warning_msg += f"⚠️ Mesaj silinemedi: {str(e)}"
                        
                        await context.bot.send_message(
                            chat_id=chat.id,
                            text=warning_msg
                        )
                    except:
                        pass
            else:
                print(f"\n✅ MESAJ TEMİZ - AKSIYON GEREKMİYOR")
                    
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")

    async def start_bot(self):
        """Start the bot"""
        try:
            print(f"\n🚀 Bot başlatılıyor...")
            self.application = Application.builder().token(self.bot_token).build()
            
            # Add message handler
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )
            
            print(f"✅ AntiSpam Bot başarıyla başlatıldı!")
            print(f"🔍 Mesajlar izlenmeye başlandı...")
            print(f"💬 Gruba spam mesaj göndermeyi deneyin!")
            print(f"🛑 Durdurmak için Ctrl+C basın")
            print(f"\n" + "="*60)
            
            # Run the bot with polling
            await self.application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            print(f"❌ Bot başlatma hatası: {e}")
            raise

    def run(self):
        """Run the bot"""
        try:
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Add message handler
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )
            
            print(f"✅ AntiSpam Bot başarıyla başlatıldı!")
            print(f"🔍 Mesajlar izlenmeye başlandı...")
            print(f"💬 Gruba spam mesaj göndermeyi deneyin!")
            print(f"🛑 Durdurmak için Ctrl+C basın")
            print(f"\n" + "="*60)
            
            # Run the bot with polling
            self.application.run_polling(drop_pending_updates=True)
            
        except KeyboardInterrupt:
            print(f"\n\n🛑 Bot kullanıcı tarafından durduruldu")
            print(f"👋 Görüşürüz!")
        except Exception as e:
            print(f"\n❌ Bot hatası: {e}")

# Example usage
if __name__ == "__main__":
    # Your credentials
    BOT_TOKEN = "7699235659:AAH5KK2Wlnf7Ym08AQmdas3GtfbM-FCK9Bw"
    GEMINI_API_KEY = "AIzaSyCnKJ6IVDQKumbTp-9mJoHxh7fPyOgDFH0"
    
    # Create and run bot
    bot = AntiSpamBot(BOT_TOKEN, GEMINI_API_KEY)
    bot.run()