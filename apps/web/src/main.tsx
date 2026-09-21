import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { type Language, type Profile, type Recommendation } from "@workspot/shared";
import { getLanguageConfig, speakText, supportedLanguages } from "./languageConfig";
import { getLocaleCopy } from "./localeRuntime";
import * as apiClient from "./api/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL ?? "";
type Screen = "welcome" | "login" | "language" | "workIntro" | "recording" | "preview" | "interview" | "home" | "profile" | "opportunities" | "opportunityDetail" | "advisor" | "progress" | "notifications" | "help";
type NavScreen = Exclude<Screen, "welcome" | "login" | "language" | "workIntro" | "recording" | "preview" | "interview" | "opportunityDetail">;

const emptyProfile: Profile = { currentWork: "सिलाई / Tailoring", skills: ["सिलाई", "कढ़ाई"], craft: "सिलाई", mobility: "15 km", intent: "Self-employment", aspirations: "सिलाई की दुकान खोलना, पूंजी सहायता", district: "Varanasi", age: 28 };
const initialOpportunities: Recommendation[] = [
  { id: "tailor-edp-01", type: "Training", title: "Self Employed Tailor (सिलाई दर्जी)", provider: "Skill India Digital Hub / PM-AJAY", location: "Varanasi Skill Center, Cantt", match: 96, explanation: "NSQF Level 4 training with hands-on garment cutting, machine operation, free toolkit, and ₹1,500 monthly stipend.", tags: ["NSQF Level 4", "Free Toolkit", "Stipend ₹1500/mo", "3 Months"] },
  { id: "pm-ajay-gia-01", type: "Government support", title: "PM-AJAY Capital Asset Grant (GIA)", provider: "District Project Implementation Unit (DPIU)", location: "Varanasi District Welfare Office", match: 98, explanation: "Capital subsidy of up to 50% or ₹50,000 to purchase machinery, work tools, and initial inventory under PM-AJAY.", tags: ["₹50,000 Capital Grant", "50% Subsidy", "DPIU Fast-track"] },
  { id: "nsfdc-credit-01", type: "Government support", title: "NSFDC Micro-Credit Working Capital", provider: "National SC Finance & Development Corp", location: "Lead District Bank / CSC Center, Varanasi", match: 88, explanation: "Concessional micro-loans up to ₹2,00,000 at low interest rates (4-6% p.a.) with Mudra tie-up for equipment and working capital.", tags: ["Concessional Credit", "4-6% Interest", "Mudra Scheme"] },
  { id: "solar-training", type: "Training", title: "Solar PV Installation", provider: "Skill India Digital", location: "15 km away", match: 76, explanation: "A modern sector option that builds on your hands-on ability and has growing district demand.", tags: ["Future-ready", "6 months"] }
];

const copy: Partial<Record<Language, { nav: string[]; start: string; continue: string; workQuestion: string; workTitle: string; workHint: string; recordingTitle: string; recordingHint: string; previewTitle: string; previewHint: string; type: string; speak: string; send: string; profile: string; opportunities: string; advisor: string; progress: string; help: string; listen: string; typeHere: string; tapSpeak: string; typeAnswer: string; uploadAudio: string; understanding: string; updating: string }>> = {
  English: { nav: ["Home", "My Profile", "Opportunities", "WorkSpot AI", "Progress", "Notifications"], start: "Get Started", continue: "Continue", workQuestion: "What kind of work do you currently do?", workTitle: "Tell us about your work", workHint: "You can describe your work in your own words. For example: farming, tailoring, bamboo craft, construction, driving, shopkeeping, or any other work.", recordingTitle: "Tell us about your work", recordingHint: "Speak naturally. You can preview your answer before sending it.", previewTitle: "Your recording", previewHint: "Listen once, then explicitly send your answer when you are ready.", type: "Type", speak: "Speak", send: "Send Answer", profile: "My Work Profile", opportunities: "Opportunities for you", advisor: "WorkSpot Voice Advisor", progress: "My Progress", help: "Need Help?", listen: "Listen to question", typeHere: "Type here...", tapSpeak: "Tap to Speak", typeAnswer: "Type Answer", uploadAudio: "Upload Audio", understanding: "Understanding your answer...", updating: "WorkSpot AI is updating your work profile." },
  Hindi: { nav: ["होम", "मेरी प्रोफ़ाइल", "अवसर", "WorkSpot AI", "प्रगति", "सूचनाएं"], start: "शुरू करें", continue: "आगे बढ़ें", workQuestion: "आप अभी किस तरह का काम करते हैं?", workTitle: "अपने काम के बारे में बताएं", workHint: "अपने काम का वर्णन अपनी भाषा में करें। जैसे खेती, सिलाई, बांस का काम, निर्माण, ड्राइविंग या दुकानदारी।", recordingTitle: "अपने काम के बारे में बताएं", recordingHint: "स्वाभाविक रूप से बोलें। भेजने से पहले अपना उत्तर सुन सकते हैं।", previewTitle: "आपकी रिकॉर्डिंग", previewHint: "एक बार सुनें और तैयार होने पर अपना उत्तर भेजें।", type: "लिखें", speak: "बोलें", send: "उत्तर भेजें", profile: "मेरी कार्य प्रोफ़ाइल", opportunities: "आपके लिए अवसर", advisor: "WorkSpot वॉइस सलाहकार", progress: "मेरी प्रगति", help: "मदद चाहिए?", listen: "सवाल सुनें", typeHere: "यहां लिखें...", tapSpeak: "बोलने के लिए टैप करें", typeAnswer: "उत्तर लिखें", uploadAudio: "ऑडियो अपलोड करें", understanding: "आपके उत्तर को समझ रहे हैं...", updating: "WorkSpot AI आपकी कार्य प्रोफ़ाइल अपडेट कर रहा है।" },
  Bengali: { nav: ["হোম", "আমার প্রোফাইল", "সুযোগ", "WorkSpot AI", "অগ্রগতি", "বিজ্ঞপ্তি"], start: "শুরু করুন", continue: "এগিয়ে যান", workQuestion: "আপনি এখন কী ধরনের কাজ করেন?", workTitle: "আপনার কাজ সম্পর্কে বলুন", workHint: "আপনার কাজ নিজের ভাষায় বলুন। যেমন কৃষিকাজ, সেলাই, বাঁশের কাজ, নির্মাণ, গাড়ি চালানো বা দোকান চালানো।", recordingTitle: "আপনার কাজ সম্পর্কে বলুন", recordingHint: "স্বাভাবিকভাবে বলুন। পাঠানোর আগে রেকর্ডিং শুনতে পারবেন।", previewTitle: "আপনার রেকর্ডিং", previewHint: "একবার শুনে প্রস্তুত হলে উত্তর পাঠান।", type: "লিখুন", speak: "বলুন", send: "উত্তর পাঠান", profile: "আমার কাজের প্রোফাইল", opportunities: "আপনার জন্য সুযোগ", advisor: "WorkSpot ভয়েস উপদেষ্টা", progress: "আমার অগ্রগতি", help: "সাহায্য দরকার?", listen: "প্রশ্ন শুনুন", typeHere: "এখানে লিখুন...", tapSpeak: "বলতে ট্যাপ করুন", typeAnswer: "উত্তর লিখুন", uploadAudio: "অডিও আপলোড করুন", understanding: "আপনার উত্তর বুঝছি...", updating: "WorkSpot AI আপনার কাজের প্রোফাইল আপডেট করছে।" }
};
const questions: Partial<Record<Language, string[]>> = {
  English: ["What work do you currently do?", "How long have you been doing this work?", "What skills do you use in your work?", "What tools or equipment do you use?", "How much do you usually earn from this work?", "Would you like to improve your current work or learn a new skill?", "How far are you able to travel for work or training?", "Would you prefer a job, your own business, or either?", "What kind of work would you like to do in the future?", "Is there any difficulty or support you need to improve your work?"],
  Hindi: ["आप अभी कौन सा काम करते हैं?", "आप यह काम कितने समय से कर रहे हैं?", "आप अपने काम में किन कौशलों का उपयोग करते हैं?", "आप कौन से औज़ार या उपकरण इस्तेमाल करते हैं?", "आप इस काम से आमतौर पर कितना कमाते हैं?", "क्या आप अपना काम बेहतर करना या नया कौशल सीखना चाहेंगे?", "आप काम या प्रशिक्षण के लिए कितनी दूर जा सकते हैं?", "आप नौकरी, अपना व्यवसाय या दोनों में से क्या पसंद करेंगे?", "भविष्य में आप किस तरह का काम करना चाहेंगे?", "अपने काम को बेहतर बनाने के लिए आपको किस सहायता की जरूरत है?"],
  Bengali: ["আপনি এখন কী কাজ করেন?", "আপনি কতদিন ধরে এই কাজ করছেন?", "আপনার কাজে কোন দক্ষতাগুলি ব্যবহার করেন?", "কোন সরঞ্জাম বা যন্ত্র ব্যবহার করেন?", "এই কাজ থেকে সাধারণত কত আয় হয়?", "আপনি কি বর্তমান কাজ উন্নত করতে বা নতুন দক্ষতা শিখতে চান?", "কাজ বা প্রশিক্ষণের জন্য কত দূর যেতে পারবেন?", "চাকরি, নিজের ব্যবসা নাকি দুটোই পছন্দ করবেন?", "ভবিষ্যতে কী ধরনের কাজ করতে চান?", "কাজ উন্নত করতে আপনার কী সাহায্য প্রয়োজন?"]
};

function App() {
  const [screen, setScreen] = useState<Screen>(() => ({ "/profile": "profile", "/opportunities": "opportunities", "/ai": "advisor", "/progress": "progress", "/notifications": "notifications", "/help": "help" } as Record<string, Screen>)[window.location.pathname] ?? (window.location.pathname.startsWith("/opportunities/") ? "opportunityDetail" : "welcome"));
  const [language, setLanguageState] = useState<string>(() => localStorage.getItem("workspot.language") ?? "Hindi");
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [mobile, setMobile] = useState("+919876543210");
  const [otpSent, setOtpSent] = useState(false);
  const [textMode, setTextMode] = useState(false);
  const [answer, setAnswer] = useState("");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [interviewIndex, setInterviewIndex] = useState(1);
  const [processing, setProcessing] = useState(false);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [currentDynamicQuestion, setCurrentDynamicQuestion] = useState<string>("");
  const [dynamicOptions, setDynamicOptions] = useState<string[]>([]);
  const [opportunitiesList, setOpportunitiesList] = useState<Recommendation[]>(initialOpportunities);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);
  const recordingCancelledRef = useRef(false);
  const recognitionRef = useRef<any>(null);
  const [activeOpportunity, setActiveOpportunity] = useState<Recommendation>(() => initialOpportunities[0]);
  const [filter, setFilter] = useState("All");
  const [saved, setSaved] = useState<string[]>([]);
  const [advisorInput, setAdvisorInput] = useState("");
  const [advisorMessages, setAdvisorMessages] = useState([
    { from: "ai", text: "नमस्ते! मैं पीएम-अजय आजीविका सलाहकार हूँ। आप कौशल प्रशिक्षण, टूल-किट, ₹50,000 की पूंजीगत सब्सिडी (GIA) या स्वरोज़गार ऋण के बारे में कुछ भी पूछ सकते हैं।" }
  ]);
  const setLanguage = (value: string) => { setLanguageState(value); localStorage.setItem("workspot.language", value); };
  const c = getLocaleCopy(language, copy[language as Language] ?? copy.English!);
  const isProduct = !["welcome", "login", "language", "workIntro", "recording", "preview", "interview"].includes(screen);

  useEffect(() => { if (screen !== "recording") return; const timer = window.setInterval(() => setRecordingSeconds((value) => value + 1), 1000); return () => window.clearInterval(timer); }, [screen]);
  useEffect(() => () => { mediaRecorderRef.current?.stream.getTracks().forEach((track) => track.stop()); if (recordingUrl) URL.revokeObjectURL(recordingUrl); }, [recordingUrl]);

  async function createSession(): Promise<string | null> {
    try {
      const data = await apiClient.createSession(language, mobile);
      const sid = data.session_id || data.id;
      setSessionId(sid);
      if (data.initial_prompt_indic) setCurrentDynamicQuestion(data.initial_prompt_indic);
      if (data.options && data.options.length > 0) setDynamicOptions(data.options);
      if (data.profile) setProfile(data.profile);
      return sid;
    } catch (err) {
      console.warn("Backend session creation fallback:", err);
      const randomPart = window.crypto.getRandomValues(new Uint32Array(1))[0].toString(36).padStart(8, "0").slice(0, 8);
      const fallbackId = `ws_${randomPart}`;
      setSessionId(fallbackId);
      return fallbackId;
    }
  }

  function goTo(target: Screen, explicitPath?: string) {
    setScreen(target);
    const path = explicitPath ?? (target === "profile" ? "/profile" : target === "opportunities" ? "/opportunities" : target === "advisor" ? "/ai" : target === "progress" ? "/progress" : target === "notifications" ? "/notifications" : target === "help" ? "/help" : target === "opportunityDetail" ? `/opportunities/${activeOpportunity.id}` : "/");
    window.history.pushState({}, "", path);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startRecording() {
    setRecordingSeconds(0);
    setRecordingUrl(null);
    setIsRecording(false);
    recordingCancelledRef.current = false;
    goTo("recording");

    // Start browser speech recognition for live transcription
    try {
      const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRec) {
        const rec = new SpeechRec();
        rec.lang = getLanguageConfig(language).asrCode || "hi-IN";
        rec.continuous = true;
        rec.interimResults = true;
        rec.onresult = (evt: any) => {
          const text = Array.from(evt.results).map((r: any) => r[0].transcript).join("");
          if (text) setAnswer(text);
        };
        rec.start();
        recognitionRef.current = rec;
      }
    } catch (e) {
      console.warn("SpeechRecognition start error:", e);
    }

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") return;
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      if (recordingCancelledRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      const recorder = new MediaRecorder(stream);
      recordingChunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size > 0) recordingChunksRef.current.push(event.data); };
      recorder.onstop = () => {
        const blob = new Blob(recordingChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setRecordingUrl(URL.createObjectURL(blob));
        setIsRecording(false);
        mediaRecorderRef.current = null;
        stream.getTracks().forEach((track) => track.stop());
        goTo("preview");
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    }).catch(() => setIsRecording(false));
  }

  function stopRecording() {
    recordingCancelledRef.current = true;
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    else goTo("preview");
  }

  function logout() {
    const activeSessionId = sessionId;
    if (activeSessionId) void apiClient.deleteSession(activeSessionId);
    setSessionId(null);
    setOtpSent(false);
    setTextMode(false);
    setAnswer("");
    setRecordingSeconds(0);
    setInterviewIndex(1);
    setProcessing(false);
    setProfile(emptyProfile);
    setSaved([]);
    setAdvisorInput("");
    setDynamicOptions([]);
    setAdvisorMessages([{ from: "ai", text: "नमस्ते! मैं पीएम-अजय आजीविका सलाहकार हूँ।" }]);
    goTo("welcome");
  }

  async function submitTurn(userText: string) {
    const text = userText.trim();
    if (!text) return;
    setProcessing(true);
    try {
      let sid = sessionId;
      if (!sid) sid = await createSession();
      if (!sid) sid = "ws_demo";

      const res = await apiClient.sendInteraction(sid, text, language);
      if (res.profile) setProfile(res.profile);
      if (res.recommended_courses && res.recommended_courses.length > 0) {
        setOpportunitiesList(res.recommended_courses);
        setActiveOpportunity(res.recommended_courses[0]);
      }
      if (res.spoken_response_indic) {
        setCurrentDynamicQuestion(res.spoken_response_indic);
        listen(res.spoken_response_indic);
      }
      if (res.options && res.options.length > 0) {
        setDynamicOptions(res.options);
      }
      setAnswer("");
      if (res.is_complete || res.current_state === "RECOMMENDATION_DELIVERY" || res.current_state === "COMPLETED") {
        goTo("opportunities");
      } else {
        setScreen("interview");
        setInterviewIndex((prev) => Math.min(prev + 1, 10));
      }
    } catch (err) {
      console.warn("submitTurn error, fallback progression:", err);
      setInterviewIndex((prev) => (prev >= 10 ? 10 : prev + 1));
      setScreen("interview");
    } finally {
      setProcessing(false);
    }
  }

  function finishAnswer(value: string) {
    if (!value.trim()) return;
    void submitTurn(value);
  }

  function nextInterview() {
    if (answer.trim()) {
      void submitTurn(answer);
    } else {
      setInterviewIndex((value) => (value >= 10 ? 10 : value + 1));
    }
  }

  function listen(text: string) { speakText(text, language); }
  const currentQuestions = questions[language as Language] ?? questions.English ?? [];
  const activeQuestion = currentDynamicQuestion || currentQuestions[Math.min(interviewIndex - 1, 9)] || "";

  return <div className="app-shell">{!isProduct ? <Onboarding screen={screen} language={language} setLanguage={setLanguage} copy={c} mobile={mobile} setMobile={setMobile} otpSent={otpSent} setOtpSent={setOtpSent} textMode={textMode} setTextMode={setTextMode} answer={answer} setAnswer={setAnswer} recordingSeconds={recordingSeconds} setRecordingSeconds={setRecordingSeconds} interviewIndex={interviewIndex} processing={processing} currentQuestion={activeQuestion} options={dynamicOptions} onOptionSelect={(opt: string) => void submitTurn(opt)} audioUrl={recordingUrl} isRecording={isRecording} onStart={() => goTo("language")} onLogin={() => setOtpSent(true)} onVerify={async () => { await createSession(); goTo("workIntro"); }} onLanguageContinue={() => goTo("login")} onSpeak={startRecording} onStop={stopRecording} onSend={finishAnswer} onNext={nextInterview} onListen={listen} onBack={() => goTo("workIntro")} /> : <AppFrame screen={screen as NavScreen} language={language} setLanguage={setLanguage} copy={c} profile={profile} setProfile={setProfile} goTo={goTo} onLogout={logout} opportunities={opportunitiesList} filter={filter} setFilter={setFilter} activeOpportunity={activeOpportunity} setActiveOpportunity={setActiveOpportunity} saved={saved} setSaved={setSaved} advisorInput={advisorInput} setAdvisorInput={setAdvisorInput} advisorMessages={advisorMessages} setAdvisorMessages={setAdvisorMessages} sessionId={sessionId} />}</div>;
}

function Logo({ tagline = "Your skills. Your work. Your future." }: { tagline?: string }) { return <div className="logo"><span>W</span><div><strong>WorkSpot</strong><small>{tagline}</small></div></div>; }
function OnboardingFrame({ children, language, setLanguage, copy }: { children: React.ReactNode; language: Language; setLanguage: (v: Language) => void; copy?: any }) { const tagline = copy?.ui?.brandTagline ?? "Your skills. Your work. Your future."; return <div className="onboarding"><header className="onboarding-header"><Logo tagline={tagline} /><LanguageSelector language={language} setLanguage={(value) => setLanguage(value as Language)} /></header>{children}<footer className="simple-footer"><span>WorkSpot · {tagline}</span><span>Protected by design · Voice-first · Multilingual</span></footer></div>; }
function AudioPreview({ audioUrl, duration, language, fallbackText }: { audioUrl: string | null; duration: number; language: string; fallbackText: string }) { const audioRef = useRef<HTMLAudioElement | null>(null); const [playing, setPlaying] = useState(false); useEffect(() => { setPlaying(false); if (audioRef.current) { audioRef.current.pause(); audioRef.current.currentTime = 0; } }, [audioUrl]); async function togglePlayback() { if (!audioUrl || !audioRef.current) { setPlaying(true); speakText(fallbackText, language); window.setTimeout(() => setPlaying(false), 1600); return; } if (playing) { audioRef.current.pause(); setPlaying(false); } else { try { await audioRef.current.play(); setPlaying(true); } catch { setPlaying(false); } } } return <div className="audio-player"><button type="button" aria-label={playing ? "Pause recording" : "Play recording"} onClick={togglePlayback}>{playing ? "■" : "▶"}</button><strong>00:{String(duration || 8).padStart(2, "0")}</strong><span className="audio-line"><i className={playing ? "playing" : ""} /></span><span>1:00</span>{audioUrl && <audio ref={audioRef} src={audioUrl} onEnded={() => setPlaying(false)} />}</div>; }

function Onboarding(p: any) { if (p.screen === "welcome") return <div className="welcome-page"><header><Logo tagline={p.copy.ui?.brandTagline} /><div className="welcome-header-actions"><LanguageSelector language={p.language} setLanguage={p.setLanguage} /><button className="ghost-button" onClick={p.onStart}>{p.copy.ui?.signIn ?? "Sign in"}</button></div></header><div className="welcome-grid"><div className="welcome-copy"><span className="eyebrow">{p.copy.ui?.welcomeEyebrow ?? "AI-POWERED LIVELIHOOD ASSISTANT"}</span><h1>{p.copy.ui?.welcomeTitle ?? "Find the work that fits"} <em>{p.copy.ui?.welcomeAccent ?? "you."}</em></h1><p>{p.copy.ui?.welcomeDescription ?? "Tell WorkSpot what you do, what you know, and what you want to achieve. Our AI will help you discover training, jobs, and livelihood opportunities."}</p><div className="welcome-actions"><button className="primary-button" onClick={p.onStart}>{p.copy.start}<span>→</span></button><button className="secondary-button" onClick={() => document.getElementById("learn-more")?.scrollIntoView({ behavior: "smooth" })}>{p.copy.ui?.learnMore ?? "Learn more"}</button></div><div className="trust-row"><span>▣ {p.copy.ui?.protected ?? "Your information stays protected"}</span><span>◎ {p.copy.ui?.multilingual ?? "Multilingual"}</span><span>◉ {p.copy.ui?.voiceFirst ?? "Voice-first"}</span></div></div><div className="welcome-art"><div className="art-glow" /><div className="art-orb"><span>W</span></div><div className="art-card art-card-one"><strong>WorkSpot AI</strong><span>{p.copy.ui?.listeningInLanguage ?? "Listening in your language"}</span></div><div className="art-card art-card-two"><span className="mini-score">82</span><div><strong>{p.copy.ui?.workProgressScore ?? "Work & Progress Score"}</strong><small>{p.copy.ui?.updatedWithProgress ?? "Updated with your progress"}</small></div></div></div></div><section id="learn-more" className="learn-strip"><div><span className="eyebrow">{p.copy.ui?.simpleConversation ?? "A SIMPLE CONVERSATION"}</span><h2>{p.copy.ui?.workStartingPoint ?? "Your work is the starting point."}</h2></div><p>{p.copy.ui?.workDescription ?? "WorkSpot listens, understands your experience, and helps you take the next useful step—whether that is better training, a nearby job, or support to grow your own work."}</p></section></div>;
  if (p.screen === "login") return <OnboardingFrame language={p.language} setLanguage={p.setLanguage} copy={p.copy}><div className="center-screen"><div className="auth-card"><span className="eyebrow">{p.copy.ui?.welcomeBack ?? "WELCOME BACK"}</span><h1>Welcome to WorkSpot</h1><p>{p.copy.ui?.signInJourney ?? "Sign in to continue your journey."}</p>{!p.otpSent ? <><label>{p.copy.ui?.mobileNumber ?? "Mobile number"}</label><input className="large-input" value={p.mobile} onChange={(e) => p.setMobile(e.target.value)} placeholder={p.copy.ui?.enterMobile ?? "Enter your mobile number"} inputMode="tel" /><button className="primary-button" onClick={p.onLogin}>{p.copy.ui?.sendOtp ?? "Send OTP"} <span>→</span></button></> : <><label>{p.copy.ui?.otpLabel ?? "Enter the 6-digit OTP"}</label><input className="large-input otp-input" placeholder="• • • • • •" inputMode="numeric" /><button className="primary-button" onClick={p.onVerify}>{p.copy.ui?.verifyContinue ?? "Verify and continue"} <span>→</span></button><div className="auth-links"><button onClick={() => p.setOtpSent(false)}>{p.copy.ui?.changeNumber ?? "Change number"}</button><button>{p.copy.ui?.resendOtp ?? "Resend OTP"}</button></div></>}<button className="whatsapp-button">{p.copy.ui?.whatsapp ?? "Continue with WhatsApp"} <span>↗</span></button><small className="privacy-note">{p.copy.ui?.privacy ?? "Your information is used only to provide personalized work and training recommendations."}</small></div></div></OnboardingFrame>;
  if (p.screen === "language") return <OnboardingFrame language={p.language} setLanguage={p.setLanguage} copy={p.copy}><div className="center-screen"><div className="language-card"><span className="eyebrow">{p.copy.ui?.languageEyebrow ?? "ONE CONVERSATION, YOUR LANGUAGE"}</span><h1>{p.copy.ui?.chooseLanguage ?? "Choose your language"}</h1><p>{p.copy.ui?.languageDescription ?? "WorkSpot will communicate with you in your selected language."}</p><div className="language-options">{supportedLanguages.map((item) => <button key={item.code} className={p.language === item.name ? "language-option active" : "language-option"} onClick={() => p.setLanguage(item.name)}><span className="language-icon">{item.nativeName.charAt(0)}</span><span><strong>{item.nativeName}</strong><small>{item.name}</small></span><span className="speaker">◉ {p.copy.ui?.preview ?? "Preview"}</span><i>{p.language === item.name ? "✓" : ""}</i></button>)}</div><button className="primary-button" onClick={p.onLanguageContinue}>{p.copy.continue}<span>→</span></button></div></div></OnboardingFrame>;
  if (p.screen === "workIntro") return <OnboardingFrame language={p.language} setLanguage={p.setLanguage} copy={p.copy}><div className="conversation-shell"><div className="conversation-heading"><span className="eyebrow">WORKSPOT AI · STEP 1 OF 10</span><h1>{p.copy.workTitle}</h1><p>{p.copy.workHint}</p></div><div className="ai-question-card"><div className="ai-card-top"><span className="ai-avatar">W</span><div><strong>WorkSpot AI</strong><small>Speaking in {p.language}</small></div><button className="listen-button" onClick={() => p.onListen(p.copy.workQuestion)}>◉ {p.copy.listen}</button></div><h2>{p.copy.workQuestion}</h2>{p.options && p.options.length > 0 && <div className="mcq-options-grid">{p.options.map((opt: string, idx: number) => <button key={opt} type="button" className="mcq-option-chip" onClick={() => p.onOptionSelect(opt)}><span className="mcq-opt-num">{idx + 1}</span><span className="mcq-opt-text">{opt}</span><span className="mcq-opt-arrow">→</span></button>)}</div>}<div className="input-choice"><button className="voice-choice" onClick={p.onSpeak}><span className="voice-icon">◉</span><strong>{p.copy.speak}</strong><small>{p.copy.ui?.useYourVoice ?? "Use your voice"}</small></button><button className="type-choice" onClick={() => p.setTextMode(true)}><span>⌨</span><strong>{p.copy.type}</strong><small>{p.copy.ui?.writeAnswer ?? "Write your answer"}</small></button></div>{p.textMode && <div className="text-answer"><textarea value={p.answer} onChange={(e) => p.setAnswer(e.target.value)} placeholder={p.copy.typeHere} /><button className="primary-button" onClick={() => p.onSend(p.answer)}>{p.copy.send}<span>→</span></button></div>}<p className="assist-note">{p.copy.ui?.privateAnswer ?? "Your answer is private. You can correct it at any time."}</p></div></div></OnboardingFrame>;
  if (p.screen === "recording") return <OnboardingFrame language={p.language} setLanguage={p.setLanguage} copy={p.copy}><div className="recording-shell"><span className="eyebrow">WORKSPOT AI · RECORDING</span><h1>{p.copy.recordingTitle}</h1><p>{p.copy.recordingHint}</p><div className="recording-panel"><div className="recording-mic"><span>◉</span></div><strong>{p.copy.ui?.recording ?? "Recording..."}</strong><div className="waveform">{Array.from({ length: 26 }, (_, i) => <i key={i} style={{ height: `${18 + ((i * 17) % 43)}px` }} />)}</div><div className="timer">00:{String(p.recordingSeconds).padStart(2, "0")}</div><div className="recording-actions"><button className="secondary-button" onClick={() => { p.setRecordingSeconds(0); p.onBack(); }}>{p.copy.ui?.cancel ?? "Cancel"}</button><button className="stop-button" onClick={p.onStop}>{p.copy.ui?.stopRecording ?? "Stop Recording"}</button></div></div></div></OnboardingFrame>;
  if (p.screen === "preview") return <OnboardingFrame language={p.language} setLanguage={p.setLanguage} copy={p.copy}><div className="recording-shell"><span className="eyebrow">{p.copy.previewLabel ?? "WORKSPOT AI · PREVIEW"}</span><h1>{p.copy.previewTitle}</h1><p>{p.copy.previewHint}</p><div className="preview-panel"><AudioPreview audioUrl={p.audioUrl} duration={p.recordingSeconds} language={p.language} fallbackText={p.copy.previewTitle} /><div style={{ margin: "12px 0", textAlign: "left" }}><small style={{ opacity: 0.8, display: "block", marginBottom: "4px" }}>Recognized speech / बोली गई आवाज़:</small><input style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.2)", background: "rgba(0,0,0,0.2)", color: "inherit" }} value={p.answer} onChange={(e) => p.setAnswer(e.target.value)} placeholder="बोलल गइल बात / Type or adjust words..." /></div><div className="preview-actions"><button className="secondary-button" onClick={p.onSpeak}>◉ {p.copy.recordAgain ?? "Record Again"}</button><button className="primary-button" onClick={() => p.onSend(p.answer.trim() || "हम सिलाई मशीन के दुकान खोलल चाहत बानी, 40000 के पूंजी चाही")}>{p.copy.send}<span>→</span></button></div><button className="text-button" onClick={() => { p.setTextMode(true); p.onBack(); }}>{p.copy.typeInstead ?? "Type instead"}</button></div></div></OnboardingFrame>;
  return <OnboardingFrame language={p.language} setLanguage={p.setLanguage} copy={p.copy}><div className="conversation-shell interview-shell"><div className="interview-top"><div><span className="eyebrow">WORKSPOT AI · BUILDING YOUR WORK PROFILE</span><h1>WorkSpot AI</h1></div><div className="question-counter">{p.copy.ui?.question ?? "Question"} <strong>{p.interviewIndex}</strong> {p.copy.ui?.of ?? "of"} 10</div></div><div className="progress-bar"><i style={{ width: `${p.interviewIndex * 10}%` }} /></div>{p.processing ? <div className="processing-card"><div className="processing-orb">W</div><h2>{p.copy.understanding}</h2><p>{p.copy.updating}</p><div className="processing-dots"><i /><i /><i /></div></div> : <><div className="ai-question-card large"><div className="ai-card-top"><span className="ai-avatar">W</span><div><strong>WorkSpot AI</strong><small>{p.language}</small></div><button className="listen-button" onClick={() => p.onListen(p.currentQuestion)}>◉ {p.copy.listen}</button></div><h2>{p.currentQuestion}</h2>{p.options && p.options.length > 0 && <div className="mcq-options-grid">{p.options.map((opt: string, idx: number) => <button key={opt} type="button" className="mcq-option-chip" onClick={() => p.onOptionSelect(opt)}><span className="mcq-opt-num">{idx + 1}</span><span className="mcq-opt-text">{opt}</span><span className="mcq-opt-arrow">→</span></button>)}</div>}</div><div className="answer-toolbar"><button className="voice-action" onClick={p.onSpeak}><span>◉</span><strong>{p.copy.tapSpeak}</strong></button><button onClick={() => p.setTextMode(true)}><span>⌨</span> {p.copy.typeAnswer}</button><button><span>▣</span> {p.copy.uploadAudio}</button></div>{p.textMode && <div className="text-answer interview-input"><textarea value={p.answer} onChange={(e) => p.setAnswer(e.target.value)} placeholder={p.copy.typeHere} /><button className="primary-button" onClick={p.onNext}>{p.copy.send}<span>→</span></button></div>}<p className="assist-note centered">{p.copy.ui?.voicePrimary ?? "Voice is primary. Tap, type, or upload whenever it is easier."}</p></>}</div></OnboardingFrame>;
}

function LanguageMenu({ language, setLanguage, onClose }: { language: string; setLanguage: (value: string) => void; onClose: () => void }) { const [query, setQuery] = useState(""); const selected = getLanguageConfig(language); const filtered = supportedLanguages.filter((item) => `${item.name} ${item.nativeName}`.toLowerCase().includes(query.toLowerCase())); return <div className="language-popover" role="dialog" aria-label="Choose your language"><div className="popover-heading"><div><span className="eyebrow">LANGUAGE</span><strong>Choose your language</strong></div><button aria-label="Close language selector" onClick={onClose}>×</button></div><input className="language-search" autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search language..." /> <div className="language-list" role="listbox">{filtered.map((item) => <button role="option" aria-selected={item.name === selected.name} className={item.name === selected.name ? "language-row selected" : "language-row"} key={item.code} onClick={() => { setLanguage(item.name); onClose(); }}><span><strong>{item.nativeName}</strong><small>{item.name}</small></span><span>{item.name === selected.name ? "✓" : ""}</span></button>)}</div></div>; }
function LanguageSelector({ language, setLanguage }: { language: string; setLanguage: (value: string) => void }) { const [open, setOpen] = useState(false); const selected = getLanguageConfig(language); useEffect(() => { const close = (event: MouseEvent | KeyboardEvent) => { const outside = event instanceof MouseEvent && !(event.target as Element).closest(".language-selector"); const escape = event instanceof KeyboardEvent && event.key === "Escape"; if (outside || escape) setOpen(false); }; document.addEventListener("mousedown", close); document.addEventListener("keydown", close); return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); }; }, []); return <div className="header-popover-wrap language-selector"><button className="header-language" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((value) => !value)}>{selected.nativeName}⌄</button>{open && <LanguageMenu language={language} setLanguage={setLanguage} onClose={() => setOpen(false)} />}</div>; }

function ProfileMenu({ goTo, onClose, onLogout }: { goTo: (target: Screen) => void; onClose: () => void; onLogout: () => void }) { useEffect(() => { const close = (event: MouseEvent | KeyboardEvent) => { const outside = event instanceof MouseEvent && !(event.target as Element).closest(".header-popover-wrap"); const escape = event instanceof KeyboardEvent && event.key === "Escape"; if (outside || escape) onClose(); }; document.addEventListener("mousedown", close); document.addEventListener("keydown", close); return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); }; }, [onClose]); return <div className="profile-popover" role="menu"><div className="profile-popover-head"><span className="avatar">AD</span><div><strong>Anita Das</strong><small>Bamboo Craft Worker</small></div></div><button role="menuitem" onClick={() => { goTo("profile"); onClose(); }}>My Profile <span>→</span></button><button role="menuitem" onClick={onClose}>Settings <span>→</span></button><button role="menuitem" onClick={() => { goTo("help"); onClose(); }}>Help <span>→</span></button><button className="profile-logout" role="menuitem" onClick={() => { onLogout(); onClose(); }}>Logout <span>↗</span></button></div>; }

function AppFrame(p: any) {
  const c = p.copy;
  const targets: NavScreen[] = ["home", "profile", "opportunities", "advisor", "progress", "notifications"];
  const [profileOpen, setProfileOpen] = useState(false);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setProfileOpen(false);
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, []);
  return <div className="product-layout">
    <aside className="sidebar">
      <Logo tagline={c.ui?.brandTagline} />
      <div className="sidebar-label">WORKSPACE</div>
      <nav>{c.nav.map((item: string, index: number) => <button key={item} className={p.screen === targets[index] ? "nav-item active" : "nav-item"} onClick={() => p.goTo(targets[index])}><span>{["⌂", "◎", "▣", "✦", "↗", "◌"][index]}</span>{item}{index === 5 && <b>2</b>}</button>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item" onClick={() => p.goTo("help")}><span>?</span>{c.help}</button><div className="sidebar-user"><span className="avatar">AD</span><div><strong>Anita Das</strong><small>Kolkata, India</small></div><span>•••</span></div></div>
    </aside>
    <main className="product-main">
      <header className="product-header"><div className="mobile-brand"><Logo tagline={c.ui?.brandTagline} /></div><div className="breadcrumb">WorkSpot <span>/</span> {p.screen === "profile" ? c.profile : p.screen === "opportunities" ? c.opportunities : p.screen === "advisor" ? c.advisor : p.screen === "progress" ? c.progress : p.screen === "help" ? c.help : "Home"}</div><div className="header-actions"><LanguageSelector language={p.language} setLanguage={p.setLanguage} /><button className="help-link" onClick={() => p.goTo("help")}>Help</button><div className="header-popover-wrap"><button className="header-avatar" aria-label="Open profile menu" aria-haspopup="menu" aria-expanded={profileOpen} onClick={() => setProfileOpen((value) => !value)}>AD</button>{profileOpen && <ProfileMenu goTo={p.goTo} onClose={() => setProfileOpen(false)} onLogout={p.onLogout} />}</div></div></header>
      {p.screen === "profile" && <ProfilePage {...p} />}
      {p.screen === "opportunities" && <OpportunitiesPage {...p} />}
      {p.screen === "opportunityDetail" && <OpportunityDetail {...p} />}
      {p.screen === "advisor" && <AdvisorPage {...p} />}
      {p.screen === "progress" && <ProgressPage {...p} />}
      {p.screen === "notifications" && <NotificationsPage {...p} />}
      {p.screen === "help" && <HelpPage {...p} />}
      {p.screen === "home" && <HomePage {...p} />}
      {!(["profile", "opportunities", "opportunityDetail", "advisor", "progress", "notifications", "help", "home"] as string[]).includes(p.screen) && <HomePage {...p} />}
    </main>
    <nav className="mobile-nav"><button onClick={() => p.goTo("home" as Screen)}><span>⌂</span>{c.nav[0]}</button><button onClick={() => p.goTo("opportunities")}><span>▣</span>{c.nav[2]}</button><button onClick={() => p.goTo("advisor")}><span>✦</span>{c.nav[3]}</button><button onClick={() => p.goTo("progress")}><span>↗</span>{c.nav[4]}</button></nav>
  </div>;
}

function PageHeader({ eyebrow, title, subtitle, action }: { eyebrow?: string; title: string; subtitle?: string; action?: React.ReactNode }) { return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action}</div>; }
function HomePage(p: any) { const u = p.copy.ui ?? {}; return <div className="page home-page"><div className="home-hero"><div><span className="eyebrow">{u.homeEyebrow ?? "GOOD MORNING, ANITA"}</span><h1>{u.homeTitle ?? "What would you like to work on today?"}</h1><p>{u.homeDescription ?? "WorkSpot is here to help you find the next useful step in your work journey."}</p><div className="home-actions"><button className="primary-button" onClick={() => p.goTo("advisor")}>{u.askAI ?? "Ask WorkSpot AI"} <span>→</span></button><button className="secondary-button" onClick={() => p.goTo("opportunities")}>{u.exploreOpportunities ?? "Explore opportunities"}</button></div></div><div className="home-hero-orb"><div className="orb-core">W</div><span>{u.listeningInLanguage ?? "Ready to listen"}</span></div></div><div className="section-row"><div><span className="eyebrow">{u.snapshot ?? "YOUR SNAPSHOT"}</span><h2>{u.keepMoving ?? "Keep moving forward"}</h2></div><button className="text-button" onClick={() => p.goTo("progress")}>{u.viewProgress ?? "View progress"} →</button></div><div className="snapshot-grid"><StatCard label={u.score ?? "Work & Progress Score"} value="82" detail={u.thisMonth ?? "+4 this month"} accent="mint" /><StatCard label={u.profileCompleteness ?? "Profile completeness"} value="90%" detail={u.detailsLeft ?? "2 details left"} accent="blue" /><StatCard label={u.savedOpportunities ?? "Saved opportunities"} value="3" detail={u.closingSoon ?? "1 closing soon"} accent="purple" /></div><div className="home-columns"><div className="surface-card next-step"><div className="card-heading"><div><span className="eyebrow">{u.recommendedNext ?? "RECOMMENDED NEXT STEP"}</span><h2>{u.continueTraining ?? "Continue your training journey"}</h2></div><span className="badge green">{u.inProgress ?? "In progress"}</span></div><p>{u.trainingDescription ?? "You enrolled in Bamboo Craft Training last week. Log your first session to keep your profile up to date."}</p><div className="mini-progress"><span style={{ width: "42%" }} /></div><div className="progress-meta"><span>42% {u.completed ?? "complete"}</span><span>3 of 8 {u.trainingCompletion ?? "sessions"}</span></div><button className="secondary-button small" onClick={() => p.goTo("progress")}>{u.updateProgress ?? "Update progress"} <span>→</span></button></div><div className="surface-card opportunity-teaser"><div className="card-heading"><div><span className="eyebrow">{u.matchedForYou ?? "MATCHED FOR YOU"}</span><h2>Bamboo Craft Training</h2></div><strong className="match-pill">92%</strong></div><p>Skill India Digital · 8 km away · 3 months</p><div className="why-line">✓ {u.matchesExperience ?? "Matches your existing experience"}</div><button className="text-button" onClick={() => { p.setActiveOpportunity(p.opportunities[0]); p.goTo("opportunityDetail", `/opportunities/${p.opportunities[0]?.id || "bamboo-training"}`); }}>{u.viewOpportunity ?? "View opportunity"} →</button></div></div></div>; }
function StatCard({ label, value, detail, accent }: { label: string; value: string; detail: string; accent: string }) { return <div className={`stat-card ${accent}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>; }
function ProfilePage(p: any) { return <div className="page"><PageHeader eyebrow="YOUR WORK JOURNEY" title={p.copy.profile} subtitle={p.copy.ui?.profileSubtitle ?? "A living profile that grows as WorkSpot learns about your work and progress."} action={<button className="primary-button compact" onClick={() => p.goTo("advisor")}>{p.copy.ui?.updateWithAI ?? "Update with AI"} <span>✦</span></button>} /><div className="profile-overview surface-card"><div className="profile-person"><span className="large-avatar">AD</span><div><span className="badge green">● Profile Active</span><h2>{p.profile?.currentWork ? `${p.profile.currentWork} Artisan` : "Beneficiary Profile"}</h2><p>{p.profile?.district || "Varanasi"}, India</p><div className="profile-tags"><span>{p.language}</span><span>{p.profile?.mobility || "15 km mobility"}</span><span>{p.profile?.intent || "Self-employment"}</span></div></div></div><div className="score-display"><div className="score-circle"><strong>88</strong><span>score</span></div><div><h3>Work & Progress Score</h3><p>Based on PM-AJAY skill qualification and livelihood pathway readiness.</p><button className="info-button">i</button></div></div></div><div className="completion-card surface-card"><div><span className="eyebrow">{p.copy.ui?.profileCompleteness ?? "PROFILE COMPLETENESS"}</span><strong>95%</strong></div><div className="completion-bar"><span style={{ width: "95%" }} /></div><p>{p.copy.ui?.completeDetails ?? "Your enterprise and skill profile has been synchronized with the PM-AJAY district desk."}</p><button className="secondary-button small" onClick={() => p.goTo("opportunities")}>View recommendations <span>→</span></button></div><div className="section-row"><div><span className="eyebrow">{p.copy.ui?.yourInformation ?? "YOUR INFORMATION"}</span><h2>{p.copy.ui?.everything ?? "Everything in one place"}</h2></div><span className="muted-label">{p.copy.ui?.editable ?? "All sections are editable"}</span></div><div className="detail-grid"><EditableCard title="Personal details" rows={[["District", p.profile?.district || "Varanasi"], ["Phone", p.mobile || "+919876543210"], ["Caste Category", "Scheduled Caste (SC)"], ["Language", p.language]]} /><EditableCard title="Work & Trade" rows={[["Current Occupation", p.profile?.currentWork || "Tailoring / সिलाई"], ["Skills", (p.profile?.skills || ["Garment cutting"]).join(", ")], ["Craft / Trade", p.profile?.craft || "Tailoring"], ["Aspirations", p.profile?.aspirations || "Enterprise setup"]]} /><EditableCard title="Work Preferences" rows={[["Preference", p.profile?.intent || "Self-employment"], ["Travel Mobility", p.profile?.mobility || "15 km"], ["Preferred Hub", p.profile?.district || "Varanasi"]]} /><EditableCard title="Government Scheme Eligibility" rows={[["PM-AJAY Capital Grant", "Eligible (Up to ₹50,000 / 50% Subsidy)"], ["NSFDC Micro-Credit", "Eligible (Up to ₹2,00,000 at 4-6%)"], ["Free Toolkit Support", "Approved on course enrollment"]]} /></div></div>; }
function EditableCard({ title, rows }: { title: string; rows: string[][] }) { return <div className="detail-card surface-card"><div className="card-heading"><h3>{title}</h3><button className="edit-button">Edit</button></div>{rows.map(([key, value]) => <div className="detail-row" key={key}><span>{key}</span><strong>{value}</strong></div>)}</div>; }
function OpportunitiesPage(p: any) { const u = p.copy.ui ?? {}; const filterLabels: Record<string, string> = { All: u.all ?? "All", Job: u.jobs ?? "Jobs", Training: u.training ?? "Training", "Self-employment": u.selfEmployment ?? "Self-employment", "Government support": u.schemes ?? "Schemes" }; const filtered = p.filter === "All" ? p.opportunities : p.opportunities.filter((item: Recommendation) => item.type === p.filter); return <div className="page"><PageHeader eyebrow="PERSONALIZED FOR YOU" title={p.copy.opportunities} subtitle={u.opportunitiesSubtitle ?? "Based on your skills, experience, location and goals."} action={<button className="secondary-button compact">{`⌕ ${u.searchOpportunities ?? "Search opportunities"}`}</button>} /><div className="filter-row">{["All", "Job", "Training", "Self-employment", "Government support"].map((item) => <button key={item} className={p.filter === item ? "filter-chip active" : "filter-chip"} onClick={() => p.setFilter(item)}>{filterLabels[item]}</button>)}</div><div className="opportunities-grid">{filtered.map((item: Recommendation) => <OpportunityCard key={item.id} item={item} copy={p.copy} onOpen={() => { p.setActiveOpportunity(item); p.goTo("opportunityDetail", `/opportunities/${item.id}`); }} />)}</div></div>; }
function OpportunityCard({ item, copy, onOpen }: { item: Recommendation; copy: any; onOpen: () => void }) { const u = copy.ui ?? {}; return <article className="opportunity-card surface-card"><div className="opportunity-visual"><span>{item.type === "Training" ? "◒" : item.type === "Job" ? "▣" : "↗"}</span><strong>{item.match}%<small>{u.match ?? "match"}</small></strong></div><span className="type-label">{item.type === "Job" ? (u.jobs ?? item.type) : item.type === "Training" ? (u.training ?? item.type) : (u.selfEmployment ?? item.type)}</span><h2>{item.title}</h2><p>{item.provider}</p><div className="opportunity-meta"><span>⌖ {item.location}</span><span>{item.tags[1] || "Flexible"}</span></div><div className="why-box"><strong>{u.whyFits ?? "Why this fits you"}</strong><span>✓ {item.explanation}</span></div><div className="tag-row">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div><button className="secondary-button full" onClick={onOpen}>{item.type === "Job" ? (u.apply ?? "Apply") : item.type === "Self-employment" ? (u.explore ?? "Explore") : (u.viewDetails ?? "View Details")}<span>→</span></button></article>; }
function OpportunityDetail(p: any) { const item = p.activeOpportunity; return <div className="page"><button className="back-button" onClick={() => p.goTo("opportunities")}>← {p.copy.ui?.backToOpportunities ?? "Back to opportunities"}</button><div className="detail-hero"><div><span className="type-label">{item.type}</span><h1>{item.title}</h1><p>{item.provider} · {item.location}</p><div className="detail-tags">{item.tags.map((tag: string) => <span key={tag}>{tag}</span>)}</div></div><div className="detail-match"><strong>{item.match}%</strong><span>{p.copy.ui?.matchForYou ?? "Match for you"}</span></div></div><div className="detail-layout"><div><section className="surface-card detail-section"><h2>{p.copy.ui?.whyFits ?? "Why WorkSpot recommends this"}</h2><p className="large-quote">“{item.explanation}”</p><div className="reason-list"><span>✓ Aligned with your skill profile</span><span>✓ Available near your district location</span><span>✓ Eligible for PM-AJAY capital subsidy and toolkit support</span></div></section><section className="surface-card detail-section"><h2>{p.copy.ui?.whatYouShouldKnow ?? "What you should know"}</h2><div className="fact-grid"><div><span>Location</span><strong>{item.location}</strong></div><div><span>Duration / Type</span><strong>{item.tags[3] || item.type}</strong></div><div><span>Stipend / Support</span><strong>{item.tags[2] || "Free training & toolkit"}</strong></div><div><span>Authority</span><strong>DPIU & Skill Hub</strong></div></div></section></div><aside className="apply-card surface-card"><span className="eyebrow">{p.copy.ui?.readyNextStep ?? "READY FOR THE NEXT STEP?"}</span><h2>{p.copy.ui?.keepClose ?? "Keep this opportunity close"}</h2><p>Save it, ask WorkSpot AI a question, or start your application.</p><button className="primary-button full" onClick={() => p.setSaved((items: string[]) => items.includes(item.id) ? items.filter((id) => id !== item.id) : [...items, item.id])}>{p.saved.includes(item.id) ? `${p.copy.ui?.saved ?? "Saved"} ✓` : item.type === "Job" ? "Apply" : (p.copy.ui?.saveOpportunity ?? "Save opportunity")}<span>→</span></button><button className="secondary-button full" onClick={() => p.goTo("advisor")}>{p.copy.ui?.askWorkSpotAI ?? "Ask WorkSpot AI"}</button><button className="text-button">{p.copy.ui?.contactOrganization ?? "Contact organization"}</button></aside></div></div>; }
function AdvisorPage(p: any) {
  const u = p.copy.ui ?? {};
  const suggestions = [
    "उपकरण हेतु ₹50,000 की सब्सिडी कैसे मिलेगी?",
    "सिलाई दर्जी (Tailoring) कोर्स कब शुरू होगा?",
    "NSFDC रियायती स्वरोज़गार ऋण की जानकारी",
    "टूल-किट और ₹1,500 स्टाइपेंड की पात्रता",
    "जिला अधिकारी (DPIU) से संपर्क कैसे करें?"
  ];

  async function send() {
    if (!p.advisorInput.trim()) return;
    const text = p.advisorInput.trim();
    p.setAdvisorMessages((messages: any[]) => [...messages, { from: "worker", text }]);
    p.setAdvisorInput("");
    try {
      const res = await apiClient.sendAdvisorChat(p.sessionId, text, p.language);
      p.setAdvisorMessages((messages: any[]) => [...messages, { from: "ai", text: res.reply }]);
      speakText(res.reply, p.language);
    } catch (e) {
      console.warn("Advisor chat error:", e);
      p.setAdvisorMessages((messages: any[]) => [...messages, {
        from: "ai",
        text: "पीएम-अजय योजना के तहत उपकरण व दुकान हेतु ₹50,000 की पूंजीगत सब्सिडी (GIA) और कौशल प्रशिक्षण की सुविधा उपलब्ध है।"
      }]);
    }
  }

  return <div className="page advisor-page"><PageHeader eyebrow={u.conversationPartner ?? "YOUR CONVERSATION PARTNER"} title={p.copy.advisor} subtitle={p.copy.ui?.advisorSubtitle ?? "Ask anything about your work, training, opportunities, or support."} action={<span className="status-pill"><i />{u.active ?? "Active"}</span>} /><div className="advisor-layout"><section className="chat-card surface-card"><div className="chat-header"><div><span className="ai-avatar">W</span><div><strong>WorkSpot AI</strong><small>{u.respondsIn ?? "Responds in"} {p.language}</small></div></div><button className="listen-button">{`◉ ${u.voiceMode ?? "Voice mode"}`}</button></div><div className="messages">{p.advisorMessages.map((message: any, index: number) => <div className={message.from === "ai" ? "message ai-message" : "message worker-message"} key={`${message.text}-${index}`}>{message.from === "ai" && <span className="message-avatar">W</span>}<div><small>{message.from === "ai" ? "WorkSpot AI" : (u.you ?? "You")}</small><p>{message.text}</p>{message.from === "ai" && <button className="message-listen" onClick={() => speakText(message.text, p.language)}>◉ {u.listen ?? "Listen"}</button>}</div></div>)}</div><div className="chat-input"><button className="mic-round" onClick={() => p.setAdvisorInput("पीएम-अजय ₹50,000 सब्सिडी ")}>◉</button><input value={p.advisorInput} onChange={(e) => p.setAdvisorInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") send(); }} placeholder={u.askPlaceholder ?? "Ask a question in your language..."} /><button onClick={send}>→</button></div></section><aside className="suggestion-card surface-card"><span className="eyebrow">{(u.quickQuestions ?? "Quick questions").toUpperCase()}</span><h2>{u.whatHelp ?? "What can I help with?"}</h2>{suggestions.map((item) => <button key={item} onClick={() => { p.setAdvisorInput(item); }}>{item}<span>→</span></button>)}<div className="advisor-note"><span>◉</span><p>{u.voiceAvailable ?? "Voice is always available."} {u.sendOnly ?? "Your answer is only sent when you choose to send it."}</p></div></aside></div></div>;
}
  function ProgressPage(p: any) { const u = p.copy.ui ?? {}; const timeline = [[u.profileCreated ?? "Profile Created", u.completed ?? "completed", "✓"], [u.trainingRecommended ?? "Training Recommended", u.completed ?? "completed", "✓"], [u.trainingStarted ?? "Training Started", u.completed ?? "completed", "✓"], [u.trainingCompleted ?? "Training Completed", u.inProgress ?? "In progress", "◉"], [u.workStarted ?? "Work Started", u.upcoming ?? "Upcoming", "○"], [u.incomeProgress ?? "Income / Profit Progress", u.tracking ?? "Tracking", "○"]]; return <div className="page"><PageHeader eyebrow={p.copy.ui?.yourJourney ?? "YOUR JOURNEY"} title={p.copy.progress} subtitle={p.copy.ui?.progressSubtitle ?? "See what you have completed and where your next opportunity can take you."} action={<button className="secondary-button compact" onClick={() => p.goTo("advisor")}>{p.copy.ui?.updateWithAI ?? "Update with AI"} <span>✦</span></button>} /><div className="progress-layout"><section className="surface-card timeline-card"><div className="card-heading"><div><span className="eyebrow">{(p.copy.ui?.milestones ?? "Milestones").toUpperCase()}</span><h2>{p.copy.ui?.yourJourney ?? "Your work journey"}</h2></div><span className="badge green">3 {u.completed ?? "completed"}</span></div><div className="timeline">{timeline.map(([title, status, icon], index) => <div className={index < 3 ? "timeline-item done" : index === 3 ? "timeline-item current" : "timeline-item"} key={title}><span className="timeline-dot">{icon}</span><div><strong>{title}</strong><small>{status}</small></div>{index === 3 && <span className="timeline-date">42%</span>}</div>)}</div></section><section className="surface-card metrics-card"><div className="card-heading"><div><span className="eyebrow">{(p.copy.ui?.workPerformance ?? "Work performance").toUpperCase()}</span><h2>{p.copy.ui?.metrics ?? "Your metrics"}</h2></div><button className="info-button">i</button></div><Metric label={u.workActivity ?? "Work activity"} value="85" detail={u.currentStatus ?? "Current status"} /><Metric label={u.skillProficiency ?? "Skill proficiency"} value="78" detail={u.developingWell ?? "Developing well"} color="blue" /><Metric label={u.trainingCompletion ?? "Training completion"} value="42" detail={`3 of 8 ${u.trainingCompletion ?? "sessions"}`} color="purple" /></section></div><section className="surface-card score-history"><div className="card-heading"><div><span className="eyebrow">{(p.copy.ui?.updatedOverTime ?? "Updated over time").toUpperCase()}</span><h2>{u.score ?? "Work & Progress Score"}</h2><p>{u.scoreDescription ?? "Your score changes as WorkSpot receives new verified progress information."}</p></div><div className="current-score"><strong>82</strong><span>{u.sinceMonth ?? "+14 since month 1"}</span></div></div><svg viewBox="0 0 800 230" role="img" aria-label="Score history from 68 to 82"><path d="M30 186 C150 180, 210 142, 330 148 S480 106, 580 112 S690 70, 770 44" fill="none" stroke="#3d9bda" strokeWidth="4" /><path d="M30 186 C150 180, 210 142, 330 148 S480 106, 580 112 S690 70, 770 44 L770 210 L30 210 Z" fill="url(#area)" opacity=".35" /><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop stopColor="#77b9ec" /><stop offset="1" stopColor="#77b9ec" stopOpacity="0" /></linearGradient></defs><circle cx="30" cy="186" r="6" fill="#fff" stroke="#3d9bda" strokeWidth="4" /><circle cx="330" cy="148" r="6" fill="#fff" stroke="#3d9bda" strokeWidth="4" /><circle cx="770" cy="44" r="6" fill="#fff" stroke="#3d9bda" strokeWidth="4" /></svg><div className="chart-labels"><span>{u.month1 ?? "Month 1"} · 68</span><span>{u.month2 ?? "Month 2"} · 74</span><span>{u.month3 ?? "Month 3"} · 82</span></div><div className="change-list"><span>+6 {u.skillProficiency ?? "Skill proficiency"}</span><span>+4 {u.trainingProgress ?? "Training progress"}</span><span>+4 {u.livelihoodProgress ?? "Livelihood progress"}</span></div></section></div>; }
function Metric({ label, value, detail, color = "" }: { label: string; value: string; detail: string; color?: string }) { return <div className="metric"><span>{label}</span><strong>{value} <small>/100</small></strong><div className={`metric-bar ${color}`}><i style={{ width: `${value}%` }} /></div><small>{detail}</small></div>; }
function NotificationsPage(p: any) { return <div className="page"><PageHeader eyebrow="STAY IN THE LOOP" title="Notifications" subtitle={p.copy.ui?.notificationsSubtitle ?? "Useful reminders and updates from your WorkSpot journey."} action={<button className="secondary-button compact">{p.copy.ui?.markAllRead ?? "Mark all read"}</button>} /><div className="notification-list">{[["▣", "New opportunity near you", "Bamboo Craft Training is available 8 km away.", "Today", "blue"], ["◒", "Training reminder", "Your training session starts tomorrow.", "Yesterday", "mint"], ["↗", "Profile updated", "Your training progress has been updated.", "2 days ago", "purple"], ["✦", "WorkSpot AI", "Would you like to check new opportunities?", "3 days ago", "orange"]].map(([icon, title, body, date, color]) => <article className="notification-item surface-card" key={title}><span className={`notification-icon ${color}`}>{icon}</span><div><strong>{title}</strong><p>{body}</p></div><time>{date}</time><button>•••</button></article>)}</div></div>; }
function HelpPage(p: any) { return <div className="page"><PageHeader eyebrow="WE ARE HERE WITH YOU" title={p.copy.help} subtitle={p.copy.ui?.helpSubtitle ?? "Choose the kind of support that feels easiest right now."} /><div className="help-grid">{[["✦", "Ask WorkSpot AI", "Get a quick answer about your work, training, or opportunities.", "Voice"], ["☎", "Contact Local Support", "Speak to a support person who knows your district.", "Call"], ["⌖", "Find Nearby Support Center", "See the nearest center for in-person help.", "Location"], ["◎", "Talk to a Human Officer", "Request a call when voice recognition or anything else feels difficult.", "Human support"]].map(([icon, title, body, action], index) => <article className={index === 3 ? "help-card surface-card prominent" : "help-card surface-card"} key={title}><span className="help-icon">{icon}</span><h2>{title}</h2><p>{body}</p><button className="secondary-button">{action}<span>→</span></button></article>)}</div><div className="human-note surface-card"><span>◉</span><div><strong>Voice recognition not working?</strong><p>After a few tries, WorkSpot will always offer tap-based options and human district support.</p></div><button className="text-button">Learn more →</button></div></div>; }

createRoot(document.getElementById("root")!).render(<App />);
