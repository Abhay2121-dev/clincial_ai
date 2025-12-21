
import sys
import requests


def fetch_trials():
    """Fetch clinical trials from ClinicalTrials.gov API"""
    print("📡 Fetching trials from ClinicalTrials.gov...")
    
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": "endometriosis",
        "pageSize": 5
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        trials = []
        for study in data.get('studies', []):
            protocol = study.get('protocolSection', {})
            ident = protocol.get('identificationModule', {})
            desc = protocol.get('descriptionModule', {})
            
            trial = {
                'nct_id': ident.get('nctId', 'Unknown'),
                'title': ident.get('briefTitle', 'Untitled'),
                'summary': desc.get('briefSummary', 'No summary available')
            }
            trials.append(trial)
        
        print(f"✅ Successfully fetched {len(trials)} trials")
        return trials
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching trials: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return []


def build_vector_database(trials):
    """Build FAISS vector database from trial data"""
    if not trials:
        print("⚠️  No trials to process")
        return False
    
    print("🔨 Building vector database...")
    
    try:
        # Import langchain components
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_core.documents import Document
        
        # Initialize embeddings model
        print("📦 Loading embedding model (this may take a moment)...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Convert trials to Document objects
        documents = []
        for trial in trials:
            doc = Document(
                page_content=trial['summary'],
                metadata={
                    'nct_id': trial['nct_id'],
                    'title': trial['title']
                }
            )
            documents.append(doc)
        
        print(f"📄 Created {len(documents)} documents")
        
        # Build FAISS index
        print("🏗️  Creating FAISS index...")
        vector_db = FAISS.from_documents(documents, embeddings)
        
        # Save to disk
        output_dir = "faiss_production_index"
        vector_db.save_local(output_dir)
        print(f"💾 Successfully saved database to '{output_dir}/'")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing required library: {e}")
        print("Please install: pip install langchain-community langchain-huggingface langchain-core faiss-cpu")
        return False
    except Exception as e:
        print(f"❌ Error building database: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main ETL pipeline orchestrator"""
    print("=" * 70)
    print("🚀 CLINICAL TRIALS ETL PIPELINE - STARTING")
    print("=" * 70)
    print()
    
    # Step 1: Fetch trials from API
    trials = fetch_trials()
    
    if not trials:
        print()
        print("=" * 70)
        print("❌ ETL PIPELINE FAILED - No trials fetched")
        print("=" * 70)
        sys.exit(1)
    
    print()
    
    # Step 2: Build vector database
    success = build_vector_database(trials)
    
    print()
    print("=" * 70)
    if success:
        print("✅ ETL PIPELINE COMPLETED SUCCESSFULLY")
        print(f"📊 Processed {len(trials)} clinical trials")
    else:
        print("❌ ETL PIPELINE FAILED - Database build error")
    print("=" * 70)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
