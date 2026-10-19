"""Localization prompts and spoken voice scripts for English, Hindi, and Marathi."""

WELCOME_IVR_MENU = (
    "Welcome to the Rural Health Helpline. "
    "Press 1 for English. "
    "ग्रामीण स्वास्थ्य हेल्पलाइन में आपका स्वागत है। हिंदी के लिए 2 दबाएं। "
    "ग्रामीण आरोग्य हेल्पलाइनमध्ये आपले स्वागत आहे. मराठीसाठी 3 दाबा."
)

PROMPTS = {
    "en": {
        "welcome": "Thank you for selecting English. Please clearly describe your health symptoms after the tone.",
        "ask_duration": "How many days have you been experiencing these symptoms? For example, say 2 days, or press 1 for less than 3 days, or press 2 for more than 3 days.",
        "ask_severity": "How severe is your pain or discomfort? Press 1 for mild, 2 for moderate, or 3 for severe.",
        "emergency_check": "Are you experiencing chest pain, difficulty breathing, or severe bleeding? Press 1 for Yes, or 2 for No.",
        "repeat_instruction": "Press 0 to repeat this information, or press 9 to end this call.",
        "silence": "We did not hear anything. Please describe your symptoms after the tone, or press 0 to repeat.",
        "unrecognized": "We could not clearly understand. Please speak clearly into your phone's microphone, or press 0 to repeat.",
        "goodbye": "Thank you for calling the Rural Health Helpline. Please take care of yourself. Goodbye.",
        "max_retries": "We are having trouble hearing you clearly. For your safety, please visit your nearest Primary Health Centre or talk to an ASHA worker. Goodbye.",
        "call_timeout": "This helpline session has reached the maximum duration limit. Please call back if you need further guidance.",
    },
    "hi": {
        "welcome": "हिंदी चुनने के लिए धन्यवाद। कृपया बीप के बाद अपने लक्षणों के बारे में विस्तार से बताएं।",
        "ask_duration": "आपको यह समस्या कितने दिनों से है? 3 दिन से कम के लिए 1 दबाएं, या 3 दिन से अधिक के लिए 2 दबाएं।",
        "ask_severity": "आपकी तकलीफ कितनी है? हल्की तकलीफ के लिए 1, मध्यम के लिए 2, या बहुत तेज दर्द के लिए 3 दबाएं।",
        "emergency_check": "क्या आपको सीने में दर्द, सांस लेने में भारी तकलीफ या अत्यधिक रक्तस्राव है? हाँ के लिए 1, नहीं के लिए 2 दबाएं।",
        "repeat_instruction": "इस जानकारी को दोबारा सुनने के लिए 0 दबाएं, या कॉल समाप्त करने के लिए 9 दबाएं।",
        "silence": "आपकी आवाज़ सुनाई नहीं दी। कृपया बीप के बाद बोलें, या दोहराने के लिए 0 दबाएं।",
        "unrecognized": "हम आपकी बात ठीक से समझ नहीं पाए। कृपया फोन के माइक के पास आकर स्पष्ट बोलें।",
        "goodbye": "ग्रामीण स्वास्थ्य हेल्पलाइन पर कॉल करने के लिए धन्यवाद। अपना ख्याल रखें। नमस्ते।",
        "max_retries": "तकनीकी समस्या के कारण आपकी आवाज़ स्पष्ट नहीं आ रही है। सुरक्षा के लिए कृपया नजदीकी प्राथमिक स्वास्थ्य केंद्र जाएं या आशा दीदी से मिलें। नमस्ते।",
        "call_timeout": "इस कॉल की समय सीमा समाप्त हो गई है। आवश्यकता पड़ने पर कृपया पुनः कॉल करें।",
    },
    "mr": {
        "welcome": "मराठी निवडल्याबद्दल धन्यवाद. कृपया बीप नंतर तुमच्या आजाराची लक्षणे सविस्तर सांगा.",
        "ask_duration": "तुम्हाला हा त्रास किती दिवसांपासून आहे? ३ दिवसांपेक्षा कमीसाठी १ दाबा, किंवा ३ दिवसांपेक्षा जास्त असल्यास २ दाबा.",
        "ask_severity": "तुमचा त्रास किती तीव्र आहे? हलक्या त्रासासाठी १, मध्यमसाठी २, किंवा तीव्र वेदनेसाठी ३ दाबा.",
        "emergency_check": "तुम्हाला छातीत तीव्र वेदना, श्वास घेण्यास त्रास किंवा प्रचंड रक्तस्त्राव होतोय का? होय साठी १, नाही साठी २ दाबा.",
        "repeat_instruction": "माहिती पुन्हा ऐकण्यासाठी ० दाबा, किंवा कॉल संपवण्यासाठी ९ दाबा.",
        "silence": "तुमचा आवाज आला नाही. कृपया बीप नंतर बोला, किंवा पुन्हा ऐकण्यासाठी ० दाबा.",
        "unrecognized": "आम्हाला नीट समजले नाही. कृपया फोनच्या माईकजवळ स्पष्ट बोला.",
        "goodbye": "ग्रामीण आरोग्य हेल्पलाइनला कॉल केल्याबद्दल धन्यवाद. काळजी घ्या. नमस्कार.",
        "max_retries": "आवाज स्पष्ट न आल्यामुळे, कृपया सुरक्षिततेसाठी आपल्या जवळच्या प्राथमिक आरोग्य केंद्राला भेट द्या किंवा आशा ताईंशी संपर्क साधा. नमस्कार.",
        "call_timeout": "कॉलची कमाल वेळ संपली आहे. गरज असल्यास कृपया पुन्हा कॉल करा.",
    },
}


def get_prompt(key: str, language: str = "en") -> str:
    lang = language if language in PROMPTS else "en"
    return PROMPTS[lang].get(key, PROMPTS["en"].get(key, ""))
