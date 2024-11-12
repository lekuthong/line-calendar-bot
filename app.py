from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, ImageMessage
)
from datetime import datetime, timedelta
import os
import logging
from dotenv import load_dotenv

# โหลด environment variables
load_dotenv()

# ตั้งค่า logging ให้ละเอียดขึ้น
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# สร้าง Flask app
app = Flask(__name__)

# ใช้ Environment Variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    logger.error('Missing LINE API credentials')
    raise Exception('กรุณาตั้งค่า LINE_CHANNEL_ACCESS_TOKEN และ LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# เพิ่ม route สำหรับหน้าแรก
@app.route("/")
def home():
    logger.info("Root route accessed")
    return "Line Calendar Bot is running!"

# เพิ่ม route สำหรับ health check
@app.route("/health")
def health():
    logger.info("Health check route accessed")
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    logger.info("Request body: %s", body)
    
    if not signature:
        logger.error("No X-Line-Signature found in headers")
        abort(400, description="X-Line-Signature is missing")

    try:
        handler.handle(body, signature)
        return 'OK'
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400, description="Invalid signature")
    except Exception as e:
        logger.error("Unexpected error in callback: %s", str(e))
        return str(e), 500

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    logger.info(f"Received message: {text}")
    
    try:
        if text.startswith('/add'):
            process_add_command(event)
        elif text == '/today':
            process_today_command(event)
        elif text == '/upcoming':
            process_upcoming_command(event)
        elif text == '/help':
            show_help_message(event)
        else:
            # เพิ่มการตอบกลับเมื่อไม่ตรงกับคำสั่งใดๆ
            show_help_message(event)
            
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง')
        )

def process_add_command(event):
    text = event.message.text
    logger.info(f"Processing add command: {text}")
    try:
        parts = text.split(' ', 2)
        if len(parts) < 3:
            raise ValueError("ข้อมูลไม่ครบถ้วน")
        
        _, date, title_and_desc = parts
        title_parts = title_and_desc.split(' ', 1)
        title = title_parts[0]
        description = title_parts[1] if len(title_parts) > 1 else ""
        
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้รูปแบบ YYYY-MM-DD")
        
        user_profile = line_bot_api.get_profile(event.source.user_id)
        user_id = user_profile.user_id
        user_name = user_profile.display_name
        
        flex_message = event_manager.add_event(date, title, description, user_id, user_name)
        line_bot_api.reply_message(event.reply_token, flex_message)
        logger.info(f"Successfully added event: {title}")
        
    except ValueError as ve:
        logger.error(f"Validation error in add command: {str(ve)}")
        error_message = TextSendMessage(
            text=f'ข้อผิดพลาด: {str(ve)}\nกรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด'
        )
        line_bot_api.reply_message(event.reply_token, error_message)

def show_help_message(event):
    help_text = """📝 คำสั่งที่ใช้ได้:
/add YYYY-MM-DD หัวข้อ รายละเอียด - เพิ่มกิจกรรมใหม่
/today - ดูกิจกรรมวันนี้
/upcoming - ดูกิจกรรมที่กำลังจะมาถึง
/help - แสดงคำสั่งที่ใช้ได้

ตัวอย่าง:
/add 2024-11-20 ประชุมทีม การประชุมสรุปงานประจำเดือน"""
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=help_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # เพิ่ม logging เมื่อเริ่มต้นแอพ
    logger.info(f"Starting application on port {port}")
    logger.info(f"LINE Bot credentials configured: {bool(LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET)}")
    
    app.run(host='0.0.0.0', port=port)
