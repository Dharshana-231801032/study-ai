from sqlalchemy.orm import Session
from app.models.models import Topic, Question
from sentence_transformers import SentenceTransformer, util
import json

# Load model (already loaded in keyword_extractor, reuse)
sentence_model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_mindmap(
    db: Session,
    syllabus_doc_id: str
) -> dict:
    """
    Generate mind map data from syllabus topics
    Returns nodes and edges for React Flow
    """
    topics = db.query(Topic).filter(
        Topic.document_id == syllabus_doc_id
    ).all()

    if not topics:
        return {"error": "No topics found"}

    # Build nodes
    nodes = []
    edges = []

    # Central node (subject)
    central_node = {
        "id": "center",
        "type": "center",
        "data": {
            "label": "Study-AI",
            "type": "center"
        },
        "position": {"x": 400, "y": 300}
    }
    nodes.append(central_node)

    # Topic nodes in a circle around center
    import math
    num_topics = len(topics)
    radius = 250

    for i, topic in enumerate(topics):
        # Calculate position in circle
        angle = (2 * math.pi * i) / num_topics
        x = 400 + radius * math.cos(angle)
        y = 300 + radius * math.sin(angle)

        # Get keywords for this topic
        keywords = []
        if topic.keywords:
            keywords = [k.strip() for k in topic.keywords.split(',')][:5]

        topic_node = {
            "id": str(topic.id),
            "type": "topic",
            "data": {
                "label": topic.unit_title,
                "unit_number": topic.unit_number,
                "keywords": keywords,
                "confidence": topic.confidence_score,
                "type": "topic"
            },
            "position": {"x": round(x), "y": round(y)}
        }
        nodes.append(topic_node)

        # Edge from center to topic
        edges.append({
            "id": f"center-{topic.id}",
            "source": "center",
            "target": str(topic.id),
            "type": "straight",
            "style": {"stroke": "#6366f1", "strokeWidth": 2}
        })

        # Add keyword nodes
        num_keywords = len(keywords)
        kw_radius = 150

        for j, keyword in enumerate(keywords[:4]):
            kw_angle = angle + (2 * math.pi * (j - num_keywords/2)) / (num_topics * 2)
            kw_x = x + kw_radius * math.cos(kw_angle)
            kw_y = y + kw_radius * math.sin(kw_angle)

            kw_id = f"{topic.id}-kw-{j}"
            kw_node = {
                "id": kw_id,
                "type": "keyword",
                "data": {
                    "label": keyword.title(),
                    "type": "keyword"
                },
                "position": {"x": round(kw_x), "y": round(kw_y)}
            }
            nodes.append(kw_node)

            # Edge from topic to keyword
            edges.append({
                "id": f"{topic.id}-{kw_id}",
                "source": str(topic.id),
                "target": kw_id,
                "type": "straight",
                "style": {"stroke": "#94a3b8", "strokeWidth": 1}
            })

    # Find semantic connections between topics
    if len(topics) > 1:
        topic_texts = [
            f"{t.unit_title} {t.keywords or ''}"
            for t in topics
        ]
        embeddings = sentence_model.encode(topic_texts)
        similarity = util.cos_sim(embeddings, embeddings)

        for i in range(len(topics)):
            for j in range(i + 1, len(topics)):
                sim_score = float(similarity[i][j])
                if sim_score > 0.4:
                    edges.append({
                        "id": f"sim-{topics[i].id}-{topics[j].id}",
                        "source": str(topics[i].id),
                        "target": str(topics[j].id),
                        "type": "curved",
                        "animated": True,
                        "style": {
                            "stroke": "#10b981",
                            "strokeWidth": 1,
                            "strokeDasharray": "5,5"
                        },
                        "label": f"{round(sim_score * 100)}% related"
                    })

    return {
        "status": "success",
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }


def get_topic_mindmap(
    db: Session,
    topic_id: str
) -> dict:
    """
    Generate detailed mind map for a single topic
    showing questions and keywords
    """
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        return {"error": "Topic not found"}

    nodes = []
    edges = []

    # Central node = topic
    nodes.append({
        "id": "center",
        "type": "center",
        "data": {
            "label": topic.unit_title,
            "unit_number": topic.unit_number,
            "type": "center"
        },
        "position": {"x": 400, "y": 300}
    })

    # Keyword nodes
    keywords = []
    if topic.keywords:
        keywords = [k.strip() for k in topic.keywords.split(',')][:8]

    import math
    num_kw = len(keywords)
    radius = 200

    for i, keyword in enumerate(keywords):
        angle = (2 * math.pi * i) / max(num_kw, 1)
        x = 400 + radius * math.cos(angle)
        y = 300 + radius * math.sin(angle)

        kw_id = f"kw-{i}"
        nodes.append({
            "id": kw_id,
            "type": "keyword",
            "data": {
                "label": keyword.title(),
                "type": "keyword"
            },
            "position": {"x": round(x), "y": round(y)}
        })

        edges.append({
            "id": f"center-{kw_id}",
            "source": "center",
            "target": kw_id,
            "type": "straight",
            "style": {"stroke": "#6366f1", "strokeWidth": 2}
        })

    # Sub-topics nodes
    subtopics = []
    if topic.sub_topics:
        subtopics = [s.strip() for s in topic.sub_topics.split('\n')][:6]

    for i, subtopic in enumerate(subtopics):
        angle = (2 * math.pi * i) / max(len(subtopics), 1)
        x = 400 + 350 * math.cos(angle)
        y = 300 + 350 * math.sin(angle)

        st_id = f"st-{i}"
        nodes.append({
            "id": st_id,
            "type": "subtopic",
            "data": {
                "label": subtopic[:40],
                "type": "subtopic"
            },
            "position": {"x": round(x), "y": round(y)}
        })

        edges.append({
            "id": f"center-{st_id}",
            "source": "center",
            "target": st_id,
            "type": "straight",
            "style": {"stroke": "#f59e0b", "strokeWidth": 1}
        })

    return {
        "status": "success",
        "topic": topic.unit_title,
        "unit_number": topic.unit_number,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }