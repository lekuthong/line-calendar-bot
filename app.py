@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logger.info("Request body: %s", body)
    
    try:
        handler.handle(body, signature)
        events = json.loads(body).get('events', [])
        logger.info(f"Number of events: {len(events)}")
        if not events:
            logger.info("No events in request")
        return 'OK'
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    logger.info(f"Received message: {event.message.text}")
    text = event.message.text
    
    try:
        # ดึงข้อมูลผู้ใช้
        user_profile = line_bot_api.get_profile(event.source.user_id)
        user_id = user_profile.user_id
        user_name = user_profile.display_name
        logger.info(f"Message from user: {user_name} ({user_id})")
        
        if text.startswith('/add'):
            try:
                logger.info("Processing /add command")
                parts = text.split(maxsplit=3)  # แยกเป็น 3 ส่วน: /add, date, title, description
                if len(parts) < 4:
                    raise ValueError("ข้อมูลไม่ครบถ้วน")
                
                _, date, title, description = parts
                
                # ตรวจสอบรูปแบบวันที่
                try:
                    datetime.strptime(date, '%Y-%m-%d')
                except ValueError:
                    raise ValueError("รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้รูปแบบ YYYY-MM-DD")
                
                # สร้างและส่ง Flex Message
                flex_message = event_manager.add_event(date, title, description, user_id, user_name)
                logger.info(f"Created event: {title} on {date}")
                
                # ส่งข้อความไปยังกลุ่ม
                if event.source.type == 'group':
                    line_bot_api.reply_message(event.reply_token, flex_message)
                    logger.info("Sent flex message to group")
                else:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text='กรุณาใช้คำสั่งในกลุ่มเท่านั้น')
                    )
                    logger.info("Sent 'group only' message")
                
            except ValueError as ve:
                logger.error(f"ValueError in /add command: {str(ve)}")
                error_message = TextSendMessage(
                    text=f'ข้อผิดพลาด: {str(ve)}\nกรุณาใช้: /add YYYY-MM-DD หัวข้อ รายละเอียด'
                )
                line_bot_api.reply_message(event.reply_token, error_message)
            except Exception as e:
                logger.error(f"Error handling /add command: {str(e)}")
                error_message = TextSendMessage(
                    text='เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง'
                )
                line_bot_api.reply_message(event.reply_token, error_message)
                
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง')
        )
