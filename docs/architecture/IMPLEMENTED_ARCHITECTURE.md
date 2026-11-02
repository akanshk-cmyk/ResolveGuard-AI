# Implemented architecture

```mermaid
flowchart TD
    UI[Guest-first browser chat] --> WEB[FastAPI: validate and bind requested resource]
    WEB --> SEC[Security signals and emergency interception]
    SEC -->|public| PUB[Python product clarification and comparison]
    PUB --> RAG[Local policy retrieval: bank, product, date, access filters]
    SEC -->|private| AUTH[Demo sign-in and backend authorization]
    AUTH --> CONV[LangGraph conversation with SQLite checkpoints]
    CONV --> GRAPH[Request graph: classify, capture, lookup, retrieve, handoff, compose, verify]
    GRAPH --> BANK[Scoped synthetic transaction and case services]
    BANK --> DB[(SQLite durable events and drafts)]
    GRAPH --> RAG
    SEC -->|active theft| EM[Deterministic synthetic lock, review intake and handoff]
    EM --> DB
    RAG --> BASE[Evidence-backed factual reply]
    GRAPH --> BASE
    BASE --> GEN[Optional LangGraph: GLM framing, validation, fallback]
    GEN --> QA[Deterministic pre-send QA and Resolution record]
    EM --> QA
    QA --> UI
    QA --> TRACE[Local traces and review evidence]
    TRACE --> OPS[Operations dashboard and recorded staff playback]
    DB --> POST[Durable post-session QA jobs]
    POST --> OPS
    TRACE -. optional, cloud unverified .-> LS[LangSmith adapter]
```

Code evidence: `resolveguard/web.py`, `workflow.py`, `conversation.py`, `request_context.py`, `bow_knowledge.py`, `reply_generation.py`, `customer_review.py`, `session_quality.py`, `reviewer.py`, and `dashboard.py`. Public/emergency/review handlers are not all nodes in one graph. No independent free-running agent swarm, vector database, verified cloud deployment or real banking services are implied.
