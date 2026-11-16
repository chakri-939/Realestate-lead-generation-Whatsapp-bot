// Load config parameters directly inside the node for self-containment
const maxLength = 2000;
const maxSpecialCharRatio = 0.5;

const blockedPatternsEn = [
  "ignore previous instructions",
  "ignore instructions",
  "forget what I said",
  "reveal your prompt",
  "reveal instructions",
  "system prompt",
  "you are now a",
  "act as a",
  "pretend to be",
  "jailbreak",
  "developer mode",
  "override rules",
  "Hack"
];

const blockedPatternsAr = [
  "تجاهل التعليمات",
  "تجاهل القواعد",
  "انسى ما قيل",
  "اكشف عن موجهك",
  "أنت الآن",
  "تصرف كأنك",
  "تظاهر بأنك",
  "تخطي القيود",
  "وضع المطور",
  "تجاوز القواعد"
];

// Fetch the input text from the previous node
// Since language detector output is dynamic, we fetch cleanedText from the branch input
let text = "";
try {
  text = $('Voice Nudge Evaluator').first().json.cleanedText;
} catch (e) {
  try {
    text = $('Text Normalizer').first().json.cleanedText;
  } catch (err) {
    text = "";
  }
}

const lowercaseText = text.toLowerCase();

let isSafe = true;
let violation = "none";

// 1. Length Check
if (text.length > maxLength) {
  isSafe = false;
  violation = "length";
}

// 2. Special Character Ratio Check
if (isSafe && text.length > 0) {
  const alphanumericCount = (text.match(/[a-zA-Z0-9\u0600-\u06FF]/g) || []).length; // Supports English + Arabic unicode characters
  const specialRatio = (text.length - alphanumericCount) / text.length;
  if (specialRatio > maxSpecialCharRatio) {
    isSafe = false;
    violation = "special_chars";
  }
}

// 3. Regex Phrase Check
if (isSafe) {
  const allBlockedPatterns = [...blockedPatternsEn, ...blockedPatternsAr];
  for (const pattern of allBlockedPatterns) {
    if (lowercaseText.includes(pattern.toLowerCase())) {
      isSafe = false;
      violation = "injection";
      break;
    }
  }
}

return {
  json: {
    isSafe: isSafe,
    violation: violation,
    cleanedText: text,
    // Pass the detected language output forward so we don't lose it
    detectedLanguage: $('OpenAI Language Detector').first().json.choices[0].message.content
  }
};
