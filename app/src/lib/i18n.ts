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
  /** The Generate affordance beside the ID field, shown only for studies with
   * `auto_participant_id` on (DATA-SPEC §3.2). The field stays editable, so
   * the hint explains the ID can still be replaced by hand. */
  idGenerate: string;
  idGenerateHint: string;
  // Condition assignment (issue 37; shown only when the study declares conditions)
  conditionLabel: string;
  conditionPlaceholder: string;
  // Duplicate-ID warn-confirm + ID validation (issue 38). duplicateBody is a
  // template: the component substitutes {id} and {n}. In Standalone Mode the
  // count is honest about its reach (DATA-SPEC §2.6): it is this station's
  // local files only — cross-station duplicates are flagged at the Hub.
  duplicateTitle: string;
  duplicateBody: string;
  duplicateBodyStandalone: string;
  duplicateContinue: string;
  duplicateCancel: string;
  idInvalid: string;
  /** Persistent Test Run banner shown on every screen of a practice session
   * (issue 43) — must read at a glance from across a lab room. */
  practiceBanner: string;
  // Kiosk in-app lock (issue 44): the passcode prompt every mid-session exit
  // path opens while the study declares an exit_passcode.
  lockTitle: string;
  lockPlaceholder: string;
  lockConfirm: string;
  lockCancel: string;
  lockWrong: string;
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
  /** Practice-run thank-you body (issue 59). A test run banners "data not
   * recorded" on every screen, so the debrief must not claim the opposite. */
  thankYouBodyPractice: string;
  /** Label over the converted amount owed (issue 41; only for payout studies). */
  payoutLabel: string;
  playAgain: string;
  // Error recovery
  retry: string;
  /** Shown on the finished screen when persisting the session to disk failed
   * (issue 49). The participant must never see the "recorded" debrief until the
   * write is confirmed; this keeps them on the finished screen to retry. */
  saveError: string;
  /** Heading of the debrief notice listing recoverable write warnings the
   * sidecar returned (issue 50) — e.g. the master CSV was locked and the rows
   * landed in a sibling file the researcher must merge by hand. */
  saveWarningTitle: string;
}

export const STRINGS: Record<Language, TaskStrings> = {
  en: {
    consentTitle: "Before you begin",
    consentBody:
      "In this task you will inflate balloons to earn money. The more you pump, the more you earn — but if a balloon pops, you lose that balloon's money. Cash out before it pops. Your responses are recorded for research. (This screen is task instructions, not a consent form — your study's consent is handled separately.)",
    consentAgree: "Continue",
    idPrompt: "Participant ID",
    idPlaceholder: "e.g. P001",
    idContinue: "Start task",
    idGenerate: "Generate",
    idGenerateHint: "Generates a random ID. You can edit it or type your own.",
    conditionLabel: "Condition",
    conditionPlaceholder: "Select a condition…",
    duplicateTitle: "This ID already has data",
    duplicateBody: "{id} already has {n} recorded session(s) in this study. Continue anyway?",
    duplicateBodyStandalone:
      "This station has {n} prior session(s) for {id}. Cross-station duplicates aren't checked here; the Hub flags them at assembly. Continue anyway?",
    duplicateContinue: "Continue anyway",
    duplicateCancel: "Cancel",
    idInvalid:
      "This ID cannot be used in file names. Use only letters, numbers, dots, underscores, and dashes.",
    practiceBanner: "TEST RUN — data not recorded",
    lockTitle: "Researcher exit",
    lockPlaceholder: "Exit passcode",
    lockConfirm: "Unlock and exit",
    lockCancel: "Return to session",
    lockWrong: "Incorrect passcode — the session continues.",
    taskTitle: "Balloon Analogue Risk Task",
    instructions:
      "Inflate the balloon to earn money. The more you pump, the more you earn — but if the balloon pops, you lose that balloon's money. Collect before it pops!",
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
    pumpButton: "Pump (Space)",
    collectButton: "Collect (Enter)",
    exploded: "Pop! Nothing for this balloon.",
    collected: "Collected!",
    finishedTitle: "Assessment complete",
    totalEarnings: "Total earnings",
    analyzing: "Analyzing…",
    seeResults: "See my results",
    thankYouTitle: "Thank you for participating!",
    thankYouBody: "Your session has been recorded. Please let the researcher know you are finished.",
    thankYouBodyPractice: "This was a test run — no data was recorded. Please let the researcher know you are finished.",
    payoutLabel: "Your payout",
    playAgain: "Play again",
    retry: "Retry",
    saveError: "Could not save this session. Check the output folder and try again.",
    saveWarningTitle: "Saved with warnings — please tell the researcher",
  },
  tr: {
    consentTitle: "Başlamadan önce",
    consentBody:
      "Bu görevde para kazanmak için balonları şişireceksiniz. Ne kadar çok şişirirseniz o kadar çok kazanırsınız — ancak bir balon patlarsa o balonun parasını kaybedersiniz. Patlamadan önce paranızı toplayın. Yanıtlarınız araştırma için kaydedilir. (Bu ekran onam formu değil, görev yönergesidir — çalışmanızın onamı ayrıca alınır.)",
    consentAgree: "Devam et",
    idPrompt: "Katılımcı Kimliği",
    idPlaceholder: "örn. P001",
    idContinue: "Göreve Başla",
    idGenerate: "Oluştur",
    idGenerateHint: "Rastgele bir kimlik oluşturur. Düzenleyebilir veya kendiniz yazabilirsiniz.",
    conditionLabel: "Koşul",
    conditionPlaceholder: "Bir koşul seçin…",
    duplicateTitle: "Bu kimliğin zaten kaydı var",
    duplicateBody: "{id} bu çalışmada zaten {n} kayıtlı oturuma sahip. Yine de devam edilsin mi?",
    duplicateBodyStandalone:
      "Bu istasyonda {id} için {n} önceki oturum kaydı var. İstasyonlar arası tekrarlar burada denetlenmez; Hub birleştirme sırasında işaretler. Yine de devam edilsin mi?",
    duplicateContinue: "Yine de devam et",
    duplicateCancel: "İptal",
    idInvalid:
      "Bu kimlik dosya adlarında kullanılamaz. Yalnızca harf, rakam, nokta, alt çizgi ve tire kullanın.",
    practiceBanner: "DENEME OTURUMU — veriler kaydedilmiyor",
    lockTitle: "Araştırmacı çıkışı",
    lockPlaceholder: "Çıkış şifresi",
    lockConfirm: "Kilidi aç ve çık",
    lockCancel: "Oturuma dön",
    lockWrong: "Şifre yanlış — oturum devam ediyor.",
    taskTitle: "Balon Analog Risk Görevi",
    instructions:
      "Balonu şişirerek para kazanın. Ne kadar çok şişirirseniz o kadar çok kazanırsınız — ancak balon patlarsa o balonun parasını kaybedersiniz. Patlamadan önce paranızı toplayın!",
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
    pumpButton: "Şişir (Boşluk)",
    collectButton: "Topla (Enter)",
    exploded: "PATLADI! Bu balon için para yok.",
    collected: "Toplandı!",
    finishedTitle: "Değerlendirme Tamamlandı",
    totalEarnings: "Toplam Kazanç",
    analyzing: "Analiz ediliyor…",
    seeResults: "Sonuçlarımı Gör",
    thankYouTitle: "Katılımınız için teşekkürler!",
    thankYouBody: "Oturumunuz kaydedildi. Lütfen bittiğinizi araştırmacıya haber verin.",
    thankYouBodyPractice: "Bu bir deneme oturumuydu — hiçbir veri kaydedilmedi. Lütfen bittiğinizi araştırmacıya haber verin.",
    payoutLabel: "Ödemeniz",
    playAgain: "Tekrar Oyna",
    retry: "Tekrar Dene",
    saveError: "Bu oturum kaydedilemedi. Çıktı klasörünü kontrol edip tekrar deneyin.",
    saveWarningTitle: "Uyarılarla kaydedildi — lütfen araştırmacıya bildirin",
  },
};

/** The string table for a study's language. */
export function taskStrings(language: Language): TaskStrings {
  return STRINGS[language];
}
