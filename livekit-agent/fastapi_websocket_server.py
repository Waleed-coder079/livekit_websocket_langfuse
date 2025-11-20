# fastapi_server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
import os
from dotenv import load_dotenv

# ✅ Load environment
load_dotenv(".env")

# ✅ Import Langfuse with version check
LANGFUSE_ENABLED = False
langfuse = None

try:
    from langfuse import Langfuse
    
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "pk-lf-7025f9e7-49ef-4a14-b1c0-1fb991a1998b"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", "sk-lf-80725aec-4448-44e6-b84f-0294afe2d08b"),
        # public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        # secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    )
    
    # Check if it has the trace method (newer versions)
    if hasattr(langfuse, 'trace') and langfuse.auth_check():
        LANGFUSE_ENABLED = True
        print("✅ Langfuse connected (v2.x with trace support)")
    elif langfuse.auth_check():
        LANGFUSE_ENABLED = True
        print("✅ Langfuse connected (legacy version)")
    else:
        print("⚠️ Langfuse auth failed")
except Exception as e:
    print(f"⚠️ Langfuse disabled: {e}")

app = FastAPI()

@app.get("/")
async def root():
    return {
        "status": "FastAPI WebSocket Server Running",
        "endpoint": "/ws",
        "langfuse": "enabled" if LANGFUSE_ENABLED else "disabled"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ Client connected")
    
    # ✅ Create session trace (only if supported)
    session_trace = None
    if LANGFUSE_ENABLED and langfuse and hasattr(langfuse, 'trace'):
        try:
            session_trace = langfuse.trace(
                name="fastapi-websocket-session",
                metadata={"connection": "websocket"}
            )
        except Exception as e:
            print(f"⚠️ Langfuse trace failed: {e}")
    
    try:
        message_count = 0
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_count += 1
            print(f"[FastAPI WS] Received: {data}")
            
            # ✅ Create generation for each message (only if trace exists)
            generation = None
            if session_trace and hasattr(session_trace, 'generation'):
                try:
                    generation = session_trace.generation(
                        name="websocket-processing",
                        model="fastapi-custom",
                        input=data,
                        metadata={"message_number": message_count}
                    )
                except Exception as e:
                    print(f"⚠️ Langfuse generation failed: {e}")
            
            # Process message
            response = f"FastAPI processed: {data}"
            
            # ✅ End generation (only if it exists)
            if generation and hasattr(generation, 'end'):
                try:
                    generation.end(output=response)
                except Exception as e:
                    print(f"⚠️ Langfuse end failed: {e}")
            
            # Send response
            await websocket.send_text(response)
            print(f"[FastAPI WS] Sent: {response}")
            
    except WebSocketDisconnect:
        print("❌ Client disconnected")
        
        # ✅ Update session trace (only if it exists)
        if session_trace and hasattr(session_trace, 'update'):
            try:
                session_trace.update(
                    output={"total_messages": message_count, "status": "disconnected"}
                )
            except Exception as e:
                print(f"⚠️ Langfuse update failed: {e}")
        
        # ✅ Flush (only if langfuse exists)
        if LANGFUSE_ENABLED and langfuse and hasattr(langfuse, 'flush'):
            try:
                langfuse.flush()
            except Exception as e:
                print(f"⚠️ Langfuse flush failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting FastAPI WebSocket Server...")
    print(f"🔍 Langfuse: {'enabled' if LANGFUSE_ENABLED else 'disabled'}")
    uvicorn.run(app, host="0.0.0.0", port=8080)