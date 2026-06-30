require("dotenv").config();
const express = require("express");
const cors = require("cors");

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static("public"));

// Health check route
app.get("/", (req, res) => {
  res.sendFile(__dirname + "/public/index.html");
});

// Translation API route
app.post("/api/translate", async (req, res) => {
  try {
    const { text, sourceLanguage, targetLanguage } = req.body;

    // Validation: Empty text
    if (!text || typeof text !== "string" || text.trim() === "") {
      return res.status(400).json({ error: "Please enter text to translate" });
    }

    // Validation: Missing languages
    if (!sourceLanguage || sourceLanguage.trim() === "") {
      return res.status(400).json({ error: "Please select a source language" });
    }

    if (!targetLanguage || targetLanguage.trim() === "") {
      return res.status(400).json({ error: "Please select a target language" });
    }

    // Validation: Same source and target language
    if (sourceLanguage.toLowerCase() === targetLanguage.toLowerCase()) {
      return res
        .status(400)
        .json({ error: "Source and target languages must be different" });
    }

    // Validation: Text length
    if (text.length > 2000) {
      return res
        .status(400)
        .json({ error: "Text must not exceed 2000 characters" });
    }

    // Get environment variables
    const apiKey = process.env.TRANSLATOR_API_KEY;
    const region = process.env.TRANSLATOR_REGION;
    const endpoint = process.env.TRANSLATOR_ENDPOINT;

    if (!apiKey || !region || !endpoint) {
      console.error("Missing required environment variables");
      return res
        .status(500)
        .json({ error: "Server configuration error. Please contact support." });
    }

    // Build Microsoft Translator API URL
    const translatorUrl = `${endpoint}/translate?api-version=3.0&from=${sourceLanguage.toLowerCase()}&to=${targetLanguage.toLowerCase()}`;

    // Prepare headers for Microsoft Translator API
    const headers = {
      "Ocp-Apim-Subscription-Key": apiKey,
      "Ocp-Apim-Subscription-Region": region,
      "Content-Type": "application/json",
    };

    // Call Microsoft Translator API
    const response = await fetch(translatorUrl, {
      method: "POST",
      headers,
      body: JSON.stringify([{ Text: text.trim() }]),
    });

    if (!response.ok) {
      console.error(
        `Microsoft Translator API error: ${response.status} ${response.statusText}`
      );
      return res
        .status(503)
        .json({ error: "Translation service is temporarily unavailable" });
    }

    const translatorData = await response.json();

    // Extract translated text
    if (
      !Array.isArray(translatorData) ||
      translatorData.length === 0 ||
      !translatorData[0].translations ||
      translatorData[0].translations.length === 0
    ) {
      console.error("Unexpected response format from Microsoft Translator");
      return res.status(500).json({ error: "Failed to process translation" });
    }

    const translatedText = translatorData[0].translations[0].text;

    res.json({ translatedText });
  } catch (error) {
    console.error("Translation API error:", error);
    res.status(500).json({ error: "An unexpected error occurred" });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`\n✅ Server running on http://localhost:${PORT}`);
  console.log(`📁 Frontend: http://localhost:${PORT}`);
  console.log(`🔌 API: http://localhost:${PORT}/api/translate\n`);
});
