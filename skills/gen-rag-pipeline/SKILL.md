---
name: gen-rag-pipeline
description: Generate RAG (Retrieval-Augmented Generation) pipeline components using LangChain + pgvector. Creates document loaders, embedding generators, vector store operations, and retrieval chains for DB documentation, incident history, and playbook knowledge bases.
argument-hint: "[knowledge-base-name] [source: docs|incidents|playbooks|manuals]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate RAG Pipeline

## Arguments
- Knowledge base: $0
- Source type: $1 (default: docs)

## Reference
- Read `ai-db-monitor-architecture-spec-v3.md` for RAG architecture

## Output Files
```
backend/app/rag/
├── loaders/{source}_loader.py      # Document loader
├── embeddings.py                    # Embedding model config
├── vectorstore.py                   # pgvector store
├── chains/{kb_name}_chain.py        # Retrieval chain
└── prompts/{kb_name}_prompt.py      # LLM prompts
```

## Pipeline Architecture
```
Documents → Loader → Splitter → Embedder → pgvector
                                              ↓
User Query → Embedder → Similarity Search → Context
                                              ↓
                              Context + Query → LLM → Response
```

## Template
```python
from langchain_community.vectorstores import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# Vector Store (pgvector)
CONNECTION_STRING = "postgresql+asyncpg://user:pass@localhost:5432/neuraldb"

vectorstore = PGVector(
    collection_name="{kb_name}",
    connection_string=CONNECTION_STRING,
    embedding_function=get_embedding_model(),
)

# Retrieval Chain
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 5, "fetch_k": 20},
)

prompt = ChatPromptTemplate.from_template("""
Based on the following context from our DB monitoring knowledge base,
answer the question. If you cannot find the answer, say so.

Context: {context}
Question: {question}
""")

chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
)
```

## Knowledge Base Types
| KB | Source | Embedding | Use Case |
|----|--------|-----------|----------|
| db_docs | PostgreSQL docs, wiki | sentence-transformers | RCA context |
| incidents | Past incident records | sentence-transformers | Similar incident search |
| playbooks | YAML playbook library | sentence-transformers | Playbook recommendation |
| query_patterns | Query plans, optimizations | sentence-transformers | Auto-tuning reference |

## Rules
- Chunk size: 1000 tokens, overlap: 200
- Embedding model: sentence-transformers (local) or OpenAI ada-002 (cloud)
- MMR search for diversity (avoid redundant results)
- Store metadata: source, timestamp, tags for filtering
- Incremental indexing (don't re-embed unchanged docs)
- pgvector index: IVFFlat for < 1M vectors, HNSW for > 1M
