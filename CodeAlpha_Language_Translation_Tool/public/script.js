// Language options
const languages = [
  { label: "English", code: "en" },
  { label: "Bangla", code: "bn" },
  { label: "Hindi", code: "hi" },
  { label: "Arabic", code: "ar" },
  { label: "Spanish", code: "es" },
  { label: "French", code: "fr" },
  { label: "German", code: "de" },
  { label: "Chinese Simplified", code: "zh-Hans" },
  { label: "Japanese", code: "ja" },
  { label: "Korean", code: "ko" },
];

// DOM Elements
const sourceLanguageSelect = document.getElementById("sourceLanguage");
const targetLanguageSelect = document.getElementById("targetLanguage");
const sourceTextarea = document.getElementById("sourceText");
const translatedTextarea = document.getElementById("translatedText");
const charCountSpan = document.getElementById("charCount");
const translateBtn = document.getElementById("translateBtn");
const clearBtn = document.getElementById("clearBtn");
const swapBtn = document.getElementById("swapBtn");
const copyBtn = document.getElementById("copyBtn");
const readSourceBtn = document.getElementById("readSourceBtn");
const readTranslatedBtn = document.getElementById("readTranslatedBtn");
const messageDiv = document.getElementById("message");
const loadingDiv = document.getElementById("loading");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  populateLanguageSelects();
  setupEventListeners();
});

// Populate language dropdowns
function populateLanguageSelects() {
  languages.forEach((lang) => {
    const option1 = document.createElement("option");
    option1.value = lang.code;
    option1.textContent = lang.label;
    if (lang.code === "en") option1.selected = true;
    sourceLanguageSelect.appendChild(option1);

    const option2 = document.createElement("option");
    option2.value = lang.code;
    option2.textContent = lang.label;
    if (lang.code === "bn") option2.selected = true;
    targetLanguageSelect.appendChild(option2);
  });
}

// Setup event listeners
function setupEventListeners() {
  translateBtn.addEventListener("click", handleTranslate);
  clearBtn.addEventListener("click", handleClear);
  swapBtn.addEventListener("click", handleSwap);
  copyBtn.addEventListener("click", handleCopy);
  readSourceBtn.addEventListener("click", () =>
    handleTextToSpeech(sourceTextarea.value, sourceLanguageSelect.value)
  );
  readTranslatedBtn.addEventListener("click", () =>
    handleTextToSpeech(translatedTextarea.value, targetLanguageSelect.value)
  );
  sourceTextarea.addEventListener("input", updateCharCounter);
}

// Update character counter
function updateCharCounter() {
  const length = sourceTextarea.value.length;
  charCountSpan.textContent = length;

  // Update disabled state
  if (length === 0) {
    translateBtn.disabled = true;
  } else {
    translateBtn.disabled = false;
  }
}

// Show message
function showMessage(message, type = "success") {
  messageDiv.textContent = message;
  messageDiv.className = `message ${type}`;

  // Auto-hide after 4 seconds
  setTimeout(() => {
    messageDiv.classList.add("hidden");
  }, 4000);
}

// Clear message
function clearMessage() {
  messageDiv.textContent = "";
  messageDiv.className = "message hidden";
}

// Handle translate
async function handleTranslate() {
  const text = sourceTextarea.value.trim();
  const sourceLanguage = sourceLanguageSelect.value;
  const targetLanguage = targetLanguageSelect.value;

  clearMessage();

  // Validation
  if (!text) {
    showMessage("Please enter text to translate", "error");
    return;
  }

  if (sourceLanguage === targetLanguage) {
    showMessage(
      "Source and target languages must be different",
      "error"
    );
    return;
  }

  if (text.length > 2000) {
    showMessage("Text must not exceed 2000 characters", "error");
    return;
  }

  // Show loading state
  loadingDiv.classList.remove("hidden");
  translateBtn.disabled = true;

  try {
    const response = await fetch("/api/translate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        sourceLanguage,
        targetLanguage,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      showMessage(
        data.error || "Translation failed. Please try again.",
        "error"
      );
      return;
    }

    translatedTextarea.value = data.translatedText;
    showMessage("Translation completed successfully!", "success");
  } catch (error) {
    console.error("Translation error:", error);
    showMessage("Network error. Please try again.", "error");
  } finally {
    loadingDiv.classList.add("hidden");
    translateBtn.disabled = sourceTextarea.value.trim() === "";
  }
}

// Handle clear
function handleClear() {
  sourceTextarea.value = "";
  translatedTextarea.value = "";
  charCountSpan.textContent = "0";
  clearMessage();
  translateBtn.disabled = true;
  sourceTextarea.focus();
}

// Handle swap
function handleSwap() {
  // Swap languages
  const tempLang = sourceLanguageSelect.value;
  sourceLanguageSelect.value = targetLanguageSelect.value;
  targetLanguageSelect.value = tempLang;

  // Swap text
  const tempText = sourceTextarea.value;
  sourceTextarea.value = translatedTextarea.value;
  translatedTextarea.value = tempText;

  // Update character counter
  updateCharCounter();
}

// Handle copy
async function handleCopy() {
  const text = translatedTextarea.value;

  if (!text) {
    showMessage("No text to copy", "error");
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    showMessage("Translated text copied to clipboard!", "success");
  } catch (error) {
    console.error("Copy error:", error);
    showMessage("Failed to copy text", "error");
  }
}

// Handle text-to-speech
function handleTextToSpeech(text, language) {
  if (!text.trim()) {
    showMessage("No text to read", "error");
    return;
  }

  // Check browser support
  if (!("speechSynthesis" in window)) {
    showMessage("Text-to-speech not supported in this browser", "error");
    return;
  }

  // Cancel any ongoing speech
  window.speechSynthesis.cancel();

  // Create utterance
  const utterance = new SpeechSynthesisUtterance(text);

  // Map language codes to speech synthesis language codes
  const languageMap = {
    en: "en-US",
    bn: "bn-IN",
    hi: "hi-IN",
    ar: "ar-SA",
    es: "es-ES",
    fr: "fr-FR",
    de: "de-DE",
    "zh-Hans": "zh-CN",
    ja: "ja-JP",
    ko: "ko-KR",
  };

  utterance.lang = languageMap[language] || language;
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.volume = 1;

  // Speak
  window.speechSynthesis.speak(utterance);
}

// Initialize character counter on page load
updateCharCounter();
