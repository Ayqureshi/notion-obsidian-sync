import os
from pathlib import Path

try:
    import spacy
    from spacy.training import Example
except ModuleNotFoundError:
    spacy = None
    Example = None

MODEL_DIR = Path(__file__).resolve().parent / "model_textcat"
LABELS = ["All Lab Tasks", "course work to do", "Research To-Do List"]

COURSE_ALIASES = {
    "Fundamentals Of Cognitive Neuroscience of Language": (
        "fundamentals of cognitive neuroscience of language",
        "cognitive neuroscience",
        "language neuroscience",
        "brain and language",
        "neural language",
        "neurolinguistics",
        "neuroscience",
        "cognition",
        "neuro",
        "fcl",
    ),
    "Csl Phd Lectures Series": (
        "cogscil 726a",
        "cogsci 726a",
        "cogscil 726",
        "cogsci 726",
        "cogscil 725",
        "cogsci 725",
        "cognitive science of language lecture series",
        "csl lecture series",
        "csl guest lecture",
        "guest lecture",
        "guest speaker",
        "guest talk",
        "lecture reading",
        "lecture discussion",
        "discussion session",
        "background paper",
        "departmental lecture",
        "departmental talk",
        "cog sci of language",
        "csl phd",
        "csl",
    ),
    "Lab Visual Language": (
        "cogscil 749",
        "cogsci 749",
        "eye-tracking lab",
        "eye tracking lab",
        "eye-tracking",
        "eye tracking",
        "eyetracking",
        "eye-movement",
        "eye movement",
        "experiment builder",
        "experimentbuilder",
        "stimuli programming",
        "gaze experiment",
        "lab visual language",
        "visual language",
        "lab visual",
        "vll",
    ),
}

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
    ("COGSCIL 749 experiment proposal", "course work to do"),
    ("ExperimentBuilder programming assignment", "course work to do"),
    ("Program the eye tracking experiment", "course work to do"),
    ("Prepare stimuli for the eye movement study", "course work to do"),
    ("COGSCIL 726A guest lecture reading", "course work to do"),
    ("CSL lecture series discussion preparation", "course work to do"),
    ("Read the background paper for the guest speaker", "course work to do"),
    ("Prepare questions for the departmental talk", "course work to do"),
    ("FCL neuroscience exam", "course work to do"),
    ("Review brain and language lecture", "course work to do"),
    
    # Research To-Do List
    ("Draft literature review section 3", "Research To-Do List"),
    ("Preprocess longitudinal eye-tracking data matrices", "Research To-Do List"),
    ("Format citations for conference paper", "Research To-Do List"),
    ("Run statistical analysis on experiment 1", "Research To-Do List"),
    ("Write abstract for symposium", "Research To-Do List"),
]

def create_example(nlp, text: str, target_label: str):
    """Helper to convert text and label into spaCy Example object."""
    if Example is None:
        raise RuntimeError("spaCy is required to train the classification model.")
    cats = {label: (label == target_label) for label in LABELS}
    doc = nlp.make_doc(text)
    return Example.from_dict(doc, {"cats": cats})

def train_and_save_model(model_path: str):
    """Trains the textcat model and saves it to disk."""
    if spacy is None:
        return None

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
    if spacy is None:
        return None
    if os.path.exists(model_path):
        return spacy.load(model_path)
    return train_and_save_model(model_path)

# Initialize pipeline
nlp = load_or_train_model(MODEL_DIR)

def classify_title(title: str) -> str:
    """Predicts the target Notion database label for a given title string."""
    if not title or not title.strip():
        return "course work to do"

    text_lower = title.lower()

    # Deterministic rules work both locally and in GitHub Actions.
    if classify_course(title) or any(
        keyword in text_lower
        for keyword in (
            "hw", "homework", "assignment", "exam", "quiz",
            "lecture", "reading", "class", "course", "ling",
        )
    ):
        return "course work to do"

    if any(
        keyword in text_lower
        for keyword in (
            "research lab", "lab meeting", "lab dinner", "lab work",
            "server", "equipment", "supabase", "shiny",
        )
    ):
        return "All Lab Tasks"

    if any(
        keyword in text_lower
        for keyword in (
            "research", "paper", "literature review", "data",
            "analysis", "abstract", "citations", "experiment",
            "preprocess",
        )
    ):
        return "Research To-Do List"

    if nlp is not None:
        doc = nlp(title)
        return max(doc.cats, key=doc.cats.get)

    # Unknown titles are safest in coursework rather than a research pipeline.
    return "course work to do"


def classify_course(title: str) -> str | None:
    """Returns the exact Notion course title for an unambiguous alias."""
    if not title:
        return None

    text_lower = title.lower()
    for course_name, aliases in COURSE_ALIASES.items():
        if any(alias in text_lower for alias in aliases):
            return course_name
    return None

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
