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
        res = await client.post(url, json={"chat_id": chat_id, "text": text})
        return res.json()

async def edit_telegram_message(chat_id, message_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "message_id": message_id, "text": text})

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
    await send_telegram_message(chat_id, "بدء العملية سيدي. جاري تشغيل الشاشة الوهمية والاتصال بـ WARP...")
    
    if display is None:
        display = Display(visible=0, size=(1920, 1080))
        display.start()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=False, 
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            
            # إعدادات المتصفح (بدون بروكسي، لأن WARP يعمل على مستوى النظام)
            context_args = {
                "user_agent": "Mozilla/5.0 (Linux; Android 13; Pixel 9 Pro XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "viewport": {"width": 412, "height": 915},
                "is_mobile": True, 
                "has_touch": True,
                "locale": "en-US"
            }

            context = await browser.new_context(**context_args)
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = await context.new_page()

            # التحقق من الـ IP
            try:
                await page.goto("https://ipinfo.io/json", wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)
                await take_screenshot(page, chat_id, "0. فحص الـ IP")
            except:
                await send_telegram_message(chat_id, "⚠️ فشل في فحص الـ IP، سنكمل...")
            
            await page.goto("https://accounts.google.com/signin?hl=en", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await take_screenshot(page, chat_id, "1. صفحة الدخول")
            
            await page.locator('input[name="identifier"]').press_sequentially(email, delay=100)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(6000)
            await take_screenshot(page, chat_id, "2. بعد إدخال الإيميل")
            
            try:
                await page.locator('input[type="password"]').first.press_sequentially(password, delay=100)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(10000)
                await take_screenshot(page, chat_id, "3. بعد إدخال الباسورد")
            except:
                await send_telegram_message(chat_id, "⚠️ فشل إدخال كلمة المرور.")
                await browser.close()
                return

            # 4. التحقق الذكي من 2FA مع عداد تنازلي
            content = await page.content()
            if "2-Step Verification" in content or "Choose how you want to sign in" in content or "التحقق بخطوتين" in content:
                await send_telegram_message(chat_id, "🔑 وصلت لشاشة التحقق! جاري الضغط على Tap Yes...")
                await take_screenshot(page, chat_id, "4. شاشة التحقق")
                
                try:
                    tap_yes = page.locator(':text-matches("Tap Yes|phone or tablet|الضغط على نعم")').first
                    if await tap_yes.is_visible():
                        await tap_yes.click()
                        
                        msg_res = await send_telegram_message(chat_id, "📲 **افتح هاتفك الآن واضغط على إشعار جوجل لتأكيد الدخول.**\nالوقت المتبقي: 30 ثانية...")
                        msg_id = msg_res.get("result", {}).get("message_id")
                        
                        logged_in = False
                        for i in range(30, 0, -1):
                            await page.wait_for_timeout(1000)
                            current_url = page.url
                            
                            if "myaccount.google.com" in current_url:
                                logged_in = True
                                break
                                
                            try:
                                current_content = await page.content()
                                if "Make sure you can always sign in" in current_content or "ضمان إمكانية تسجيل الدخول" in current_content:
                                    logged_in = True
                                    break
                            except Exception:
                                pass
                                
                            if i % 5 == 0 or i <= 5:
                                if msg_id:
                                    await edit_telegram_message(chat_id, msg_id, f"📲 **افتح هاتفك الآن واضغط على إشعار جوجل لتأكيد الدخول.**\nالوقت المتبقي: {i} ثانية...")
                                    
                        if not logged_in:
                            await send_telegram_message(chat_id, "❌ انتهت الـ 30 ثانية ولم يتم تأكيد الدخول من هاتفك. تم إلغاء العملية.")
                            await browser.close()
                            return
                except Exception as e:
                    await send_telegram_message(chat_id, f"⚠️ فشل في عملية 2FA: {str(e)}")
                    await browser.close()
                    return

            # 5. تخطي شاشة الاسترداد (Recovery Info)
            try:
                content = await page.content()
                if "Make sure you can always sign in" in content or "ضمان إمكانية تسجيل الدخول" in content:
                    await send_telegram_message(chat_id, "🔄 تم الدخول بنجاح! جاري تخطي شاشة ضمان الدخول...")
                    try:
                        cancel_btn = page.locator('button:has-text("Cancel"), button:has-text("إلغاء"), button:has-text("Dismiss")').first
                        if await cancel_btn.is_visible():
                            await cancel_btn.click()
                            await page.wait_for_timeout(3000)
                    except: pass
                    await page.go_back()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

            await take_screenshot(page, chat_id, "5. النتيجة النهائية")
            await send_telegram_message(chat_id, "🎉 **نجاح! تم تسجيل الدخول بالكامل سيدي. البوت جاهز للخطوات التالية.**")
            
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
