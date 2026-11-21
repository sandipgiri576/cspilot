# Chemistry Literature RAG

CSPilot includes a local retrieval-augmented generation pipeline for chemistry
abstracts and papers. Retrieval is deterministic and inspectable; OpenRouter is
called only after the relevant passages have been selected.

## Install

```bash
python -m pip install -e ".[rag]"
```

The optional extra installs SentenceTransformers, FAISS, and pypdf. The default
embedding model is `sentence-transformers/all-MiniLM-L6-v2`; its first use may
download model files. A local SentenceTransformer path can be supplied instead.

## Data layout

```text
data/
├── demo/
│   └── chemistry_abstracts.json
├── literature/
│   ├── openalex_abstracts.json
│   └── papers/
│       ├── paper_001.pdf
│       └── paper_002.pdf
└── rag/
    ├── chunks.json
    ├── config.json
    └── index.faiss
```

JSON input may be a list of records or an object with a `records` list. JSONL is
also accepted. Each record needs `abstract`, `text`, or `content`; useful optional
fields are `id`, `title`, `doi`, `url`, and `page`. PDF chunks retain page numbers.
The bundled 40-record demo was adapted from the tutorial notebook in
`agent-example/`; it contains synthetic teaching abstracts and must not be cited
as real literature.

## Build and query

```bash
cspilot rag index data/demo/chemistry_abstracts.json \
  --output-dir data/rag

cspilot rag query "Which solvents are reported for Suzuki coupling?" \
  --index-dir data/rag --top-k 5
```

The query command prints the answer and writes `query_result.json`. Answers are
instructed to use only retrieved passages and cite them as `[1]`, `[2]`, and so
on. Retrieval can be inspected without an API call:

```bash
cspilot rag query "Which studies use water?" \
  --index-dir data/rag --retrieve-only
```

## OpenAlex ingestion

```bash
cspilot rag openalex "density functional theory catalysis" \
  --output-path data/literature/openalex_abstracts.json --limit 40
```

This uses the public OpenAlex API and therefore requires network access. It
normalizes identifiers, authors, journal metadata, DOI and open-access links,
and reconstructs abstracts when OpenAlex supplies an inverted index. OpenAlex
records without abstract text remain in the downloaded metadata but are skipped
during indexing.

## Grounding boundary

The RAG answer is model-generated prose, not a deterministic scientific result.
Every returned match includes its similarity score and source metadata so the
answer can be audited. CSPilot does not treat a generated answer as an energy,
structure, or calculated property, and it does not execute instructions found in
retrieved papers.
