import spacy
from spacy.training import Example

# 1. Initialize & setup pipeline
nlp = spacy.blank("en")
textcat = nlp.add_pipe("textcat")

LABELS = ["All Lab Tasks", "course work to do", "Research To-Do List"]
for label in LABELS:
    textcat.add_label(label)

TRAIN_DATA = [
    ("Lab meeting with team", {"All Lab Tasks": 1.0, "course work to do": 0.0, "Research To-Do List": 0.0}),
    ("Restart server and test websocket integration", {"All Lab Tasks": 1.0, "course work to do": 0.0, "Research To-Do List": 0.0}),
    ("LING 701 Reading assignment", {"All Lab Tasks": 0.0, "course work to do": 1.0, "Research To-Do List": 0.0}),
    ("Grade undergraduate sample quizzes", {"All Lab Tasks": 0.0, "course work to do": 1.0, "Research To-Do List": 0.0}),
    ("Draft literature review section 3", {"All Lab Tasks": 0.0, "course work to do": 0.0, "Research To-Do List": 1.0}),
    ("Preprocess longitudinal eye-tracking data matrices", {"All Lab Tasks": 0.0, "course work to do": 0.0, "Research To-Do List": 1.0}),
]

# 2. Train model
optimizer = nlp.begin_training()
for epoch in range(20):
    losses = {}
    for text, cats in TRAIN_DATA:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, {"cats": cats})
        nlp.update([example], sgd=optimizer, losses=losses)

# 3. Exportable inference function
def classify_title(title: str) -> str:
    """Predicts the target Notion database label for a given title string."""
    doc = nlp(title)
    predicted_label = max(doc.cats, key=doc.cats.get)
    return predicted_label