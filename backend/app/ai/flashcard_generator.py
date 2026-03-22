from transformers import BartForConditionalGeneration, BartTokenizer
import torch
import re
import spacy

print("Loading Flashcard & Summary models...")

BART_MODEL = "facebook/bart-large-cnn"
bart_tokenizer = BartTokenizer.from_pretrained(BART_MODEL)
bart_model = BartForConditionalGeneration.from_pretrained(BART_MODEL)
bart_model.eval()

nlp = spacy.load("en_core_web_lg")

print("Flashcard & Summary models loaded ✅")


def clean_content(text: str) -> str:
    """Clean content for flashcard generation"""
    text = text.replace('\n', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    return text.strip()


def summarize_text(text: str, max_length: int = 80,
                   min_length: int = 20) -> str:
    """Summarize text using BART"""
    try:
        text = clean_content(text)[:1024]
        inputs = bart_tokenizer(
            text,
            return_tensors="pt",
            max_length=1024,
            truncation=True
        )
        with torch.no_grad():
            summary_ids = bart_model.generate(
                inputs["input_ids"],
                max_length=max_length,
                min_length=min_length,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=3,
                length_penalty=2.0
            )
        result = bart_tokenizer.decode(
            summary_ids[0],
            skip_special_tokens=True
        ).strip()
        return result
    except Exception as e:
        print(f"Summarization error: {e}")
        return text[:200]


def extract_flashcard_pairs(text: str, num_cards: int = 10) -> list:
    """
    Extract question-answer pairs for flashcards
    from any text content

    Strategy:
    - Find definition sentences (X is Y, X refers to Y)
    - Find concept sentences with clear subjects
    - Front = concept/subject
    - Back = BART summary of the sentence
    """
    text = clean_content(text)
    doc = nlp(text[:8000])

    pairs = []

    # Pattern 1: Definition sentences (X is/are/refers to Y)
    definition_patterns = [
        r'^([A-Z][^.]{3,40}?)\s+(?:is|are|refers to|defined as|means|describes)\s+(.{20,200})\.',
        r'^([A-Z][^.]{3,40}?)\s*[–—-]\s*(.{20,200})\.',
        r'^([A-Z][^.]{3,40}?):\s*(.{20,200})\.'
    ]

    sentences = [sent.text.strip() for sent in doc.sents
                 if len(sent.text.strip()) > 30]

    for sent in sentences:
        for pattern in definition_patterns:
            match = re.match(pattern, sent)
            if match:
                front = match.group(1).strip()
                context = sent

                # Skip if front is too long or too generic
                if len(front.split()) > 5:
                    continue
                if len(front) < 3:
                    continue

                # Generate back using BART
                back = summarize_text(context, max_length=60, min_length=15)

                if back and len(back) > 15:
                    pairs.append({
                        "front": front,
                        "back": back,
                        "keyword": front
                    })
                break

        if len(pairs) >= num_cards:
            break

    # Pattern 2: If not enough from definitions,
    # use important sentences
    if len(pairs) < num_cards:
        for sent in sentences:
            sent_doc = nlp(sent)

            # Find the main subject of the sentence
            subject = None
            for token in sent_doc:
                if token.dep_ == "nsubj" and not token.is_stop:
                    # Get the full noun phrase
                    for chunk in sent_doc.noun_chunks:
                        if token in chunk:
                            if 2 <= len(chunk.text.split()) <= 4:
                                subject = chunk.text
                            elif len(chunk.text.split()) == 1:
                                subject = chunk.text
                            break
                    break

            if not subject:
                # Fallback: use first noun phrase
                for chunk in sent_doc.noun_chunks:
                    if not chunk.root.is_stop and len(chunk.text) > 3:
                        subject = chunk.text
                        break

            if not subject:
                continue

            # Skip generic subjects
            generic = {
                'it', 'this', 'that', 'they', 'we',
                'you', 'he', 'she', 'data', 'system',
                'method', 'way', 'type', 'form', 'part'
            }
            if subject.lower() in generic:
                continue

            # Skip duplicates
            existing_fronts = [p['front'].lower() for p in pairs]
            if subject.lower() in existing_fronts:
                continue

            back = summarize_text(sent, max_length=60, min_length=15)

            if back and len(back) > 15:
                pairs.append({
                    "front": subject.title(),
                    "back": back,
                    "keyword": subject
                })

            if len(pairs) >= num_cards:
                break

    return pairs[:num_cards]


def generate_flashcard(keyword: str, context: str) -> dict:
    """Generate single flashcard"""
    back = summarize_text(context, max_length=80, min_length=20)
    return {
        "front": keyword.title(),
        "back": back,
        "keyword": keyword
    }


def generate_topic_summary(text: str, max_length: int = 150) -> str:
    """Generate topic summary"""
    text = clean_content(text)
    return summarize_text(text, max_length=max_length, min_length=40)


def generate_flashcards_from_keywords(
    keywords: str,
    mapped_content: str,
    num_cards: int = 10
) -> list:
    """
    Main flashcard generation function
    Works for ANY subject, ANY topic, ANY department
    """
    if not mapped_content:
        return []

    return extract_flashcard_pairs(
        text=mapped_content,
        num_cards=num_cards
    )