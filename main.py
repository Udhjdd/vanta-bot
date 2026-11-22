from fastapi import FastAPI, Request
import httpx
import os
import asyncio
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager

BOT_TOKEN = "9032675094:AAGk8zSeWv9ewfztsAATj6_8utGZedynV44"
MY_CHAT_ID = "7306346652"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://vanta-bot-vn9e.onrender.com")

user_states = {}

async def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

async def send_telegram_photo(chat_id, photo_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as client:
        with open(photo_path, "rb") as f:
            await client.post(url, data={"chat_id": chat_id}, files={"photo": f})

async def process_google_account(chat_id, email, password):
    await send_telegram_message(chat_id, "بدء العملية سيدي. جاري فتح المتصفح الخفي...")
    
    async with async_playwright() as p:
        try:
            # استخدام خدعة تمويه مدمجة بدون مكتبات خارجية
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()
            
            await page.goto("https://accounts.google.com/", wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            try:
                await page.wait_for_selector('input[type="email"]', timeout=10000)
                await page.fill('input[type="email"]', email)
                await page.click('button:has-text("Next")')
                await page.wait_for_timeout(3000)
                
                await page.wait_for_selector('input[type="password"]', timeout=10000)
                await page.fill('input[type="password"]', password)
                await page.click('button:has-text("Next")')
                await page.wait_for_timeout(5000)
                
            except Exception as e:
                screenshot_path = f"/tmp/error_{chat_id}.png"
                await page.screenshot(path=screenshot_path)
                await send_telegram_photo(chat_id, screenshot_path)
                await send_telegram_message(chat_id, "❌ فشل في العثور على خانات الدخول. قد يكون بسبب حظر جوجل. (راجع الصورة)")
                await browser.close()
                return

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

            await send_telegram_message(chat_id, "تم تسجيل الدخول بنجاح. جاري إضافة العنوان السويسري...")
            
            await page.goto("https://myaccount.google.com/address", wait_until="networkidle")
            await page.wait_for_timeout(4000)
            
            try:
                await page.click('text="Add address"', timeout=5000)
                await page.wait_for_timeout(2000)
                await page.fill('input[aria-label="Full name"]', "Vanta User")
                await page.fill('input[aria-label="Street address"]', "Bahnhofstrasse 10")
                await page.fill('input[aria-label="Postal code"]', "8001")
                await page.fill('input[aria-label="City"]', "Zürich")
                await send_telegram_message(chat_id, "تمت محاولة إضافة العنوان.")
            except Exception as e:
                await send_telegram_message(chat_id, f"ملاحظة: لم نتمكن من إضافة العنوان تلقائياً. الخطأ: {str(e)}")

            await send_telegram_message(chat_id, "جاري التوجه لمتجر بلاي لتفعيل النقاط...")
            
            await page.goto("https://play.google.com/store/points", wait_until="networkidle")
            await page.wait_for_timeout(4000)
            
            try:
                join_btn = page.locator('button:has-text("Join")')
                if await join_btn.count() > 0:
                    await join_btn.first.click()
                    await send_telegram_message(chat_id, "تم الضغط على Join. (قد تحتاج لإضافة بطاقة دفع).")
                else:
                    await send_telegram_message(chat_id, "لم يتم العثور على زر Join. قد يكون الحساب مؤهلاً بالفعل.")
            except Exception as e:
                await send_telegram_message(chat_id, f"خطأ أثناء تفعيل النقاط: {str(e)}")
            
            await send_telegram_message(chat_id, "✅ انتهت العملية سيدي.")
            await browser.close()
            
        except Exception as e:
            await send_telegram_message(chat_id, f"❌ حدث خطأ غير متوقع: {str(e)}")
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
        chat_id = str(data["message"]["chat"]["id"])
        text = data["message"]["text"]
        if chat_id != MY_CHAT_ID:
            return {"ok": True}
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
