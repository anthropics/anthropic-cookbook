# Embeddings

Text embeddings are numerical representations of text strings, represented as a vector of floating point numbers. We can use the distance between two text embeddings (popularly cosine similarity) to measure how related two pieces of text are to one another, with smaller distances predicting higher relatedness.

Comparing the similarity of strings, or clustering strings by their distance from one another, allows for a wide variety of applications including **search** (popular in RAG architectures), **recommendations**, and **anomaly detection**.

## How to get embeddings with Anthropic

While Anthropic does not offer its own embedding model, we have partnered with [Voyage AI](https://www.voyageai.com/?ref=anthropic) as our preferred provider for text embeddings. Voyage makes [state of the art](https://blog.voyageai.com/2023/10/29/voyage-embeddings/?ref=anthropic) embedding models, and even offers models customized for specific industry domains such as finance and healthcare, and models that can be fine-tuned for your company.

To access Voyage embeddings, please first sign up on [Voyage AI’s website](https://dash.voyageai.com/?ref=anthropic),  obtain an API key, and set the API key as an environment variable for convenience:

```bash
export VOYAGE_API_KEY="<your secret key>"
```

You can obtain the embeddings either using the official [`voyageai` Python package](https://github.com/voyage-ai/voyageai-python) or HTTP requests, as described below.

### Voyage Python Package

The `voyageai` package can be installed using the following command:

```bash
pip install -U voyageai
```

Then, you can create a client object and start using it to embed your texts:

```python
import voyageai

vo = voyageai.Client()
# This will automatically use the environment variable VOYAGE_API_KEY.
# Alternatively, you can use vo = voyageai.Client(api_key="<your secret key>")

texts = ["Sample text 1", "Sample text 2"]

result = vo.embed(texts, model="voyage-3", input_type="document")
print(result.embeddings[0])
print(result.embeddings[1])
```

`result.embeddings` will be a list of two embedding vectors, each containing 1024 floating-point numbers. After running the above code, the two embeddings will be printed on the screen:

```
[0.02012746, 0.01957859, ...]  # embedding for "Sample text 1"
[0.01429677, 0.03077182, ...]  # embedding for "Sample text 2"
```

When creating the embeddings, you may specify a few other arguments to the `embed()` function. Here is the specification:

> `voyageai.Client.embed (texts: List[str], model: str, input_type: Optional[str] = None, truncation: Optional[bool] = None)`

- **texts** (List[str]) - A list of texts as a list of strings, such as `["I like cats", "I also like dogs"]`. Currently, we have two constraints on the list:
    - The maximum length of the list is 128.
    - The total number of tokens in the list is at most 1M for `voyage-3-lite`; 320K for `voyage-3` and `voyage-2`; and 120K for `voyage-large-2-instruct`, `voyage-finance-2`, `voyage-multilingual-2`, `voyage-law-2`, `voyage-code-2`, and `voyage-large-2`.
- **model** (str) - Name of the model. Recommended options: `voyage-3`, `voyage-3-lite`, `voyage-finance-2`, `voyage-multilingual-2`, `voyage-law-2`, `voyage-code-2`.
- **input_type** (str, optional, defaults to `None`) - Type of the input text. Default to `None`. Other options: `query`, `document`.
    - When the **input_type** is set to `None`, and the input text will be directly encoded by our embedding model. Alternatively, when the inputs are documents or queries, the users can specify **input_type** to be `query` or `document`, respectively. In such cases, Voyage will prepend a special prompt to input text and send the extended inputs to the embedding model.
    - For retrieval/search use cases, we recommend specifying this argument when encoding queries or documents to enhance retrieval quality. Embeddings generated with and without the **input_type** argument are compatible.
    - For transparency, the prompts the backend will prepend to your texts are below.
        - For query, the prompt is "*Represent the query for retrieving supporting documents:* ".
        - For document, the prompt is "*Represent the document for retrieval:* ".
- **truncation** (bool, optional, defaults to `True`) - Whether to truncate the input texts to fit within the context length.
    - If `True`, over-length input texts will be truncated to fit within the context length, before vectorized by the embedding model.
    - If `False`, an error will be raised if any given text exceeds the context length.

**Returns**

- A `EmbeddingsObject`, containing the following attributes:
    - **embeddings** (List[List[float]]) - A list of embeddings for the corresponding list of input texts, where each embedding is a vector represented as a list of floats.
    - **total_tokens** (int) - The total number of tokens in the input texts.

### Voyage HTTP API

You can also get embeddings by requesting Voyage HTTP API. For example, you can send an HTTP request through the `curl` command in a terminal:

```bash
curl <https://api.voyageai.com/v1/embeddings> \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $VOYAGE_API_KEY" \\
  -d '{
    "input": ["Sample text 1", "Sample text 2"],
    "model": "voyage-3"
  }'

```

The response you would get is a JSON object containing the embeddings and the token usage:

```bash
{
  "object": "list",
  "data": [
    {
      "embedding": [0.02012746, 0.01957859, ...],
      "index": 0
    },
    {
      "embedding": [0.01429677, 0.03077182, ...],
      "index": 1
    }
  ],
  "model": "voyage-3",
  "usage": {
    "total_tokens": 10
  }
}

```

Voyage AI's embedding endpoint is `https://api.voyageai.com/v1/embeddings` (POST). The request header must contain the API key. The request body is a JSON object containing the following arguments:

- **input** (object, required) - A single text string, or a list of texts as a list of strings. Currently, we have two constraints on the list:
    - The maximum length of the list is 128.
    - The total number of tokens in the list is at most 1M for `voyage-3-lite`; 320K for `voyage-3` and `voyage-2`; and 120K for `voyage-large-2-instruct`, `voyage-finance-2`, `voyage-multilingual-2`, `voyage-law-2`, `voyage-code-2`, and `voyage-large-2`.
- **model** (string, required) - Name of the model. Recommended options: `voyage-3`, `voyage-3-lite`, `voyage-finance-2`, `voyage-multilingual-2`, `voyage-law-2`, `voyage-code-2`.
- **input_type** (string) - Type of the input text. Defaults to `null`. Other options: `query`, `document`.
- **truncation** (boolean) - Whether to truncate the input texts to fit within the context length. Defaults to `true`.
    - If `true`, over-length input texts will be truncated to fit within the context length, before vectorized by the embedding model.
    - If `false`, an error will be raised if any given text exceeds the context length.
- **encoding_format** (string) - Format in which the embeddings are encoded. We support two options:
    - If not specified (defaults to `null`): the embeddings are represented as lists of floating-point numbers;
    - `base64`: the embeddings are compressed to [base64](https://docs.python.org/3/library/base64.html) encodings.

### AWS Marketplace

Voyage embeddings are available on [AWS Marketplace](https://aws.amazon.com/marketplace/seller-profile?id=seller-snt4gb6fd7ljg). Instructions for accessing Voyage on AWS are available [here](https://docs.voyageai.com/docs/aws-marketplace-model-package).

### Azure Marketplace

Voyage embeddings are also available on [Azure Marketplace](https://azuremarketplace.microsoft.com/en-us/marketplace/apps?search=voyageaiinnovationsinc1718340344903). Instructions for accessing Voyage on Azure are available [here](https://docs.voyageai.com/docs/azure-marketplace-managed-application).

## Available Models

Voyage recommends using the following text embedding models:

| Model | Context Length | Embedding Dimension | Description |
| --- | --- | --- | --- |
| `voyage-3` | 32000 | 1024 | Optimized for general-purpose and multilingual retrieval quality. See [blog post](https://blog.voyageai.com/2024/09/18/voyage-3/) for details. |
| `voyage-3-lite`  | 32000 | 512 | Optimized for latency and cost. See [blog post](https://blog.voyageai.com/2024/09/18/voyage-3/) for details. |
| `voyage-finance-2` | 32000 | 1024 | Optimized for **finance** retrieval and RAG. See [blog post](https://blog.voyageai.com/2024/06/03/domain-specific-embeddings-finance-edition-voyage-finance-2/) for details. |
| `voyage-multilingual-2` | 32000 | 1024 | Optimized for **multilingual** retrieval and RAG. See [blog post](https://blog.voyageai.com/2024/06/10/voyage-multilingual-2-multilingual-embedding-model/) for details. |
| `voyage-law-2` | 16000 | 1024 | Optimized for **legal** and **long-context** retrieval and RAG. Also improved performance across all domains. See [blog post](https://blog.voyageai.com/2024/04/15/domain-specific-embeddings-and-retrieval-legal-edition-voyage-law-2/) for details. |
| `voyage-code-2` | 16000 | 1536 | Optimized for code retrieval (17% better than alternatives). See [blog post](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/) for details. |

Additionally, the following multimodal embedding models are recommended:

| Model | Context Length | Embedding Dimension | Description |
| --- | --- | --- | --- |
| `voyage-multimodal-3` | 32000 | 1024 | Rich multimodal embedding model that can vectorize interleaved text and content-rich images, such as screenshots of PDFs, slides, tables, figures, and more. See [blog post](https://blog.voyageai.com/2024/11/12/voyage-multimodal-3/) for details. |

Need help deciding which text embedding model to use? Check out our [FAQ](https://docs.voyageai.com/docs/faq#what-embedding-models-are-available-and-which-one-should-i-use).

Voyage is actively developing more advanced and specialized models, and can fine-tune embeddings for your company. Please email [contact@voyageai.com](mailto:contact@voyageai.com) for trial access or finetuning on your own data!

- `voyage-3-large`: coming soon
- `voyage-code-3`: coming soon

## Quickstart Example

Now that we know how to get embeddings, let's see a brief motivating example.

Suppose we have a small corpus of six documents to retrieve from

```python
documents = [
    "The Mediterranean diet emphasizes fish, olive oil, and vegetables, believed to reduce chronic diseases.",
    "Photosynthesis in plants converts light energy into glucose and produces essential oxygen.",
    "20th-century innovations, from radios to smartphones, centered on electronic advancements.",
    "Rivers provide water, irrigation, and habitat for aquatic species, vital for ecosystems.",
    "Apple’s conference call to discuss fourth fiscal quarter results and business updates is scheduled for Thursday, November 2, 2023 at 2:00 p.m. PT / 5:00 p.m. ET.",
    "Shakespeare's works, like 'Hamlet' and 'A Midsummer Night's Dream,' endure in literature."
]

```

We will first use Voyage to convert each of them into an embedding vector

```python
import voyageai

vo = voyageai.Client()

# Embed the documents
doc_embds = vo.embed(
    documents, model="voyage-3", input_type="document"
).embeddings

```

The embeddings will allow us to do semantic search / retrieval in the vector space. Given an example query,

```python
query = "When is Apple's conference call scheduled?"

```

we convert it into an embedding, and conduct a nearest neighbor search to find the most relevant document based on the distance in the embedding space.

```python
import numpy as np

# Embed the query
query_embd = vo.embed(
    [query], model="voyage-3", input_type="query"
).embeddings[0]

# Compute the similarity
# Voyage embeddings are normalized to length 1, therefore dot-product
# and cosine similarity are the same.
similarities = np.dot(doc_embds, query_embd)

retrieved_id = np.argmax(similarities)
print(documents[retrieved_id])
```

Note that we use `input_type="document"` and `input_type="query"` for embedding the document and query, respectively. More specification can be found [here](https://www.notion.so/Anthropic-Embeddings-page-13eaf4e25caf8006963ecc959cf85bf0?pvs=21).

The output would be the 5th document, which is indeed the most relevant to the query:

```
Apple’s conference call to discuss fourth fiscal quarter results and business updates is scheduled for Thursday, November 2, 2023 at 2:00 p.m. PT / 5:00 p.m. ET.
```

If you are looking for a detailed set of cookbooks on how to do RAG with embeddings, including vector databases, check out our [RAG cookbook](https://github.com/anthropics/anthropic-cookbook/blob/main/third_party/Pinecone/rag_using_pinecone.ipynb).

## Frequently Asked Questions

### Why do Voyage embeddings have superior quality?

Embedding models, much like generative models, rely on powerful neural network (and often transformer-based) architecture to capture and compress semantic context. And, much like generative models, they’re incredibly hard to train. We are a team of leading AI researchers who had experience in training embedding models for 5+ years. We make all the components right, from model architecture and data collection to selecting suitable loss functions and optimizers. Please see our [blog post](https://blog.voyageai.com/2023/10/29/voyage-embeddings/) for more details.

### What text embedding models are available, and which one should I use?

For general-purpose embedding, our default recommendation is `voyage-3` for quality and `voyage-3-lite` for latency and low cost. For retrieval, please use the `input_type` parameter to specify whether the text is a query or document, which adds instructions on the backend.

If your application is in a domain addressed by one of our domain-specific embedding models, we recommend using that model. Specifically:

- `voyage-law-2` is recommended for retrieval tasks in the legal domain.
- `voyage-code-2` is recommended for code-related tasks and programming documentation.
- `voyage-finance-2` is recommended for finance-related tasks.
- `voyage-multilingual-2` is recommended for multilingual tasks.

### Which similarity function should I use?

You can use Voyage embeddings with either dot-product similarity, cosine similarity, or Euclidean distance. An explanation about embedding similarity can be found [here](https://www.pinecone.io/learn/vector-similarity/).

Voyage AI embeddings are normalized to length 1, which means that:

- Cosine similarity is equivalent to dot-product similarity, while the latter can be computed more quickly.
- Cosine similarity and Euclidean distance will result in the identical rankings.

### What is the relationship between characters, words, and tokens?

Please see this [page](https://docs.voyageai.com/docs/tokenization).

### When and how should I use the `input_type` parameter?

For all retrieval tasks and use cases (e.g., RAG), we recommend that the `input_type` parameter be used to specify whether the input text is a query or document. Do not omit `input_type` or set `input_type=None`. Specifying whether input text is a query or document can create better dense vector representations for retrieval, which can lead to better retrieval quality.

When using the `input_type` parameter, special prompts are prepended to the input text prior to embedding. Specifically:

> 📘 **Prompts associated with `input_type`**
> 
> - For a query, the prompt is “Represent the query for retrieving supporting documents: “.
> - For a document, the prompt is “Represent the document for retrieval: “.
> - Example
>     - When `input_type="query"`, a query like "When is Apple's conference call scheduled?" will become "**Represent the query for retrieving supporting documents:** When is Apple's conference call scheduled?"
>     - When `input_type="document"`, a query like "Apple’s conference call to discuss fourth fiscal quarter results and business updates is scheduled for Thursday, November 2, 2023 at 2:00 p.m. PT / 5:00 p.m. ET." will become "**Represent the document for retrieval:** Apple’s conference call to discuss fourth fiscal quarter results and business updates is scheduled for Thursday, November 2, 2023 at 2:00 p.m. PT / 5:00 p.m. ET."

`voyage-large-2-instruct`, as the name suggests, is trained to be responsive to additional instructions that are prepended to the input text. For classification, clustering, or other [MTEB](https://huggingface.co/mteb) subtasks, please use the instructions [here](https://github.com/voyage-ai/voyage-large-2-instruct).

### What is the total number of tokens for the rerankers?

We define the total number of tokens as the “(number of query tokens × the number of documents) + sum of the number of tokens in all documents". This cannot exceed 300K. However, if you are latency-sensitive, we recommend you to use `rerank-2-lite` and use no more than 200K total tokens per request.
