import { useEffect, useRef, useState, type CSSProperties } from "react";

import { persistSession, submitSession } from "./lib/api";
import type { TaskConfig } from "./lib/config";
import type { GameEvent } from "./lib/events";
import { taskStrings } from "./lib/i18n";
import { buildSessionPayload } from "./lib/session";
import {
  advance,
  type EngineCtx,
  type EngineEvent,
  type GameState,
  initialState,
} from "./lib/taskEngine";
import { type AssessmentResult, Debrief } from "./run/Debrief";
import { type Balloon, buildSequence, mulberry32 } from "./run/sequence";

// ── Types ───────────────────────────────────────────────────────────────────

interface BalloonState {
    id: number;
    pumps: number;
    status: "active" | "collected" | "exploded";
}

// Vertically-centered full-height screen (idle / finished), Light Posture (ADR 0003).
// Pairs with the "flex flex-col items-center gap-6" utility classes.
const centeredScreenStyle: CSSProperties = {
    flex: 1,
    justifyContent: "center",
    padding: "48px 24px",
};

// ── Component ───────────────────────────────────────────────────────────────
//
// A thin rendering shell over the pure task engine (lib/taskEngine.ts). The engine
// owns the gameplay rules; this component owns the seeded rng, timestamps, the
// feedback delay, and the view. It dispatches user input to `advance()` and derives
// the view names (gamePhase, currentBalloon, …) from the engine state so the markup
// stays declarative. The results screen is the standalone <Debrief>.

interface BartGameProps {
    config: TaskConfig;
    hazards: Record<string, number[]>;
    candidateId: string;
    /** Assigned condition for between-subject designs; omitted when the study
     * declares no conditions (issue 37). */
    condition?: string | null;
    /** True when the ID screen warned this ID already had sessions and the
     * researcher chose to continue (issue 38). */
    duplicateAcknowledged?: boolean;
    onComplete?: (data: AssessmentResult) => void;
    /** Escape hatch back to the researcher view. Only offered while no balloon is
     * live (idle / finished / results) so a participant can't exit mid-trial. */
    onExit?: () => void;
}

export default function BartGame({ config, hazards, candidateId, condition = null, duplicateAcknowledged = false, onComplete, onExit }: BartGameProps) {
    const eventLogRef = useRef<GameEvent[]>([]);
    const sessionIdRef = useRef(crypto.randomUUID());
    const sequenceRef = useRef<Balloon[]>([]);
    const rngRef = useRef<() => number>(() => Math.random());
    const feedbackTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const containerRef = useRef<HTMLDivElement>(null);

    const t = taskStrings(config.language);
    const totalBalloons = config.colors.reduce((n, c) => n + c.trials, 0);

    const [engine, setEngine] = useState<GameState>(initialState);
    const [started, setStarted] = useState(false);
    const [feedbackMessage, setFeedbackMessage] = useState("");
    const [results, setResults] = useState<AssessmentResult | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const ctx = (): EngineCtx => ({ sequence: sequenceRef.current, reward: config.reward_per_pump });

    /** Stamp the engine's events with a monotonic timestamp and append to the log. */
    const logEvents = (events: EngineEvent[]) => {
        const ts = performance.now();
        for (const e of events) {
            eventLogRef.current.push({ timestamp: ts, type: e.type, payload: e.payload });
        }
    };

    /** After feedback, advance to the next balloon (or finish) — the timing the
     * engine deliberately leaves to the view. */
    const scheduleNext = (delay: number) => {
        feedbackTimer.current = setTimeout(() => {
            setEngine((s) => advance(s, { type: "next" }, ctx()).state);
            setFeedbackMessage("");
        }, delay);
    };

    const startGame = () => {
        eventLogRef.current = [];
        sessionIdRef.current = crypto.randomUUID();
        // One seeded rng drives both the shuffle and the per-pump burst draws, so a
        // fixed seed reproduces the whole run (SPEC §7.2); null seed → fresh run.
        const seed = config.seed ?? ((Math.random() * 2 ** 32) >>> 0);
        const rng = mulberry32(seed);
        rngRef.current = rng;
        sequenceRef.current = buildSequence(config, hazards, rng);
        setEngine(initialState());
        setResults(null);
        setFeedbackMessage("");
        setStarted(true);
    };

    const handlePump = () => {
        if (engine.phase !== "playing" || engine.status !== "active") return;
        const { state, events } = advance(engine, { type: "pump", draw: rngRef.current() }, ctx());
        logEvents(events);
        setEngine(state);
        if (state.status === "exploded") {
            setFeedbackMessage(t.exploded);
            scheduleNext(1200);
        }
    };

    const handleCollect = () => {
        if (engine.phase !== "playing" || engine.status !== "active" || engine.pumps === 0) return;
        const money = engine.pumps * config.reward_per_pump;
        const { state, events } = advance(engine, { type: "collect" }, ctx());
        logEvents(events);
        setEngine(state);
        setFeedbackMessage(`${t.collected} $${money.toFixed(2)}`);
        scheduleNext(1000);
    };

    const handleSubmit = async () => {
        setIsSubmitting(true);
        const payload = buildSessionPayload(sessionIdRef.current, candidateId, eventLogRef.current, condition, duplicateAcknowledged);
        try {
            const data = await submitSession<AssessmentResult>(payload, config);
            setResults(data);

            // Persist the session locally via the sidecar (best-effort; the engine
            // owns file writing, SPEC §13). A write failure must not block results.
            void persistSession(payload, config).catch((persistErr) =>
                console.error("Failed to persist session:", persistErr),
            );

            if (onComplete) onComplete(data);
        } catch (err) {
            console.error("Submission error:", err);
            setFeedbackMessage(err instanceof Error ? err.message : "Failed to submit");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.code === "Space") {
            e.preventDefault();
            handlePump();
        } else if (e.code === "Enter") {
            e.preventDefault();
            handleCollect();
        }
    };

    // Derived view state: map the engine onto the names the markup already uses.
    const gamePhase: "idle" | "playing" | "feedback" | "finished" | "results" = results
        ? "results"
        : !started
            ? "idle"
            : engine.phase;
    const currentBalloon: BalloonState = {
        id: engine.index + 1,
        pumps: engine.pumps,
        status: engine.status,
    };
    const completedBalloons: BalloonState[] = engine.completed.map((c, i) => ({
        id: i + 1,
        pumps: c.pumps,
        status: c.status,
    }));
    const totalScore = engine.score;
    const balloonCount = engine.completed.length + 1;

    useEffect(() => {
        if (gamePhase === "playing" && containerRef.current) {
            containerRef.current.focus();
        }
    }, [gamePhase]);

    // Clear any pending feedback timer on unmount.
    useEffect(() => () => {
        if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
    }, []);

    const currentConfig = sequenceRef.current[engine.index];
    const balloonColor = currentConfig ? currentConfig.displayHex : "#9CA3AF";
    const balloonScale = 1 + currentBalloon.pumps * 0.08;
    const balloonSize = 100 * balloonScale;

    const showExit =
        onExit && (gamePhase === "idle" || gamePhase === "finished" || gamePhase === "results");

    return (
        <div
            ref={containerRef}
            className="w-full"
            onKeyDown={handleKeyDown}
            tabIndex={0}
            style={{ outline: "none", display: "flex", flexDirection: "column", flex: 1 }}
        >
            {showExit && (
                <div style={{ padding: 16, alignSelf: "flex-start" }}>
                    <button type="button" className="btn-ghost-participant" onClick={onExit}>
                        ← Back to setup
                    </button>
                </div>
            )}

            {/* ── Idle Screen ──────────────────────────────────────────────────── */}
            {gamePhase === "idle" && (
                <div className="flex flex-col items-center gap-6" style={centeredScreenStyle}>
                    <div className="text-6xl">🎈</div>
                    <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#111827" }}>
                        {t.taskTitle}
                    </h2>
                    <p
                        style={{
                            color: "#4b5563",
                            textAlign: "center",
                            maxWidth: "400px",
                            lineHeight: 1.6,
                        }}
                    >
                        {t.instructions}
                    </p>
                    <p style={{ color: "#6b7280", fontSize: "0.85rem" }}>
                        {totalBalloons} {t.balloonsWord} · {t.controlsHint}
                    </p>
                    <button
                        className="btn-primary-participant"
                        onClick={startGame}
                        style={{
                            marginTop: "0.5rem",
                            padding: "12px 40px",
                            fontSize: "1rem",
                            fontWeight: 600,
                            borderRadius: 10,
                        }}
                    >
                        {t.startButton}
                    </button>
                </div>
            )}

            {/* ── Playing / Feedback ───────────────────────────────────────────── */}
            {(gamePhase === "playing" || gamePhase === "feedback") && (
                <div
                    className="flex flex-col items-center"
                    style={{ flex: 1, width: "100%", padding: "24px 0" }}
                >
                    {/* Understated top bar: balloon progress left, running total right. */}
                    <div
                        style={{
                            display: "flex",
                            justifyContent: "space-between",
                            width: "100%",
                            maxWidth: 560,
                            padding: "0 1rem",
                        }}
                    >
                        <span style={{ color: "#6b7280", fontSize: "0.9rem" }}>
                            {t.balloonLabel} {Math.min(balloonCount, totalBalloons)}/{totalBalloons}
                        </span>
                        <span style={{ color: "#6b7280", fontSize: "0.9rem" }}>
                            {t.totalLabel} ${totalScore.toFixed(2)}
                        </span>
                    </div>

                    {/* Centered play area: balloon → earnings → feedback → controls. */}
                    <div
                        style={{
                            flex: 1,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 24,
                        }}
                    >
                        <div
                            style={{
                                position: "relative",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                height: "280px",
                            }}
                        >
                            {currentBalloon.status === "exploded" ? (
                                <div
                                    style={{
                                        fontSize: "5rem",
                                        animation: "fadeIn 0.2s ease-out",
                                    }}
                                >
                                    💥
                                </div>
                            ) : (
                                <div
                                    style={{
                                        width: `${balloonSize}px`,
                                        height: `${balloonSize * 1.2}px`,
                                        borderRadius: "50% 50% 50% 50% / 40% 40% 60% 60%",
                                        background: `radial-gradient(circle at 35% 35%, ${balloonColor}CC, ${balloonColor})`,
                                        boxShadow: `0 8px 30px ${balloonColor}40, inset 0 -8px 20px rgba(0,0,0,0.2)`,
                                        transition: "width 0.15s ease, height 0.15s ease",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        position: "relative",
                                    }}
                                >
                                    <div
                                        style={{
                                            position: "absolute",
                                            top: "20%",
                                            left: "30%",
                                            width: "25%",
                                            height: "20%",
                                            borderRadius: "50%",
                                            background:
                                                "radial-gradient(ellipse, rgba(255,255,255,0.4), transparent)",
                                        }}
                                    />
                                </div>
                            )}

                            {currentBalloon.status === "active" && (
                                <div
                                    style={{
                                        position: "absolute",
                                        bottom: `${-20 + (280 - balloonSize * 1.2) / 2}px`,
                                        width: "2px",
                                        height: "30px",
                                        background: "#6B7280",
                                    }}
                                />
                            )}
                        </div>

                        {/* Static earnings counter — outside the balloon (Issue 27). */}
                        <div style={{ fontSize: "2rem", fontWeight: 700, color: "#111827" }}>
                            {t.currentLabel}: ${(currentBalloon.pumps * config.reward_per_pump).toFixed(2)}
                        </div>

                        <div
                            style={{
                                fontSize: "1.1rem",
                                fontWeight: 600,
                                color: currentBalloon.status === "exploded" ? "#dc2626" : "#16a34a",
                                minHeight: "1.6rem",
                            }}
                        >
                            {feedbackMessage}
                        </div>

                        {/* Both controls deliberately identical and neutral: the UI must
                          * not visually prime pumping over collecting (or vice versa). */}
                        <div style={{ display: "flex", gap: "1rem" }}>
                            <button
                                className="btn-secondary-participant"
                                onClick={handlePump}
                                disabled={
                                    gamePhase !== "playing" || currentBalloon.status !== "active"
                                }
                                style={{ padding: "12px 32px", fontSize: "1rem", fontWeight: 600 }}
                            >
                                {t.pumpButton}
                            </button>
                            <button
                                className="btn-secondary-participant"
                                onClick={handleCollect}
                                disabled={
                                    gamePhase !== "playing" ||
                                    currentBalloon.status !== "active" ||
                                    currentBalloon.pumps === 0
                                }
                                style={{ padding: "12px 32px", fontSize: "1rem", fontWeight: 600 }}
                            >
                                {t.collectButton}
                            </button>
                        </div>
                    </div>

                    {/* Session-progress timeline along the bottom: one dot per balloon,
                        green = collected, red = popped, hollow = upcoming (CONTEXT.md). */}
                    <ol
                        role="list"
                        aria-label={t.progressLabel}
                        style={{
                            listStyle: "none",
                            display: "flex",
                            flexWrap: "wrap",
                            justifyContent: "center",
                            gap: 8,
                            margin: 0,
                            padding: "12px 1rem 0",
                            maxWidth: 720,
                        }}
                    >
                        {Array.from({ length: totalBalloons }, (_, i) => {
                            const done = engine.completed[i];
                            const status = !done
                                ? t.statusUpcoming
                                : done.status === "collected"
                                    ? t.statusCollected
                                    : t.statusExploded;
                            return (
                                <li
                                    key={i}
                                    aria-label={`${t.balloonLabel} ${i + 1}: ${status}`}
                                    style={{
                                        width: 12,
                                        height: 12,
                                        borderRadius: "50%",
                                        background: !done
                                            ? "transparent"
                                            : done.status === "collected"
                                                ? "#16a34a"
                                                : "#dc2626",
                                        border: done ? "none" : "2px solid #d1d5db",
                                    }}
                                />
                            );
                        })}
                    </ol>
                </div>
            )}

            {/* ── Game Over → Submit ────────────────────────────────────────────── */}
            {gamePhase === "finished" && (
                <div className="flex flex-col items-center gap-6" style={centeredScreenStyle}>
                    <div className="text-5xl">🏁</div>
                    <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#111827" }}>
                        {t.finishedTitle}
                    </h2>
                    <p style={{ color: "#4b5563" }}>
                        {t.totalEarnings}:{" "}
                        <span style={{ color: "#16a34a", fontWeight: 700 }}>
                            ${totalScore.toFixed(2)}
                        </span>{" "}
                        / {totalBalloons} {t.balloonsWord}
                    </p>

                    <div
                        style={{
                            display: "flex",
                            gap: "8px",
                            flexWrap: "wrap",
                            justifyContent: "center",
                            maxWidth: 560,
                        }}
                    >
                        {completedBalloons.map((b) => (
                            <div
                                key={b.id}
                                style={{
                                    width: 32,
                                    height: 32,
                                    borderRadius: "50%",
                                    background:
                                        b.status === "collected" ? "#16a34a" : "#dc2626",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: "0.7rem",
                                    color: "#fff",
                                    fontWeight: 700,
                                }}
                            >
                                {b.pumps}
                            </div>
                        ))}
                    </div>

                    <button
                        className="btn-primary-participant"
                        onClick={handleSubmit}
                        disabled={isSubmitting}
                        style={{
                            marginTop: "1rem",
                            padding: "14px 48px",
                            fontSize: "1.05rem",
                            fontWeight: 600,
                            borderRadius: 10,
                            cursor: isSubmitting ? "wait" : "pointer",
                        }}
                    >
                        {isSubmitting ? t.analyzing : t.seeResults}
                    </button>

                    {feedbackMessage && (
                        <p style={{ color: "#dc2626", fontSize: "0.9rem" }}>
                            {feedbackMessage}
                        </p>
                    )}
                </div>
            )}

            {/* ── Debrief (participant thank-you) ──────────────────────────────── */}
            {gamePhase === "results" && results && (
                <div className="flex flex-col items-center gap-6" style={centeredScreenStyle}>
                    <Debrief
                        language={config.language}
                        earnings={totalScore}
                        balloonsCompleted={completedBalloons.length}
                    />
                    <button type="button" className="btn-ghost-participant" onClick={startGame}>
                        {t.playAgain}
                    </button>
                </div>
            )}
        </div>
    );
}
