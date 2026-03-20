import spacy
from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
import numpy as np

# Load models once (global — avoids reloading every request)
print("Loading NLP models...")
nlp = spacy.load("en_core_web_lg")
sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
kw_model = KeyBERT(model=sentence_model)
print("NLP models loaded ✅")


def preprocess_text(text: str) -> str:
    """
    Clean and preprocess text using spaCy
    - Tokenize, lemmatize, remove stopwords
    """
    doc = nlp(text[:100000])  # Limit for speed

    tokens = [
        token.lemma_.lower()
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and not token.is_space
        and len(token.text) > 2
    ]

    return " ".join(tokens)


def extract_tfidf_keywords(text: str, top_n: int = 20) -> list:
    """
    Extract keywords using TF-IDF
    Returns list of (keyword, score) tuples
    """
    # Split text into paragraphs as documents
    paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]

    if len(paragraphs) < 2:
        paragraphs = [text]

    try:
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=100,
            stop_words='english',
            min_df=1
        )
        tfidf_matrix = vectorizer.fit_transform(paragraphs)
        feature_names = vectorizer.get_feature_names_out()
        scores = np.array(tfidf_matrix.sum(axis=0)).flatten()

        # Get top keywords
        top_indices = scores.argsort()[-top_n:][::-1]
        keywords = [
            (feature_names[i], float(scores[i]))
            for i in top_indices
        ]
        return keywords

    except Exception as e:
        print(f"TF-IDF error: {e}")
        return []


def extract_keybert_keywords(text: str, top_n: int = 15) -> list:
    """
    Extract keywords using KeyBERT with MMR
    Returns list of (keyword, score) tuples
    """
    try:
        keywords = kw_model.extract_keywords(
            text[:10000],  # Limit for speed
            keyphrase_ngram_range=(1, 2),
            use_mmr=True,          # Diversity
            diversity=0.5,         # Balance relevance & diversity
            top_n=top_n,
            stop_words='english'
        )
        return keywords

    except Exception as e:
        print(f"KeyBERT error: {e}")
        return []


def extract_keywords(text: str, top_n: int = 20) -> list:
    """
    MAIN FUNCTION: Combine TF-IDF + KeyBERT for best accuracy
    Returns list of keyword strings
    """
    # Layer 1: TF-IDF keywords
    tfidf_keywords = extract_tfidf_keywords(text, top_n=30)
    tfidf_set = {kw for kw, score in tfidf_keywords}

    # Layer 2: KeyBERT keywords
    keybert_keywords = extract_keybert_keywords(text, top_n=20)
    keybert_set = {kw for kw, score in keybert_keywords}

    # Combine both — KeyBERT first (higher quality), then TF-IDF
    combined = list(keybert_set)
    for kw in tfidf_set:
        if kw not in combined:
            combined.append(kw)

    # Return top N unique keywords
    return combined[:top_n]


def extract_named_entities(text: str) -> list:
    """
    Extract named entities using spaCy NER
    Returns list of (entity, label) tuples
    """
    doc = nlp(text[:50000])
    entities = [
        (ent.text, ent.label_)
        for ent in doc.ents
        if ent.label_ in [
            "ORG", "PRODUCT", "EVENT",
            "WORK_OF_ART", "LAW", "LANGUAGE",
            "GPE", "NORP", "FAC"
        ]
    ]
    # Remove duplicates
    return list(set(entities))