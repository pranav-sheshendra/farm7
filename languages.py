"""English plus India's 22 scheduled languages; speech availability is device-specific."""
LANGUAGES = [
    ("en", "English", "English", "en-IN"),
    ("as", "অসমীয়া", "Assamese", "as-IN"), ("bn", "বাংলা", "Bengali", "bn-IN"),
    ("brx", "बड़ो", "Bodo", "brx-IN"), ("doi", "डोगरी", "Dogri", "doi-IN"),
    ("gu", "ગુજરાતી", "Gujarati", "gu-IN"), ("hi", "हिन्दी", "Hindi", "hi-IN"),
    ("kn", "ಕನ್ನಡ", "Kannada", "kn-IN"), ("ks", "کٲشُر", "Kashmiri", "ks-IN"),
    ("gom", "कोंकणी", "Konkani", "kok-IN"), ("mai", "मैथिली", "Maithili", "mai-IN"),
    ("ml", "മലയാളം", "Malayalam", "ml-IN"), ("mni-Mtei", "ꯃꯤꯇꯩꯂꯣꯟ", "Manipuri", "mni-IN"),
    ("mr", "मराठी", "Marathi", "mr-IN"), ("ne", "नेपाली", "Nepali", "ne-NP"),
    ("or", "ଓଡ଼ିଆ", "Odia", "or-IN"), ("pa", "ਪੰਜਾਬੀ", "Punjabi", "pa-IN"),
    ("sa", "संस्कृतम्", "Sanskrit", "sa-IN"), ("sat", "ᱥᱟᱱᱛᱟᱲᱤ", "Santali", "sat-IN"),
    ("sd", "سنڌي", "Sindhi", "sd-IN"), ("ta", "தமிழ்", "Tamil", "ta-IN"),
    ("te", "తెలుగు", "Telugu", "te-IN"), ("ur", "اردو", "Urdu", "ur-IN"),
]
LANGUAGE_MAP = {code: {"name": name, "english": english, "speech": speech,
                       "rtl": code in {"ur", "ks", "sd"}}
                for code, name, english, speech in LANGUAGES}
