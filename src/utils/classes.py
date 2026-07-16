"""Damage-class definitions shared across the project."""

# Neural-network targets must be integer indices starting at zero.
CLASS_TO_INDEX: dict[str, int] = {
    "D00": 0,  # Longitudinal crack
    "D10": 1,  # Transverse crack
    "D20": 2,  # Alligator crack
    "D40": 3,  # Pothole
}

# Reverse mapping used when converting model predictions back to labels.
INDEX_TO_CLASS: dict[int, str] = {
    index: class_name
    for class_name, index in CLASS_TO_INDEX.items()
}

CLASS_DESCRIPTIONS: dict[str, str] = {
    "D00": "Longitudinal crack",
    "D10": "Transverse crack",
    "D20": "Alligator crack",
    "D40": "Pothole",
}

NUM_CLASSES: int = len(CLASS_TO_INDEX)