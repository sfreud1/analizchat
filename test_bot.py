#!/usr/bin/env python3
"""
Test script for the antispam bot
"""

import asyncio
from antispam_bot import AntiSpamBot

async def test_bot():
    # Your credentials
    BOT_TOKEN = "7699235659:AAH5KK2Wlnf7Ym08AQmdas3GtfbM-FCK9Bw"
    GEMINI_API_KEY = "AIzaSyCnKJ6IVDQKumbTp-9mJoHxh7fPyOgDFH0"
    
    # Create bot instance
    bot = AntiSpamBot(BOT_TOKEN, GEMINI_API_KEY)
    
    print("🤖 AntiSpam Bot Test")
    print("=" * 40)
    
    # Test spam patterns loading
    print(f"✅ Loaded {len(bot.spam_patterns['forbidden_links'])} forbidden links")
    print(f"✅ Loaded {len(bot.spam_patterns['forbidden_tags'])} forbidden tags")
    print(f"✅ Loaded {len(bot.spam_patterns['crypto_addresses'])} crypto addresses")
    print()
    
    # Test messages
    test_messages = [
        "Hello, how are you?",  # Normal message
        "Check out google.com for more info",  # Forbidden link
        "Hey @adam how are you?",  # Forbidden tag
        "0x59f4f336bf3d0c49dbfba4a74ebd2a6ace40539a",  # Crypto address
        "🚀 EASY MONEY! Click here to earn 1000$ daily! 💰💰💰"  # Suspicious spam
    ]
    
    print("📋 İlk birkaç yasak link:")
    for i, link in enumerate(bot.spam_patterns['forbidden_links'][:5]):
        print(f"   {i+1}. {link}")
    print()
    
    print("📝 Testing messages:")
    print("-" * 40)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. Testing: '{message[:50]}...'")
        result = await bot.analyze_message(message)
        
        status = "🚫 SPAM" if result["is_spam"] else "✅ Clean"
        confidence = result["confidence"]
        method = result["method"]
        
        print(f"   Result: {status} (Confidence: {confidence:.2f}, Method: {method})")
        if result["is_spam"]:
            print(f"   Details: {result['details']}")

if __name__ == "__main__":
    asyncio.run(test_bot())