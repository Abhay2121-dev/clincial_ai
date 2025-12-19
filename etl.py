import sys
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import mlflow
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from google.genai.errors import ClientError
from google import genai

# --- WINDOWS FIX ---
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
app = FastAPI(title="EndoMatch API", version="2.5-Parallel")

# --- CONFIGURATION ---
mlflow.set_tracking_uri("file:./mlruns")
mlflow.set_experiment("EndoMatch_Production")
# Disable autolog to prevent Windows threading conflicts
# mlflow.langchain.autolog() 

vector_db = None
embeddings = None
llm = None

@app.on_event("startup")
def load_resources():
    global vector_db, embeddings, llm
    print("Loading AI Models...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    try:
        vector_db = FAISS.load_local("faiss_production_index", embeddings, allow_dangerous_deserialization=True)
        print("✅ Database Loaded.")
    except:
        print("❌ Database NOT found.")
    
    # Use Flash model for speed
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-09-2025",
        temperature=0,
        google_api_key= "AIzaSyD1NhGTEXax5Pd_WB0hjQt-pKj9CfrMwus"
    )

@app.get("/")
def home():
    return {"status": "online", "service": "EndoMatch Parallel API"}

@mlflow.trace(name="FAISS_Retrieve")
def retrieve_trials(query: str, k: int = 4):
    if not vector_db: return []
    # Strict US Filter
    return vector_db.similarity_search(
        query, k=k,
        filter=lambda metadata: metadata.get("is_us_trial") is True
    )

# --- ASYNC RETRY WRAPPER ---
@retry(
    retry=retry_if_exception_type((ClientError, ChatGoogleGenerativeAIError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5)
)
async def async_generate_audit(prompt):
    # CRITICAL: Use 'ainvoke' for parallel execution
    return await llm.ainvoke(prompt)

class PatientRequest(BaseModel):
    summary: str 

# --- WORKER FUNCTION ---
async def audit_single_trial(doc, patient_summary):
    prompt = f"""
    Act as a Clinical Trial Auditor.
    Patient: {patient_summary}
    Trial Phase: {doc.metadata.get('phase', 'Unknown')}
    Criteria: {doc.page_content[:2500]}
    
    Is the patient ELIGIBLE? Start with YES, NO, or MAYBE. Then explain why.
    """
    try:
        response = await async_generate_audit(prompt)
        analysis_content = response.content
    except Exception as e:
        analysis_content = f"⚠️ Error: AI Service Failed ({str(e)})"
    
    return {
        "nct_id": doc.metadata.get('nct_id', 'N/A'),
        "title": doc.metadata.get('title', 'Untitled'),
        "phase": doc.metadata.get('phase', 'N/A'),
        "url": doc.metadata.get('url', '#'),
        "analysis": analysis_content
    }

# --- MAIN ENDPOINT ---
@app.post("/match")
async def match_trials(patient: PatientRequest):
    if not vector_db:
        raise HTTPException(status_code=500, detail="Database not loaded")

    # 1. Fast Retrieval
    docs = retrieve_trials(patient.summary, k=4)
    
    # 2. Parallel Processing (The Speed Fix)
    tasks = [audit_single_trial(doc, patient.summary) for doc in docs]
    
    print(f"🚀 Processing {len(tasks)} trials in parallel...") # Look for this log!
    results = await asyncio.gather(*tasks)
        
    return {"matches": results}

if __name__ == "__main__":
    import uvicorn
    # Workers must be 1 on Windows
    uvicorn.run(app, host="0.0.0.0", port=8000)