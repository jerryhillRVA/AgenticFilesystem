# Agentic Platform Architecture

## Overview

The Agentic Platform is a multi-tenant system designed for orchestrating autonomous AI agents. It provides a comprehensive framework for agent management, task delegation, and workflow automation.

## Core Components

### Agent Framework
The Agent Framework is the central orchestration layer. It manages agent lifecycles, coordinates multi-agent workflows, and provides a unified interface to various LLM providers including Claude and GPT.

Key capabilities:
- Multi-agent coordination and task delegation
- Unified LLM interface with provider abstraction
- Tool registration and MCP (Model Context Protocol) integration
- Reusable skills and prompt templates

### Web UI
The Web UI provides an organization-scoped interface for managing projects, agents, and workflows. It supports portfolio-level organization, project workspaces, and context-aware navigation.

### Agentic Filesystem
The Agentic Filesystem is a tenant-scoped file storage and semantic search system. It provides:
- RESTful API for file CRUD operations
- Async indexing pipeline for text extraction and embedding
- Vector-based semantic search using Qdrant
- Binary-to-text pairing for document processing
- Hybrid search combining dense vectors and BM25 sparse retrieval

## Data Flow

1. Files are uploaded through the File API
2. An async indexing job is enqueued
3. Text is extracted from binary files (PDF, DOCX, images)
4. Text is chunked into overlapping segments
5. Chunks are embedded using OpenAI's embedding model
6. Vectors are stored in Qdrant for semantic retrieval

## Tenant Isolation

All data is isolated by tenant ID. Vector search queries include mandatory tenant filters to ensure complete data separation between organizations.

## Technology Stack

- Python 3.12 with FastAPI
- Qdrant for vector storage
- Redis for job queue (Celery)
- Apache Tika for text extraction
- OpenAI for embeddings and RAG
