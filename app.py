from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage
)
from datetime import datetime, timedelta
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = 'df6f9bbeb2bc9974136e7472e1766ebe'
LINE_CHANNEL_SECRET = 'HFIYFXcVSxi8fBDOXyt424XGKNHHjv6llGdnMCudwRxqfCbWGvH7AYEFmXUZ7kFtu8mXbcm0o8d87KgCamxzBVP3sTj+qSscSGZIBfq2u5JdlwbejkjyVNKUkzVLy0UJ76dPdHwTBIlicebuc7GEXgdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

class EventManager:
    def __init__(self):
        self.events = {}
    
    def add_event(self, date, title, description, creator_id, creator_name):
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
        return self.create_flex_message(date, event)

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

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    
    # ดึงข้อมูลผู้ใช้
    user_profile = line_bot_api.get_profile(event.source.user_id)
    user_id = user_profile.user_id
    user_name = user_profile.display_name
    
    if text.startswith('/add'):
        try:
            _, date, title, *desc = text.split()
            description = ' '.join(desc)
            
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
            
        except Exception as e:
            # ส่งข้อความผิดพลาดแบบส่วนตัว
            error_message = TextSendMessage(
                text='รูปแบบคำสั่งไม่ถูกต้อง\nกรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด'
            )
            line_bot_api.reply_message(event.reply_token, error_message)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
