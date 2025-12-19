from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import mlflow
# We use standard synchronous retry logic which is much more stable on Windows
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from google.genai.errors import ClientError

load_dotenv()
app = FastAPI(title="EndoMatch API", version="2.0-Stable")

# --- CONFIG ---
mlflow.set_tracking_uri("file:./mlruns")
mlflow.set_experiment("EndoMatch_Production")

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
        print("❌ Database NOT found. Run 'python etl.py' first.")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-09-2025",
        temperature=0,
        google_api_key= os.getenv('GOOGLE_API_KEY')
    )

@app.get("/")
def home():
    return {"status": "online", "mode": "stable_sequential"}

@mlflow.trace(name="FAISS_Retrieve")
def retrieve_trials(query: str, k: int = 3):
    if not vector_db: return []
    # Strict US Filter
    return vector_db.similarity_search(
        query, k=k,
        filter=lambda metadata: metadata.get("is_us_trial") is True
    )

# --- STABLE SYNC RETRY ---
@retry(
    retry=retry_if_exception_type((ClientError, ChatGoogleGenerativeAIError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5)
)
def generate_audit_sync(prompt):
    # We use invoke (blocking) instead of ainvoke to prevent Windows Event Loop crashes
    return llm.invoke(prompt)

class PatientRequest(BaseModel):
    summary: str 

@app.post("/match")
async def match_trials(patient: PatientRequest):
    if not vector_db:
        raise HTTPException(status_code=500, detail="Database not loaded")

    # Start MLflow run
    with mlflow.start_run(nested=True):
        
        # 1. Retrieve Docs
        docs = retrieve_trials(patient.summary, k=3)
        
        results = []
        # 2. Sequential Loop (Safe & Reliable)
        for doc in docs:
            prompt = f"""
            Act as a Clinical Trial Auditor.
            Patient: {patient.summary}
            Trial Phase: {doc.metadata.get('phase', 'Unknown')}
            Criteria: {doc.page_content[:2500]}
            
            Is the patient ELIGIBLE? Start with YES, NO, or MAYBE. Then explain why.
            """
            
            try:
                # Synchronous call - won't crash your internet connection
                response = generate_audit_sync(prompt)
                analysis_content = response.content
            except Exception as e:
                analysis_content = f"⚠️ AI Error: {str(e)}"
            
            results.append({
                "nct_id": doc.metadata.get('nct_id', 'N/A'),
                "title": doc.metadata.get('title', 'Untitled'),
                "phase": doc.metadata.get('phase', 'N/A'),
                "url": doc.metadata.get('url', '#'),
                "analysis": analysis_content
            })
            
        return {"matches": results}

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 to listen, but access via 127.0.0.1
    uvicorn.run(app, host="0.0.0.0", port=8000)