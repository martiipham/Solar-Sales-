import time
import json
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.post("/api/agents/calls")
async def create_agent_call(data):
    try:
        # Simulate external API call with retry logic and exception handling
        attempts = 0
        max_attempts = 5
        delay = 1
        while attempts < max_attempts:
            try:
                response = await external_api_call(data)
                return {"message": "Call created successfully", "data": response}
            except Exception as e:
                print(f"Attempt {attempts + 1} failed with error: {e}")
                time.sleep(delay)
                attempts += 1
                delay *= 2
        raise HTTPException(status_code=500, detail="Failed to create call after retries")
        
    except Exception as e:
        print(f"Failed to create agent call: {e}")
        return {"message": "Failed to create call", "error": str(e)}

async def external_api_call(data):
    # Simulate external API call
    return data

@app.post("/api/billing/webhook")
async def handle_stripe_webhook(event):
    try:
        # Simulate webhook handling with exception handling
        validated_event = validate_webhook_signature(event)
        processed_data = process_webhook_data(validated_event)
        return {"message": "Webhook processed successfully", "data": processed_data}
    
    except Exception as e:
        print(f"Failed to handle Stripe webhook: {e}")
        return {"message": "Failed to process webhook", "error": str(e)}

def validate_webhook_signature(event):
    # Simulate signature validation
    if 'some_key' in event:
        return event
    else:
        raise Exception("Invalid webhook signature")

def process_webhook_data(data):
    # Simulate data processing
    processed_data = {"status": "Processed", "data": data}
    return processed_data

