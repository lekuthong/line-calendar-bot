from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage
)
from datetime import datetime, timedelta
import json
import os
import logging
import requests.exceptions
from queue import Queue
from threading import Thread

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# สร้าง Flask app
app = Flask(__name__)

# ใช้ Environment Variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise Exception('กรุณาตั้งค่า LINE_CHANNEL_ACCESS_TOKEN และ LINE_CHANNEL_SECRET')

# สร้าง LINE API instance พร้อม timeout
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN, timeout=30)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# สร้าง message queue
message_queue = Queue()

def process_message_queue():
    while True:
        if not message_queue.empty():
            msg_data = message_queue.get()
            try:
                if msg_data['type'] == 'push':
                    line_bot_api.push_message(
                        msg_data['user_id'],
                        msg_data['message']
                    )
                elif msg_data['type'] == 'reply':
                    line_bot_api.reply_message(
                        msg_data['reply_token'],
                        msg_data['message']
                    )
                logger.info(f"Successfully processed queued message for {msg_data['user_id']}")
            except Exception as e:
                logger.error(f"Error processing queued message: {str(e)}")
            finally:
                message_queue.task_done()

# เริ่ม worker thread
worker_thread = Thread(target=process_message_queue, daemon=True)
worker_thread.start()

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
                        "text": event['title'] or "ไม่มีหัวข้อ",
                        "weight": "bold",
                        "size": "xxl",
                        "margin": "md",
                        "wrap": True
                    },
                    {
                        "type": "text",
                        "text": event['description'] or "ไม่มีรายละเอียด",
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
                                        "text": event['creator_name'] or "ไม่ระบุ",
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

def handle_line_bot_error(e):
    if isinstance(e, LineBotApiError):
        if e.status_code == 429:
            return "ระบบกำลังมีการใช้งานมาก กรุณาลองใหม่ในภายหลัง"
        elif e.status_code == 500:
            return "เซิร์ฟเวอร์ LINE ขัดข้อง กรุณาลองใหม่ภายหลัง"
    return "เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง"

def clear_pending_messages(user_id):
    try:
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text="กำลังรีเซ็ตระบบข้อความ...")
        )
        return True
    except Exception as e:
        logger.error(f"Error clearing messages: {str(e)}")
        return False

event_manager = EventManager()

@app.route("/health")
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route("/")
def home():
    return "LINE Bot is running!"

@app.route("/reset", methods=['POST'])
def reset_messages():
    user_id = request.json.get('user_id')
    if user_id:
        success = clear_pending_messages(user_id)
        return jsonify({'success': success})
    return jsonify({'success': False, 'error': 'No user_id provided'})

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
    logger.info(f"Received message: {text}")
    
    try:
        if text.startswith('/add'):
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
                logger.info(f"Created event: {title}")
                
                try:
                    if event.delivery_context.is_redelivery:
                        logger.info("Redelivery detected, using push_message")
                        message_queue.put({
                            'type': 'push',
                            'user_id': event.source.user_id,
                            'message': flex_message
                        })
                    else:
                        logger.info("Normal delivery, using reply_message")
                        message_queue.put({
                            'type': 'reply',
                            'reply_token': event.reply_token,
                            'user_id': event.source.user_id,
                            'message': flex_message
                        })
                    logger.info("Message queued successfully")
                except Exception as send_error:
                    logger.error(f"Error queuing message: {str(send_error)}")
                    raise
                
            except ValueError as ve:
                error_message = TextSendMessage(
                    text=f'ข้อผิดพลาด: {str(ve)}\nกรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด'
                )
                line_bot_api.reply_message(event.reply_token, error_message)
            except Exception as e:
                logger.error(f"Error handling /add command: {str(e)}")
                error_message = TextSendMessage(
                    text=handle_line_bot_error(e)
                )
                line_bot_api.reply_message(event.reply_token, error_message)
                
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        error_message = TextSendMessage(text=handle_line_bot_error(e))
        line_bot_api.reply_message(event.reply_token, error_message)

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 10000))
        app.run(host='0.0.0.0', port=port, threaded=True)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
