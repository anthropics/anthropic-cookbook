const anthropic = require("@anthropic/client");

// Set up the Anthropic API client
const client = new anthropic.Client("YOUR_API_KEY");

// Define a function to calculate investment returns
async function calculateInvestmentReturns(initialInvestment, years, expectedReturn) {
  const prompt = `
    Calculate the potential returns for an initial investment of ${initialInvestment} over ${years} years with an expected annual return of ${expectedReturn}%.
    
    Provide the calculation steps and the final amount in a clear and easy-to-understand format.
  `;

  const response = await client.complete({
    prompt,
    maxTokens: 500,
    stopSequences: [],
  });

  console.log(response.result.choice);
}

// Example usage
calculateInvestmentReturns(10000, 10, 7);