import json
import uuid
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db_chat_history.json")

def load_chats():
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        return []
    try:
        with open(DB_PATH, "r") as f:
            chats = json.load(f)
            # Filter out completely empty chats
            return [chat for chat in chats if chat.get("messages")]
    except json.JSONDecodeError:
        return []

def save_chats(chats):
    # Only save non-empty chats
    valid_chats = [c for c in chats if c.get("messages")]
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(valid_chats, f, indent=4)

def create_chat(title="New Chat"):
    return {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title,
        "messages": []
    }

def append_message(chat, role, content):
    chat["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M")
    })
