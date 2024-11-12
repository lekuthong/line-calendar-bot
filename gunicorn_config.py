# gunicorn_config.py
bind = "0.0.0.0:10000"
workers = 2  # ปรับลดจำนวน workers เนื่องจากเป็น free tier
worker_class = "sync"
timeout = 300  # เพิ่ม timeout เป็น 5 นาที
keepalive = 2
