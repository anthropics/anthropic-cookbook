# Evaluations with Promptfoo



### Pre-requisities 
To use Promptfoo you will need to have node.js & npm installed on your system. For more information follow [this guide](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)  

You can install promptfoo using npm or run it directly using npx. In this guide we will use npx.  

*Note: For this example you will not need to run `npx promptfoo@latest init` there is already an initialized `promptfooconfig.yaml` file in this directory*  

See the official docs [here](https://www.promptfoo.dev/docs/getting-started)  



### Getting Started
The evaluation is orchestrated by the `promptfooconfig.yaml` file. In this file we define the following sections:

- Prompts
    - Promptfoo enables you to import prompts in many different formats. You can read more about this [here](https://www.promptfoo.dev/docs/configuration/parameters).
    - In this example we will load 3 prompts - the same used in `guide.ipynb` from the `prompts.py` file:
        - The functions are identical to those used in `guide.ipynb` except that instead of calling the Claude API they just return the prompt. Promptfoo then handles the orchestration of calling the API and storing the results.
        - You can read more about prompt functions [here](https://www.promptfoo.dev/docs/configuration/parameters#prompt-functions). Using python allows us to reuse the VectorDB class which is necessary for RAG, this is defined in `vectordb.py`.
- Providers
    - With Promptfoo you can connect to many different LLMs from different platforms, see [here for more](https://www.promptfoo.dev/docs/providers). In `guide.ipynb` we used Haiku with default temperature 0.0. We will use Promptfoo to experiment with an array of different temperature settings to identify the optimal choice for our use case.
- Tests
    - We will use the same data that was used in `guide.ipynb` which can be found in this [Google Sheet](https://docs.google.com/spreadsheets/d/1UwbrWCWsTFGVshyOfY2ywtf5BEt7pUcJEGYZDkfkufU/edit#gid=0).
    - Promptfoo has a wide array of built in tests which can be found [here](https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic).
    - In this example we will define a test in our `dataset.csv` as the conditions of our evaluation change with each row and a test in the `promptfooconfig.yaml` for conditions that are consistent across all test cases. Read more about this [here](https://www.promptfoo.dev/docs/configuration/parameters/#import-from-csv)
- Transform
    - In the `defaultTest` section we define a transform function. This is a python function which extracts the specific output we want to test from the LLM response. 
- Output
    - We define the path for the output file. Promptfoo can output results in many formats, [see here](https://www.promptfoo.dev/docs/configuration/parameters/#output-file). Alternatively you can use Promptfoo's web UI, [see here](https://www.promptfoo.dev/docs/usage/web-ui).


### Run the eval

To get started with Promptfoo open your terminal and navigate to this directory (`./evaluation`).

Before running your evaluation you must define the following environment variables:

`export ANTHROPIC_API_KEY=YOUR_API_KEY`  
`export VOYAGE_API_KEY=YOUR_API_KEY`

From the `evaluation` directory, run the following command.  

`npx promptfoo@latest eval`

If you would like to increase the concurrency of the requests (default = 4), run the following command.  

`npx promptfoo@latest eval -j 25`  

When the evaluation is complete the terminal will print the results for each row in the dataset.

You can now go back to `guide.ipynb` to analyze the results!


