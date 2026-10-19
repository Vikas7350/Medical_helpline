/**
 * Rural Feature Phone Interactive Simulator
 * Supports DTMF keypad tones, real browser microphone speech recognition (en-IN, hi-IN, mr-IN),
 * speech synthesis playback, and manual fallback text input.
 */

class FeaturePhoneSimulator {
  constructor() {
    this.sessionId = null;
    this.isActive = false;
    this.currentLanguage = "en";
    this.currentState = "OFFLINE";
    this.audioCtx = null;

    // Speech Recognition state
    this.recognition = null;
    this.isListening = false;
    this.isSubmitting = false;
    this.hasFinalResult = false;
    this.hasError = false;

    // DTMF Frequencies (Hz)
    this.dtmfFreqs = {
      "1": [697, 1209], "2": [697, 1336], "3": [697, 1477],
      "4": [770, 1209], "5": [770, 1336], "6": [770, 1477],
      "7": [852, 1209], "8": [852, 1336], "9": [852, 1477],
      "*": [941, 1209], "0": [941, 1336], "#": [941, 1477],
    };

    this.initElements();
    this.bindEvents();
  }

  initElements() {
    this.screenHeader = document.getElementById("phone-screen-header");
    this.screenContent = document.getElementById("phone-screen-content");
    this.screenStatus = document.getElementById("phone-screen-status");
    this.symptomInput = document.getElementById("phone-symptom-text");
    this.sendSymptomBtn = document.getElementById("phone-send-symptom");
    this.sendTextBtn = document.getElementById("phone-send-text");
    this.micStatusIndicator = document.getElementById("mic-status-indicator");
    this.callBtn = document.getElementById("phone-call-btn");
    this.endBtn = document.getElementById("phone-end-btn");
    this.keypadButtons = document.querySelectorAll(".keypad-btn");

    // Check browser speech recognition capability
    const hasSpeech = !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!hasSpeech && this.micStatusIndicator) {
      this.micStatusIndicator.textContent = "Mic: Not supported in this browser";
      this.micStatusIndicator.style.color = "var(--accent-amber)";
    }
  }

  bindEvents() {
    if (this.callBtn) {
      this.callBtn.addEventListener("click", () => this.startCall());
    }
    if (this.endBtn) {
      this.endBtn.addEventListener("click", () => this.endCall());
    }

    this.keypadButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const digit = btn.getAttribute("data-digit");
        this.handleDigitPress(digit);
      });
    });

    // Speak button (Microphone Speech Recognition)
    if (this.sendSymptomBtn) {
      this.sendSymptomBtn.addEventListener("click", () => this.handleSpeakClick());
    }

    // Manual Send button (Fallback typed text submission)
    if (this.sendTextBtn) {
      this.sendTextBtn.addEventListener("click", () => this.handleManualSend());
    }

    // Pressing Enter in symptom input field triggers manual send
    if (this.symptomInput) {
      this.symptomInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.handleManualSend();
        }
      });
    }

    // Cleanup when window unloads
    window.addEventListener("beforeunload", () => {
      this.cleanup();
    });
  }

  getLocaleForLanguage(lang = this.currentLanguage) {
    const langMap = {
      en: "en-IN",
      hi: "hi-IN",
      mr: "mr-IN",
    };
    return langMap[lang] || "en-IN";
  }

  getLanguageLabel(lang = this.currentLanguage) {
    const labels = {
      en: "English (en-IN)",
      hi: "Hindi - हिन्दी (hi-IN)",
      mr: "Marathi - मराठी (mr-IN)",
    };
    return labels[lang] || "English";
  }

  playDTMFTone(digit) {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      const freqs = this.dtmfFreqs[digit];
      if (!freqs) return;

      const now = this.audioCtx.currentTime;
      const osc1 = this.audioCtx.createOscillator();
      const osc2 = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc1.frequency.value = freqs[0];
      osc2.frequency.value = freqs[1];

      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 0.15);
      osc2.stop(now + 0.15);
    } catch (e) {
      console.warn("DTMF audio context not available", e);
    }
  }

  speakResponse(text, lang = "en") {
    if (!("speechSynthesis" in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const locale = this.getLocaleForLanguage(lang);
      utterance.lang = locale;

      // Select localized voice if available
      const voices = window.speechSynthesis.getVoices();
      if (voices && voices.length > 0) {
        const matchingVoice = voices.find((v) => v.lang === locale || v.lang.startsWith(lang));
        if (matchingVoice) {
          utterance.voice = matchingVoice;
        }
      }

      utterance.rate = 0.95;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("Speech synthesis error", e);
    }
  }

  async startCall() {
    this.updateScreen("Calling Rural Helpline...\n[Browser Simulation - Not a real phone connection]", "DIALING", "en");
    try {
      const response = await fetch("/api/v1/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_synthetic: false }),
      });

      if (!response.ok) throw new Error("Could not connect call.");

      const data = await response.json();
      this.sessionId = data.session_id;
      this.isActive = true;
      this.currentState = data.state;
      this.currentLanguage = "en";

      this.updateScreen(data.spoken_text, "CONNECTED - MENU", "en");
      this.speakResponse(data.spoken_text, "en");

      if (this.micStatusIndicator) {
        this.micStatusIndicator.textContent = `Mic: Ready (${this.getLocaleForLanguage("en")})`;
        this.micStatusIndicator.style.color = "var(--text-muted)";
      }
    } catch (err) {
      this.updateScreen("Call Failed: " + err.message, "ERROR", "en");
    }
  }

  async handleDigitPress(digit) {
    this.playDTMFTone(digit);

    if (!this.isActive || !this.sessionId) {
      this.screenContent.textContent = "Dialed: " + digit + "\n(Press Green CALL button to start simulation)";
      return;
    }

    if (this.currentState === "LANGUAGE_SELECT") {
      await this.selectLanguage(digit);
    } else {
      await this.sendTurn(digit, true);
    }
  }

  async selectLanguage(digit) {
    this.updateScreen("Selecting language option " + digit + "...", "PROCESSING", this.currentLanguage);
    try {
      const response = await fetch(`/api/v1/sessions/${this.sessionId}/language`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language: digit }),
      });

      const data = await response.json();
      this.currentState = data.state;
      this.currentLanguage = data.language || "en";

      const locale = this.getLocaleForLanguage(this.currentLanguage);
      if (this.micStatusIndicator) {
        this.micStatusIndicator.textContent = `Mic: Ready (${locale})`;
      }

      this.updateScreen(data.spoken_text, this.currentState, this.currentLanguage);
      this.speakResponse(data.spoken_text, this.currentLanguage);

      if (data.is_completed && window.loadAnalytics) {
        window.loadAnalytics();
      }
    } catch (err) {
      this.updateScreen("Language selection error: " + err.message, "ERROR", "en");
    }
  }

  handleSpeakClick() {
    if (!this.isActive || !this.sessionId) {
      this.updateScreen(
        "Please start the helpline session first by pressing the green CALL button.",
        "CALL REQUIRED",
        this.currentLanguage
      );
      return;
    }

    if (this.isListening) {
      // Toggle off if already listening
      this.stopListening(true);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      this.updateScreen(
        "Speech Recognition is not supported by your browser.\n\n" +
        "Please type your symptoms in the text box and click 'Send', or use Google Chrome / Microsoft Edge.",
        "UNSUPPORTED",
        this.currentLanguage
      );
      if (this.micStatusIndicator) {
        this.micStatusIndicator.textContent = "Mic: Unsupported in browser";
        this.micStatusIndicator.style.color = "var(--accent-amber)";
      }
      return;
    }

    this.startListening();
  }

  startListening() {
    if (this.isSubmitting) return;

    // Stop active speech synthesis so microphone does not pick up audio output
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const locale = this.getLocaleForLanguage(this.currentLanguage);
    const langLabel = this.getLanguageLabel(this.currentLanguage);

    try {
      this.cleanupRecognition();

      this.recognition = new SpeechRecognition();
      this.recognition.lang = locale;
      this.recognition.continuous = false;
      this.recognition.interimResults = true;
      this.recognition.maxAlternatives = 1;

      this.isListening = true;
      this.hasFinalResult = false;
      this.hasError = false;

      // Update button visual state
      if (this.sendSymptomBtn) {
        this.sendSymptomBtn.textContent = "🔴 Listening...";
        this.sendSymptomBtn.classList.add("btn-listening");
      }

      if (this.micStatusIndicator) {
        this.micStatusIndicator.textContent = `Mic: Listening (${locale})...`;
        this.micStatusIndicator.style.color = "var(--accent-red)";
      }

      this.updateScreen(
        `[Microphone Active]\nListening in ${langLabel}...\nPlease speak your symptoms into your microphone now.`,
        "LISTENING...",
        this.currentLanguage
      );

      this.recognition.onstart = () => {
        console.log(`Speech recognition started for locale: ${locale}`);
      };

      this.recognition.onresult = (event) => {
        let interimTranscript = "";
        let finalTranscript = "";

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const item = event.results[i];
          const text = item[0] ? item[0].transcript : "";
          if (item.isFinal) {
            finalTranscript += text;
          } else {
            interimTranscript += text;
          }
        }

        const currentDisplay = finalTranscript || interimTranscript;
        if (currentDisplay && this.symptomInput) {
          this.symptomInput.value = currentDisplay;
        }

        if (finalTranscript.trim()) {
          this.hasFinalResult = true;
          const transcript = finalTranscript.trim();
          this.updateScreen(
            `[Heard via Mic (${locale})]:\n"${transcript}"\n\nSubmitting to triage...`,
            "PROCESSING",
            this.currentLanguage
          );

          // Submit the actual recognized transcript
          this.submitTranscript(transcript);
        }
      };

      this.recognition.onerror = (event) => {
        this.hasError = true;
        this.handleRecognitionError(event.error, locale);
      };

      this.recognition.onend = () => {
        this.isListening = false;
        this.resetSpeakButton();

        if (!this.hasFinalResult && !this.hasError) {
          this.updateScreen(
            `No speech was detected in ${langLabel}.\n\nClick 'Speak' to try again, or type your symptoms into the input box and click 'Send'.`,
            "NO SPEECH",
            this.currentLanguage
          );
          if (this.micStatusIndicator) {
            this.micStatusIndicator.textContent = `Mic: Idle (${locale})`;
            this.micStatusIndicator.style.color = "var(--text-muted)";
          }
        }

        this.cleanupRecognition();
      };

      this.recognition.start();
    } catch (err) {
      this.isListening = false;
      this.resetSpeakButton();
      this.updateScreen(`Failed to start speech recognition: ${err.message}`, "MIC ERROR", this.currentLanguage);
    }
  }

  stopListening(userCancelled = false) {
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {}
    }
    this.cleanupRecognition();
    this.resetSpeakButton();

    if (userCancelled) {
      this.updateScreen("Microphone listening cancelled.\nType symptoms or click Speak to try again.", "CANCELLED", this.currentLanguage);
      if (this.micStatusIndicator) {
        this.micStatusIndicator.textContent = `Mic: Idle (${this.getLocaleForLanguage()})`;
        this.micStatusIndicator.style.color = "var(--text-muted)";
      }
    }
  }

  handleRecognitionError(error, locale) {
    this.resetSpeakButton();
    let message = "";
    let statusText = "MIC ERROR";

    switch (error) {
      case "not-allowed":
      case "service-not-allowed":
        message = (
          "Microphone permission was denied or blocked.\n\n" +
          "How to enable microphone in Chrome:\n" +
          "1. Click the lock/tune icon on the left of your browser address bar.\n" +
          "2. Set 'Microphone' to 'Allow'.\n" +
          "3. Reload the page or click Speak again.\n\n" +
          "(You can also type symptoms in the box below and click Send.)"
        );
        statusText = "MIC DENIED";
        if (this.micStatusIndicator) {
          this.micStatusIndicator.textContent = "Mic: Permission Denied";
          this.micStatusIndicator.style.color = "var(--accent-red)";
        }
        break;

      case "no-speech":
        message = (
          "No speech was detected by your microphone.\n\n" +
          "Please check your microphone connection, speak closer to the mic, or type your symptoms and click Send."
        );
        statusText = "NO SPEECH";
        if (this.micStatusIndicator) {
          this.micStatusIndicator.textContent = `Mic: No speech detected (${locale})`;
          this.micStatusIndicator.style.color = "var(--accent-amber)";
        }
        break;

      case "network":
        message = (
          "Network error during speech recognition.\n\n" +
          "Browser speech recognition requires internet access to connect to the speech service. " +
          "Please check your internet connection or use manual text input."
        );
        statusText = "NETWORK ERROR";
        if (this.micStatusIndicator) {
          this.micStatusIndicator.textContent = "Mic: Network Error";
          this.micStatusIndicator.style.color = "var(--accent-red)";
        }
        break;

      case "audio-capture":
        message = "No microphone was found on your device. Please plug in or enable an audio input device.";
        statusText = "NO MIC";
        if (this.micStatusIndicator) {
          this.micStatusIndicator.textContent = "Mic: Device Missing";
          this.micStatusIndicator.style.color = "var(--accent-red)";
        }
        break;

      case "aborted":
        // Graceful abort
        return;

      default:
        message = `Speech recognition error (${error}).\nPlease try again or use the manual text box below.`;
        statusText = "ERROR";
        if (this.micStatusIndicator) {
          this.micStatusIndicator.textContent = `Mic: Error (${error})`;
          this.micStatusIndicator.style.color = "var(--accent-amber)";
        }
        break;
    }

    this.updateScreen(message, statusText, this.currentLanguage);
  }

  resetSpeakButton() {
    if (this.sendSymptomBtn) {
      this.sendSymptomBtn.textContent = "🎙️ Speak";
      this.sendSymptomBtn.classList.remove("btn-listening");
    }
  }

  cleanupRecognition() {
    if (this.recognition) {
      this.recognition.onstart = null;
      this.recognition.onaudiostart = null;
      this.recognition.onspeechstart = null;
      this.recognition.onresult = null;
      this.recognition.onerror = null;
      this.recognition.onend = null;
      this.recognition = null;
    }
    this.isListening = false;
  }

  handleManualSend() {
    if (!this.isActive || !this.sessionId) {
      this.updateScreen(
        "Please start the helpline session first by pressing the green CALL button.",
        "CALL REQUIRED",
        this.currentLanguage
      );
      return;
    }

    const text = this.symptomInput ? this.symptomInput.value.trim() : "";
    if (!text) {
      this.updateScreen(
        "Please type your symptoms in the box, or click '🎙️ Speak' to dictate with your microphone.",
        "EMPTY INPUT",
        this.currentLanguage
      );
      return;
    }

    this.submitTranscript(text);
    if (this.symptomInput) {
      this.symptomInput.value = "";
    }
  }

  async submitTranscript(transcript) {
    if (this.isSubmitting) return;
    this.isSubmitting = true;

    // Stop recognition if still active
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {}
    }
    this.cleanupRecognition();
    this.resetSpeakButton();

    try {
      await this.sendTurn(transcript, false);
    } finally {
      this.isSubmitting = false;
    }
  }

  async sendTurn(userInput, isDtmf = false) {
    this.updateScreen(`Transmitting: "${userInput}"...`, "PROCESSING", this.currentLanguage);
    try {
      const response = await fetch(`/api/v1/sessions/${this.sessionId}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: userInput,
          is_dtmf: isDtmf,
        }),
      });

      if (!response.ok) {
        throw new Error(`Turn failed with status ${response.status}`);
      }

      const data = await response.json();
      this.currentState = data.state;
      this.currentLanguage = data.language || this.currentLanguage;

      let displayText = data.spoken_text;
      if (data.triage) {
        displayText = `[TRIAGE: ${data.triage.urgency_category.toUpperCase()}]\n\n${displayText}`;
      }

      this.updateScreen(displayText, this.currentState, this.currentLanguage);
      this.speakResponse(data.spoken_text, this.currentLanguage);

      if (data.should_hangup || data.is_completed) {
        if (window.loadAnalytics) {
          setTimeout(() => window.loadAnalytics(), 1000);
        }
      }
    } catch (err) {
      this.updateScreen("Turn error: " + err.message, "ERROR", this.currentLanguage);
    }
  }

  endCall() {
    this.cleanup();

    if (this.isActive && this.sessionId) {
      fetch(`/api/v1/sessions/${this.sessionId}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_input: "9", is_dtmf: true }),
      }).catch(() => {});
    }

    this.isActive = false;
    this.currentState = "CALL ENDED";
    this.updateScreen(
      "Call Disconnected.\n\nThank you for using the Rural Medical Helpline.\n[Browser Simulation Ended]",
      "OFFLINE",
      "en"
    );

    if (this.micStatusIndicator) {
      this.micStatusIndicator.textContent = "Mic: Idle";
      this.micStatusIndicator.style.color = "var(--text-muted)";
    }

    if (window.loadAnalytics) {
      setTimeout(() => window.loadAnalytics(), 800);
    }
  }

  cleanup() {
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {}
      this.cleanupRecognition();
    }
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    this.resetSpeakButton();
  }

  updateScreen(content, statusText, lang) {
    if (this.screenHeader) {
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const langLabel = { en: "EN", hi: "HI", mr: "MR" }[lang] || "EN";
      this.screenHeader.innerHTML = `<span>4G VoLTE [${langLabel}]</span><span>${timeStr}</span>`;
    }
    if (this.screenContent) {
      this.screenContent.textContent = content;
    }
    if (this.screenStatus) {
      this.screenStatus.textContent = statusText;
    }
  }
}

// Initialize on page load
window.addEventListener("DOMContentLoaded", () => {
  window.phoneSimulator = new FeaturePhoneSimulator();
});
