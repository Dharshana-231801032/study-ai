from transformers import T5ForConditionalGeneration, T5Tokenizer
import torch
import re
import random
import spacy

print("Loading Question Generation model...")
QG_MODEL_NAME = "valhalla/t5-base-qg-hl"
qg_tokenizer = T5Tokenizer.from_pretrained(QG_MODEL_NAME)
qg_model = T5ForConditionalGeneration.from_pretrained(QG_MODEL_NAME)
qg_model.eval()
nlp = spacy.load("en_core_web_lg")
print("Question Generation model loaded ✅")


def generate_question_from_sentence(context: str, answer: str) -> str:
    try:
        highlighted = context.replace(answer, f"<hl> {answer} <hl>", 1)
        input_text = f"generate question: {highlighted}"
        inputs = qg_tokenizer(
            input_text,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding=True
        )
        with torch.no_grad():
            outputs = qg_model.generate(
                inputs["input_ids"],
                max_length=64,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=2
            )
        return qg_tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    except Exception as e:
        print(f"QG error: {e}")
        return None

def get_sentences(text: str, min_len: int = 40) -> list:
    """
    Extract clean, meaningful sentences from text
    """
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[●•·▪▸►◆★✓✔]', '', text)

    doc = nlp(text[:10000])
    sentences = []

    for sent in doc.sents:
        s = sent.text.strip()
        s = re.sub(r'\s+', ' ', s)

        # Skip too short
        if len(s) < min_len:
            continue

        # Skip too long (likely merged table rows)
        if len(s) > 300:
            continue

        # Skip sentences with too many special characters
        alpha_ratio = sum(c.isalpha() for c in s) / max(len(s), 1)
        if alpha_ratio < 0.5:
            continue

        # Skip ALL CAPS sentences (headers)
        if s.isupper():
            continue

        # Skip sentences with formatting artifacts
        if '___' in s or '  ' in s:
            continue

        # Skip sentences that look like table entries
        # (contain multiple parenthetical definitions)
        paren_count = s.count('(')
        if paren_count > 2:
            continue

        # Skip sentences with too many capitalized words (table headers)
        words = s.split()
        cap_ratio = sum(1 for w in words if w[0].isupper()) / max(len(words), 1)
        if cap_ratio > 0.5 and len(words) > 5:
            continue

        # Must have a verb (real sentence)
        has_verb = any(token.pos_ == "VERB" for token in nlp(s))
        if not has_verb:
            continue

        sentences.append(s)

    return sentences


def classify_difficulty(text: str) -> str:
    words = text.split()
    avg = sum(len(w) for w in words) / max(len(words), 1)
    if avg > 7 or len(words) > 25:
        return "hard"
    elif avg > 5 or len(words) > 15:
        return "medium"
    return "easy"


# ── 1 MARK: Fill in the Blank ─────────────────────────────
def generate_fill_blank(text: str, num: int = 5) -> list:
    sentences = get_sentences(text, min_len=40)
    results = []
    for sent in sentences[:num * 3]:
        # Skip sentences with formatting issues
        if '   ' in sent or '\n' in sent:
            continue
        if len(sent.split()) < 8:
            continue

        doc = nlp(sent)
        keywords = [
            t.text for t in doc
            if t.pos_ in ["NOUN", "PROPN"]
            and len(t.text) > 3
            and not t.is_stop
            and t.is_alpha  # Only alphabetic keywords
        ]
        if not keywords:
            continue

        keyword = keywords[0]
        blanked = sent.replace(keyword, "_____", 1)

        # Make sure blank is clean
        if "_____" not in blanked:
            continue
        if '\n' in blanked or '   ' in blanked:
            continue

        results.append({
            "question_text": blanked,
            "answer_text": keyword,
            "question_type": "fill_blank",
            "marks": 1,
            "difficulty": classify_difficulty(sent)
        })
        if len(results) >= num:
            break
    return results


# ── 1 MARK: True or False ─────────────────────────────────
def generate_true_false(text: str, num: int = 5) -> list:
    sentences = get_sentences(text, min_len=40)
    results = []
    for i, sent in enumerate(sentences[:num * 2]):
        # Skip sentences with formatting issues
        if '\n' in sent or '   ' in sent:
            continue
        if len(sent.split()) < 8:
            continue

        is_true = i % 2 == 0
        if is_true:
            statement = sent
            answer = "True"
        else:
            # Simple negation
            if " is " in sent:
                statement = sent.replace(" is ", " is not ", 1)
            elif " are " in sent:
                statement = sent.replace(" are ", " are not ", 1)
            elif " can " in sent:
                statement = sent.replace(" can ", " cannot ", 1)
            elif " must " in sent:
                statement = sent.replace(" must ", " must not ", 1)
            else:
                statement = "It is incorrect that: " + sent
            answer = "False"

        results.append({
            "question_text": f"True or False: {statement}",
            "answer_text": answer,
            "question_type": "true_false",
            "marks": 1,
            "difficulty": "easy"
        })
        if len(results) >= num:
            break
    return results


# ── 1 MARK: MCQ ───────────────────────────────────────────
def generate_mcq(text: str, num: int = 5) -> list:
    sentences = get_sentences(text, min_len=40)
    results = []
    for sent in sentences[:num * 3]:
        doc = nlp(sent)
        noun_phrases = list(set([
            chunk.text for chunk in doc.noun_chunks
            if len(chunk.text) > 3
        ]))
        if len(noun_phrases) < 2:
            continue
        correct = noun_phrases[0]
        question = generate_question_from_sentence(sent, correct)
        if not question or len(question) < 10:
            continue
        wrong = noun_phrases[1:4]
        while len(wrong) < 3:
            wrong.append(f"None of the above")
        options = [correct] + wrong[:3]
        random.shuffle(options)
        correct_label = ["A", "B", "C", "D"][options.index(correct)]
        results.append({
            "question_text": question,
            "answer_text": f"{correct_label}) {correct}",
            "question_type": "mcq",
            "marks": 1,
            "difficulty": classify_difficulty(sent),
            "options": {
                "A": options[0],
                "B": options[1],
                "C": options[2],
                "D": options[3]
            }
        })
        if len(results) >= num:
            break
    return results


# ── 2 MARKS: Short Answer ─────────────────────────────────
def generate_short_answer(text: str, num: int = 5) -> list:
    sentences = get_sentences(text, min_len=40)
    results = []
    for sent in sentences[:num * 2]:
        doc = nlp(sent)
        noun_phrases = [
            chunk.text for chunk in doc.noun_chunks
            if len(chunk.text) > 3
        ]
        if not noun_phrases:
            continue
        answer = noun_phrases[0]
        question = generate_question_from_sentence(sent, answer)
        if not question or len(question) < 10:
            continue
        # Make it a "define/what is" question
        question = f"Define: {answer}. {question}"
        results.append({
            "question_text": question,
            "answer_text": sent,
            "question_type": "short_answer",
            "marks": 2,
            "difficulty": classify_difficulty(sent)
        })
        if len(results) >= num:
            break
    return results


# ── 11 MARKS: Explain with Example ───────────────────────
def generate_11_mark(text: str, num: int = 3) -> list:
    sentences = get_sentences(text, min_len=50)
    results = []
    # Group sentences into chunks of 4-5 for longer answers
    chunks = [
        sentences[i:i+5]
        for i in range(0, len(sentences), 5)
    ]
    for chunk in chunks[:num * 2]:
        if len(chunk) < 2:
            continue
        combined = " ".join(chunk)
        doc = nlp(combined)
        noun_phrases = [
            chunk.text for chunk in doc.noun_chunks
            if len(chunk.text) > 3
        ]
        if not noun_phrases:
            continue
        topic = noun_phrases[0]
        question = f"Explain {topic} in detail with suitable examples. (11 Marks)"
        results.append({
            "question_text": question,
            "answer_text": combined,
            "question_type": "long_answer",
            "marks": 11,
            "difficulty": "medium"
        })
        if len(results) >= num:
            break
    return results


# ── 13 MARKS: Compare/Analyze ────────────────────────────
def generate_13_mark(text: str, num: int = 2) -> list:
    sentences = get_sentences(text, min_len=50)
    results = []
    chunks = [
        sentences[i:i+6]
        for i in range(0, len(sentences), 6)
    ]
    for chunk in chunks[:num * 2]:
        if len(chunk) < 2:
            continue
        combined = " ".join(chunk)
        doc = nlp(combined)
        noun_phrases = list(set([
            c.text for c in doc.noun_chunks
            if len(c.text) > 3
        ]))
        if len(noun_phrases) < 2:
            continue
        t1 = noun_phrases[0]
        t2 = noun_phrases[1]
        question = f"Compare and contrast {t1} and {t2}. Analyze their advantages, disadvantages and use cases. (13 Marks)"
        results.append({
            "question_text": question,
            "answer_text": combined,
            "question_type": "long_answer",
            "marks": 13,
            "difficulty": "hard"
        })
        if len(results) >= num:
            break
    return results


# ── 16 MARKS: Detailed Essay ─────────────────────────────
def generate_16_mark(text: str, num: int = 2) -> list:
    sentences = get_sentences(text, min_len=50)
    results = []
    chunks = [
        sentences[i:i+8]
        for i in range(0, len(sentences), 8)
    ]
    for chunk in chunks[:num * 2]:
        if len(chunk) < 2:
            continue
        combined = " ".join(chunk)
        doc = nlp(combined)
        noun_phrases = [
            c.text for c in doc.noun_chunks
            if len(c.text) > 3
        ]
        if not noun_phrases:
            continue
        topic = noun_phrases[0]
        question = f"Write a detailed note on {topic}. Include its definition, working principle, types, applications, advantages and disadvantages. (16 Marks)"
        results.append({
            "question_text": question,
            "answer_text": combined,
            "question_type": "essay",
            "marks": 16,
            "difficulty": "hard"
        })
        if len(results) >= num:
            break
    return results


# ── MAIN: Generate ALL Question Types ────────────────────
def generate_all_questions(text: str, num_each: int = 3) -> list:
    all_questions = []

    print("Generating Fill in the Blank (1 mark)...")
    all_questions.extend(generate_fill_blank(text, num_each * 2))

    print("Generating True/False (1 mark)...")
    all_questions.extend(generate_true_false(text, num_each * 2))

    print("Generating MCQ (1 mark)...")
    all_questions.extend(generate_mcq(text, num_each * 2))

    print("Generating Short Answer (2 marks)...")
    all_questions.extend(generate_short_answer(text, num_each))

    print("Generating 11 mark questions...")
    all_questions.extend(generate_11_mark(text, 2))

    print("Generating 13 mark questions...")
    all_questions.extend(generate_13_mark(text, 2))

    print("Generating 16 mark questions...")
    all_questions.extend(generate_16_mark(text, 2))

    print(f"Total questions generated: {len(all_questions)}")
    return all_questions