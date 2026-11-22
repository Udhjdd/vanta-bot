from fastapi import FastAPI, Request
import httpx
import os
import asyncio
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager
from pyvirtualdisplay import Display

BOT_TOKEN = "9032675094:AAGk8zSeWv9ewfztsAATj6_8utGZedynV44"
MY_CHAT_ID = "7306346652"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://vanta-bot-vn9e.onrender.com")

user_states = {}
display = None

async def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

async def send_telegram_photo(chat_id, photo_path, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    async with httpx.AsyncClient() as client:
        with open(photo_path, "rb") as f:
            await client.post(url, data={"chat_id": chat_id, "caption": caption}, files={"photo": f})

async def take_screenshot(page, chat_id, caption):
    screenshot_path = f"/tmp/step_{chat_id}.png"
    await page.screenshot(path=screenshot_path)
    await send_telegram_photo(chat_id, screenshot_path, caption)

async def process_google_account(chat_id, email, password):
    global display
    await send_telegram_message(chat_id, "بدء العملية سيدي. جاري تشغيل الشاشة الوهمية...")
    
    # تشغيل الشاشة الوهمية (Xvfb)
    if display is None:
        display = Display(visible=0, size=(1920, 1080))
        display.start()

    async with async_playwright() as p:
        try:
            # headless=False لأننا نستخدم شاشة وهمية
            browser = await p.chromium.launch(
                headless=False, 
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 9 Pro XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                viewport={"width": 412, "height": 915},
                is_mobile=True, has_touch=True
            )
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = await context.new_page()

            await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await take_screenshot(page, chat_id, "1. صفحة الدخول")
            
            # كتابة الإيميل ببطء
            await page.locator('input[name="identifier"]').press_sequentially(email, delay=100)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(6000)
            await take_screenshot(page, chat_id, "2. بعد إدخال الإيميل")
            
            # كتابة الباسورد
            try:
                await page.locator('input[type="password"]').first.press_sequentially(password, delay=100)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(10000)
                await take_screenshot(page, chat_id, "3. بعد إدخال الباسورد")
            except:
                await send_telegram_message(chat_id, "⚠️ فشل إدخال كلمة المرور.")
                await browser.close()
                return

            # التحقق من 2FA
            content = await page.content()
            if "2-Step Verification" in content or "Choose how you want to sign in" in content:
                await send_telegram_message(chat_id, "🔑 وصلت لشاشة التحقق! يرجى تأكيد الدخول من هاتفك الآن. اكتب 'done' بعد التأكيد.")
                await take_screenshot(page, chat_id, "4. شاشة التحقق")
                
                user_states[chat_id] = "waiting_2fa"
                for _ in range(120): # انتظار دقيقتين
                    if user_states.get(chat_id) == "2fa_done":
                        break
                    await asyncio.sleep(1)
                
                if user_states.get(chat_id) != "2fa_done":
                    await send_telegram_message(chat_id, "انتهى وقت الانتظار. تم إلغاء العملية.")
                    await browser.close()
                    return
                await page.wait_for_timeout(5000)

            # تخطي شاشة الاسترداد إذا ظهرت
            content = await page.content()
            if "Make sure you can always sign in" in content or "Add a recovery phone" in content:
                await send_telegram_message(chat_id, "🔄 ظهرت شاشة استرداد الحساب. جاري تخطيها...")
                try:
                    cancel_btn = page.locator('button:has-text("Cancel"), button:has-text("Dismiss"), button:has-text("إلغاء")').first
                    if await cancel_btn.is_visible():
                        await cancel_btn.click()
                        await page.wait_for_timeout(3000)
                except: pass

            await take_screenshot(page, chat_id, "5. بعد تسجيل الدخول")
            
            if "myaccount.google.com" in page.url or "Google Account" in content:
                await send_telegram_message(chat_id, "🎉 نجاح! تم تسجيل الدخول بنجاح. جاري إضافة العنوان السويسري...")
                
                await page.goto("https://myaccount.google.com/address", wait_until="networkidle")
                await page.wait_for_timeout(4000)
                await take_screenshot(page, chat_id, "6. صفحة العناوين")
                
                try:
                    await page.click('text="Add address"', timeout=5000)
                    await page.wait_for_timeout(2000)
                    await page.fill('input[aria-label="Full name"]', "Vanta User")
                    await page.fill('input[aria-label="Street address"]', "Bahnhofstrasse 10")
                    await page.fill('input[aria-label="Postal code"]', "8001")
                    await page.fill('input[aria-label="City"]', "Zürich")
                    await take_screenshot(page, chat_id, "7. تم إضافة العنوان")
                    await send_telegram_message(chat_id, "تمت محاولة إضافة العنوان.")
                except Exception as e:
                    await send_telegram_message(chat_id, f"ملاحظة: لم نتمكن من إضافة العنوان تلقائياً. الخطأ: {str(e)}")

                await send_telegram_message(chat_id, "جاري التوجه لمتجر بلاي لتفعيل النقاط...")
                await page.goto("https://play.google.com/store/points", wait_until="networkidle")
                await page.wait_for_timeout(4000)
                await take_screenshot(page, chat_id, "8. صفحة Play Points")
                
                try:
                    join_btn = page.locator('button:has-text("Join")')
                    if await join_btn.count() > 0:
                        await join_btn.first.click()
                        await send_telegram_message(chat_id, "تم الضغط على Join. (قد تحتاج لإضافة بطاقة دفع).")
                    else:
                        await send_telegram_message(chat_id, "لم يتم العثور على زر Join. قد يكون الحساب مؤهلاً بالفعل.")
                except Exception as e:
                    await send_telegram_message(chat_id, f"خطأ أثناء تفعيل النقاط: {str(e)}")
                
                await take_screenshot(page, chat_id, "9. النتيجة النهائية")
                await send_telegram_message(chat_id, "✅ انتهت العملية سيدي.")
            else:
                await send_telegram_message(chat_id, "⚠️ يبدو أن تسجيل الدخول لم يكتمل. راجع الصور.")

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
