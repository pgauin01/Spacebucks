require("dotenv").config();
const express = require("express");
const fs = require("fs");
const path = require("path");
const solc = require("solc");
const { GoogleGenerativeAI } = require("@google/generative-ai");

const app = express();
app.use(express.json());

// Initialize Gemini
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

console.log("Key:", process.env.GEMINI_API_KEY);

// Configure the Model
// We set 'systemInstruction' here effectively acting as the "Persona"
const model = genAI.getGenerativeModel({
  model: "gemini-2.5-pro",
  systemInstruction: `
        You are an expert Solidity Engineer. 
        - Version: ^0.8.20
        - USE OpenZeppelin standard contracts (import "@openzeppelin/contracts/...").
        - Output ONLY the raw Solidity code. No markdown, no explanations.
    `,
});

// Helper: Configure the Compiler Input
const createCompilerInput = (fileName, content) => {
  return JSON.stringify({
    language: "Solidity",
    sources: { [fileName]: { content } },
    settings: {
      outputSelection: {
        "*": { "*": ["abi", "evm.bytecode"] },
      },
    },
  });
};

function findImports(importPath) {
  try {
    const fullPath = path.resolve(process.cwd(), "node_modules", importPath);
    if (fs.existsSync(fullPath)) {
      return { contents: fs.readFileSync(fullPath, "utf8") };
    } else {
      return { error: "File not found" };
    }
  } catch (e) {
    return { error: e.message };
  }
}

function cleanCode(llmOutput) {
  const pattern = /```(?:solidity)?\n([\s\S]*?)```/;
  const match = llmOutput.match(pattern);
  return match ? match[1].trim() : llmOutput.trim();
}

app.post("/generate", async (req, res) => {
  const userPrompt = req.body.prompt;

  try {
    // --- Step A: Initial Generation ---
    console.log("Generating initial code with Gemini...");

    // Gemini Call: Simple text-in, text-out
    const result = await model.generateContent(userPrompt);
    const response = await result.response;
    let sourceCode = cleanCode(response.text());

    // --- Step B: Compilation Loop (Self-Healing) ---
    const MAX_RETRIES = 1;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      console.log(`Attempt ${attempt + 1}: Compiling...`);

      const input = createCompilerInput("Contract.sol", sourceCode);
      const output = JSON.parse(solc.compile(input, { import: findImports }));

      // Check for Errors (severity === 'error')
      const errors = output.errors
        ? output.errors.filter((e) => e.severity === "error")
        : [];

      if (errors.length === 0) {
        // SUCCESS!
        const contractName = Object.keys(output.contracts["Contract.sol"])[0];
        const contract = output.contracts["Contract.sol"][contractName];

        return res.json({
          status: "success",
          contractName: contractName,
          sourceCode: sourceCode,
          abi: contract.abi,
          bytecode: contract.evm.bytecode.object,
        });
      }

      // FAILURE - Self-Healing
      console.log("Compilation failed. Retrying with Gemini...");
      const errorMsg = errors.map((e) => e.formattedMessage).join("\n");

      if (attempt < MAX_RETRIES) {
        // Create a "Fix It" prompt
        const fixPrompt = `
                The code you generated failed to compile.
                
                CODE:
                ${sourceCode}
                
                ERRORS:
                ${errorMsg}
                
                Fix the errors and return ONLY the full, corrected Solidity code.
                `;

        // For the fix, we send a fresh request
        const fixResult = await model.generateContent(fixPrompt);
        const fixResponse = await fixResult.response;
        sourceCode = cleanCode(fixResponse.text());
      } else {
        // Out of retries
        return res.status(400).json({
          status: "failed",
          message: "Could not compile contract after retries.",
          errors: errorMsg,
        });
      }
    }
  } catch (error) {
    console.error("Gemini Error:", error);
    res.status(500).json({ error: "Internal Server Error" });
  }
});

const PORT = 3000;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
