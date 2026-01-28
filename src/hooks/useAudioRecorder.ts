
import { useState, useRef, useCallback } from "react";

export type AudioRecorderState = "idle" | "recording" | "processing";

export interface UseAudioRecorderReturn {
    state: AudioRecorderState;
    visualizerData: Uint8Array | null;
    startRecording: () => Promise<void>;
    stopRecording: () => Promise<Blob | null>;
    cancelRecording: () => void;
    error: string | null;
    durationMs: number;
}

export function useAudioRecorder(): UseAudioRecorderReturn {
    const [state, setState] = useState<AudioRecorderState>("idle");
    const [error, setError] = useState<string | null>(null);
    const [durationMs, setDurationMs] = useState(0);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const startTimeRef = useRef<number>(0);

    const startRecording = useCallback(async () => {
        try {
            setError(null);
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Prefer webm/opus, fallback to default
            const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                ? "audio/webm;codecs=opus"
                : "";

            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
            mediaRecorderRef.current = recorder;
            chunksRef.current = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunksRef.current.push(e.data);
            };

            recorder.start(200); // Timeslice 200ms to ensure we get data
            setState("recording");
            startTimeRef.current = Date.now();

            // Update duration every 100ms
            timerRef.current = setInterval(() => {
                const diff = Date.now() - startTimeRef.current;
                setDurationMs(diff);
                if (diff >= 20000) {
                    stopRecording();
                }
            }, 100);

        } catch (err: any) {
            console.error("Failed to start recording:", err);
            setError(err.message || "Microphone access denied");
        }
    }, []);

    const stopRecording = useCallback(async (): Promise<Blob | null> => {
        const recorder = mediaRecorderRef.current;
        if (!recorder || recorder.state === "inactive") {
            return null;
        }

        const elapsed = Date.now() - startTimeRef.current;
        const MIN_DURATION = 600; // 0.6s minimum

        if (elapsed < MIN_DURATION) {
            await new Promise(r => setTimeout(r, MIN_DURATION - elapsed));
        }

        return new Promise((resolve) => {
            recorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
                cleanup();
                if (blob.size < 100) {
                    // Empty or malformed
                    resolve(null);
                } else {
                    resolve(blob);
                }
            };
            recorder.stop();
            setState("processing");
        });
    }, []);

    const cancelRecording = useCallback(() => {
        const recorder = mediaRecorderRef.current;
        if (recorder && recorder.state !== "inactive") {
            recorder.stop();
        }
        cleanup();
        setError("Cancelled");
    }, []);

    const cleanup = () => {
        if (timerRef.current) clearInterval(timerRef.current);
        const stream = mediaRecorderRef.current?.stream;
        stream?.getTracks().forEach(track => track.stop());
        mediaRecorderRef.current = null;
        setState("idle");
        setDurationMs(0);
    };

    return {
        state,
        visualizerData: null, // Placeholder for later
        startRecording,
        stopRecording,
        cancelRecording,
        error,
        durationMs
    };
}
