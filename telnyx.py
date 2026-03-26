from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhook")
async def telnyx_webhook(request: Request):
    data = await request.json()
    print("Incoming webhook:", data)

    return {"status": "ok"}
