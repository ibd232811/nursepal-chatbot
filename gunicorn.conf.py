import os
from dotenv import load_dotenv

print("Loading Gunicorn configuration...")
# Load environment variables
load_dotenv()

bind = f"{os.getenv('HOST', '127.0.0.1')}:{os.getenv('PORT', '9000')}"
workers = int(os.getenv('WORKERS', '2'))  # Reduced for ASGI workers
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv('TIMEOUT', '600'))
accesslog = os.getenv('ACCESS_LOG', 'access.log')
errorlog = os.getenv('ERROR_LOG', 'error.log')
capture_output = True
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
preload_app = True
