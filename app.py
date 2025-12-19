import streamlit as st
import requests
import time

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000"
st.set_page_config(
    page_title="EndoMatch AI", 
    page_icon="🧬", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (To make it look like a real app) ---
st.markdown("""
<style>
    /* Hide standard Streamlit header/footer for clean look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Style the Chat Input to look floating */
    .stChatInput {
        padding-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm Dr. EndoMatch. 🧬\n\nI can screen patients against **1,000+ active clinical trials**. Please paste a patient case or clinical note to begin."}
    ]

# --- SIDEBAR (Like ChatGPT History) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3004/3004458.png", width=50)
    st.title("EndoMatch")
    st.caption("Enterprise Edition v2.0")
    
    st.markdown("---")
    
    # "New Chat" Button
    if st.button("➕ New Patient Case", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("### 🕒 Recent History")
    st.info("Session History is cleared on refresh in this demo.")
    
    st.markdown("---")
    st.markdown("**Backend Status:**")
    try:
        if requests.get(API_URL).status_code == 200:
            st.success("🟢 Online (FastAPI)")
        else:
            st.error("🔴 Offline")
    except:
        st.error("🔴 Connection Failed")

# --- MAIN CHAT WINDOW ---

# Display Chat History
for msg in st.session_state.messages:
    # Choose Avatars: User=Person, Assistant=DNA Icon
    avatar = "👤" if msg["role"] == "user" else "🧬"
    
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- USER INPUT AREA ---
if prompt := st.chat_input("Message EndoMatch..."):
    
    # 1. Display User Message Immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # 2. Fetch Response from Backend
    with st.chat_message("assistant", avatar="🧬"):
        message_placeholder = st.empty()
        full_response = ""
        
        # UI "Thinking" Indicator
        with st.spinner("Searching protocols & analyzing eligibility..."):
            try:
                # API Call to your FastAPI Backend
                payload = {"summary": prompt}
                response = requests.post(f"{API_URL}/match", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    matches = data.get("matches", [])
                    
                    if not matches:
                        full_response = "I searched the database but found **no matching trials** for this specific profile."
                    else:
                        full_response = f"### 🔍 Found {len(matches)} Potential Matches\n\n"
                        for match in matches:
                            # Icon Logic
                            status = match['analysis'][:10].upper()
                            icon = "✅" if "YES" in status else "❌" if "NO" in status else "⚠️"
                            
                            # Clean Card Layout
                            full_response += (
                                f"#### {icon} {match['title']}\n"
                                f"**Protocol ID:** [{match['nct_id']}]({match['url']}) | **Phase:** {match['phase']}\n\n"
                                f"> {match['analysis']}\n\n"
                                f"---\n"
                            )
                else:
                    full_response = f"⚠️ **Server Error:** {response.text}"

            except Exception as e:
                full_response = f"❌ **Connection Error:** Could not reach the AI server.\n\n`{e}`"

        # 3. Stream the Response (ChatGPT Typing Effect)
        # We simulate streaming because the backend returns full JSON
        current_text = ""
        for chunk in full_response.split(" "): # Split by words for smoother effect
            current_text += chunk + " "
            message_placeholder.markdown(current_text + "▌")
            time.sleep(0.04) # Adjust typing speed here
            
        message_placeholder.markdown(full_response)
        
        # Save Assistant Response to History
        st.session_state.messages.append({"role": "assistant", "content": full_response})