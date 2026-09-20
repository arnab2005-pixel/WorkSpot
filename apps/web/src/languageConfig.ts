export type SupportedLanguage = {
  code: string;
  name: string;
  nativeName: string;
  asrCode: string;
  ttsCode: string;
};

export const supportedLanguages: SupportedLanguage[] = [
  { code: "en", name: "English", nativeName: "English", asrCode: "en-IN", ttsCode: "en-IN" },
  { code: "bn", name: "Bengali", nativeName: "বাংলা", asrCode: "bn-IN", ttsCode: "bn-IN" },
  { code: "hi", name: "Hindi", nativeName: "हिंदी", asrCode: "hi-IN", ttsCode: "hi-IN" },
  { code: "mr", name: "Marathi", nativeName: "मराठी", asrCode: "mr-IN", ttsCode: "mr-IN" },
  { code: "ta", name: "Tamil", nativeName: "தமிழ்", asrCode: "ta-IN", ttsCode: "ta-IN" },
  { code: "te", name: "Telugu", nativeName: "తెలుగు", asrCode: "te-IN", ttsCode: "te-IN" },
  { code: "kn", name: "Kannada", nativeName: "ಕನ್ನಡ", asrCode: "kn-IN", ttsCode: "kn-IN" },
  { code: "ml", name: "Malayalam", nativeName: "മലയാളം", asrCode: "ml-IN", ttsCode: "ml-IN" },
  { code: "gu", name: "Gujarati", nativeName: "ગુજરાતી", asrCode: "gu-IN", ttsCode: "gu-IN" },
  { code: "pa", name: "Punjabi", nativeName: "ਪੰਜਾਬੀ", asrCode: "pa-IN", ttsCode: "pa-IN" },
  { code: "or", name: "Odia", nativeName: "ଓଡ଼ିଆ", asrCode: "or-IN", ttsCode: "or-IN" },
  { code: "as", name: "Assamese", nativeName: "অসমীয়া", asrCode: "as-IN", ttsCode: "as-IN" },
  { code: "bho", name: "Bhojpuri", nativeName: "भोजपुरी", asrCode: "bho-IN", ttsCode: "hi-IN" },
  { code: "mai", name: "Maithili", nativeName: "मैथिली", asrCode: "mai-IN", ttsCode: "hi-IN" },
  { code: "ur", name: "Urdu", nativeName: "اردو", asrCode: "ur-IN", ttsCode: "ur-IN" }
];

export function getLanguageConfig(value: string): SupportedLanguage {
  return supportedLanguages.find((item) => item.name === value || item.code === value) ?? supportedLanguages[0];
}

export function speakText(text: string, language: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = getLanguageConfig(language).ttsCode;
  window.speechSynthesis.speak(utterance);
}
