# Claude Skills

Welcome to the Skills section of the Anthropic Cookbook! This directory contains a collection of guides that showcase specific skills and capabilities where Claude excels. Each guide provides an in-depth exploration of a particular skill, discussing potential use cases, prompt engineering techniques to optimize results, and approaches for evaluating Claude's performance.

## Guides

- **[Classification with Claude](./classification/guide.ipynb)**: Discover how Claude can revolutionize classification tasks, especially in scenarios with complex business rules and limited training data. This guide walks you through data preparation, prompt engineering with retrieval-augmented generation (RAG), testing, and evaluation.

- **[Retrieval Augmented Generation with Claude](./retrieval_augmented_generation/guide.ipynb)**: Learn how to enhance Claude's capabilities with domain-specific knowledge using RAG. This guide demonstrates how to build a RAG system from scratch, optimize its performance, and create an evaluation suite. You'll learn how techniques like summary indexing and re-ranking can significantly improve precision, recall, and overall accuracy in question-answering tasks.

- **[Retrieval Augmented Generation with Contextual Embeddings](./contextual-embeddings/guide.ipynb)**: Learn how to use a new technique to improve the performance of your RAG system. In traditional RAG, documents are typically split into smaller chunks for efficient retrieval. While this approach works well for many applications, it can lead to problems when individual chunks lack sufficient context. Contextual Embeddings solve this problem by adding relevant context to each chunk before embedding. You'll learn how to use contextual embeddings with semantic search, BM25 search, and reranking to improve performance.

- **[Summarization with Claude](./summarization/guide.ipynb)**: Explore Claude's ability to summarize and synthesize information from multiple sources. This guide covers a variety of summarization techniques, including multi-shot, domain-based, and chunking methods, as well as strategies for handling long-form content and multiple documents. We also explore evaluating summaries, which can be a balance of art, subjectivity, and the right approach!

- **[Text-to-SQL with Claude](./text_to_sql/guide.ipynb)**: This guide covers how to generate complex SQL queries from natural language using prompting techniques, self-improvement, and RAG. We'll also explore how to evaluate and improve the accuracy of generated SQL queries, with evals that test for syntax, data correctness, row count, and more.

## Getting Started

To get started with the Skills guides, simply navigate to the desired guide's directory and follow the instructions provided in the `guide.ipynb` file. Each guide is self-contained and includes all the necessary code, data, and evaluation scripts to reproduce the examples and experiments.