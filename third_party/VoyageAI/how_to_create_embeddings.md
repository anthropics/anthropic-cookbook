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

result = vo.embed(texts, model="voyage-2", input_type="document")
print(result.embeddings[0])
print(result.embeddings[1])
```

`result.embeddings` will be a list of two embedding vectors, each containing 1024 floating-point numbers. After running the above code, the two embeddings will be printed on the screen:

```
[0.02012746, 0.01957859, ...]  # embedding for "Sample text 1"
[0.01429677, 0.03077182, ...]  # embedding for "Sample text 2"
```

When creating the embeddings, you may specify a few other arguments to the `embed()` function. Here is the specification:

> `voyageai.Client.embed(texts : List[str], model : str = "voyage-2", input_type : Optional[str] = None, truncation : Optional[bool] = None)`

- **texts** (List[str]) - A list of texts as a list of strings, such as `["I like cats", "I also like dogs"]`. Currently, the maximum length of the list is 128, and total number of tokens in the list is at most 320K for `voyage-2` and 120K for `voyage-code-2`.
- **model** (str) - Name of the model. Recommended options: `voyage-2` (default), `voyage-code-2`.
- **input_type** (str, optional, defaults to `None`) - Type of the input text. Defalut to `None`. Other options:  `query`, `document`.
    - When the input_type is set to `None`, and the input text will be directly encoded by our embedding model. Alternatively, when the inputs are documents or queries, the users can specify input_type to be `query` or `document`, respectively. In such cases, Voyage will prepend a special prompt to input text and send the extended inputs to the embedding model.
    - For retrieval/search use cases, we recommend specifying this argument when encoding queries or documents to enhance retrieval quality. Embeddings generated with and without the input_type argument are compatible.

- **truncation** (bool, optional, defaults to `None`) - Whether to truncate the input texts to fit within the context length.
    - If `True`, over-length input texts will be truncated to fit within the context length, before vectorized by the embedding model.
    - If `False`, an error will be raised if any given text exceeds the context length.
    - If not specified (defaults to `None`), Voyage will truncate the input text before sending it to the embedding model if it slightly exceeds the context window length. If it significantly exceeds the context window length, an error will be raised.

### Voyage HTTP API

You can also get embeddings by requesting Voyage HTTP API. For example, you can send an HTTP request through the `curl` command in a terminal:

```bash
curl https://api.voyageai.com/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $VOYAGE_API_KEY" \
  -d '{
    "input": ["Sample text 1", "Sample text 2"],
    "model": "voyage-2"
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
  "model": "voyage-2",
  "usage": {
    "total_tokens": 10
  }
}
```

Voyage AI's embedding endpoint is `https://api.voyageai.com/v1/embeddings` (POST). The request header must contain the API key. The request body is a JSON object containing the following arguments:

- **input** (str, List[str]) - A single text string, or a list of texts as a list of strings. Currently, the maximum length of the list is 128, and total number of tokens in the list is at most 320K for `voyage-2` and 120K for `voyage-code-2`.
- **model** (str) - Name of the model. Recommended options: `voyage-2` (default), `voyage-code-2`.
- **input_type** (str, optional, defaults to `None`) - Type of the input text. Defalut to `None`. Other options:  `query`, `document`.
- **truncation** (bool, optional, defaults to `None`) - Whether to truncate the input texts to fit within the context length.
    - If `True`, over-length input texts will be truncated to fit within the context length, before vectorized by the embedding model.
    - If `False`, an error will be raised if any given text exceeds the context length.
    - If not specified (defaults to `None`), Voyage will truncate the input text before sending it to the embedding model if it slightly exceeds the context window length. If it significantly exceeds the context window length, an error will be raised.
- **encoding_format** (str, optional, default to `None`) - Format in which the embeddings are encoded. Voyage currently supports two options:
    - If not specified (defaults to `None`): the embeddings are represented as lists of floating-point numbers;
    - `"base64"`: the embeddings are compressed to [Base64](https://docs.python.org/3/library/base64.html) encodings.


### AWS Marketplace

Voyage embeddings are available on [AWS Marketplace](https://aws.amazon.com/marketplace/seller-profile?id=seller-snt4gb6fd7ljg). Here is the instruction for accessing Voyage on AWS:

1. Subscribe to the model package

    1. Navigate to the [model package listing page](https://aws.amazon.com/marketplace/seller-profile?id=seller-snt4gb6fd7ljg) and select the model to deploy.
    1. Click on the *Continue to subscribe* button.
    1. On the *Subscribe to this software* page, please carefully review the details. If you and your organization agree with the standard End-User License Agreement (EULA), pricing, and support terms, click on "Accept Offer".
    1. After selecting *Continue to configuration* and choosing a region, you will be presented with a Product Arn. This is the model package ARN required for creating a deployable model using Boto3. Copy the ARN that corresponds to your selected region and use it in the subsequent cell.

2. Deploy the model package

    From now on, we recommend you to continue with our provided [notebook](https://github.com/voyage-ai/voyageai-aws/blob/main/notebooks/deploy_voyage_code_2_sagemaker.ipynb) in [Sagemaker Studio](https://aws.amazon.com/sagemaker/studio/). Please create a JupyterLab space, upload our notebook, and continue from there.


## Available Models

Voyage recommends using the following embedding models:

|  Model | Context Length | Embedding Dimension | Description |
| --- | --- | --- | --- |
| `voyage-2` | 4000 | 1024 | Latest base (generalist) embedding model with the best retrieval quality. See [blog post](https://blog.voyageai.com/2023/10/29/voyage-embeddings/?ref=anthropic) for details. |
| `voyage-code-2` | 16000 | 1536 | Optimized for code retrieval (17% better than alternatives), and also SoTA on general-purpose corpora. See [blog post](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/?ref=anthropic) for details. |

`voyage-2` is a generalist embedding model, which achieves state-of-the-art performance across domains and retains high efficiency. `voyage-code-2` is optimized for code applications, offering 4x the context length for more flexible usage, albeit at a slightly higher latency.

Voyage is actively developing more advanced and specialized models, and can fine-tune embeddings for your company. Please email [contact@voyageai.com](mailto:contact@voyageai.com) for trial access or finetuning on your own data!

- `voyage-finance-2`: coming soon
- `voyage-law-2`: coming soon
- `voyage-multilingual-2`: coming soon
- `voyage-healthcare-2`: coming soon

## Motivating Example
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
    documents, model="voyage-2", input_type="document"
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
    [query], model="voyage-2", input_type="query"
).embeddings[0]

# Compute the similarity
# Voyage embeddings are normalized to length 1, therefore dot-product
# and cosine similarity are the same.
similarities = np.dot(doc_embds, query_embd)

retrieved_id = np.argmax(similarities)
print(documents[retrieved_id])
```

Note that we use `input_type="document"` and `input_type="query"` for embedding the document and query, respectively. More specification can be found [here](#voyage-python-package).

The output would be the 5th document, which is indeed the most relevant to the query:

```
Apple’s conference call to discuss fourth fiscal quarter results and business updates is scheduled for Thursday, November 2, 2023 at 2:00 p.m. PT / 5:00 p.m. ET.
```

If you are looking for a detailed set of cookbooks on how to do RAG with embeddings, including vector databases, check out our [RAG cookbook](https://github.com/anthropics/anthropic-cookbook/blob/main/third_party/Pinecone/rag_using_pinecone.ipynb).

## Frequently Asked Questions
### How do I calculate the distance between two embedding vectors?
Cosine similarity is a popular choice, but most distance functions will do fine. Voyage embeddings are normalized to length 1, therefore cosine similarity is essentially the same as the dot-product between two vectors. Here is a code snippet you can use for calculating cosine similarity between two embedding vectors.

```python
import numpy

similarity = np.dot(embd1, embd2)
# Voyage embeddings are normalized to length 1, therefore cosine similarity
# is the same as dot-product.
```

If you want to find the K nearest embedding vectors over a large corpus, we recommend using the capabilities built into most vector databases.

### Can I count the number of tokens in a string before embedding it?
Yes! You can do so with the following code.

```python
import voyageai

vo = voyageai.Client()
total_tokens = vo.count_tokens(["Sample text"])
```

## Pricing
Pricing information is available on the Voyage website's [pricing page](https://docs.voyageai.com/pricing/?ref=anthropic), and should be checked there.
