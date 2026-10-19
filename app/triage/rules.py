"""Clinician-Reviewable Medical Triage Rules for Rural Helpline.

IMPORTANT DISCLAIMER:
These rules represent structured clinical triage heuristics designed for initial risk
stratification on rural telephony helplines. They are NOT clinically validated or certified
diagnostic algorithms, and must be reviewed and adapted by local licensed medical professionals
before clinical deployment.
"""

from dataclasses import dataclass, field
from typing import List, Literal, Optional

UrgencyLevel = Literal["emergency", "prompt_assessment", "general_guidance"]


@dataclass(frozen=True)
class TriageRule:
    """Clinician-reviewable rule definition."""
    rule_id: str
    symptom_category: str
    urgency: UrgencyLevel
    clinical_rationale: str
    keywords_en: List[str]
    keywords_hi: List[str]
    keywords_mr: List[str]
    requires_immediate_bypass: bool
    referral_recommended: bool
    guidance_summary_en: str
    guidance_summary_hi: str
    guidance_summary_mr: str
    clinician_status: str = "DRAFT - PROTOCOL FOR CLINICAL REVIEW"


# ============================================================================
# TIER 1: EMERGENCY RULES (Immediate Emergency Care - 108 Ambulance / Nearest Hospital)
# ============================================================================

EMERGENCY_RULES: List[TriageRule] = [
    TriageRule(
        rule_id="EMERG_CARDIO_01",
        symptom_category="cardiovascular",
        urgency="emergency",
        clinical_rationale=(
            "Potential Acute Coronary Syndrome, myocardial infarction, or aortic dissection. "
            "Requires immediate emergency medical intervention and 108 ambulance transfer."
        ),
        keywords_en=[
            "chest pain", "chest tightness", "chest pressure", "heart attack", 
            "pain radiating to left arm", "heavy chest", "crushing pain", "sweating with chest pain"
        ],
        keywords_hi=[
            "छाती में दर्द", "सीने में दर्द", "सीने में भारीपन", "दिल का दौरा",
            "छाती में दबाव", "seene me dard", "chhati me dard", "dil ka daura"
        ],
        keywords_mr=[
            "छातीत दुखणे", "छातीत वेदना", "छातीवर दाब", "हार्ट अटॅक", "छातीत जड वाटणे",
            "chaatit dukhne", "chhati madhe vedna", "chhatit dab"
        ],
        requires_immediate_bypass=True,
        referral_recommended=True,
        guidance_summary_en=(
            "EMERGENCY: Symptoms of severe chest pain require immediate medical attention. "
            "Please call 108 immediately or arrange urgent transport to the nearest hospital. "
            "Do not exert yourself. Sit upright and rest."
        ),
        guidance_summary_hi=(
            "आपातकालीन चेतावनी: सीने या छाती में तेज दर्द गंभीर हो सकता है। "
            "तुरंत 108 पर कॉल करें या नजदीकी अस्पताल या प्राथमिक स्वास्थ्य केंद्र जाएं। "
            "कोई भी मेहनत का काम न करें और आराम से बैठें।"
        ),
        guidance_summary_mr=(
            "तातडीची सूचना: छातीत होणाऱ्या तीव्र वेदना गंभीर असू शकतात. "
            "कृपया ताबडतोब १०८ रुग्णवाहिकेला फोन करा किंवा तातडीने जवळच्या रुग्णालयात जा. "
            "शारीरिक हालचाल करू नका आणि शांत बसा."
        ),
    ),
    TriageRule(
        rule_id="EMERG_RESP_02",
        symptom_category="respiratory",
        urgency="emergency",
        clinical_rationale=(
            "Severe respiratory distress, hypoxemia, acute airway obstruction, or acute asthma/COPD exacerbation. "
            "Risk of respiratory failure."
        ),
        keywords_en=[
            "severe breathing problem", "cannot breathe", "gasping for air", "lips turning blue", 
            "choking", "struggling to breathe", "shortness of breath", "suffocation"
        ],
        keywords_hi=[
            "सांस लेने में भारी तकलीफ", "सांस नहीं आ रही", "दम घुट रहा है", "होंठ नीले पड़ रहे हैं",
            "saas lene me takleef", "dam phoolna", "dam ghutna"
        ],
        keywords_mr=[
            "श्वास घेण्यास गंभीर त्रास", "दम लागतोय", "श्वास कोंडला आहे", "ओठ निळे पडणे",
            "shwas ghenyas tras", "dam lagne", "shwas kondne"
        ],
        requires_immediate_bypass=True,
        referral_recommended=True,
        guidance_summary_en=(
            "EMERGENCY: Inability to breathe properly is a life-threatening emergency. "
            "Call 108 immediately or proceed urgently to the nearest emergency clinic."
        ),
        guidance_summary_hi=(
            "आपातकालीन चेतावनी: सांस लेने में अत्यधिक कठिनाई खतरनाक हो सकती है। "
            "बिना देरी किए 108 पर संपर्क करें अथवा नजदीकी अस्पताल पहुंचें।"
        ),
        guidance_summary_mr=(
            "तातडीची सूचना: श्वास घेण्यास गंभीर त्रास होणे जीवितास धोकादायक ठरू शकते. "
            "त्वरित १०८ रुग्णवाहिकेला कॉल करा किंवा तातडीने जवळच्या दवाखान्यात जा."
        ),
    ),
    TriageRule(
        rule_id="EMERG_NEURO_03",
        symptom_category="neurological",
        urgency="emergency",
        clinical_rationale=(
            "Suspected stroke (FAST criteria), acute intracranial event, status epilepticus, or coma. "
            "Time-critical window for brain tissue preservation."
        ),
        keywords_en=[
            "sudden weakness", "facial droop", "slurred speech", "paralysis", 
            "unconscious", "fainted and not waking up", "seizure", "convulsions", "fits"
        ],
        keywords_hi=[
            "लकवा", "चेहरा टेढ़ा होना", "बोली लड़खड़ाना", "बेहोश", "दौरा पड़ना", "मिर्गी",
            "lakwa", "behosh", "daura", "fits"
        ],
        keywords_mr=[
            "पक्षाघात", "अर्धांगवायू", "चेहरा वाकडा होणे", "बोबडी वळणे", "शुद्ध हरपणे", "फिट येणे", "झटके",
            "pakshaghat", "shuddha harapne", "fits yene", "jhatke"
        ],
        requires_immediate_bypass=True,
        referral_recommended=True,
        guidance_summary_en=(
            "EMERGENCY: Sudden numbness, facial drooping, speech difficulty, or unconsciousness indicates suspected stroke or neurological emergency. "
            "Seek immediate emergency care at the nearest equipped hospital or call 108."
        ),
        guidance_summary_hi=(
            "आपातकालीन चेतावनी: शरीर के एक हिस्से में कमजोरी, चेहरे का टेढ़ा होना, बोली लड़खड़ाना या बेहोशी ब्रेन स्ट्रोक का संकेत हो सकती है। "
            "तुरंत 108 एम्बुलेंस बुलाएं या नजदीकी बड़े अस्पताल जाएं।"
        ),
        guidance_summary_mr=(
            "तातडीची सूचना: शरीराचा एका बाजूचा भाग लुळा पडणे, बोलण्यात अडखळणे किंवा बेशुद्ध पडणे हे पक्षाघाताचे (स्ट्रोक) लक्षण असू शकते. "
            "ताबडतोब १०८ ला फोन करा किंवा त्वरित मोठ्या रुग्णालयात जा."
        ),
    ),
    TriageRule(
        rule_id="EMERG_TRAUMA_04",
        symptom_category="trauma_bleeding",
        urgency="emergency",
        clinical_rationale="Massive uncontrolled external hemorrhage or major polytrauma with hemorrhagic shock risk.",
        keywords_en=[
            "heavy bleeding", "bleeding not stopping", "gushing blood", "severe injury", 
            "deep wound bleeding continuously", "stab", "accident with severe bleeding"
        ],
        keywords_hi=[
            "खून नहीं रुक रहा", "तेज रक्तस्राव", "गंभीर चोट से खून", "khoon nahi ruk raha", "bhaari khoon"
        ],
        keywords_mr=[
            "प्रचंड रक्तस्त्राव", "रक्त थांबत नाही", "गंभीर दुखापत", "rakta thambat nahi", "mohta jakhama"
        ],
        requires_immediate_bypass=True,
        referral_recommended=True,
        guidance_summary_en=(
            "EMERGENCY: Uncontrolled bleeding requires immediate pressure with a clean cloth and urgent transport to an emergency hospital. "
            "Call 108 right away."
        ),
        guidance_summary_hi=(
            "आपातकालीन चेतावनी: रक्तस्राव न रुकना गंभीर है। घाव पर साफ कपड़े से जोर से दबाव बनाएं और तुरंत 108 बुलाएं या अस्पताल जाएं।"
        ),
        guidance_summary_mr=(
            "तातडीची सूचना: रक्तस्त्राव न थांबणे धोकादायक आहे. जखमेवर स्वच्छ कपड्याने दाबून धरा आणि त्वरित १०८ वर संपर्क करा किंवा तातडीने दवाखान्यात जा."
        ),
    ),
]


# ============================================================================
# TIER 2: PROMPT MEDICAL ASSESSMENT RULES (Visit PHC / Doctor within 24-48 hours)
# ============================================================================

PROMPT_ASSESSMENT_RULES: List[TriageRule] = [
    TriageRule(
        rule_id="PROMPT_FEVER_01",
        symptom_category="fever_infection",
        urgency="prompt_assessment",
        clinical_rationale=(
            "Prolonged fever (> 3 days) or high fever with severe chills. "
            "Possible endemic tropical infections (Malaria, Dengue, Typhoid, Scrub Typhus). "
            "Requires diagnostic blood tests at Primary Health Centre (PHC)."
        ),
        keywords_en=[
            "fever for 3 days", "fever for many days", "persistent fever", "high fever with shivering", 
            "fever and vomiting", "dengue suspected", "malaria suspected"
        ],
        keywords_hi=[
            "3 दिन से बुखार", "लगातार तेज बुखार", "कंपकंपी के साथ बुखार", "बुखार और उल्टी",
            "bukhar 3 din se", "tez bukhar", "thand lagke bukhar"
        ],
        keywords_mr=[
            "३ दिवसांपेक्षा जास्त ताप", "सतत ताप", "थंडी वाजून ताप", "ताप आणि उलट्या",
            "3 divasapasun tap", "satat tap", "thandi vaajun tap"
        ],
        requires_immediate_bypass=False,
        referral_recommended=True,
        guidance_summary_en=(
            "Prompt Assessment: Fever lasting multiple days needs professional evaluation to rule out infections like malaria or dengue. "
            "Please visit your nearest Primary Health Centre (PHC) or registered medical practitioner for a clinical checkup and blood tests. "
            "Drink plenty of clean boiled water and oral rehydration solution."
        ),
        guidance_summary_hi=(
            "शीघ्र चिकित्सकीय परामर्श: कई दिनों से बना बुखार मलेरिया या डेंगू जैसी बीमारी का संकेत हो सकता है। "
            "कृपया अपने नजदीकी प्राथमिक स्वास्थ्य केंद्र (PHC) या योग्य डॉक्टर से जांच करवाएं और खून की जांच कराएं। "
            "उबला हुआ पानी और ओआरएस पिएं।"
        ),
        guidance_summary_mr=(
            "त्वरित वैद्यकीय सल्ला: अनेक दिवस असलेला ताप डेंग्यू किंवा मलेरियाचे लक्षण असू शकतो. "
            "कृपया आपल्या जवळच्या प्राथमिक आरोग्य केंद्राला (PHC) भेट देऊन तपासणी आणि रक्त तपासणी करून घ्या. "
            "उकळलेले पाणी आणि ओआरएसचे भरपूर प्रमाण घ्या."
        ),
    ),
    TriageRule(
        rule_id="PROMPT_GI_02",
        symptom_category="gastrointestinal",
        urgency="prompt_assessment",
        clinical_rationale=(
            "Acute gastroenteritis with risk of dehydration, or acute localized abdominal pain. "
            "Requires clinical assessment for fluid resuscitation or acute abdomen."
        ),
        keywords_en=[
            "severe stomach pain", "vomiting and diarrhea together", "cannot keep water down", 
            "loose motions continuously", "dehydration", "sunken eyes"
        ],
        keywords_hi=[
            "पेट में तेज दर्द", "उल्टी और दस्त", "पानी नहीं रुक रहा", "शरीर में पानी की कमी",
            "pet me dard", "ulti dast", "pani ki kami"
        ],
        keywords_mr=[
            "पोटात तीव्र दुखणे", "उलट्या आणि जुलाब", "शरीरातील पाणी कमी होणे", "अशक्तपणा",
            "potat dukhne", "ultya julab", "ashaktapana"
        ],
        requires_immediate_bypass=False,
        referral_recommended=True,
        guidance_summary_en=(
            "Prompt Assessment: Persistent diarrhea or severe abdominal pain can cause dangerous dehydration. "
            "Continuously sip ORS (Oral Rehydration Solution) or salted rice water, and visit your village ASHA worker or Primary Health Centre today."
        ),
        guidance_summary_hi=(
            "शीघ्र चिकित्सकीय परामर्श: लगातार उल्टी-दस्त से शरीर में पानी की गंभीर कमी हो सकती है। "
            "तुरंत ओआरएस का घोल या नमक-पानी पिएं और आज ही अपनी आशा दीदी या प्राथमिक स्वास्थ्य केंद्र (PHC) जाएं।"
        ),
        guidance_summary_mr=(
            "त्वरित वैद्यकीय सल्ला: सतत जुलाब आणि उलट्यांमुळे निर्जलीकरण (पाण्याची कमतरता) होऊ शकते. "
            "ओआरएसचे पाणी किंवा भाताची पेज सतत घेत राहा आणि आजच आपल्या आशा ताईंना किंवा प्राथमिक आरोग्य केंद्राला दाखवा."
        ),
    ),
    TriageRule(
        rule_id="PROMPT_BITES_03",
        symptom_category="animal_bite_wound",
        urgency="prompt_assessment",
        clinical_rationale=(
            "Animal bite (dog, monkey, bat) carries rabies and tetanus risk. Snakebite is an immediate emergency. "
            "Requires immediate soap washing and anti-rabies vaccine / tetanus toxoid."
        ),
        keywords_en=[
            "dog bite", "monkey bite", "animal bite", "cut with rusty metal", "deep puncture"
        ],
        keywords_hi=[
            "कुत्ते ने काटा", "जानवर का काटना", "बंदर ने काटा", "जंग लगे लोहे से चोट",
            "kutte ne kata", "janwar ne kata"
        ],
        keywords_mr=[
            "कुत्रा चावला", "प्राणी चावला", "माकड चावले", "गंजलेल्या लोखंडाने जखम",
            "kutra chavla", "prani chavla"
        ],
        requires_immediate_bypass=False,
        referral_recommended=True,
        guidance_summary_en=(
            "Prompt Assessment: Wash the bite wound immediately under running water with soap for at least 15 minutes. "
            "Do NOT apply chili, lime, or bandages. Visit the nearest hospital promptly for Anti-Rabies Vaccine and Tetanus injection."
        ),
        guidance_summary_hi=(
            "शीघ्र चिकित्सकीय परामर्श: जानवर के काटने पर घाव को बहते पानी और साबुन से 15 मिनट तक अच्छी तरह धोएं। "
            "घाव पर मिर्च, चूना या पट्टी न लगाएं। तुरंत रेबीज और टिटनेस के टीके के लिए सरकारी अस्पताल जाएं।"
        ),
        guidance_summary_mr=(
            "त्वरित वैद्यकीय सल्ला: प्राणी चावल्यास जखम वाहत्या पाण्याखाली साबणाने किमान १५ मिनिटे स्वच्छ धुवा. "
            "जखमेवर मिरची, चुना किंवा हळद लावू नका. रेबीज व धनुर्वाताच्या लशीसाठी त्वरित सरकारी रुग्णालयात जा."
        ),
    ),
    TriageRule(
        rule_id="PROMPT_PREGNANCY_04",
        symptom_category="maternal_health",
        urgency="prompt_assessment",
        clinical_rationale="Obstetric warning symptoms during pregnancy require urgent midwifery/obstetric evaluation.",
        keywords_en=[
            "pregnant with pain", "pregnancy bleeding", "severe headache in pregnancy", 
            "swelling in hands and feet during pregnancy"
        ],
        keywords_hi=[
            "गर्भावस्था में दर्द", "गर्भवती महिला को रक्तस्राव", "गर्भावस्था में सूजन",
            "garbhwati", "garbh me dard"
        ],
        keywords_mr=[
            "गरोदरपणात पोटदुखी", "गरोदरपणात रक्तस्त्राव", "गरोदरपणात हातापायांवर सूज",
            "garodarpanat dukhne", "garodar"
        ],
        requires_immediate_bypass=False,
        referral_recommended=True,
        guidance_summary_en=(
            "Prompt Assessment: Any bleeding, severe pain, or vision issues during pregnancy require prompt clinical evaluation. "
            "Please contact your local ANM/ASHA worker or visit the Community Health Centre immediately."
        ),
        guidance_summary_hi=(
            "शीघ्र चिकित्सकीय परामर्श: गर्भावस्था में कोई भी दर्द या रक्तस्त्राव होने पर तुरंत एएनएम या नजदीकी सामुदायिक स्वास्थ्य केंद्र (CHC) जाएं।"
        ),
        guidance_summary_mr=(
            "त्वरित वैद्यकीय सल्ला: गरोदरपणात कोणताही रक्तस्त्राव किंवा तीव्र वेदना झाल्यास त्वरित आरोग्य सेविकेशी संपर्क करा किंवा सरकारी रुग्णालयात जा."
        ),
    ),
]


# ============================================================================
# TIER 3: GENERAL GUIDANCE RULES (Mild / Self-Limiting / Home Supportive Care)
# ============================================================================

GENERAL_GUIDANCE_RULES: List[TriageRule] = [
    TriageRule(
        rule_id="GENERAL_COLD_01",
        symptom_category="respiratory_mild",
        urgency="general_guidance",
        clinical_rationale="Mild upper respiratory tract infection without red flags. Self-limiting viral etiology.",
        keywords_en=[
            "mild cold", "running nose", "slight cough", "sneezing", "throat tickle", "stuffy nose"
        ],
        keywords_hi=[
            "हल्की सर्दी", "नाक बहना", "हल्की खांसी", "छींक आना", "gale me kharash", "halki sardi"
        ],
        keywords_mr=[
            "हलकी सर्दी", "नाक गळणे", "हलका खोकला", "शिंका येणे", "galyat khaskhas", "halki sardi"
        ],
        requires_immediate_bypass=False,
        referral_recommended=False,
        guidance_summary_en=(
            "General Guidance: Your symptoms suggest a common mild viral cold. Drink warm fluids, take steam inhalation, and get plenty of rest. "
            "If fever exceeds 3 days, breathing becomes difficult, or phlegm contains blood, visit your Primary Health Centre."
        ),
        guidance_summary_hi=(
            "सामान्य मार्गदर्शन: यह सामान्य मौसमी सर्दी-जुकाम के लक्षण लगते हैं। गुनगुना पानी पिएं, भाप लें और पर्याप्त आराम करें। "
            "यदि 3 दिन से अधिक बुखार रहे या सांस में तकलीफ हो, तो तुरंत डॉक्टर को दिखाएं।"
        ),
        guidance_summary_mr=(
            "सामान्य मार्गदर्शन: ही सर्वसाधारण सर्दीची लक्षणे दिसतात. कोमट पाणी प्या, वाफ घ्या आणि पुरेशी विश्रांती घ्या. "
            "जर ताप ३ दिवसांपेक्षा जास्त राहिला किंवा श्वास घेण्यास त्रास झाला तर डॉक्टरांचा सल्ला घ्या."
        ),
    ),
    TriageRule(
        rule_id="GENERAL_BODYACHE_02",
        symptom_category="musculoskeletal_mild",
        urgency="general_guidance",
        clinical_rationale="Mild musculoskeletal fatigue or exertion ache without localized swelling or trauma.",
        keywords_en=[
            "body ache", "tiredness", "mild backache", "fatigue from field work", "muscle soreness"
        ],
        keywords_hi=[
            "शरीर में दर्द", "थकान", "कमर में हल्का दर्द", "badan dard", "thakan"
        ],
        keywords_mr=[
            "अंगदुखी", "थकवा", "पाठीत हलके दुखणे", "ang dukhi", "thakva"
        ],
        requires_immediate_bypass=False,
        referral_recommended=False,
        guidance_summary_en=(
            "General Guidance: Mild fatigue and muscle aches often resolve with adequate rest, hydration, and gentle stretching. "
            "Avoid heavy lifting. If pain becomes severe or limits your walking, consult a healthcare provider."
        ),
        guidance_summary_hi=(
            "सामान्य मार्गदर्शन: हल्की थकान और बदन दर्द के लिए पर्याप्त आराम करें और पानी पिएं। "
            "यदि दर्द बहुत बढ़ जाए या चलने-फिरने में रुकावट आए, तो डॉक्टर से परामर्श लें।"
        ),
        guidance_summary_mr=(
            "सामान्य मार्गदर्शन: हलक्या अंगदुखीसाठी भरपूर विश्रांती घ्या आणि पाणी प्या. "
            "जर वेदना जास्त वाढल्या तर जवळच्या डॉक्टरांना दाखवा."
        ),
    ),
]

ALL_TRIAGE_RULES = EMERGENCY_RULES + PROMPT_ASSESSMENT_RULES + GENERAL_GUIDANCE_RULES
