import re
import spacy
from sentence_transformers import SentenceTransformer, util

# Load models
nlp = spacy.load("en_core_web_lg")
sentence_model = SentenceTransformer("all-MiniLM-L6-v2")


def extract_units_from_syllabus(text: str) -> list:
    """
    Extract UNIT-I, UNIT-II... structure from syllabus PDF
    Returns list of unit dicts
    """
    units = []
    lines = text.split('\n')
    lines = [line.strip() for line in lines if line.strip()]

    current_unit = None
    current_subtopics = []

    # Patterns for unit detection
    unit_patterns = [
        r'UNIT[\s\-–—]*([IVX]+|[1-5])\s*[:\|\-–—]?\s*(.+)',
        r'Unit[\s\-–—]*([IVX]+|[1-5])\s*[:\|\-–—]?\s*(.+)',
        r'MODULE[\s\-–—]*([IVX]+|[1-5])\s*[:\|\-–—]?\s*(.+)',
    ]

    for line in lines:
        # Check if line is a unit header
        matched_unit = False
        for pattern in unit_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                # Save previous unit
                if current_unit:
                    current_unit['sub_topics'] = current_subtopics
                    units.append(current_unit)

                unit_num = match.group(1).strip()
                unit_title = match.group(2).strip()

                # Clean unit title
                unit_title = re.sub(r'\s+', ' ', unit_title)
                unit_title = unit_title[:100]  # Max 100 chars

                current_unit = {
                    'unit_number': f'UNIT-{unit_num}',
                    'unit_title': unit_title,
                    'sub_topics': []
                }
                current_subtopics = []
                matched_unit = True
                break

        # If not a unit header, treat as subtopic
        if not matched_unit and current_unit:
            # Filter out noise
            if (len(line) > 10 and
                not line.isdigit() and
                'contact hours' not in line.lower() and
                'total' not in line.lower()[:10]):
                current_subtopics.append(line)

    # Save last unit
    if current_unit:
        current_unit['sub_topics'] = current_subtopics
        units.append(current_unit)

    return units


def map_content_to_units(
    units: list,
    notes_text: str,
    min_similarity: float = 0.3
) -> list:
    """
    Map notes content to syllabus units using cosine similarity
    """
    if not units:
        return []

    # Split notes into paragraphs
    paragraphs = [
        p.strip() for p in notes_text.split('\n')
        if len(p.strip()) > 50
    ]

    if not paragraphs:
        return units

    # Create unit descriptions for embedding
    unit_descriptions = [
        f"{u['unit_number']} {u['unit_title']} {' '.join(u['sub_topics'][:5])}"
        for u in units
    ]

    # Embed units and paragraphs
    unit_embeddings = sentence_model.encode(unit_descriptions)
    para_embeddings = sentence_model.encode(paragraphs[:200])  # Limit for speed

    # Map each paragraph to most similar unit
    for i, unit in enumerate(units):
        unit['mapped_content'] = []

    for para_idx, para in enumerate(paragraphs[:200]):
        similarities = util.cos_sim(
            para_embeddings[para_idx],
            unit_embeddings
        )[0]

        best_unit_idx = int(similarities.argmax())
        best_score = float(similarities[best_unit_idx])

        if best_score >= min_similarity:
            units[best_unit_idx]['mapped_content'].append(para)

    # Convert mapped content to string
    for unit in units:
        unit['mapped_content'] = '\n'.join(
            unit['mapped_content'][:20]  # Max 20 paragraphs per unit
        )

    return units