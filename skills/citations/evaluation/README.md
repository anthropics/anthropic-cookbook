# Evaluations with Promptfoo

### Pre-requisities 
To use Promptfoo you will need to have node.js & npm installed on your system. For more information follow [this guide](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)  

You can install promptfoo using npm or run it directly using npx. In this guide we will use npx.  

*Note: For this example you will not need to run `npx promptfoo@latest init` there is already an initialized `promptfooconfig.yaml` file in this directory*  

See the official docs [here](https://www.promptfoo.dev/docs/getting-started)  

### Getting Started
The evaluation is orchestrated by the `promptfooconfig.yaml` file. In this file we define the following sections:

- Prompts
    - We are testing a single prompt which is contructed in `prompt.py`
- Providers
    - In this example we will evaluate our prompt against three different Claude models
- Tests
    - Our tests are defined in `dataset.csv`. We have over a dozen (question, expected citation) pairs. Questions that should not result in a citation are expected to have the value -1
- Transform
    - In the `defaultTest` section we define a transform function. This is a python function which extracts the citation from the output string. If no citation is found we return -1 instead.


### Run the eval

To get started with Promptfoo open your terminal and navigate to this directory (`./evaluation`).

Before running your evaluation you must define the following enviroment variables:

`export ANTHROPIC_API_KEY=YOUR_API_KEY`  

From the `evaluation` directory, run the following command.  

`npx promptfoo@latest eval`

If you would like to increase the concurrency of the requests (default = 4), run the following command.  

`npx promptfoo@latest eval -j 25`  

When the evaluation is complete the terminal will print the results for each row in the dataset.