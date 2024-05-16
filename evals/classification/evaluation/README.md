# Evaluations with Promptfoo

### Pre-requisities 
To use promptfoo you will need to have node.js & npm installed on your system. For more information follow [this guide](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)  

You can install promptfoo using npm or run it directly using npx.  
See the official docs [here](https://www.promptfoo.dev/docs/getting-started)  

In this guide we will use npx.

### Getting Started
The evaluation is orchestrated by the `promptfooconfig.yaml` file. In this file we define the following sections:

- Prompts
    - Promptfoo enables you to import prompts in many different formats. You can read more about this [here](https://www.promptfoo.dev/docs/configuration/parameters).
    - In this example we will load 3 prompts - the same used in `guide.ipynb` in two seperate formats:
        - For the `simple_classify` prompt we will load it directly from the `prompt.txt` file as the content is static between examples.
        - For the `rag_classify` and `rag_chain_of_thought_classify` we will load the prompts from a python file called `prompts.py`. You can read more about prompt functions [here](https://www.promptfoo.dev/docs/configuration/parameters#prompt-functions). Using python allows us to reuse the VectorDB class which is necessary for RAG, this is defined in `vectordb.py`.
- Providers
    - With Promptfoo you can connect to many different LLMs from different platforms, see [here for more](https://www.promptfoo.dev/docs/providers). In `guide.ipynb` we used Haiku with default temperature 0.0. We will use promptfoo to experiment with an array of different temperature settings to identify the optimal choice for our use case.
- Tests
    - We will use the same data that was used in `guide.ipynb` which can be found in this [Google Sheet](https://docs.google.com/spreadsheets/d/1UwbrWCWsTFGVshyOfY2ywtf5BEt7pUcJEGYZDkfkufU/edit#gid=0).
    - Promptfoo has a wide array of built in tests which can be found [here](https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic).
    - In this example we will define a test in our `dataset.csv` as the conditions of our evaluation change with each row and a test in the `promptfooconfig.yaml` for conditions that are consistent across all test cases. 
- Transform
    - In the `defaultTest` section we define a transform function. This is a python function which extracts the specific output we want to test from the LLM response. 
- Output
    - We define the path for the output file. Promptfoo can output results in many formats, [see here](https://www.promptfoo.dev/docs/configuration/parameters/#output-file). You can also use Promptfoo's web UI, [see here](https://www.promptfoo.dev/docs/usage/web-ui).


### Run an eval

Before running your evaluation you must deinfe the following enviroment variables:

`export ANTHROPIC_API_KEY=YOUR_API_KEY`  
`export VOYAGE_API_KE=YOUR_API_KEY`

Assuming you in the `evaluation` directory, run the following command.  

`npx promptfoo@latest eval`

If you would like to increase the concurrency of the requests (default = 4), run the following command.  

`npx promptfoo@latest eval -j 25`  

When the evaluation is complete the terminal will print the results for each row in the dataset.

You can now go back to `guide.ipynb` to analyze the results!


