# Evaluations with Promptfoo

### Pre-requisities 
To use Promptfoo you will need to have node.js & npm installed on your system. For more information follow [this guide](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)  

You can install promptfoo using npm or run it directly using npx. In this guide we will use npx.  

*Note: For this example you will not need to run `npx promptfoo@latest init` there is already an initialized `promptfooconfig.yaml` file in this directory*  

See the official docs [here](https://www.promptfoo.dev/docs/getting-started)  


### Getting Started
The evaluation is orchestrated by the `promptfooconfig...` `.yaml` files. In our application we divide the evaluation logic between `promptfooconfig_retrieval.yaml` for evaluating the retrieval system and `promptfooconfig_end_to_end.yaml` to evaluate the end to end performance. In each of these files we define the following sections

### Retrieval Evaluations

- Prompts
    - Promptfoo enables you to import prompts in many different formats. You can read more about this [here](https://www.promptfoo.dev/docs/configuration/parameters).
    - In our case, we skip providing a new prompt each time, and merely pass through the `{{query}}` to each retrieval 'provider' for evaluation
- Providers
    - Instead of using a standard LLM provider, we wrote custom providers for each retrieval method found in `guide.ipynb`
- Tests
    - We will use the same data that was used in `guide.ipynb`. We split it into `end_to_end_dataset.csv` and `retrieval_dataset.csv` and added an `__expected` column to each dataset which allows us to automatically run assertions for each row
    - You can find our retrieval evaluation logic in `eval_end_to_end.py`

### End to End Evaluations

- Prompts
    - Promptfoo enables you to import prompts in many different formats. You can read more about this [here](https://www.promptfoo.dev/docs/configuration/parameters).
    - We have 3 prompts in our end to end evaluation config: each of which corresponds to a method use
        - The functions are identical to those used in `guide.ipynb` except that instead of calling the Claude API they just return the prompt. Promptfoo then handles the orchestration of calling the API and storing the results.
        - You can read more about prompt functions [here](https://www.promptfoo.dev/docs/configuration/parameters#prompt-functions). Using python allows us to reuse the VectorDB class which is necessary for RAG, this is defined in `vectordb.py`.
- Providers
    - With Promptfoo you can connect to many different LLMs from different platforms, see [here for more](https://www.promptfoo.dev/docs/providers). In `guide.ipynb` we used Haiku with default temperature 0.0. We will use Promptfoo to experiment with different models.
- Tests
    - We will use the same data that was used in `guide.ipynb`. We split it into `end_to_end_dataset.csv` and `retrieval_dataset.csv` and added an `__expected` column to each dataset which allows us to automatically run assertions for each row
    - Promptfoo has a wide array of built in tests which can be found [here](https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic).
    - You can find the test logic for the retrieval system in `eval_retrieval.py` and the test logic for the end to end system in `eval_end_to_end.py`
- Output
    - We define the path for the output file. Promptfoo can output results in many formats, [see here](https://www.promptfoo.dev/docs/configuration/parameters/#output-file). Alternatively you can use Promptfoo's web UI, [see here](https://www.promptfoo.dev/docs/usage/web-ui).


### Run the eval

To get started with Promptfoo open your terminal and navigate to this directory (`./evaluation`).

Before running your evaluation you must define the following enviroment variables:

`export ANTHROPIC_API_KEY=YOUR_API_KEY`  
`export VOYAGE_API_KEY=YOUR_API_KEY`

From the `evaluation` directory, run one of the following commands.  

- To evaluate the end to end system performance: `npx promptfoo@latest eval -c promptfooconfig_end_to_end.yaml --output ../data/end_to_end_results.json`

- To evaluate the retrieval system performance in isolation: `npx promptfoo@latest eval -c promptfooconfig_retrieval.yaml --output ../data/retrieval_results.json`

When the evaluation is complete the terminal will print the results for each row in the dataset. You can also run `npx promptfoo@latest view` to view outputs in the promptfoo UI viewer.