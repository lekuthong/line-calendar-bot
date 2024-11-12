from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage
)
from datetime import datetime, timedelta
import json
import os
import logging

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ใช้ Environment Variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise Exception('กรุณาตั้งค่า LINE_CHANNEL_ACCESS_TOKEN และ LINE_CHANNEL_SECRET ใน Environment Variables')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

class EventManager:
    def __init__(self):
        self.events = {}
        self.logger = logging.getLogger(__name__)
    
    def add_event(self, date, title, description, creator_id, creator_name):
        try:
            if date not in self.events:
                self.events[date] = []
            
            event = {
                'title': title,
                'description': description,
                'creator_id': creator_id,
                'creator_name': creator_name,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.events[date].append(event)
            self.logger.info(f"เพิ่มกิจกรรมสำเร็จ: {title} วันที่ {date}")
            
            return self.create_flex_message(date, event)
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการเพิ่มกิจกรรม: {str(e)}")
            raise

    def create_flex_message(self, date, event):
        flex_content = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✨ กิจกรรมใหม่",
                        "weight": "bold",
                        "color": "#1DB446",
                        "size": "sm"
                    },
                    {
                        "type": "text",
                        "text": event['title'],
                        "weight": "bold",
                        "size": "xxl",
                        "margin": "md",
                        "wrap": True
                    },
                    {
                        "type": "text",
                        "text": event['description'],
                        "size": "md",
                        "color": "#666666",
                        "margin": "sm",
                        "wrap": True
                    },
                    {
                        "type": "separator",
                        "margin": "xxl"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "วันที่",
                                        "size": "sm",
                                        "color": "#888888",
                                        "flex": 1
                                    },
                                    {
                                        "type": "text",
                                        "text": date,
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 2
                                    }
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "ผู้สร้าง",
                                        "size": "sm",
                                        "color": "#888888",
                                        "flex": 1
                                    },
                                    {
                                        "type": "text",
                                        "text": event['creator_name'],
                                        "size": "sm",
                                        "color": "#111111",
                                        "flex": 2
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        return FlexSendMessage(
            alt_text=f"กิจกรรมใหม่: {event['title']}",
            contents=flex_content
        )

event_manager = EventManager()

# Health check endpoint
@app.route("/health")
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route("/")
def home():
    return "LINE Bot is running!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logger.info("Request body: %s", body)
    
    try:
        handler.handle(body, signature)
        return 'OK'
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    
    try:
        # ดึงข้อมูลผู้ใช้
        user_profile = line_bot_api.get_profile(event.source.user_id)
        user_id = user_profile.user_id
        user_name = user_profile.display_name
        
        if text.startswith('/add'):
            try:
                _, date, title, *desc = text.split()
                description = ' '.join(desc)
                
                # ตรวจสอบรูปแบบวันที่
                try:
                    datetime.strptime(date, '%Y-%m-%d')
                except ValueError:
                    raise ValueError("รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้รูปแบบ YYYY-MM-DD")
                
                # สร้างและส่ง Flex Message
                flex_message = event_manager.add_event(date, title, description, user_id, user_name)
                
                # ส่งข้อความไปยังกลุ่ม
                if event.source.type == 'group':
                    line_bot_api.reply_message(event.reply_token, flex_message)
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='กรุณาใช้คำสั่งในกลุ่มเท่านั้น')
                    )
                
            except ValueError as ve:
                error_message = TextSendMessage(
                    text=f'ข้อผิดพลาด: {str(ve)}\nกรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด'
                )
                line_bot_api.reply_message(event.reply_token, error_message)
            except Exception as e:
                logger.error(f"Error handling /add command: {str(e)}")
                error_message = TextSendMessage(
                    text='รูปแบบคำสั่งไม่ถูกต้อง\nกรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด'
                )
                line_bot_api.reply_message(event.reply_token, error_message)
                
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง')
        )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port)
