/** Participant-facing strings for the Run task, in the study's language (SPEC §11).
 *
 * Scope (this issue): the core flow — consent, participant ID, gameplay, and the
 * debrief title/summary. The detailed results-metric labels stay as-is for now
 * (engagement-only debrief detail; a later bilingual pass). Amounts/counts are
 * composed by the component, so these stay static and key-parity-checked.
 */

import type { Language } from "./config";

export interface TaskStrings {
  // Consent
  consentTitle: string;
  consentBody: string;
  consentAgree: string;
  // Participant ID
  idPrompt: string;
  idPlaceholder: string;
  idContinue: string;
  // Condition assignment (issue 37; shown only when the study declares conditions)
  conditionLabel: string;
  conditionPlaceholder: string;
  // Idle / instructions
  taskTitle: string;
  instructions: string;
  controlsHint: string;
  startButton: string;
  balloonsWord: string;
  // Gameplay
  balloonLabel: string;
  totalLabel: string;
  currentLabel: string;
  progressLabel: string;
  statusCollected: string;
  statusExploded: string;
  statusUpcoming: string;
  pumpButton: string;
  collectButton: string;
  exploded: string;
  collected: string;
  // Finished / submit
  finishedTitle: string;
  totalEarnings: string;
  analyzing: string;
  seeResults: string;
  // Debrief
  thankYouTitle: string;
  thankYouBody: string;
  playAgain: string;
  // Error recovery
  retry: string;
}

export const STRINGS: Record<Language, TaskStrings> = {
  en: {
    consentTitle: "Before you begin",
    consentBody:
      "You will inflate balloons to earn money. Each pump raises the chance of a pop. Cash out before it pops. Your responses are recorded for research.",
    consentAgree: "I agree — continue",
    idPrompt: "Participant ID",
    idPlaceholder: "e.g. P001",
    idContinue: "Start task",
    conditionLabel: "Condition",
    conditionPlaceholder: "Select a condition…",
    taskTitle: "Balloon Analogue Risk Task",
    instructions:
      "Inflate the balloon to earn money. Each pump raises the chance it pops. Collect your money before it pops!",
    controlsHint: "Space: pump · Enter: collect",
    startButton: "Start task",
    balloonsWord: "balloons",
    balloonLabel: "Balloon",
    totalLabel: "Total",
    currentLabel: "Current",
    progressLabel: "Session progress",
    statusCollected: "Collected",
    statusExploded: "Popped",
    statusUpcoming: "Upcoming",
    pumpButton: "🎈 Pump (Space)",
    collectButton: "💰 Collect (Enter)",
    exploded: "Pop! Nothing for this balloon.",
    collected: "Collected!",
    finishedTitle: "Assessment complete",
    totalEarnings: "Total earnings",
    analyzing: "Analyzing…",
    seeResults: "See my results",
    thankYouTitle: "Thank you for participating!",
    thankYouBody: "Your session has been recorded. Please let the researcher know you are finished.",
    playAgain: "Play again",
    retry: "Retry",
  },
  tr: {
    consentTitle: "Başlamadan önce",
    consentBody:
      "Para kazanmak için balonları şişireceksiniz. Her şişirme patlama olasılığını artırır. Patlamadan önce paranızı toplayın. Yanıtlarınız araştırma için kaydedilir.",
    consentAgree: "Kabul ediyorum — devam et",
    idPrompt: "Katılımcı Kimliği",
    idPlaceholder: "örn. P001",
    idContinue: "Göreve Başla",
    conditionLabel: "Koşul",
    conditionPlaceholder: "Bir koşul seçin…",
    taskTitle: "Balon Analog Risk Görevi",
    instructions:
      "Balonu şişirerek para kazanın. Her şişirme patlama riskini artırır. Patlamadan önce paranızı toplayın!",
    controlsHint: "Boşluk: şişir · Enter: topla",
    startButton: "Göreve Başla",
    balloonsWord: "balon",
    balloonLabel: "Balon",
    totalLabel: "Toplam",
    currentLabel: "Şu an",
    progressLabel: "Oturum ilerlemesi",
    statusCollected: "Toplandı",
    statusExploded: "Patladı",
    statusUpcoming: "Sırada",
    pumpButton: "🎈 Şişir (Boşluk)",
    collectButton: "💰 Topla (Enter)",
    exploded: "PATLADI! Bu balon için para yok.",
    collected: "Toplandı!",
    finishedTitle: "Değerlendirme Tamamlandı",
    totalEarnings: "Toplam Kazanç",
    analyzing: "Analiz ediliyor…",
    seeResults: "Sonuçlarımı Gör",
    thankYouTitle: "Katılımınız için teşekkürler!",
    thankYouBody: "Oturumunuz kaydedildi. Lütfen bittiğinizi araştırmacıya haber verin.",
    playAgain: "Tekrar Oyna",
    retry: "Tekrar Dene",
  },
};

/** The string table for a study's language. */
export function taskStrings(language: Language): TaskStrings {
  return STRINGS[language];
}
