import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject language detection function
detect_js = """
    function detectLanguage(text) {
      if (!text) return "en-US";
      
      const jaRegex = /[\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\uFF00-\uFFEF]/;
      const koRegex = /[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]/;
      const zhRegex = /[\u4E00-\u9FFF\u3400-\u4DBF]/;
      const viRegex = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]/;
      const frRegex = /[çœæ]/i; // Specific French characters not common in English
      const deRegex = /[ßäöüÄÖÜ]/; // Specific German characters
      const ruRegex = /[А-яЁё]/; // Cyrillic
      const esRegex = /[ñÑ¿¡]/; // Spanish
      
      if (jaRegex.test(text)) return "ja-JP";
      if (koRegex.test(text)) return "ko-KR";
      if (zhRegex.test(text)) return "zh-CN"; // Note: Japanese Kanji will match zhRegex too, so jaRegex must be tested first
      if (viRegex.test(text)) return "vi-VN";
      if (ruRegex.test(text)) return "ru-RU";
      if (esRegex.test(text)) return "es-ES";
      if (frRegex.test(text)) return "fr-FR";
      if (deRegex.test(text)) return "de-DE";
      
      return "en-US";
    }
"""
if "function detectLanguage" not in content:
    content = content.replace("function speakText(", detect_js + "\n    function speakText(")

# 2. Modify speakText function
search_speak = """    function speakText(text, lang = "en") {
      if (!text) return;
      const clean = cleanTextForSpeech(text);
      if (!clean) return;

      if (!("speechSynthesis" in window)) {
        console.warn("SpeechSynthesis không được hỗ trợ trên trình duyệt này.");
        return;
      }

      try {
        window.speechSynthesis.cancel();
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }
      } catch (e) {}

      // Slight timeout to prevent Chromium from canceling the new utterance immediately
      setTimeout(() => {
        try {
          const utter = new SpeechSynthesisUtterance(clean);
          utter.lang = lang === "vi" ? "vi-VN" : "en-US";
          utter.rate = 0.95;
          utter.pitch = 1.0;

          if (cachedVoices.length === 0) {
            cachedVoices = window.speechSynthesis.getVoices() || [];
          }

          if (lang === "en" && cachedVoices.length > 0) {
            const voice = 
              cachedVoices.find(v => (v.lang === "en-US" || v.lang === "en_US") && (v.name.includes("Google") || v.name.includes("Samantha") || v.name.includes("Natural") || v.name.includes("Ava") || v.name.includes("Alex") || v.name.includes("Jenny") || v.name.includes("Victoria"))) ||
              cachedVoices.find(v => v.lang.startsWith("en") && !v.name.toLowerCase().includes("bad")) ||
              cachedVoices.find(v => v.lang.startsWith("en"));
            if (voice) {
              utter.voice = voice;
            }
          }"""

replace_speak = """    function speakText(text, forceLang = null) {
      if (!text) return;
      const clean = cleanTextForSpeech(text);
      if (!clean) return;

      if (!("speechSynthesis" in window)) {
        console.warn("SpeechSynthesis không được hỗ trợ trên trình duyệt này.");
        return;
      }

      try {
        window.speechSynthesis.cancel();
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }
      } catch (e) {}

      setTimeout(() => {
        try {
          const detectedLang = forceLang || detectLanguage(clean);
          const utter = new SpeechSynthesisUtterance(clean);
          utter.lang = detectedLang;
          utter.rate = detectedLang.startsWith("ja") || detectedLang.startsWith("zh") ? 0.85 : 0.95; // Speak Asian languages slightly slower for clarity
          utter.pitch = 1.0;

          if (cachedVoices.length === 0) {
            cachedVoices = window.speechSynthesis.getVoices() || [];
          }

          if (cachedVoices.length > 0) {
            // Find a high quality voice for the detected language
            const langPrefix = detectedLang.split('-')[0];
            const voice = 
              cachedVoices.find(v => v.lang.startsWith(detectedLang) && (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("Premium") || v.name.includes("Enhanced"))) ||
              cachedVoices.find(v => v.lang.startsWith(detectedLang)) ||
              cachedVoices.find(v => v.lang.startsWith(langPrefix));
              
            if (voice) {
              utter.voice = voice;
            }
          }"""

content = content.replace(search_speak, replace_speak)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched TTS language detection.")
