import os
import spacy
from spacy.training import Example

MODEL_DIR = "./model_textcat"
LABELS = ["All Lab Tasks", "course work to do", "Research To-Do List"]

# Expanded training set for real-world coverage
TRAIN_DATA = [
    # All Lab Tasks
    ("Lab meeting with team", "All Lab Tasks"),
    ("Restart server and test websocket integration", "All Lab Tasks"),
    ("Sync with lab supervisor regarding equipment", "All Lab Tasks"),
    ("Research lab dinner", "All Lab Tasks"),
    ("Order new lab hardware", "All Lab Tasks"),
    
    # course work to do
    ("LING 701 Reading assignment", "course work to do"),
    ("Grade undergraduate sample quizzes", "course work to do"),
    ("linguistics hw", "course work to do"),
    ("Read chapter 4 for class", "course work to do"),
    ("Submit homework 2", "course work to do"),
    
    # Research To-Do List
    ("Draft literature review section 3", "Research To-Do List"),
    ("Preprocess longitudinal eye-tracking data matrices", "Research To-Do List"),
    ("Format citations for conference paper", "Research To-Do List"),
    ("Run statistical analysis on experiment 1", "Research To-Do List"),
    ("Write abstract for symposium", "Research To-Do List"),
]

def create_example(nlp, text: str, target_label: str) -> Example:
    """Helper to convert text and label into spaCy Example object."""
    cats = {label: (label == target_label) for label in LABELS}
    doc = nlp.make_doc(text)
    return Example.from_dict(doc, {"cats": cats})

def train_and_save_model(model_path: str):
    """Trains the textcat model and saves it to disk."""
    print("Training new textcat model...")
    
    # Using blank 'en' with pretrained embeddings/vectors is faster and clean
    nlp = spacy.blank("en")
    
    # Add textcat component
    textcat = nlp.add_pipe("textcat_multilabel") if "textcat_multilabel" in nlp.pipe_names else nlp.add_pipe("textcat")
    
    for label in LABELS:
        textcat.add_label(label)
    
    # Convert training data
    examples = [create_example(nlp, text, label) for text, label in TRAIN_DATA]
    
    # Train pipeline
    optimizer = nlp.begin_training()
    for epoch in range(25):
        losses = {}
        # Batch updates for better gradient estimates
        nlp.update(examples, sgd=optimizer, losses=losses)
    
    # Save trained model to disk
    nlp.to_disk(model_path)
    print(f"Model saved successfully to '{model_path}'")
    return nlp

def load_or_train_model(model_path: str):
    """Loads existing model from disk if available, otherwise trains a new one."""
    if os.path.exists(model_path):
        return spacy.load(model_path)
    return train_and_save_model(model_path)

# Initialize pipeline
nlp = load_or_train_model(MODEL_DIR)

def classify_title(title: str) -> str:
    """Predicts the target Notion database label for a given title string."""
    if not title or not title.strip():
        return "All Lab Tasks"  # Fallback default
        
    doc = nlp(title)
    
    # Fallback to rules for high-confidence edge cases (e.g. short tokens)
    text_lower = title.lower()
    if any(k in text_lower for k in ["hw", "homework", "ling", "class", "quiz"]):
        return "course work to do"
        
    return max(doc.cats, key=doc.cats.get)

# --- Quick Test ---
if __name__ == "__main__":
    test_titles = [
        "linguistics hw",
        "Restart lab server",
        "Write draft for paper",
        "LING 701 prep"
    ]
    for t in test_titles:
        print(f"'{t}' -> {classify_title(t)}")