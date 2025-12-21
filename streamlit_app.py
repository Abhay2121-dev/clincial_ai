import streamlit as st
import requests
import time
import os

# --- CONFIGURATION ---
# Use environment variable for API URL, fallback to local for development
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="EndoMatch AI", 
    page_icon="🧬", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stChatInput {
        padding-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! I'm Dr. EndoMatch. 🧬\n\nI can screen patients against **clinical trials** for endometriosis. Please paste a patient case or clinical note to begin."}
    ]

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3004/3004458.png", width=50)
    st.title("EndoMatch")
    st.caption("Clinical Trial Matcher v2.0")
    
    st.markdown("---")
    
    if st.button("➕ New Patient Case", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("### 🕒 Recent History")
    st.info("Session history cleared on refresh")
    
    st.markdown("---")
    st.markdown("**Backend Status:**")
    try:
        health_check = requests.get(f"{API_URL}/", timeout=5)
        if health_check.status_code == 200:
            st.success("🟢 API Online")
        else:
            st.error("🔴 API Offline")
    except:
        st.error("🔴 Connection Failed")
        st.caption(f"Trying: {API_URL}")

# --- MAIN CHAT WINDOW ---
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "🧬"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- USER INPUT ---
if prompt := st.chat_input("Message EndoMatch..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🧬"):
        message_placeholder = st.empty()
        full_response = ""
        
        with st.spinner("Searching protocols & analyzing eligibility..."):
            try:
                payload = {"summary": prompt}
                response = requests.post(f"{API_URL}/match", json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    matches = data.get("matches", [])
                    
                    if not matches:
                        full_response = "I searched the database but found **no matching trials** for this profile."
                    else:
                        full_response = f"### 🔍 Found {len(matches)} Potential Matches\n\n"
                        for match in matches:
                            status = match['analysis'][:10].upper()
                            icon = "✅" if "YES" in status else "❌" if "NO" in status else "⚠️"
                            
                            full_response += (
                                f"#### {icon} {match['title']}\n"
                                f"**Protocol ID:** [{match['nct_id']}]({match['url']}) | **Phase:** {match['phase']}\n\n"
                                f"> {match['analysis']}\n\n"
                                f"---\n"
                            )
                else:
                    full_response = f"⚠️ **Server Error ({response.status_code}):** {response.text[:200]}"

            except requests.exceptions.Timeout:
                full_response = "⏱️ **Timeout Error:** The request took too long. Please try again."
            except requests.exceptions.ConnectionError:
                full_response = f"❌ **Connection Error:** Cannot reach API at {API_URL}"
            except Exception as e:
                full_response = f"❌ **Error:** {str(e)}"

        # Stream response
        current_text = ""
        for chunk in full_response.split(" "):
            current_text += chunk + " "
            message_placeholder.markdown(current_text + "▌")
            time.sleep(0.04)
            
        message_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
