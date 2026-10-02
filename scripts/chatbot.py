import os
import threading
import time
import uvicorn
import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq

# -------------------------------------------------------------------
# Setup & Config
# -------------------------------------------------------------------
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file.")

VAULT_DIR = os.environ.get("OBSIDIAN_BASE_DIR")
if not VAULT_DIR or not os.path.isdir(VAULT_DIR):
    raise RuntimeError(
        f"OBSIDIAN_BASE_DIR ({VAULT_DIR!r}) is missing or does not exist. Set it "
        "in your .env file to your actual Obsidian vault folder (e.g. the iCloud "
        "Obsidian directory)."
    )

# 1. Global Settings & API Keys
Settings.llm = Groq(model="openai/gpt-oss-120b", api_key=GROQ_API_KEY)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

REFRESH_INTERVAL_SECONDS = int(os.environ.get("RAG_REFRESH_INTERVAL_SECONDS", "60"))

# Set by run_chatbot.py after prompting the user which top-level vault
# folders to index. Empty/unset means index the whole vault (e.g. when
# running this file directly instead of through the launcher).
INDEX_FOLDERS = [f for f in os.environ.get("CHATBOT_INDEX_FOLDERS", "").split(",") if f]

def load_vault_documents():
    # filename_as_id keeps each document's id stable (based on its file path)
    # across separate reads, which refresh_ref_docs() needs to tell "unchanged
    # file" apart from "new file" instead of re-embedding everything each time.
    if not INDEX_FOLDERS:
        return SimpleDirectoryReader(
            input_dir=VAULT_DIR,
            required_exts=[".md"],
            recursive=True,
            filename_as_id=True,
        ).load_data()

    documents = []
    for folder_name in INDEX_FOLDERS:
        folder_path = os.path.join(VAULT_DIR, folder_name)
        if not os.path.isdir(folder_path):
            print(f"  [!] Skipping missing folder: {folder_name}")
            continue
        documents.extend(
            SimpleDirectoryReader(
                input_dir=folder_path,
                required_exts=[".md"],
                recursive=True,
                filename_as_id=True,
            ).load_data()
        )
    return documents

# 2. Connect to ChromaDB & Initialize Index
db = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = db.get_or_create_collection("notes")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

scope_label = ", ".join(INDEX_FOLDERS) if INDEX_FOLDERS else f"the whole vault ({VAULT_DIR})"

if chroma_collection.count() > 0:
    print("Loading existing Chroma vector store...")
    index = VectorStoreIndex.from_vector_store(vector_store)
else:
    print(f"Indexing {scope_label} for the first time...")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(load_vault_documents(), storage_context=storage_context)

query_engine = index.as_query_engine()

# 3. Keep the index in sync with the vault without a full rebuild.
# refresh_ref_docs() diffs incoming documents against what's already embedded
# and only re-embeds new/changed notes, so a GoodNotes-converted paste shows
# up in query results within one refresh cycle instead of never.
index_lock = threading.Lock()

def refresh_index():
    documents = load_vault_documents()
    with index_lock:
        changed = index.refresh_ref_docs(documents)
    num_changed = sum(1 for c in changed if c)
    if num_changed:
        print(f"Refreshed index: {num_changed} note(s) added/updated.")
    return num_changed

# Run once at startup too, not just on the background timer -- this is what
# actually applies this run's folder selection even when chroma_db already
# has data from a previous run with a different (or no) selection.
print(f"Syncing index for this run's selection: {scope_label}")
refresh_index()

def background_refresh_loop():
    while True:
        time.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            refresh_index()
        except Exception as e:
            print(f"Background refresh failed: {e}")

threading.Thread(target=background_refresh_loop, daemon=True).start()

app = FastAPI(title="PhD Vault RAG Backend")

class QueryPayload(BaseModel):
    prompt: str

@app.post("/query")
def query_vault(payload: QueryPayload):
    """Endpoint for your pop-up UI to send questions to."""
    with index_lock:
        res = query_engine.query(payload.prompt)
    return {"response": str(res)}

@app.post("/refresh")
def refresh_vault():
    """Manually trigger an immediate re-scan, e.g. right after pasting a new note."""
    num_changed = refresh_index()
    return {"updated_notes": num_changed}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)