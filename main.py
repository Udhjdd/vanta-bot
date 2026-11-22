from fastapi import FastAPI, Request
import httpx
import os
import asyncio
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app-name.onrender.com")

user_states = {}

async def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

async def process_google_account(chat_id, email, password):
    await send_telegram_message(chat_id, "بدء العملية. جاري فتح المتصفح الخفي...")
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto("https://accounts.google.com/signin")
            await send_telegram_message(chat_id, "تم فتح صفحة تسجيل الدخول.")
            
            # إدخال الإيميل
            await page.fill('input[type="email"]', email)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)
            
            # إدخال الباسورد
            await page.fill('input[type="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(5000)
            
            # التحقق من 2FA
            if "challenge" in page.url or "verify" in page.url:
                await send_telegram_message(chat_id, "⚠️ مطلوب تحقق 2FA. يرجى تأكيد الدخول من هاتفك، ثم اكتب كلمة 'done' هنا.")
                user_states[chat_id] = "waiting_2fa"
                
                for _ in range(120):
                    if user_states.get(chat_id) == "2fa_done":
                        break
                    await asyncio.sleep(1)
                
                if user_states.get(chat_id) != "2fa_done":
                    await send_telegram_message(chat_id, "انتهى وقت الانتظار. تم إلغاء العملية.")
                    await browser.close()
                    return

            await send_telegram_message(chat_id, "تم تسجيل الدخول بنجاح. جاري تجهيز Play Points...")
            
            await page.goto("https://myaccount.google.com/address")
            await page.wait_for_timeout(3000)
            
            await page.goto("https://play.google.com/store")
            await page.wait_for_timeout(3000)
            
            await send_telegram_message(chat_id, "✅ تمت العملية بنجاح سيدي.")
            await browser.close()
            
        except Exception as e:
            await send_telegram_message(chat_id, f"❌ حدث خطأ: {str(e)}")
            if 'browser' in locals():
                await browser.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    webhook_endpoint = f"{WEBHOOK_URL}/webhook"
    async with httpx.AsyncClient() as client:
        await client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_endpoint}")
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"]["text"]
        
        if text == "done" and user_states.get(chat_id) == "waiting_2fa":
            user_states[chat_id] = "2fa_done"
            await send_telegram_message(chat_id, "تم استلام التأكيد. جاري الاستكمال...")
            return {"ok": True}
        
        lines = text.strip().split('\n')
        if len(lines) >= 2:
            email = lines[0].strip()
            password = lines[1].strip()
            asyncio.create_task(process_google_account(chat_id, email, password))
            await send_telegram_message(chat_id, "تم استلام البيانات. جاري البدء...")
        else:
            await send_telegram_message(chat_id, "أرسل الإيميل في سطر والباسورد في السطر التالي.")
            
    return {"ok": True}

@app.get("/")
def read_root():
    return {"status": "VANTA Bot is running"}
