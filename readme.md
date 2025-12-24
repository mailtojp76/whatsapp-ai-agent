
# WhatsApp Cloud API Webhook (Python + FastAPI + Render)

## Deploy on Render
1. Upload this repo to GitHub
2. Create **New Web Service** on Render
3. Use:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port 10000`
4. Add Environment Variables:
   - VERIFY_TOKEN=your_verify_token
   - LOG_LEVEL=INFO

## Webhook URL
https://<your-app>.onrender.com/webhook

## Health Check
/health

## Logs
View logs directly in Render dashboard.
