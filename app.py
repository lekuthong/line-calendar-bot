from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage,
    FlexSendMessage, BubbleContainer,
    GroupEventMessage
)
from datetime import datetime, timedelta
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN'
LINE_CHANNEL_SECRET = 'YOUR_CHANNEL_SECRET'

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
        return self.create_group_tab_message(date, event)

    def create_group_tab_message(self, date, event):
        return {
            "type": "group_event",
            "title": event['title'],
            "description": event['description'],
            "date": date,
            "creator": event['creator_name'],
            "content": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": event['title'],
                            "weight": "bold",
                            "size": "xl"
                        },
                        {
                            "type": "text",
                            "text": event['description'],
                            "margin": "md",
                            "wrap": True
                        },
                        {
                            "type": "text",
                            "text": f"วันที่: {date}",
                            "margin": "md",
                            "size": "sm",
                            "color": "#888888"
                        },
                        {
                            "type": "text",
                            "text": f"สร้างโดย: {event['creator_name']}",
                            "margin": "sm",
                            "size": "sm",
                            "color": "#888888"
                        }
                    ]
                }
            }
        }

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
            
            # สร้างกิจกรรมในแถบกิจกรรมกลุ่ม
            group_event = event_manager.add_event(date, title, description, user_id, user_name)
            
            # ส่ง Group Event Message
            line_bot_api.push_message(
                event.source.group_id,
                GroupEventMessage(**group_event)
            )
            
        except Exception as e:
            # ส่งข้อความผิดพลาดแบบส่วนตัวไปยังผู้สร้างกิจกรรม
            line_bot_api.push_message(
                user_id,
                TextMessage(text='รูปแบบคำสั่งไม่ถูกต้อง กรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด')
            )

if __name__ == "__main__":
    app.run()
