
# Evaluations with Promptfoo

### A Note on This Evaluation Suite

1) Be sure to follow the instructions below - specifically the pre-requisites about required packages.

2) Running the full eval suite may require higher than normal rate limits. Consider only running a subset of tests in promptfoo.

3) Not every test will pass out of the box - we've designed the evaluation to be moderately challenging.

### Pre-requisities 
To use Promptfoo you will need to have node.js & npm installed on your system. For more information follow [this guide](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)  

You can install promptfoo using npm or run it directly using npx. In this guide we will use npx.  

*Note: For this example you will not need to run `npx promptfoo@latest init` there is already an initialized `promptfooconfig.yaml` file in this directory*  

See the official docs [here](https://www.promptfoo.dev/docs/getting-started)  

#### NOTE - Additional Deps
For this example you will need to install the following dependencies in order for our custom_evals to run properly.

`pip install nltk rouge-score`

### Getting Started

To get started, set your ANTHROPIC_API_KEY environment variable, or other required keys for the providers you selected. You can do `export ANTHROPIC_API_KEY=YOUR_API_KEY`.

Then, `cd` into the `evaluation` directory and write `npx promptfoo@latest eval -c promptfooconfig.yaml --output ../data/results.csv`

Afterwards, you can view the results by running `npx promptfoo@latest view`.

### How it Works

The promptfooconfig.yaml file is the heart of our evaluation setup. It defines several crucial sections:

Prompts:
- Prompts are imported from the prompts.py file.
- These prompts are designed to test various aspects of LM performance.


Providers:
- We configure different Claude versions and their settings here.
- This allows us to test across multiple models or with varying parameters (e.g., different temperature settings).


Tests:
- Test cases are defined either in this file, or in this case imported from tests.yaml.
- These tests specify the inputs and expected outputs for our evaluations.
- Promptfoo offers various built-in test types (see docs), or you can define your own. We have 3 custom evaluations and 1 out of the box (contains method):
    - `bleu_eval.py`: Implements the BLEU (Bilingual Evaluation Understudy) score, which measures the similarity between machine-generated text and reference texts.
    - `rouge_eval.py`: Implements the ROUGE (Recall-Oriented Understudy for Gisting Evaluation) score, which assesses the quality of summarization by comparing it to reference summaries.
    - `llm_eval.py`: Contains custom evaluation metrics that leverage Language Models to assess various aspects of generated text, such as coherence, relevance, or factual accuracy.

Output:
- Specifies the format and location of evaluation results.
- Promptfoo supports various output formats too!

### Overriding the Python binary

By default, promptfoo will run python in your shell. Make sure python points to the appropriate executable.

If a python binary is not present, you will see a "python: command not found" error.

To override the Python binary, set the PROMPTFOO_PYTHON environment variable. You may set it to a path (such as /path/to/python3.11) or just an executable in your PATH (such as python3.11).