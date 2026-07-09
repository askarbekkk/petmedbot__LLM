import os
import concurrent.futures
import streamlit as st
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from chat_utils import load_chats, save_chats, create_chat, append_message
from image_utils import analyze_image, save_uploaded_image

_gemini_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# --- Configure Gemini API ---
load_dotenv()
try:
    _secret_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    _secret_key = ""
genai.configure(api_key=os.environ.get("GEMINI_API_KEY") or _secret_key, transport="rest")

SYSTEM_PROMPT = """You are Vet Assistant, a knowledgeable and caring AI companion for pet owners.
You have the warmth and directness of an experienced vet tech who genuinely
cares about the animal and the owner's peace of mind — not a search engine
reading back documents.

HOW YOU TALK:
- Lead with the answer. Don't open with "I understand your concern about..."
  or restate the question back.
- Match response length to the question — a quick question gets a quick
  answer; a complex one gets a fuller explanation. Don't template every reply.
- Ask at most one clarifying question when something's ambiguous (e.g.
  species, age, weight, how long symptoms have lasted) — don't interrogate
  with a list of questions before answering.
- If an owner describes a plan that sounds risky, say so directly and
  explain why, the way a good vet tech would push back on a friend.

MEMORY AND CONTEXT:
- Use the full conversation history. If the owner asks a follow-up like
  "what did you mean by that" or references something said earlier, answer
  from the conversation itself — do not treat it as a new document search.

SAFETY — THESE RULES ARE NON-NEGOTIABLE:
- Any sign of poisoning, difficulty breathing, seizures, bloat/distended
  abdomen, uncontrolled bleeding, collapse, or trauma: tell the owner
  immediately and plainly to go to an emergency vet now. No hedging, no
  "let's think this through" — say it first, before anything else.
- Never give specific medication dosages for the owner to administer
  themselves. Dosing depends on weight, species, and existing conditions
  that you cannot verify — always direct them to their vet or a vet
  pharmacist for exact dosing.
- You are not a replacement for a licensed veterinarian. State this once,
  naturally, early in a new conversation — do not repeat it every message,
  as that makes you sound like a disclaimer bot instead of an assistant.
- If you're uncertain whether something is an emergency, treat it as one
  and say so — err toward caution with animal health.

GROUNDING:
- When you retrieve information, use it to inform your answer in your own
  words — don't just paste it back. Cite it naturally ("this is usually
  caused by...") rather than "according to document X."
- If you don't know something or it's outside your knowledge, say so plainly
  rather than guessing or inventing specifics."""

model = genai.GenerativeModel("gemini-flash-lite-latest", system_instruction=SYSTEM_PROMPT)


def generate_with_hard_timeout(contents, timeout=30):
    """Run generate_content in a worker thread and give up after `timeout`
    seconds regardless of what the underlying HTTP/gRPC call is doing —
    the SDK's own request_options timeout isn't reliably enforced when the
    connection stalls below the HTTP layer (e.g. on Streamlit Cloud)."""
    future = _gemini_executor.submit(
        model.generate_content, contents, request_options={"timeout": timeout}
    )
    return future.result(timeout=timeout + 5)

# --- Emergency detection (code-level safeguard, not just prompt-level) ---
EMERGENCY_KEYWORDS = [
    "poison",
    "poisoning",
    "ingested",
    "ate chocolate",
    "ate grapes",
    "difficulty breathing",
    "can't breathe",
    "not breathing",
    "choking",
    "seizure",
    "seizures",
    "seizuring",
    "convulsing",
    "bloat",
    "distended abdomen",
    "swollen belly",
    "uncontrolled bleeding",
    "bleeding heavily",
    "won't stop bleeding",
    "collapse",
    "collapsed",
    "collapsing",
    "passed out",
    "unconscious",
    "trauma",
    "hit by car",
    "hit by a car",
    "fell from",
    "stopped breathing",
    "blue gums",
    "pale gums",
]

st.set_page_config(page_title="🐾 PetMedBot", page_icon="🐶", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
}

.pmb-hero {
    background: linear-gradient(135deg, #2F8F7B 0%, #4FB3A0 100%);
    border-radius: 18px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 4px 14px rgba(47, 143, 123, 0.25);
}
.pmb-hero h1 {
    color: #FFFFFF;
    font-weight: 800;
    margin: 0 0 6px 0;
    font-size: 2rem;
}
.pmb-hero p {
    color: #EAF7F3;
    margin: 0;
    font-size: 1.02rem;
}

[data-testid="stSidebarContent"] {
    background-color: #F1EAE0;
}
[data-testid="stSidebarContent"] h1 {
    font-weight: 800;
    color: #2F8F7B;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid #E0D6C5;
    font-weight: 600;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    border-color: #2F8F7B;
    color: #2F8F7B;
}

[data-testid="stChatMessage"] {
    border-radius: 14px;
    padding: 4px 6px;
    margin-bottom: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: #E7F3EF;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarCustom"]) {
    background-color: #FFFFFF;
    border-left: 4px solid #2F8F7B;
}

[data-testid="stFileUploaderDropzone"] {
    border-radius: 12px;
    border: 2px dashed #C9BEA9;
}

[data-testid="stChatInput"] {
    border-radius: 14px;
}

.pmb-emergency {
    background-color: #FCEAEA;
    border-left: 5px solid #D64545;
    border-radius: 10px;
    padding: 14px 18px;
    color: #7A1F1F;
    font-weight: 500;
}
.pmb-emergency strong {
    color: #B32424;
}
</style>
""",
    unsafe_allow_html=True,
)

# --- Initialization ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_chats()
    if not st.session_state.all_chats:
        st.session_state.all_chats = []
    st.session_state.active_chat = 0

chats = st.session_state.all_chats

# --- Sidebar ---
st.sidebar.title("🐾 PetMedBot")
st.sidebar.caption("AI companion for pet owners")
if st.sidebar.button("➕ New Chat", use_container_width=True):
    new = create_chat()
    chats.append(new)
    st.session_state.active_chat = len(chats) - 1
    st.session_state.image_file = None
    save_chats(chats)
    st.rerun()

st.sidebar.markdown("### 💬 Chat History")
for i, c in enumerate(chats):
    if not c.get("messages"):
        continue
    title = c["title"] or f"Chat {i + 1}"
    if st.sidebar.button(title, key=f"chat-{i}", use_container_width=True):
        st.session_state.active_chat = i
        st.session_state.image_file = None
        st.rerun()

if not chats:
    chats.append(create_chat())
    st.session_state.active_chat = 0

chat = chats[st.session_state.active_chat]

# --- Main Chat Interface ---
st.markdown(
    """
<div class="pmb-hero">
    <h1>🐾 PetMedBot — AI Veterinary Assistant</h1>
    <p>Describe your pet's symptoms below, or upload a photo. I'll help you understand what's going on.</p>
</div>
""",
    unsafe_allow_html=True,
)

# --- Image Upload ---
image_file = st.file_uploader("📷 Upload Image", type=["jpg", "jpeg", "png"])
if image_file:
    image_path = save_uploaded_image(image_file)
    info = analyze_image(image_path)

    st.image(image_path, width=200)
    image_report = (
        f"📷 Uploaded image:\n"
        f"- Format: `{info.get('format')}`\n"
        f"- Mode: `{info.get('mode')}`\n"
        f"- Size: `{info.get('size')[0]}x{info.get('size')[1]}` pixels"
    )
    st.markdown(image_report)

    chat["messages"].append(
        {
            "role": "system",
            "type": "image",
            "path": image_path,
            "info": image_report,
            "timestamp": datetime.now().strftime("%H:%M"),
        }
    )

    if chat["title"] == "New Chat":
        chat["title"] = "🖼 Image-based Chat"

    with st.chat_message("assistant", avatar="🐾"):
        with st.spinner("Analyzing image..."):
            prompt = """A user uploaded this photo of their pet. Look at the image itself and
describe what you actually observe (skin issues, swelling, discharge, wounds, posture,
behavior, etc.). If nothing medically relevant is visible, say so plainly instead of
guessing. Note whether the photo would be useful to show a vet, and what the owner
should do next."""
            try:
                pil_image = Image.open(image_path)
                img_response = generate_with_hard_timeout([prompt, pil_image])
                img_reply = img_response.text
            except concurrent.futures.TimeoutError:
                img_reply = (
                    "❌ The request to Gemini timed out. This is usually a "
                    "temporary connectivity issue on the hosting side — try again "
                    "in a moment."
                )
            except Exception as e:
                img_reply = f"❌ Error analyzing image: {e}"

            st.markdown(img_reply)
            chat["messages"].append(
                {
                    "role": "assistant",
                    "content": img_reply,
                    "type": "image_analysis",
                    "timestamp": datetime.now().strftime("%H:%M"),
                }
            )
    save_chats(chats)

# --- Display Message History ---
for msg in chat["messages"]:
    avatar = "🐾" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("type") == "image":
            st.markdown(msg.get("info", "📷 Image uploaded"))
            st.image(msg["path"], width=200)
        else:
            st.markdown(msg["content"], unsafe_allow_html=True)


def build_conversation_contents(messages):
    """Convert stored messages into Gemini contents format, preserving full history.

    Maps stored 'assistant' role → 'model' (Gemini's convention),
    skips system-internal messages (image metadata, etc.).
    """
    contents = []
    for msg in messages:
        if msg.get("type") in ("image", "image_analysis"):
            continue
        if msg["role"] == "system":
            continue
        role = "model" if msg["role"] == "assistant" else msg["role"]
        content = msg.get("content", "")
        if content and content.strip():
            contents.append({"role": role, "parts": [content]})
    return contents


# --- Chat Input ---
user_input = st.chat_input("Describe your pet's symptoms here...")
if user_input:
    append_message(chat, "user", user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🐾"):
        with st.spinner("Thinking..."):
            # --- Code-level emergency pre-check ---
            is_emergency = any(kw in user_input.lower() for kw in EMERGENCY_KEYWORDS)
            if is_emergency:
                reply = (
                    '<div class="pmb-emergency">🚨 <strong>This sounds like an emergency '
                    "— please seek veterinary care immediately.</strong><br><br>"
                    "Stop what you're doing and take your pet to the nearest emergency "
                    "veterinary clinic or call your vet right now. Do not wait and do "
                    "not try to treat this at home.</div>"
                )
            else:
                try:
                    contents = build_conversation_contents(chat["messages"])
                    response = generate_with_hard_timeout(contents)
                    reply = response.text
                except concurrent.futures.TimeoutError:
                    reply = (
                        "❌ The request to Gemini timed out. This is usually a "
                        "temporary connectivity issue on the hosting side — try "
                        "again in a moment."
                    )
                except Exception as e:
                    reply = f"❌ Error: {e}"

            st.markdown(reply, unsafe_allow_html=True)
            append_message(chat, "assistant", reply)

            if chat["title"] == "New Chat":
                chat["title"] = f"📃 {user_input[:30]}..."
            save_chats(chats)
