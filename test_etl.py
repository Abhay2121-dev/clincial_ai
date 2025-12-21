"""
Unit tests for ETL pipeline
"""
import pytest
import os
from etl import fetch_trials, build_vector_database


def test_api_connection():
    """Check if the ClinicalTrials.gov API returns data."""
    trials = fetch_trials()
    
    assert isinstance(trials, list), "API should return a list"
    assert len(trials) > 0, "API returned zero results for endometriosis"


def test_trial_structure():
    """Ensure the trials have the required fields."""
    trials = fetch_trials()
    
    if len(trials) > 0:
        trial = trials[0]
        assert isinstance(trial, dict), "Trial must be a dictionary"
        assert "nct_id" in trial, "Trial missing nct_id"
        assert "title" in trial, "Trial missing title"
        assert "summary" in trial, "Trial missing summary"
        assert len(trial['summary']) > 10, "Summary is too short"


def test_build_database():
    """Test that we can build a vector database."""
    # Fetch a small set of trials
    trials = fetch_trials()
    
    # Try to build the database
    success = build_vector_database(trials)
    
    assert success is True, "Database build failed"


def test_vector_folder_creation():
    """Check if the FAISS index folder was created."""
    folder_path = "faiss_production_index"
    
    # Run the ETL to create the folder
    trials = fetch_trials()
    build_vector_database(trials)
    
    # Check if folder exists
    assert os.path.exists(folder_path), "FAISS folder was not created"
    assert os.path.isdir(folder_path), "FAISS path is not a directory"
    
    # Check for FAISS index files
    files = os.listdir(folder_path)
    assert len(files) > 0, "FAISS folder is empty"


def test_fetch_trials_returns_correct_count():
    """Verify we get the expected number of trials."""
    trials = fetch_trials()
    
    # We set pageSize=5 in the ETL, so we should get up to 5 trials
    assert len(trials) <= 5, "Got more trials than expected"
    assert len(trials) > 0, "Got zero trials"


def test_trial_has_valid_nct_id():
    """Ensure NCT IDs follow the correct format."""
    trials = fetch_trials()
    
    if len(trials) > 0:
        trial = trials[0]
        nct_id = trial.get('nct_id', '')
        
        # NCT IDs typically start with "NCT"
        assert nct_id.startswith('NCT') or nct_id == 'Unknown', \
            f"Invalid NCT ID format: {nct_id}"
