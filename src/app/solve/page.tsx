"use client";

import DashboardNavBar from "@/components/DashboardNavBar";
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import type { TimelineStep } from "@/components/solve/ProgressTimeline";
import { useRouter } from "next/navigation";
import MathRenderer from "@/components/math/MathJaxRenderer";
import MathRendererMJX from "@/components/MathRendererMJX";
import MathInput, { MathInputRef } from "@/components/MathInput";
import { MODES, ModeId, Suggestion } from "@/lib/modes";
import SnapSolveV2 from "@/components/snap/SnapSolveV2";
import SnapSolveInputPanel from "@/components/snap_solve/SnapSolveInputPanel";

// Token validation imports
import { estimateTokens } from "@/lib/tokenEstimator";
import { detectMultiQuestion, autoSplitQuestions, extractSharedContext } from "@/lib/multiQuestionDetector";
import { TokenBudgetPolicy, willRequestFit } from "@/lib/tokenBudget";
import InputStatus from "@/components/InputStatus";
import SplitModal from "@/components/SplitModal";

// Input mode imports
import LiveMathPreview from "@/components/LiveMathPreview";

import {
    validateMathQuery,
    isBlockingInputError,
    isInputTooShort,
    INPUT_ERROR_BLOCKED,
    INPUT_ERROR_NOT_MATH
} from "@/lib/mathValidation";

// Tier-aware solve imports
import SegmentedControl from "@/components/ui/SegmentedControl";
import CostPreview from "@/components/solve/CostPreview";
import TransferAndNotificationsPanel from "@/components/solve/TransferAndNotificationsPanel";
import { fetchCreditsEstimate, CreditsEstimateResponse, SolveTier, WalletProgramEnrollment, WalletSummary, fetchWalletPrograms, fetchWalletSummary } from "@/lib/wallet";
import { TokenPolicy, fetchTokenPolicy } from "@/lib/tokenPolicy";
import ThemeToggle from "@/components/ThemeToggle";
import { useToast } from "@/components/ui/ToastProvider";
import { SolveBatchResponse } from "@/lib/contracts";

interface ChatSession {
    id: number;
    title: string;
    created_at: string;
    telemetry?: {
        tier_effective?: string;
        effective_tier?: string;
        tier_requested?: string;
        tier?: string;
    };
}

interface ActiveUser {
    id: number;
    avatar_url?: string;
    full_name: string;
    learning_interests?: string[];
}

interface ClarifierOption {
    label: string;
    value: string;
}

interface ClarifierQuestion {
    question: string;
    options: ClarifierOption[];
}

interface TaskBundleTask {
    task_id: string;
    task_text: string;
    order_index: number;
}

interface VoiceArtifact {
    id: number;
    transcript_raw?: string;
    normalized_math_text?: string;
    clarifier_question?: ClarifierQuestion;
}

interface StreamingTelemetry {
    provider?: string;
    model?: string;
    input_tokens?: number;
    output_tokens?: number;
    cached_tokens?: number;
    total_tokens?: number;
    latency_ms_openai?: number;
    truncated?: boolean;
}

interface StreamingRuntimeMeta {
    attempt_id?: string;
    request_id?: string;
    provider?: string;
    model?: string;
    tier_requested?: string;
    tier_effective?: string;
    effective_tier?: string;
    mode_family?: string;
    mode?: string;
    prompt_binding_id?: string;
    global_system_prompt_id?: string;
    developer_prompt_id?: string;
    output_schema_id?: string;
    global_system_prompt_version?: number;
    developer_prompt_version?: number;
    output_schema_version?: number;
    token_config?: {
        max_output_tokens?: number;
        max_input_tokens?: number;
        temperature?: number;
        top_p?: number;
        timeout_ms?: number;
        trim_strategy?: string;
    };
    features?: {
        allow_research?: boolean;
        allow_verify?: boolean;
        allow_plot?: boolean;
    };
}

interface OcrMetadata {
    ocr_confidence: number;
    ocr_warnings: string[];
    ocr_source: string;
    ocr_engine: string;
}

interface VoiceFeatures {
    voice_confirmed: boolean;
    voice_used?: boolean;
    voice_ambiguity_flags?: string[];
    voice_clarifier_question?: string;
    voice_stt_provider?: string;
    voice_transcript_confidence?: number;
}

const ALL_SOLVE_TIERS: SolveTier[] = ["SHORT_STEPS", "FINAL", "STANDARD"];
const MAX_TASKS_PER_QUESTION = 15;
const SHORT_FINAL_MAX_TASKS = 3;

const detectExplicitTaskCount = (text: string): number => {
    const src = String(text || "");
    const header = src.match(/(?:^|\n)\s*(Tasks|Instructions|Steps|Do the following|Part)\s*:\s*/i);
    const body = (!header || header.index == null)
        ? src
        : src.slice(header.index + header[0].length);
    const lines = body.split(/\r?\n/);
    const numbered = lines
        .map((line) => {
            const m = line.match(/^(\s*)(\d+)[.):-]\s+/);
            if (!m) return null;
            return {
                indent: (m[1] || "").length,
                idx: Number(m[2]),
            };
        })
        .filter((x): x is { indent: number; idx: number } => Boolean(x));

    // If numbered tasks exist, count only top-level numbered items.
    // This avoids counting nested bullet points under a numbered task as extra tasks.
    if (numbered.length > 0) {
        const minIndent = Math.min(...numbered.map((n) => n.indent));
        return numbered.filter((n) => n.indent === minIndent).length;
    }

    // Fallback for bullet-only prompts.
    const bulletCount = lines.filter((line) => /^\s*[-*\u2022]\s+/.test(line)).length;
    if (bulletCount > 0) return bulletCount;

    const regexCount = (body.match(/(?:^|\\n|\n)\s*\d+[.)]\s+/g) || []).length;
    if (regexCount > 0) return regexCount;

    const inlineCount = (body.match(/\b\d+[.)]\s+/g) || []).length;
    return inlineCount > 0 ? inlineCount : 0;
};

const formatBatchFinalAnswer = (value: unknown): string => {
    if (typeof value === "string") return value;
    if (!value || typeof value !== "object") return "";
    const obj = value as Record<string, unknown>;
    const candidates = [
        obj.answer_text,
        obj.answer_latex,
        obj.answer,
        obj.text,
        obj.latex,
        obj.value,
    ];
    for (const candidate of candidates) {
        if (typeof candidate === "string" && candidate.trim()) return candidate;
        if (typeof candidate === "number" || typeof candidate === "boolean") return String(candidate);
    }
    return "";
};

const normalizeLanguageCode = (value: string): string => {
    const raw = (value || "").trim().toLowerCase();
    const map: Record<string, string> = {
        en: "en",
        english: "en",
        "english (us)": "en",
        ar: "ar",
        arabic: "ar",
        "العربية": "ar",
        fr: "fr",
        french: "fr",
        francais: "fr",
        "français": "fr",
        es: "es",
        spanish: "es",
        espanol: "es",
        "español": "es",
        pt: "pt",
        portuguese: "pt",
        portugues: "pt",
        "português": "pt",
        ru: "ru",
        russian: "ru",
        "русский": "ru",
        it: "it",
        italian: "it",
        italiano: "it",
    };
    return map[raw] || "en";
};

const SOLVE_I18N: Record<string, Record<string, string>> = {
    en: {
        solvingMathProblem: "Solving Math Problem...",
        advancedNeuralComputation: "Advanced Neural Computation",
        elapsedTime: "Elapsed Time",
        systemPipelineState: "System Pipeline State",
        semanticExtraction: "Semantic Extraction",
        parsingMathSymbols: "Parsing math symbols...",
        neuralReasoning: "Neural Reasoning",
        mappingLogicalSteps: "Mapping logical steps...",
        strictValidation: "Strict Validation",
        checkingSchema: "Checking schema v1.0...",
        packetDelivery: "Packet Delivery",
        assemblingResponse: "Assembling response...",
        extractionComplete: "Extraction complete.",
        initializingReasoning: "Initializing reasoning...",
        callingProvider: "Calling {provider}...",
        reasoningComplete: "Reasoning complete.",
        validatingOutput: "Validating output...",
        validatingSchema: "Validating schema v1.0...",
        validationSuccessful: "Validation successful.",
        streamingResults: "Streaming results...",
        schemaInvalidRepair: "Schema invalid, attempting repair...",
        attemptingRepair: "Attempting automated repair...",
        repairSuccessful: "Repair successful.",
        validationFailed: "Validation failed.",
        solveComplete: "Solve complete.",
        solveFailed: "Solve failed.",
        clarificationRequested: "Clarification requested.",
        batchSolving: "Batch solving...",
        solvingProgress: "Solving {current}/{total} questions...",
        batchPackagedForChat: "Batch packaged for chat.",
        restoringSession: "Restoring session...",
        initializing: "Initializing...",
        resolvingAmbiguity: "Resolving ambiguity...",
        streamingActive: "Streaming Active",
        packetDeliveryRealtime: "Packet delivery in real-time",
        solutionGenerationInProgress: "Solution generation in progress",
        encryptedStream: "Encrypted Stream",
        secureStream: "Secure Stream",
        debugRuntime: "DEBUG / RUNTIME",
    },
    ar: {
        solvingMathProblem: "جاري حل مسألة الرياضيات...",
        advancedNeuralComputation: "حوسبة عصبية متقدمة",
        elapsedTime: "الوقت المنقضي",
        systemPipelineState: "حالة خط سير النظام",
        semanticExtraction: "استخراج دلالي",
        parsingMathSymbols: "تحليل رموز الرياضيات...",
        neuralReasoning: "استدلال عصبي",
        mappingLogicalSteps: "مواءمة الخطوات المنطقية...",
        strictValidation: "تحقق صارم",
        checkingSchema: "فحص المخطط v1.0...",
        packetDelivery: "تسليم الحزمة",
        assemblingResponse: "تجميع الاستجابة...",
        extractionComplete: "اكتمل الاستخراج.",
        initializingReasoning: "تهيئة الاستدلال...",
        callingProvider: "جارٍ استدعاء {provider}...",
        reasoningComplete: "اكتمل الاستدلال.",
        validatingOutput: "جارٍ التحقق من المخرجات...",
        validatingSchema: "جارٍ التحقق من المخطط v1.0...",
        validationSuccessful: "تم التحقق بنجاح.",
        streamingResults: "جارٍ بث النتائج...",
        schemaInvalidRepair: "المخطط غير صالح، محاولة الإصلاح...",
        attemptingRepair: "محاولة إصلاح آلي...",
        repairSuccessful: "نجح الإصلاح.",
        validationFailed: "فشل التحقق.",
        solveComplete: "اكتمل الحل.",
        solveFailed: "فشل الحل.",
        clarificationRequested: "تم طلب توضيح.",
        batchSolving: "جاري الحل الدفعي...",
        solvingProgress: "جاري حل {current}/{total} أسئلة...",
        batchPackagedForChat: "تم تجهيز الدفعة للدردشة.",
        restoringSession: "جاري استعادة الجلسة...",
        initializing: "جارٍ التهيئة...",
        resolvingAmbiguity: "جارٍ حل الغموض...",
        streamingActive: "البث نشط",
        packetDeliveryRealtime: "تسليم الحزمة في الزمن الحقيقي",
        solutionGenerationInProgress: "جاري توليد الحل",
        encryptedStream: "بث مشفر",
        secureStream: "بث آمن",
        debugRuntime: "التصحيح / وقت التشغيل",
    },
    fr: {
        solvingMathProblem: "Resolution du probleme de mathematiques...",
        advancedNeuralComputation: "Calcul neuronal avance",
        elapsedTime: "Temps ecoule",
        systemPipelineState: "Etat du pipeline systeme",
        semanticExtraction: "Extraction semantique",
        parsingMathSymbols: "Analyse des symboles mathematiques...",
        neuralReasoning: "Raisonnement neuronal",
        mappingLogicalSteps: "Cartographie des etapes logiques...",
        strictValidation: "Validation stricte",
        checkingSchema: "Verification du schema v1.0...",
        packetDelivery: "Livraison du paquet",
        assemblingResponse: "Assemblage de la reponse...",
        extractionComplete: "Extraction terminee.",
        initializingReasoning: "Initialisation du raisonnement...",
        callingProvider: "Appel de {provider}...",
        reasoningComplete: "Raisonnement termine.",
        validatingOutput: "Validation de la sortie...",
        validatingSchema: "Validation du schema v1.0...",
        validationSuccessful: "Validation reussie.",
        streamingResults: "Diffusion des resultats...",
        schemaInvalidRepair: "Schema invalide, tentative de correction...",
        attemptingRepair: "Tentative de correction automatique...",
        repairSuccessful: "Correction reussie.",
        validationFailed: "Echec de validation.",
        solveComplete: "Resolution terminee.",
        solveFailed: "Echec de la resolution.",
        clarificationRequested: "Clarification demandee.",
        batchSolving: "Resolution par lot...",
        solvingProgress: "Resolution de {current}/{total} questions...",
        batchPackagedForChat: "Lot pret pour le chat.",
        restoringSession: "Restauration de la session...",
        initializing: "Initialisation...",
        resolvingAmbiguity: "Resolution de l'ambiguite...",
        streamingActive: "Streaming actif",
        packetDeliveryRealtime: "Livraison des paquets en temps reel",
        solutionGenerationInProgress: "Generation de solution en cours",
        encryptedStream: "Flux chiffre",
        secureStream: "Flux securise",
        debugRuntime: "DEBUG / EXECUTION",
    },
    es: {
        solvingMathProblem: "Resolviendo problema matematico...",
        advancedNeuralComputation: "Computacion neuronal avanzada",
        elapsedTime: "Tiempo transcurrido",
        systemPipelineState: "Estado de la canalizacion del sistema",
        semanticExtraction: "Extraccion semantica",
        parsingMathSymbols: "Analizando simbolos matematicos...",
        neuralReasoning: "Razonamiento neuronal",
        mappingLogicalSteps: "Mapeando pasos logicos...",
        strictValidation: "Validacion estricta",
        checkingSchema: "Comprobando esquema v1.0...",
        packetDelivery: "Entrega de paquete",
        assemblingResponse: "Ensamblando respuesta...",
        extractionComplete: "Extraccion completada.",
        initializingReasoning: "Inicializando razonamiento...",
        callingProvider: "Llamando a {provider}...",
        reasoningComplete: "Razonamiento completado.",
        validatingOutput: "Validando salida...",
        validatingSchema: "Validando esquema v1.0...",
        validationSuccessful: "Validacion exitosa.",
        streamingResults: "Transmitiendo resultados...",
        schemaInvalidRepair: "Esquema invalido, intentando reparacion...",
        attemptingRepair: "Intentando reparacion automatica...",
        repairSuccessful: "Reparacion exitosa.",
        validationFailed: "Validacion fallida.",
        solveComplete: "Resolucion completada.",
        solveFailed: "Resolucion fallida.",
        clarificationRequested: "Se solicito aclaracion.",
        batchSolving: "Resolucion por lotes...",
        solvingProgress: "Resolviendo {current}/{total} preguntas...",
        batchPackagedForChat: "Lote preparado para chat.",
        restoringSession: "Restaurando sesion...",
        initializing: "Inicializando...",
        resolvingAmbiguity: "Resolviendo ambiguedad...",
        streamingActive: "Transmision activa",
        packetDeliveryRealtime: "Entrega de paquetes en tiempo real",
        solutionGenerationInProgress: "Generacion de solucion en progreso",
        encryptedStream: "Flujo cifrado",
        secureStream: "Flujo seguro",
        debugRuntime: "DEPURACION / RUNTIME",
    },
    pt: {
        solvingMathProblem: "Resolvendo problema matematico...",
        advancedNeuralComputation: "Computacao neural avancada",
        elapsedTime: "Tempo decorrido",
        systemPipelineState: "Estado do pipeline do sistema",
        semanticExtraction: "Extracao semantica",
        parsingMathSymbols: "Analisando simbolos matematicos...",
        neuralReasoning: "Raciocinio neural",
        mappingLogicalSteps: "Mapeando passos logicos...",
        strictValidation: "Validacao rigorosa",
        checkingSchema: "Verificando esquema v1.0...",
        packetDelivery: "Entrega de pacote",
        assemblingResponse: "Montando resposta...",
        extractionComplete: "Extracao concluida.",
        initializingReasoning: "Inicializando raciocinio...",
        callingProvider: "Chamando {provider}...",
        reasoningComplete: "Raciocinio concluido.",
        validatingOutput: "Validando saida...",
        validatingSchema: "Validando esquema v1.0...",
        validationSuccessful: "Validacao bem-sucedida.",
        streamingResults: "Transmitindo resultados...",
        schemaInvalidRepair: "Esquema invalido, tentando reparar...",
        attemptingRepair: "Tentando reparo automatizado...",
        repairSuccessful: "Reparo concluido.",
        validationFailed: "Falha na validacao.",
        solveComplete: "Resolucao concluida.",
        solveFailed: "Falha na resolucao.",
        clarificationRequested: "Esclarecimento solicitado.",
        batchSolving: "Resolucao em lote...",
        solvingProgress: "Resolvendo {current}/{total} perguntas...",
        batchPackagedForChat: "Lote preparado para o chat.",
        restoringSession: "Restaurando sessao...",
        initializing: "Inicializando...",
        resolvingAmbiguity: "Resolvendo ambiguidade...",
        streamingActive: "Streaming ativo",
        packetDeliveryRealtime: "Entrega de pacotes em tempo real",
        solutionGenerationInProgress: "Geracao de solucao em andamento",
        encryptedStream: "Fluxo criptografado",
        secureStream: "Fluxo seguro",
        debugRuntime: "DEBUG / EXECUCAO",
    },
    ru: {
        solvingMathProblem: "\u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0439 \u0437\u0430\u0434\u0430\u0447\u0438...",
        advancedNeuralComputation: "\u041f\u0440\u043e\u0434\u0432\u0438\u043d\u0443\u0442\u044b\u0435 \u043d\u0435\u0439\u0440\u043e\u043d\u043d\u044b\u0435 \u0432\u044b\u0447\u0438\u0441\u043b\u0435\u043d\u0438\u044f",
        elapsedTime: "\u041f\u0440\u043e\u0448\u0435\u0434\u0448\u0435\u0435 \u0432\u0440\u0435\u043c\u044f",
        systemPipelineState: "\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u043e\u0433\u043e \u043a\u043e\u043d\u0432\u0435\u0439\u0435\u0440\u0430",
        semanticExtraction: "\u0421\u0435\u043c\u0430\u043d\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0438\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435",
        parsingMathSymbols: "\u0420\u0430\u0437\u0431\u043e\u0440 \u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432...",
        neuralReasoning: "\u041d\u0435\u0439\u0440\u043e\u043d\u043d\u043e\u0435 \u0440\u0430\u0441\u0441\u0443\u0436\u0434\u0435\u043d\u0438\u0435",
        mappingLogicalSteps: "\u041f\u043e\u0441\u0442\u0440\u043e\u0435\u043d\u0438\u0435 \u043b\u043e\u0433\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u0448\u0430\u0433\u043e\u0432...",
        strictValidation: "\u0421\u0442\u0440\u043e\u0433\u0430\u044f \u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f",
        checkingSchema: "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0441\u0445\u0435\u043c\u044b v1.0...",
        packetDelivery: "\u0414\u043e\u0441\u0442\u0430\u0432\u043a\u0430 \u043f\u0430\u043a\u0435\u0442\u0430",
        assemblingResponse: "\u0421\u0431\u043e\u0440\u043a\u0430 \u043e\u0442\u0432\u0435\u0442\u0430...",
        extractionComplete: "\u0418\u0437\u0432\u043b\u0435\u0447\u0435\u043d\u0438\u0435 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e.",
        initializingReasoning: "\u0418\u043d\u0438\u0446\u0438\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f \u0440\u0430\u0441\u0441\u0443\u0436\u0434\u0435\u043d\u0438\u044f...",
        callingProvider: "\u0412\u044b\u0437\u043e\u0432 {provider}...",
        reasoningComplete: "\u0420\u0430\u0441\u0441\u0443\u0436\u0434\u0435\u043d\u0438\u0435 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e.",
        validatingOutput: "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0432\u044b\u0432\u043e\u0434\u0430...",
        validatingSchema: "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0441\u0445\u0435\u043c\u044b v1.0...",
        validationSuccessful: "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0443\u0441\u043f\u0435\u0448\u043d\u0430.",
        streamingResults: "\u041f\u043e\u0442\u043e\u043a\u043e\u0432\u0430\u044f \u043f\u0435\u0440\u0435\u0434\u0430\u0447\u0430 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u043e\u0432...",
        schemaInvalidRepair: "\u0421\u0445\u0435\u043c\u0430 \u043d\u0435\u0432\u0430\u043b\u0438\u0434\u043d\u0430, \u043f\u043e\u043f\u044b\u0442\u043a\u0430 \u0438\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f...",
        attemptingRepair: "\u041f\u043e\u043f\u044b\u0442\u043a\u0430 \u0430\u0432\u0442\u043e\u0438\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f...",
        repairSuccessful: "\u0418\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0441\u043f\u0435\u0448\u043d\u043e.",
        validationFailed: "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043d\u0435 \u043f\u0440\u043e\u0439\u0434\u0435\u043d\u0430.",
        solveComplete: "\u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e.",
        solveFailed: "\u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c.",
        clarificationRequested: "\u0422\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u0443\u0442\u043e\u0447\u043d\u0435\u043d\u0438\u0435.",
        batchSolving: "\u041f\u0430\u043a\u0435\u0442\u043d\u043e\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u0435...",
        solvingProgress: "\u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432 {current}/{total}...",
        batchPackagedForChat: "\u041f\u0430\u043a\u0435\u0442 \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d \u0434\u043b\u044f \u0447\u0430\u0442\u0430.",
        restoringSession: "\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0441\u0435\u0441\u0441\u0438\u0438...",
        initializing: "\u0418\u043d\u0438\u0446\u0438\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f...",
        resolvingAmbiguity: "\u0423\u0441\u0442\u0440\u0430\u043d\u0435\u043d\u0438\u0435 \u043d\u0435\u043e\u0434\u043d\u043e\u0437\u043d\u0430\u0447\u043d\u043e\u0441\u0442\u0438...",
        streamingActive: "\u041f\u043e\u0442\u043e\u043a \u0430\u043a\u0442\u0438\u0432\u0435\u043d",
        packetDeliveryRealtime: "\u0414\u043e\u0441\u0442\u0430\u0432\u043a\u0430 \u043f\u0430\u043a\u0435\u0442\u043e\u0432 \u0432 \u0440\u0435\u0430\u043b\u044c\u043d\u043e\u043c \u0432\u0440\u0435\u043c\u0435\u043d\u0438",
        solutionGenerationInProgress: "\u0418\u0434\u0435\u0442 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0440\u0435\u0448\u0435\u043d\u0438\u044f",
        encryptedStream: "\u0417\u0430\u0448\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 \u043f\u043e\u0442\u043e\u043a",
        secureStream: "\u0411\u0435\u0437\u043e\u043f\u0430\u0441\u043d\u044b\u0439 \u043f\u043e\u0442\u043e\u043a",
        debugRuntime: "\u041e\u0422\u041b\u0410\u0414\u041a\u0410 / RUNTIME",
    },
    it: {
        solvingMathProblem: "Risoluzione del problema matematico...",
        advancedNeuralComputation: "Calcolo neurale avanzato",
        elapsedTime: "Tempo trascorso",
        systemPipelineState: "Stato della pipeline di sistema",
        semanticExtraction: "Estrazione semantica",
        parsingMathSymbols: "Analisi dei simboli matematici...",
        neuralReasoning: "Ragionamento neurale",
        mappingLogicalSteps: "Mappatura dei passaggi logici...",
        strictValidation: "Validazione rigorosa",
        checkingSchema: "Controllo schema v1.0...",
        packetDelivery: "Consegna pacchetto",
        assemblingResponse: "Assemblaggio risposta...",
        extractionComplete: "Estrazione completata.",
        initializingReasoning: "Inizializzazione del ragionamento...",
        callingProvider: "Chiamata a {provider}...",
        reasoningComplete: "Ragionamento completato.",
        validatingOutput: "Validazione output...",
        validatingSchema: "Validazione schema v1.0...",
        validationSuccessful: "Validazione riuscita.",
        streamingResults: "Trasmissione risultati...",
        schemaInvalidRepair: "Schema non valido, tentativo di riparazione...",
        attemptingRepair: "Tentativo di riparazione automatica...",
        repairSuccessful: "Riparazione riuscita.",
        validationFailed: "Validazione fallita.",
        solveComplete: "Risoluzione completata.",
        solveFailed: "Risoluzione fallita.",
        clarificationRequested: "Richiesta chiarimento.",
        batchSolving: "Risoluzione batch...",
        solvingProgress: "Risoluzione {current}/{total} domande...",
        batchPackagedForChat: "Batch preparato per la chat.",
        restoringSession: "Ripristino sessione...",
        initializing: "Inizializzazione...",
        resolvingAmbiguity: "Risoluzione ambiguita...",
        streamingActive: "Streaming attivo",
        packetDeliveryRealtime: "Consegna pacchetti in tempo reale",
        solutionGenerationInProgress: "Generazione della soluzione in corso",
        encryptedStream: "Flusso crittografato",
        secureStream: "Flusso sicuro",
        debugRuntime: "DEBUG / RUNTIME",
    },
};

const translateSolveText = (
    language: string,
    key: string,
    vars?: Record<string, string | number>
): string => {
    const lang = normalizeLanguageCode(language);
    const dict = SOLVE_I18N[lang] || SOLVE_I18N.en;
    const template = dict[key] || SOLVE_I18N.en[key] || key;
    if (!vars) return template;
    return template.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""));
};

type SolveOverlayStageKey = "preparing_engine" | "executing_solver" | "calling_ai_core" | "plotting_coordinates";

type PersistedSolveOverlayState = {
    attemptId?: string | null;
    requestId?: string | null;
    startTimeMs: number;
    currentStage: SolveOverlayStageKey;
    streamingActive: boolean;
    updatedAt: number;
};

const SOLVE_OVERLAY_STORAGE_KEY = "uask.solveOverlayState.v1";
const SOLVE_STAGE_ORDER: SolveOverlayStageKey[] = [
    "preparing_engine",
    "executing_solver",
    "calling_ai_core",
    "plotting_coordinates",
];

const buildSolvePipelineStages = (): TimelineStep[] => ([
    { key: "preparing_engine", label: "Preparing Engine", description: "Allocating solver resources.", status: "pending", icon: "memory" },
    { key: "executing_solver", label: "Executing Solver", description: "Processing symbolic and numeric steps.", status: "pending", icon: "function" },
    { key: "calling_ai_core", label: "Calling AI Core", description: "Requesting model inference.", status: "pending", icon: "neurology" },
    { key: "plotting_coordinates", label: "Plotting Coordinates", description: "Finalizing visuals and structured output.", status: "pending", icon: "scatter_plot" },
]);

const readPersistedSolveOverlayState = (): PersistedSolveOverlayState | null => {
    if (typeof window === "undefined") return null;
    try {
        const raw = localStorage.getItem(SOLVE_OVERLAY_STORAGE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw) as PersistedSolveOverlayState;
        if (!parsed || typeof parsed.startTimeMs !== "number" || !SOLVE_STAGE_ORDER.includes(parsed.currentStage)) {
            return null;
        }
        return parsed;
    } catch {
        return null;
    }
};

const writePersistedSolveOverlayState = (state: PersistedSolveOverlayState): void => {
    if (typeof window === "undefined") return;
    localStorage.setItem(SOLVE_OVERLAY_STORAGE_KEY, JSON.stringify(state));
};

const clearPersistedSolveOverlayState = (): void => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(SOLVE_OVERLAY_STORAGE_KEY);
};

const mapBackendEventToOverlayStage = (raw: string | undefined | null): SolveOverlayStageKey | null => {
    if (!raw) return null;
    const value = raw.trim().toLowerCase();
    if (!value) return null;
    if (value.includes("attempt_created") || value.includes("restore") || value.includes("prepare")) {
        return "preparing_engine";
    }
    if (value.includes("execut") || value.includes("solver_start") || value.includes("schema_validate_start")) {
        return "executing_solver";
    }
    if (value.includes("calling_ai_core") || value.includes("ai_core") || value.includes("provider")) {
        return "calling_ai_core";
    }
    if (value.includes("plot") || value.includes("stream") || value.includes("schema_validate_done") || value.includes("schema_repair") || value.includes("complete")) {
        return "plotting_coordinates";
    }
    return null;
};

const normalizeSessionId = (raw: unknown): string | number | null => {
    if (typeof raw === "number" && Number.isFinite(raw) && raw > 0) return raw;
    if (typeof raw === "string") {
        const text = raw.trim();
        if (!text) return null;
        const lowered = text.toLowerCase();
        if (lowered === "null" || lowered === "none" || lowered === "undefined" || text === "0") return null;
        return text;
    }
    return null;
};

const resolveSessionRouteByTier = (tier: SolveTier, sessionId: string | number): string =>
    (tier === "FINAL" || tier === "SHORT_STEPS")
        ? `/chat_final/${sessionId}`
        : `/chat/${sessionId}`;

export default function DashboardPage() {
    const { pushToast } = useToast();
    const router = useRouter();
    const useSnapSolveUploadPanelV2 = process.env.NEXT_PUBLIC_SNAP_SOLVE_UPLOAD_PANEL_V2 !== "false";
    const mapTierToApi = (tier: SolveTier) => {
        if (tier === "SHORT_STEPS") return "short_steps";
        if (tier === "FINAL") return "final";
        return tier.toLowerCase();
    };
    const [activeTab, setActiveTab] = useState<'text' | 'snap' | 'voice'>('text');
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [query, setQuery] = useState("sqrt(x+5) = x - 1");
    const [isSolving, setIsSolving] = useState(false);
    const [onlineUsers, setOnlineUsers] = useState<ActiveUser[]>([]);
    const [isPublic, setIsPublic] = useState(false);
    const [, setLastSolveError] = useState<{ code?: string; message?: string; request_id?: string; details?: unknown } | null>(null);
    const [batchSolveResult] = useState<SolveBatchResponse | null>(null);

    const [activeMode, setActiveMode] = useState<ModeId | null>(null);
    const [isSeeAllOpen, setIsSeeAllOpen] = useState(false);
    const [mathModeEnabled, setMathModeEnabled] = useState(true);
    const mathInputRef = useRef<MathInputRef>(null);
    const [inputError, setInputError] = useState<string | null>(null);

    // Voice State
    const [voiceStage, setVoiceStage] = useState<'idle' | 'recording' | 'processing' | 'review' | 'error'>('idle');
    const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
    const [voiceArtifact, setVoiceArtifact] = useState<VoiceArtifact | null>(null);
    const [recordingTime, setRecordingTime] = useState(0);
    // const [voiceSessionId, setVoiceSessionId] = useState<number | null>(null);
    const voiceSubject = "Mathematics";
    const [formattingEnabled, setFormattingEnabled] = useState(true);
    const [solveProgress, setSolveProgress] = useState(0);

    // Token validation state
    const [showSplitModal, setShowSplitModal] = useState(false);
    const [suggestedSplits, setSuggestedSplits] = useState<string[]>([]);
    const [multiQuestionConfirmed, setMultiQuestionConfirmed] = useState(false);
    const [, setConfirmedBatchQuestions] = useState<string[]>([]);
    const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
    const [, setTaskBundleTasks] = useState<TaskBundleTask[]>([]);
    const [taskUserAction, setTaskUserAction] = useState<"confirm_selected" | "solve_one" | "combined_solution">("confirm_selected");
    const [mathValidityConfirmed, setMathValidityConfirmed] = useState(false);
    const [taskConfirmSnapshot, setTaskConfirmSnapshot] = useState<string | null>(null);
    const [requiresTaskReconfirm, setRequiresTaskReconfirm] = useState(false);

    // Input mode state


    // Plot/Graph inclusion state
    const [graphMode, setGraphMode] = useState<'off' | 'auto' | 'on'>('auto');
    const [tierFeatureGates, setTierFeatureGates] = useState<{ allow_verify: boolean; allow_plot: boolean }>({
        allow_verify: true,
        allow_plot: true,
    });
    const [tierEstimateByTier, setTierEstimateByTier] = useState<Record<SolveTier, number>>({
        SHORT_STEPS: 0,
        FINAL: 0,
        STANDARD: 0,
        RESEARCH: 0,
    });
    const [attachToStepId] = useState<number | null>(null);

    // Random light background for Plot Mode, Tier Section, and Free Type Mode
    const [plotModeColor, setPlotModeColor] = useState("bg-sky-50");
    const [tierSectionColor, setTierSectionColor] = useState("bg-white");
    const [freeTypeColor, setFreeTypeColor] = useState("bg-white");
    useEffect(() => {
        const colors = [
            "bg-blue-50", "bg-green-50", "bg-purple-50", "bg-orange-50",
            "bg-teal-50", "bg-rose-50", "bg-indigo-50", "bg-cyan-50"
        ];
        setPlotModeColor(colors[Math.floor(Math.random() * colors.length)]);
        setTierSectionColor(colors[Math.floor(Math.random() * colors.length)]);
        setFreeTypeColor(colors[Math.floor(Math.random() * colors.length)]);
    }, []);

    // Streaming Solve States (Part F1)
    const [currentStage, setCurrentStage] = useState("");
    const [currentStageKey, setCurrentStageKey] = useState<SolveOverlayStageKey>("preparing_engine");
    const [streamingActive, setStreamingActive] = useState(false);
    const [, setStreamingTelemetry] = useState<StreamingTelemetry | null>(null);
    const [streamingMeta, setStreamingMeta] = useState<StreamingRuntimeMeta | null>(null);
    const [solveStartTime, setSolveStartTime] = useState<number | null>(null);

    // Phase 1: Clarification States
    const [isClarifying, setIsClarifying] = useState(false);
    const [clarificationMessage, setClarificationMessage] = useState("");
    const [clarificationResponse, setClarificationResponse] = useState("");
    const [activeAttemptId, setActiveAttemptId] = useState<string | null>(null);
    const [clarificationHistory, setClarificationHistory] = useState<string[]>([]);
    const [preferredLanguage, setPreferredLanguage] = useState<string>("en");
    const effectiveSolveTierRef = useRef<SolveTier>("SHORT_STEPS");
    const uiDirection = preferredLanguage === "ar" ? "rtl" : "ltr";
    const t = (key: string, vars?: Record<string, string | number>) => translateSolveText(preferredLanguage, key, vars);

    const [pipelineStages, setPipelineStages] = useState<TimelineStep[]>(() => buildSolvePipelineStages());

    const hydrateOverlayPersistence = useCallback((patch: Partial<PersistedSolveOverlayState>) => {
        const prev = readPersistedSolveOverlayState();
        const merged: PersistedSolveOverlayState = {
            attemptId: patch.attemptId ?? prev?.attemptId ?? activeAttemptId ?? null,
            requestId: patch.requestId ?? prev?.requestId ?? streamingMeta?.request_id ?? null,
            startTimeMs: patch.startTimeMs ?? prev?.startTimeMs ?? solveStartTime ?? Date.now(),
            currentStage: patch.currentStage ?? prev?.currentStage ?? currentStageKey,
            streamingActive: patch.streamingActive ?? prev?.streamingActive ?? streamingActive,
            updatedAt: Date.now(),
        };
        writePersistedSolveOverlayState(merged);
    }, [activeAttemptId, currentStageKey, solveStartTime, streamingActive, streamingMeta?.request_id]);

    const applyPipelineStage = useCallback((stage: SolveOverlayStageKey, failed = false) => {
        const activeIdx = SOLVE_STAGE_ORDER.indexOf(stage);
        setCurrentStageKey(stage);
        setPipelineStages((prev) =>
            prev.map((step, idx) => {
                if (idx < activeIdx) return { ...step, status: "completed" };
                if (idx === activeIdx) return { ...step, status: failed ? "failed" : "active" };
                return { ...step, status: "pending" };
            })
        );
        hydrateOverlayPersistence({ currentStage: stage });
    }, [hydrateOverlayPersistence]);

    const markPipelineCompleted = useCallback(() => {
        setPipelineStages((prev) => prev.map((step) => ({ ...step, status: "completed" })));
        hydrateOverlayPersistence({ currentStage: "plotting_coordinates" });
    }, [hydrateOverlayPersistence]);

    const resetPipeline = useCallback((stage: SolveOverlayStageKey = "preparing_engine") => {
        const activeIdx = SOLVE_STAGE_ORDER.indexOf(stage);
        setCurrentStageKey(stage);
        setPipelineStages(
            buildSolvePipelineStages().map((step, idx) => ({
                ...step,
                status: idx === activeIdx ? "active" : idx < activeIdx ? "completed" : "pending",
            }))
        );
    }, []);

    useEffect(() => {
        if (!isSolving) return;

        const interval = setInterval(() => {
            let nextActiveKey: SolveOverlayStageKey | null = null;

            setPipelineStages((prev) => {
                if (!prev.length) return prev;
                if (prev.some((step) => step.status === "failed")) return prev;

                const activeIdx = prev.findIndex((step) => step.status === "active");
                const nextIdx = activeIdx >= 0 ? (activeIdx + 1) % prev.length : 0;

                let allCompletedAfterMark = true;
                const marked = prev.map((step, idx) => {
                    if (idx === activeIdx) return { ...step, status: "completed" as const };
                    if (step.status !== "completed") allCompletedAfterMark = false;
                    return step;
                });

                if (allCompletedAfterMark && nextIdx === 0) {
                    nextActiveKey = SOLVE_STAGE_ORDER[0];
                    return marked.map((step, idx) => ({
                        ...step,
                        status: idx === 0 ? "active" : "pending",
                    }));
                }

                nextActiveKey = (SOLVE_STAGE_ORDER[nextIdx] || SOLVE_STAGE_ORDER[0]) as SolveOverlayStageKey;
                return marked.map((step, idx) => {
                    if (idx === nextIdx) return { ...step, status: "active" };
                    if (step.status === "completed") return step;
                    return { ...step, status: "pending" };
                });
            });

            if (nextActiveKey) {
                setCurrentStageKey(nextActiveKey);
                const stageMeta = buildSolvePipelineStages().find((s) => s.key === nextActiveKey);
                if (stageMeta) setCurrentStage(stageMeta.label);
                hydrateOverlayPersistence({ currentStage: nextActiveKey });
            }
        }, 7000);

        return () => clearInterval(interval);
    }, [hydrateOverlayPersistence, isSolving]);

    // SSE / Polling Event Listener
    useEffect(() => {
        if (!activeAttemptId || !isSolving) return;

        let eventSource: EventSource | null = null;
        let pollInterval: NodeJS.Timeout | null = null;
        const channel = `/api/v1/attempt/${activeAttemptId}/events`;

        type BackendEvent = { phase?: string; status?: string; metadata?: Record<string, unknown> };
        const handleBackendEvent = (data: BackendEvent) => {
            const { phase, status, metadata } = data;

            if (phase === "completed_success" || status === "success") {
                markPipelineCompleted();
                return;
            }
            if (phase === "completed_failure" || status === "failure") {
                applyPipelineStage(currentStageKey, true);
                return;
            }
            if (phase === "clarification_needed" || status === "ambiguous") {
                applyPipelineStage("plotting_coordinates");
                return;
            }
            if (phase === "calling_ai_core_start" && metadata?.provider) {
                setCurrentStage(`Calling AI Core (${String(metadata.provider)})`);
            }
            const mapped = mapBackendEventToOverlayStage(phase);
            if (mapped) {
                applyPipelineStage(mapped);
            }
        };

        const startSSE = () => {
            eventSource = new EventSource(channel, { withCredentials: true });
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleBackendEvent(data);
                } catch (e) {
                    console.error("SSE parse error", e);
                }
            };
            eventSource.onerror = (err) => {
                console.warn("SSE error, falling back to polling", err);
                eventSource?.close();
                startPolling();
            };
        };

        const startPolling = () => {
            pollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/v1/attempt/${activeAttemptId}`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data.status === "success") {
                            markPipelineCompleted();
                            const sessionId = normalizeSessionId(data.session_id);
                            if (sessionId) {
                                localStorage.removeItem("uask.activeAttemptId");
                                localStorage.removeItem("uask.activeQuery");
                                clearPersistedSolveOverlayState();
                                setStreamingActive(false);
                                setIsSolving(false);
                                setSolveStartTime(null);
                                router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, sessionId));
                            }
                            if (pollInterval) clearInterval(pollInterval);
                        } else if (data.status === "failure") {
                            applyPipelineStage(currentStageKey, true);
                            localStorage.removeItem("uask.activeAttemptId");
                            localStorage.removeItem("uask.activeQuery");
                            clearPersistedSolveOverlayState();
                            setStreamingActive(false);
                            setIsSolving(false);
                            setSolveStartTime(null);
                            if (pollInterval) clearInterval(pollInterval);
                        } else if (data.status === "ambiguous") {
                            applyPipelineStage("plotting_coordinates");
                            setIsSolving(false);
                            if (pollInterval) clearInterval(pollInterval);
                        }
                    }
                } catch (e) {
                    console.error("Polling error", e);
                }
            }, 2000);
        };

        startSSE();

        return () => {
            eventSource?.close();
            if (pollInterval) clearInterval(pollInterval);
        };
    }, [activeAttemptId, applyPipelineStage, currentStageKey, isSolving, markPipelineCompleted, router]);

    const buildRuntimeMetaFromPayload = (payload: unknown, fallbackRequestedMode: string): StreamingRuntimeMeta => {
        const toObject = (value: unknown): Record<string, unknown> =>
            (value && typeof value === "object" ? (value as Record<string, unknown>) : {});

        const payloadObj = toObject(payload);
        const nested = toObject(payloadObj.solve_meta ?? payloadObj);
        const versions = toObject(nested.prompt_versions ?? payloadObj.prompt_versions);
        const tokenConfig = toObject(payloadObj.token_config ?? nested.token_config);
        const features = toObject(payloadObj.features ?? nested.features);
        return {
            request_id: (payloadObj.request_id as string | undefined) ?? (nested.request_id as string | undefined),
            provider: (payloadObj.provider as string | undefined) ?? (nested.provider as string | undefined),
            model: (payloadObj.model as string | undefined) ?? (nested.model as string | undefined),
            tier_requested: (payloadObj.tier_requested as string | undefined) ?? (nested.tier_requested as string | undefined),
            effective_tier:
                (payloadObj.effective_tier as string | undefined) ??
                (payloadObj.tier_effective as string | undefined) ??
                (nested.effective_tier as string | undefined) ??
                (nested.tier_effective as string | undefined),
            mode_family:
                (payloadObj.mode_family as string | undefined) ??
                (nested.mode_family as string | undefined) ??
                (nested.mode as string | undefined) ??
                "SOLVE",
            mode: (payloadObj.mode as string | undefined) ?? (nested.mode as string | undefined) ?? fallbackRequestedMode,
            prompt_binding_id:
                (payloadObj.prompt_binding_id as string | undefined) ??
                (nested.prompt_binding_id as string | undefined),
            global_system_prompt_id:
                (payloadObj.global_system_prompt_id as string | undefined) ??
                (nested.global_system_prompt_id as string | undefined),
            developer_prompt_id:
                (payloadObj.developer_prompt_id as string | undefined) ??
                (nested.developer_prompt_id as string | undefined),
            output_schema_id:
                (payloadObj.output_schema_id as string | undefined) ??
                (nested.output_schema_id as string | undefined),
            global_system_prompt_version:
                (payloadObj.global_system_prompt_version as number | undefined) ??
                (versions.system as number | undefined),
            developer_prompt_version:
                (payloadObj.developer_prompt_version as number | undefined) ??
                (versions.developer as number | undefined),
            output_schema_version:
                (payloadObj.output_schema_version as number | undefined) ??
                (versions.schema as number | undefined),
            token_config: Object.keys(tokenConfig).length ? tokenConfig : undefined,
            features: Object.keys(features).length
                ? {
                    allow_research: Boolean(features.allow_research),
                    allow_verify: Boolean(features.allow_verify ?? true),
                    allow_plot: Boolean(features.allow_plot ?? true),
                }
                : undefined,
        };
    };

    const fetchSolveRuntimeMeta = async (
        userId: string,
        tier: SolveTier,
        requestedMode: string
    ): Promise<StreamingRuntimeMeta> => {
        const queryParams = new URLSearchParams({
            user_id: userId,
            tier: mapTierToApi(tier),
            mode_family: "SOLVE",
            requested_mode: requestedMode,
        });
        const res = await fetch(`/api/v1/solve_v3_runtime_meta?${queryParams.toString()}`, {
            method: "GET",
            credentials: "include",
        });
        if (!res.ok) {
            const raw = await res.text();
            throw new Error(raw || "Failed to fetch runtime metadata");
        }
        const data = await res.json();
        return buildRuntimeMetaFromPayload(data, requestedMode);
    };

    // Tier-Aware Solve State
    const selectedGoal = 'solve';
    const [selectedSolveTier, setSelectedSolveTier] = useState<SolveTier>("SHORT_STEPS");
    const explicitTaskCountRaw = useMemo(() => detectExplicitTaskCount(query), [query]);
    const explicitTaskCountCapped = useMemo(
        () => Math.min(MAX_TASKS_PER_QUESTION, Math.max(0, explicitTaskCountRaw)),
        [explicitTaskCountRaw],
    );
    const exceedsMaxTasks = explicitTaskCountRaw > MAX_TASKS_PER_QUESTION;
    const mustForceDetailedTier = (selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL")
        && explicitTaskCountCapped > SHORT_FINAL_MAX_TASKS;
    const effectiveSolveTier: SolveTier = mustForceDetailedTier ? "STANDARD" : selectedSolveTier;
    useEffect(() => {
        effectiveSolveTierRef.current = effectiveSolveTier;
    }, [effectiveSolveTier]);
    const isPlotLockedByTier = effectiveSolveTier === "FINAL";
    const resolveHistorySessionRoute = (session: ChatSession) => {
        const telemetry = session?.telemetry;
        const rawTier =
            telemetry?.tier_effective ||
            telemetry?.effective_tier ||
            telemetry?.tier_requested ||
            telemetry?.tier ||
            "";
        const normalizedTier = String(rawTier).trim().toUpperCase();
        return (normalizedTier === "FINAL" || normalizedTier === "SHORT_STEPS")
            ? `/chat_final/${session.id}`
            : `/chat/${session.id}`;
    };
    const [walletSummary, setWalletSummary] = useState<WalletSummary | null>(null);
    const [walletPrograms, setWalletPrograms] = useState<WalletProgramEnrollment[]>([]);
    const [walletLoaded, setWalletLoaded] = useState(false);
    const [walletError, setWalletError] = useState<string | null>(null);
    type TrustedProfile = {
        grade_level?: string | null;
        region_country?: string | null;
        region_state_province?: string | null;
        is_public?: boolean;
        preferred_language?: string | null;
        school_name?: string | null;
        profile_province_state?: string | null;
        profile_country?: string | null;
    };
    const [userProfile, setUserProfile] = useState<TrustedProfile | null>(null);
    const [estimate, setEstimate] = useState<CreditsEstimateResponse | null>(null);
    const [tokenPolicy, setTokenPolicy] = useState<TokenPolicy | null>(null);
    const [tokenPolicyLoaded, setTokenPolicyLoaded] = useState(false);
    const [tokenPolicyError, setTokenPolicyError] = useState<string | null>(null);
    const ocrMetadata: OcrMetadata = {
        ocr_confidence: 0,
        ocr_warnings: [],
        ocr_source: "image",
        ocr_engine: "snap_v2",
    };
    const [voiceFeatures, setVoiceFeatures] = useState<VoiceFeatures>({
        voice_confirmed: false,
    });

    // Compute token estimate and multi-question detection
    const tokenEstimate = useMemo(() => estimateTokens(query), [query]);
    const multiQuestionResult = useMemo(() => detectMultiQuestion(query), [query]);
    const tokenPolicyReady = tokenPolicyLoaded && !tokenPolicyError && !!tokenPolicy;
    const textInputMaxTokens = tokenPolicy?.text.input_max ?? 1;
    const textInputMaxChars = tokenPolicy?.text.input_max_chars ?? 1;
    const requestBudget: TokenBudgetPolicy | null = useMemo(() => {
        if (!tokenPolicyReady || !tokenPolicy) return null;
        return {
            textInputMax: tokenPolicy.text.input_max,
            textInputMaxChars: tokenPolicy.text.input_max_chars,
            systemAndSchemaBudget: tokenPolicy.request.system_and_schema_budget,
            expectedOutputBudget: tokenPolicy.request.expected_output_budget,
        };
    }, [tokenPolicyReady, tokenPolicy]);
    const requestFit = useMemo(
        () => (requestBudget ? willRequestFit(tokenEstimate.tokens, requestBudget) : { fits: false, estimatedTotal: 0, limit: 0, headroom: 0 }),
        [tokenEstimate.tokens, requestBudget]
    );

    // Determine if solve should be blocked
    const isInputTooLong = tokenPolicyReady
        ? tokenEstimate.tokens > textInputMaxTokens || query.length > textInputMaxChars
        : true;
    const isRequestTooLarge = !requestFit.fits;
    const tokenBlockReason = !tokenPolicyReady
        ? "Token policy unavailable. Please refresh."
        : isInputTooLong
            ? "Input too long. Please split into smaller parts."
            : isRequestTooLarge
                ? "Request too large for AI context. Please shorten."
                : null;

    const walletReady = walletLoaded && !walletError && !!walletSummary;
    const readyWallet = walletReady ? walletSummary : null;
    const estimatedQuestionCount = 1;
    const estimatedSolveCost = useMemo(() => {
        if (!estimate) return null;
        return Number(estimate.estimated_total_credits ?? estimate.total_credits ?? estimate.per_question_credits ?? 0);
    }, [estimate]);
    const currentTaskBundle = useMemo(() => {
        const maxTasks = MAX_TASKS_PER_QUESTION;
        const splitsForTasks = activeTab === "text"
            ? (suggestedSplits.length > 0 ? suggestedSplits : multiQuestionResult.suggestedSplits)
            : [];
        const cleanedSplits = (splitsForTasks || [])
            .map((s) => String(s || "").trim())
            .filter((s) => s.length > 0);
        const effective = cleanedSplits.length > 0 ? cleanedSplits : [String(query || "")];
        const capped = effective.slice(0, maxTasks);
        const tasks: TaskBundleTask[] = capped.map((taskText, idx) => ({
            task_id: `t${idx + 1}`,
            task_text: taskText,
            order_index: idx + 1,
        }));
        const selected = selectedTaskIds.length > 0 ? selectedTaskIds : tasks.map((t) => t.task_id);
        return {
            context_text: extractSharedContext(query) || query,
            tasks,
            selected_task_ids: selected.filter((id) => tasks.some((t) => t.task_id === id)),
            tasks_truncated: effective.length > capped.length,
            tasks_truncated_from: effective.length > capped.length ? effective.length : null,
        };
    }, [activeTab, suggestedSplits, multiQuestionResult.suggestedSplits, query, selectedTaskIds]);
    const estimateBreakdown = useMemo(() => {
        if (!estimate?.breakdown) return undefined;
        const raw = estimate.breakdown as Record<string, unknown>;
        const addons = (raw.addons && typeof raw.addons === "object") ? raw.addons as Record<string, unknown> : {};
        const toNumber = (...values: unknown[]) => {
            for (const value of values) {
                const numeric = Number(value);
                if (Number.isFinite(numeric)) return numeric;
            }
            return 0;
        };
        return {
            // Support both legacy and new response layouts.
            tier_base: toNumber(raw.tier_base, raw.base),
            ocr: toNumber(raw.ocr, addons.ocr),
            voice: toNumber(raw.voice, addons.voice),
            verify: toNumber(raw.verify, addons.verify),
            plot: toNumber(raw.plot, addons.plot),
            asset_type_addon: toNumber(raw.asset_type_addon, addons.asset_type_addon, addons.asset),
            attempt_fee: toNumber(raw.attempt_fee, addons.attempt_fee),
        };
    }, [estimate]);
    const hasEnoughCredits = readyWallet && estimatedSolveCost != null
        ? readyWallet.computed_balance >= estimatedSolveCost
        : true;
    const canAffordTier = (tier: SolveTier): boolean => {
        if (!readyWallet) return true;
        const required = Number(tierEstimateByTier[tier] || 0);
        return readyWallet.computed_balance >= required;
    };
    const creditBlockReason = readyWallet && estimatedSolveCost != null && !hasEnoughCredits
        ? `Insufficient credits. Need ${estimatedSolveCost.toFixed(2)} credits.`
        : null;
    const taskBlockReason = exceedsMaxTasks
        ? `Maximum ${MAX_TASKS_PER_QUESTION} tasks per question. Detected ${explicitTaskCountRaw}.`
        : null;

    useEffect(() => {
        if (typeof window === "undefined") return;
        if (!readyWallet?.user_id) return;
        localStorage.setItem("user_id", String(readyWallet.user_id));
    }, [readyWallet?.user_id]);

    useEffect(() => {
        const stored = typeof window !== "undefined" ? localStorage.getItem("uask.solveTier") : null;
        if (stored === "RESEARCH") {
            setSelectedSolveTier("STANDARD");
            return;
        }
        if (stored === "SHORT_STEPS" || stored === "FINAL" || stored === "STANDARD") {
            setSelectedSolveTier(stored as SolveTier);
        }
    }, []);

    useEffect(() => {
        if (!walletReady) return;
        const stored = typeof window !== "undefined" ? localStorage.getItem("uask.solveTier") : null;
        const defaultTier: SolveTier =
            stored === "SHORT_STEPS" || stored === "FINAL" || stored === "STANDARD"
                ? (stored as SolveTier)
                : "STANDARD";
        setSelectedSolveTier(defaultTier);
        if (typeof window !== "undefined" && !stored) {
            localStorage.setItem("uask.solveTier", defaultTier);
        }
    }, [walletReady, readyWallet]);

    useEffect(() => {
        if (!tokenPolicyReady || !walletReady || !readyWallet) return;
        let active = true;
        const runTierAffordabilityEstimate = async () => {
            const inputType = activeTab === "snap" ? "snap" : activeTab === "voice" ? "voice" : "text";
            const assetType = activeTab === "snap" ? "image" : "none";
            const rows = await Promise.all(
                ALL_SOLVE_TIERS.map(async (tier) => {
                    try {
                        const response = await fetchCreditsEstimate({
                            tier,
                            input_type: inputType,
                            asset_type: assetType,
                            question_count: estimatedQuestionCount,
                            original_input_text: query,
                            context_text: currentTaskBundle.context_text,
                            tasks: currentTaskBundle.tasks,
                            selected_task_ids: currentTaskBundle.selected_task_ids,
                            user_action: taskUserAction,
                            solve_mode: taskUserAction === "combined_solution" ? "BUNDLE_COMBINED" : "PER_TASK_STEPS",
                            detection_confidence: multiQuestionResult.confidence as "high" | "medium" | "low",
                            addons: {
                                ocr: activeTab === "snap",
                                voice: activeTab === "voice",
                                verify: false,
                                plot: graphMode !== "off",
                            },
                        });
                        return [tier, Number(response.total_credits || 0)] as const;
                    } catch {
                        return [tier, 0] as const;
                    }
                }),
            );
            if (!active) return;
            const next: Record<SolveTier, number> = {
                SHORT_STEPS: 0,
                FINAL: 0,
                STANDARD: 0,
                RESEARCH: 0,
            };
            for (const [tier, credits] of rows) next[tier] = credits;
            setTierEstimateByTier(next);
        };
        void runTierAffordabilityEstimate();
        return () => {
            active = false;
        };
    }, [tokenPolicyReady, walletReady, readyWallet, activeTab, estimatedQuestionCount, graphMode, query, currentTaskBundle, taskUserAction, multiQuestionResult.confidence]);

    useEffect(() => {
        if (!readyWallet) return;
        const selectedTierBlockedByCredits = !canAffordTier(effectiveSolveTier);
        if (!selectedTierBlockedByCredits) return;

        const fallbackOrder: SolveTier[] = ["STANDARD", "FINAL", "SHORT_STEPS"];
        const fallback = fallbackOrder.find((tier) => {
            return canAffordTier(tier);
        }) || "STANDARD";
        setSelectedSolveTier(fallback);
        if (typeof window !== "undefined") {
            localStorage.setItem("uask.solveTier", fallback);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [readyWallet?.computed_balance, tierEstimateByTier, effectiveSolveTier]);

    useEffect(() => {
        if (!mustForceDetailedTier) return;
        if (String(selectedSolveTier) === "STANDARD") return;
        setSelectedSolveTier("STANDARD");
        if (typeof window !== "undefined") {
            localStorage.setItem("uask.solveTier", "STANDARD");
        }
        pushToast({
            type: "info",
            title: "Tier Auto-Upgraded",
            message: "Questions with more than 3 tasks require Standard tier.",
        });
    }, [mustForceDetailedTier, selectedSolveTier, pushToast]);

    useEffect(() => {
        if (!tokenPolicyReady) return;
        const runEstimate = async () => {
            try {
                const inputType = activeTab === "snap" ? "snap" : activeTab === "voice" ? "voice" : "text";
                const response = await fetchCreditsEstimate({
                    tier: effectiveSolveTier,
                    input_type: inputType,
                    asset_type: activeTab === "snap" ? "image" : "none",
                    question_count: estimatedQuestionCount,
                    original_input_text: query,
                    context_text: currentTaskBundle.context_text,
                    tasks: currentTaskBundle.tasks,
                    selected_task_ids: currentTaskBundle.selected_task_ids,
                    user_action: taskUserAction,
                    solve_mode: taskUserAction === "combined_solution" ? "BUNDLE_COMBINED" : "PER_TASK_STEPS",
                    detection_confidence: multiQuestionResult.confidence as "high" | "medium" | "low",
                    addons: {
                        ocr: activeTab === "snap",
                        voice: activeTab === "voice",
                        verify: false,
                        plot: !isPlotLockedByTier && tierFeatureGates.allow_plot && graphMode !== "off",
                    },
                });
                setEstimate(response);
            } catch {
                setEstimate(null);
            }
        };
        void runEstimate();
    }, [tokenPolicyReady, effectiveSolveTier, activeTab, estimatedQuestionCount, graphMode, tierFeatureGates.allow_plot, isPlotLockedByTier, query, currentTaskBundle, taskUserAction, multiQuestionResult.confidence]);

    useEffect(() => {
        if (isPlotLockedByTier && graphMode !== "off") {
            setGraphMode("off");
        }
    }, [isPlotLockedByTier, graphMode]);

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) return;
        const requestedMode = (effectiveSolveTier === "SHORT_STEPS" || effectiveSolveTier === "FINAL") ? "minimal" : "detailed";
        void fetchSolveRuntimeMeta(userId, effectiveSolveTier, requestedMode)
            .then((runtimeMeta) => {
                const gates = {
                    allow_verify: runtimeMeta.features?.allow_verify ?? true,
                    allow_plot: runtimeMeta.features?.allow_plot ?? true,
                };
                setTierFeatureGates(gates);
                if ((isPlotLockedByTier || !gates.allow_plot) && graphMode !== "off") {
                    setGraphMode("off");
                }
            })
            .catch(() => {
                // Keep last known gates on fetch failure.
            });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [effectiveSolveTier, graphMode, isPlotLockedByTier]);

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) {
            router.push("/login");
            return;
        }

        const fetchHistory = async () => {
            try {
                const response = await fetch(`/api/v1/history?user_id=${userId}`);
                if (response.ok) {
                    const data = await response.json();
                    setHistory(data);
                }
            } catch (error) {
                console.error("Failed to fetch history:", error);
            }
        };

        const fetchOnline = async () => {
            try {
                const profileRes = await fetch(`/api/v1/user/profile?user_id=${userId}`);
                if (profileRes.ok) {
                    const profile = await profileRes.json();
                    setIsPublic(profile.is_public);
                    setUserProfile(profile);
                    setPreferredLanguage(normalizeLanguageCode(profile.preferred_language || "en"));

                    if (profile.is_public) {
                        const onlineRes = await fetch(`/api/v1/users/online`);
                        if (onlineRes.ok) {
                            setOnlineUsers(await onlineRes.json());
                        }
                    }
                }
            } catch (e) { console.error(e); }
        };

        // Fetch wallet for tier-aware solve UX
        const loadWallet = async () => {
            try {
                const [summary, programs] = await Promise.all([
                    fetchWalletSummary(),
                    fetchWalletPrograms(50, 0),
                ]);
                setWalletSummary(summary);
                setWalletPrograms(programs.items || []);
                setWalletError(null);
            } catch (e) {
                const message = e instanceof Error ? e.message : "Wallet unavailable";
                const requestId = e && typeof e === "object" && "requestId" in e ? (e as { requestId?: string }).requestId : undefined;
                console.warn("Failed to load wallet:", message);
                setWalletError("Unable to load wallet data. Please refresh or contact support.");
                pushToast({
                    type: "error",
                    title: "Wallet unavailable",
                    message: message,
                    requestId,
                });
            } finally {
                setWalletLoaded(true);
            }
        };
        const loadTokenPolicy = async () => {
            try {
                const policy = await fetchTokenPolicy();
                setTokenPolicy(policy);
                setTokenPolicyError(null);
                setTokenPolicyLoaded(true);
            } catch (e) {
                const message = e instanceof Error ? e.message : "Token policy unavailable";
                console.warn("Failed to load token policy:", message);
                setTokenPolicyError("Unable to load token policy. Please refresh or contact support.");
                setTokenPolicyLoaded(true);
            }
        };

        const restoreAttempt = async () => {
            const savedAttemptId = localStorage.getItem("uask.activeAttemptId");
            const savedQuery = localStorage.getItem("uask.activeQuery");
            if (savedAttemptId) {
                console.log("[RESTORE] Found active attempt:", savedAttemptId);
                setActiveAttemptId(savedAttemptId);
                if (savedQuery) setQuery(savedQuery);
                const persisted = readPersistedSolveOverlayState();

                try {
                    setIsSolving(true);
                    setCurrentStage("Preparing Engine");
                    setStreamingActive(Boolean(persisted?.streamingActive));
                    if (persisted?.currentStage) {
                        applyPipelineStage(persisted.currentStage);
                    } else {
                        resetPipeline("preparing_engine");
                    }

                    const res = await fetch(`/api/v1/attempt/${savedAttemptId}`);
                    if (!res.ok) throw new Error("Failed to fetch attempt");

                    const data = await res.json();
                    const createdAtMs = typeof data?.created_at === "string" ? Date.parse(data.created_at) : NaN;
                    const restoredStartTime =
                        Number.isFinite(createdAtMs) && createdAtMs > 0
                            ? createdAtMs
                            : (persisted?.startTimeMs ?? Date.now());
                    setSolveStartTime(restoredStartTime);
                    hydrateOverlayPersistence({
                        attemptId: savedAttemptId,
                        requestId: typeof data?.request_id === "string" ? data.request_id : persisted?.requestId,
                        startTimeMs: restoredStartTime,
                    });
                    const restoredSessionId = normalizeSessionId(data.session_id);
                    if (data.status === "success" && restoredSessionId) {
                        // Already solved
                        localStorage.removeItem("uask.activeAttemptId");
                        localStorage.removeItem("uask.activeQuery");
                        clearPersistedSolveOverlayState();
                        router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, restoredSessionId));
                    } else if (data.status === "ambiguous") {
                        setIsClarifying(true);
                        setClarificationMessage(data.error_message || "Clarification needed.");
                        applyPipelineStage("plotting_coordinates");
                    } else if (data.status === "failure") {
                        localStorage.removeItem("uask.activeAttemptId");
                        localStorage.removeItem("uask.activeQuery");
                        clearPersistedSolveOverlayState();
                        pushToast({
                            type: "error",
                            title: "Previous attempt failed",
                            message: data.error_message || "Unknown error",
                        });
                        setIsSolving(false);
                        setSolveStartTime(null);
                    } else if (data.status === "pending" || data.status === "processing") {
                        setIsSolving(true);
                        const mapped = mapBackendEventToOverlayStage(typeof data?.phase === "string" ? data.phase : "");
                        if (mapped) {
                            applyPipelineStage(mapped);
                        } else if (!persisted?.currentStage) {
                            applyPipelineStage("executing_solver");
                        }
                    } else {
                        setIsSolving(false);
                        setSolveStartTime(null);
                        clearPersistedSolveOverlayState();
                    }
                } catch (e) {
                    console.error("[RESTORE] Failed:", e);
                    localStorage.removeItem("uask.activeAttemptId");
                    localStorage.removeItem("uask.activeQuery");
                    clearPersistedSolveOverlayState();
                    setIsSolving(false);
                    setSolveStartTime(null);
                }
            }
        };

        fetchHistory();
        fetchOnline();
        loadWallet();
        loadTokenPolicy();
        restoreAttempt();
        const interval = setInterval(fetchOnline, 30000);
        return () => clearInterval(interval);
    }, [applyPipelineStage, hydrateOverlayPersistence, pushToast, resetPipeline, router]);

    const handleSuggestionClick = (suggestion: Suggestion) => {
        setMathModeEnabled(true);

        if (suggestion.insertMode === 'replace') {
            // If Math Mode was off, this state update will initialize MathInput with this value
            setQuery(suggestion.latex);
            setConfirmedBatchQuestions([]);
            setMultiQuestionConfirmed(false);
            setMathValidityConfirmed(false);

            // If checking ref immediately (it might be stale if we just switched mode), try to set it
            if (mathInputRef.current) {
                mathInputRef.current.setValue(suggestion.latex);
                mathInputRef.current.focus();
            }
        } else {
            // Append
            if (mathInputRef.current) {
                mathInputRef.current.insert(suggestion.latex);
                mathInputRef.current.focus();
            } else {
                // If switching from text mode, just append to state
                setQuery(prev => prev + suggestion.latex);
                setConfirmedBatchQuestions([]);
                setMultiQuestionConfirmed(false);
                setMathValidityConfirmed(false);
            }
        }

        // Close the dropdown panel
        setActiveMode(null);
    };

    const handleClear = () => {
        setQuery("");
        setConfirmedBatchQuestions([]);
        setMultiQuestionConfirmed(false);
        setMathValidityConfirmed(false);
        setInputError(null);
        if (mathInputRef.current) {
            mathInputRef.current.setValue("");
            mathInputRef.current.focus();
        }
    };

    useEffect(() => {
        let timer: ReturnType<typeof setInterval> | undefined;
        if (voiceStage === 'recording') {
            timer = setInterval(() => setRecordingTime(prev => prev + 1), 1000);
        }
        return () => {
            if (timer) {
                clearInterval(timer);
            }
        };
    }, [voiceStage]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            const chunks: Blob[] = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunks.push(e.data);
            };

            recorder.onstop = async () => {
                const audioBlob = new Blob(chunks, { type: 'audio/webm' });
                await handleAudioUpload(audioBlob);
            };

            setMediaRecorder(recorder);
            recorder.start();
            setVoiceStage('recording');
            setRecordingTime(0);
        } catch (err) {
            console.error("Failed to start recording", err);
            setVoiceStage('error');
        }
    };

    const stopRecording = () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            setVoiceStage('processing');
        }
    };

    const handleAudioUpload = async (blob: Blob) => {
        const storedUserId = localStorage.getItem("user_id");
        const normalizedStoredUserId = storedUserId && /^\d+$/.test(storedUserId) ? storedUserId : null;
        const userId = String(readyWallet?.user_id ?? normalizedStoredUserId ?? "1");
        try {
            // 1. Create Session
            const sessionRes = await fetch('/api/v1/voice/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: parseInt(userId) })
            });
            const sessData = await sessionRes.json();
            const vsid = sessData.voice_session_id;
            // setVoiceSessionId(vsid);

            // 2. Upload Audio
            const formData = new FormData();
            formData.append('file', blob, 'voice.webm');
            await fetch(`/api/v1/voice/sessions/${vsid}/audio`, {
                method: 'POST',
                body: formData
            });

            // 3. Create Job
            const jobRes = await fetch(`/api/v1/voice/sessions/${vsid}/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ priority: 'high' })
            });
            const { job_id } = await jobRes.json();

            // 4. Poll
            pollVoiceJob(job_id);

        } catch (err) {
            console.error(err);
            setVoiceStage('error');
        }
    };

    const pollVoiceJob = async (jobId: number) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/v1/voice/jobs/${jobId}`);
                const data = await res.json();
                if (data.status === 'done') {
                    clearInterval(interval);
                    fetchVoiceArtifact(data.artifact_id);
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    setVoiceStage('error');
                }
            } catch (err) {
                console.error(err);
                clearInterval(interval);
                setVoiceStage('error');
            }
        }, 1000);
    };

    const fetchVoiceArtifact = async (artifactId: number) => {
        try {
            const res = await fetch(`/api/v1/voice/artifacts/${artifactId}`);
            const data = await res.json();
            setVoiceArtifact(data);
            setQuery(data.normalized_math_text);
            if (mathInputRef.current) mathInputRef.current.setValue(data.normalized_math_text);
            setVoiceStage('review');
        } catch (err) {
            console.error(err);
            setVoiceStage('error');
        }
    };

    const handleConfirmVoice = async () => {
        if (!voiceArtifact || isSolving) return;
        const transcriptError = validateMathQuery(voiceArtifact.transcript_raw || "");
        const normalizedError = validateMathQuery(query || "");
        if (transcriptError || normalizedError) {
            setInputError(transcriptError || normalizedError);
            return;
        }
        setIsSolving(true);
        setVoiceFeatures((prev) => ({
            ...prev,
            voice_confirmed: true,
            voice_used: true,
        }));
        try {
            await fetch(`/api/v1/voice/artifacts/${voiceArtifact.id}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    confirmed_transcript_text: voiceArtifact.transcript_raw,
                    confirmed_normalized_math_text: query
                })
            });
            await handleSolve(undefined, { voice_confirmed: true, voice_used: true });
        } catch (err) {
            console.error(err);
            setIsSolving(false);
        }
    };

    const formatQuestionsForInput = (questions: string[]): string =>
        questions
            .map((question, index) => `${index + 1}) ${question.trim()}`)
            .join("\n\n");

    const buildConfirmedInputText = (questions: string[], sharedContext?: string): string => {
        const formattedQuestions = formatQuestionsForInput(questions);
        const context = (sharedContext || "").trim();
        if (!context) return formattedQuestions;
        return `${context}\n\n${formattedQuestions}`.trim();
    };

    const buildTaskBundleFromText = useCallback((inputText: string, splits: string[]) => {
        const maxTasks = MAX_TASKS_PER_QUESTION;
        const cleanedSplits = (splits || [])
            .map((s) => String(s || "").trim())
            .filter((s) => s.length > 0);
        const effective = cleanedSplits.length > 0 ? cleanedSplits : [String(inputText || "")];
        const capped = effective.slice(0, maxTasks);
        const tasks: TaskBundleTask[] = capped.map((taskText, idx) => ({
            task_id: `t${idx + 1}`,
            task_text: taskText,
            order_index: idx + 1,
        }));
        return {
            context_text: extractSharedContext(inputText) || inputText,
            tasks,
            selected_task_ids: tasks.map((t) => t.task_id),
            tasks_truncated: effective.length > capped.length,
            tasks_truncated_from: effective.length > capped.length ? effective.length : null,
        };
    }, []);

    useEffect(() => {
        if (!query) {
            setTaskBundleTasks([]);
            setSelectedTaskIds([]);
            setTaskConfirmSnapshot(null);
            setRequiresTaskReconfirm(false);
            return;
        }
        const bundle = buildTaskBundleFromText(query, multiQuestionResult.suggestedSplits || []);
        setTaskBundleTasks(bundle.tasks);
        setSelectedTaskIds(bundle.selected_task_ids);
    }, [query, multiQuestionResult.suggestedSplits, buildTaskBundleFromText]);

    useEffect(() => {
        const snap = String(taskConfirmSnapshot || "").trim();
        const now = String(query || "").trim();
        if (!snap) return;
        if (now !== snap) {
            setRequiresTaskReconfirm(true);
            setMultiQuestionConfirmed(false);
            if (inputError) setInputError(null);
        }
    }, [query, taskConfirmSnapshot, inputError]);

    const handleSolveTextBatch = async (questionsToSolve: string[], sharedContext?: string) => {
        // Batch solve is disabled. Route as a single question request with the original content.
        const combined = buildConfirmedInputText(questionsToSolve, sharedContext);
        await handleSolve(combined);
    };
    void handleSolveTextBatch;

    const handleSolve = async (textOverride?: string, featureOverrides?: Record<string, unknown>) => {
        if (isSolving) return;
        if (!tokenPolicyReady) {
            setInputError("Token policy unavailable. Please refresh.");
            return;
        }
        if (!hasEnoughCredits) {
            pushToast({
                title: "Insufficient credits",
                message: creditBlockReason || "Please top up your wallet before solving.",
                type: "error",
            });
            return;
        }
        if (taskBlockReason) {
            setInputError(taskBlockReason);
            pushToast({
                title: "Too many tasks",
                message: taskBlockReason,
                type: "error",
            });
            return;
        }

        const userId = localStorage.getItem("user_id") || "1";
        const mathFieldValue = mathModeEnabled && mathInputRef.current?.getValue
            ? mathInputRef.current.getValue()
            : "";
        const textToSolve = textOverride ?? (mathFieldValue.trim() ? mathFieldValue : query);

        if (activeTab === "text") {
            const splitCandidates = autoSplitQuestions(textToSolve)
                .map((q) => q.trim())
                .filter((q) => q.length > 0);
            setSuggestedSplits(splitCandidates);
            const mustReconfirm = requiresTaskReconfirm && splitCandidates.length > 1;
            if ((!multiQuestionConfirmed || mustReconfirm) && splitCandidates.length > 1) {
                const bundle = buildTaskBundleFromText(textToSolve, splitCandidates);
                setTaskBundleTasks(bundle.tasks);
                setSelectedTaskIds(bundle.selected_task_ids);
                setTaskUserAction("confirm_selected");
                setInputError(null);
                if (mustReconfirm) {
                    pushToast({
                        title: "Input changed",
                        message: "Input changed, please reconfirm tasks.",
                        type: "info",
                    });
                }
                setShowSplitModal(true);
                return;
            }
        }

        const validationError = validateMathQuery(textToSolve);
        const isOverridableError = validationError === INPUT_ERROR_BLOCKED || validationError === INPUT_ERROR_NOT_MATH;

        if (validationError) {
            if (isOverridableError) {
                if (!mathValidityConfirmed) {
                    setInputError(validationError);
                    return;
                }
            } else {
                setInputError(validationError);
                return;
            }
        }

        const solveStartedAt = Date.now();
        setIsSolving(true);
        setCurrentStage("Preparing Engine");
        setCurrentStageKey("preparing_engine");
        setStreamingActive(false);
        setStreamingTelemetry(null);
        setStreamingMeta(null);
        setSolveStartTime(solveStartedAt);
        setLastSolveError(null);
        resetPipeline("preparing_engine");
        hydrateOverlayPersistence({
            startTimeMs: solveStartedAt,
            currentStage: "preparing_engine",
            streamingActive: false,
            attemptId: null,
            requestId: null,
        });

        // Reset Phase 1 Clarification
        setIsClarifying(false);
        setClarificationMessage("");
        setClarificationResponse("");
        setClarificationHistory([]);
        setActiveAttemptId(null);
        if (typeof window !== "undefined") {
            localStorage.removeItem("uask.activeAttemptId");
            localStorage.removeItem("uask.activeQuery");
        }

        const createIdempotencyKey = () =>
            typeof crypto !== "undefined" && "randomUUID" in crypto
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

        try {
            // Prefer direct stream first to avoid stale detached-worker state.
            const streamCandidates = ["/api/v1/solve_v3_stream", "/api/v1/solve_v3_stream_detached"];
            const requestedMode = (effectiveSolveTier === "SHORT_STEPS" || effectiveSolveTier === "FINAL") ? "minimal" : "detailed";
            const idempotencyKey = createIdempotencyKey();
            const recoverSessionFromHistory = async (): Promise<string | number | null> => {
                try {
                    const res = await fetch(`/api/v1/history?user_id=${encodeURIComponent(userId)}`);
                    if (!res.ok) return null;
                    const data = await res.json();
                    if (!Array.isArray(data) || data.length === 0) return null;
                    const latest = data[0] as { id?: string | number };
                    return normalizeSessionId(latest?.id);
                } catch {
                    return null;
                }
            };

            void fetchSolveRuntimeMeta(userId, effectiveSolveTier, requestedMode)
                .then((runtimeMeta) => {
                    setStreamingMeta((prev) => ({ ...(prev || {}), ...runtimeMeta }));
                })
                .catch((metaErr) => {
                    console.warn("[SOLVER_STREAM] Runtime meta prefetch failed:", metaErr);
                });

            const overridePayload = (featureOverrides || {}) as Record<string, unknown>;
            const {
                source_type,
                source_id,
                question_text,
                original_input_text,
                context_text,
                tasks,
                selected_task_ids,
                user_action,
                solve_mode,
                detection_confidence,
                ...featureOverrideFeatures
            } = overridePayload;
            const features = {
                ocr_used: activeTab === 'snap',
                voice_used: activeTab === 'voice',
                plot_requested: !isPlotLockedByTier && tierFeatureGates.allow_plot && graphMode !== 'off',
                ...(activeTab === 'snap' ? ocrMetadata : {}),
                ...(activeTab === 'voice' ? voiceFeatures : {}),
                ...featureOverrideFeatures,
            };

            let response: Response | null = null;
            let lastFetchError: unknown = null;
            for (const endpoint of streamCandidates) {
                try {
                    response = await fetch(`${endpoint}?user_id=${encodeURIComponent(userId)}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            confirmed_text: textToSolve,
                            original_input_text: String(original_input_text || textToSolve),
                            context_text: String(context_text || currentTaskBundle.context_text || textToSolve),
                            tasks: (Array.isArray(tasks) ? tasks : currentTaskBundle.tasks),
                            selected_task_ids: (
                                Array.isArray(selected_task_ids) && selected_task_ids.length > 0
                                    ? selected_task_ids
                                    : currentTaskBundle.selected_task_ids
                            ),
                            user_action: String(user_action || taskUserAction || "confirm_selected"),
                            solve_mode: String(solve_mode || (taskUserAction === "combined_solution" ? "BUNDLE_COMBINED" : "PER_TASK_STEPS")),
                            detection_confidence: String(detection_confidence || multiQuestionResult.confidence || "low"),
                            requested_mode: requestedMode,
                            tier: mapTierToApi(effectiveSolveTier),
                            source_type,
                            source_id,
                            question_text,
                            trusted_context: {
                                learning_mode: selectedGoal,
                                grade_level: userProfile?.grade_level || undefined,
                                region_country: userProfile?.region_country || undefined,
                                region_state_province: userProfile?.region_state_province || undefined
                            },
                            features_used: features,
                            graph_mode: (isPlotLockedByTier || !tierFeatureGates.allow_plot) ? "off" : graphMode,
                            attach_to_step_id: attachToStepId,
                            force_validity: mathValidityConfirmed,
                            idempotency_key: idempotencyKey
                        })
                    });
                    break;
                } catch (fetchErr) {
                    lastFetchError = fetchErr;
                    response = null;
                }
            }

            if (!response) throw (lastFetchError instanceof Error ? lastFetchError : new Error("Network error"));
            if (!response.ok) {
                const message = await response.text();
                throw new Error(message || "Solve request failed");
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No reader available");

            const decoder = new TextDecoder();
            let accumulatedBuffer = "";
            let currentEvent = "";
            let shouldTerminateStream = false;
            const streamStartedAt = Date.now();
            const streamIdleTimeoutMs = 30000;
            const streamHardTimeoutMs = 8 * 60 * 1000;
            const streamNoMetaHardTimeoutMs = 90 * 1000;
            let observedAttemptId: string | null = null;

            while (true) {
                let readChunk: ReadableStreamReadResult<Uint8Array>;
                try {
                    readChunk = await Promise.race<ReadableStreamReadResult<Uint8Array>>([
                        reader.read(),
                        new Promise<ReadableStreamReadResult<Uint8Array>>((_, reject) => {
                            setTimeout(() => reject(new Error("__STREAM_IDLE_TIMEOUT__")), streamIdleTimeoutMs);
                        }),
                    ]);
                } catch (readErr) {
                    const message = readErr instanceof Error ? readErr.message : "";
                    if (message === "__STREAM_IDLE_TIMEOUT__" && !shouldTerminateStream) {
                        if (Date.now() - streamStartedAt > streamHardTimeoutMs) {
                            throw new Error("Solve timed out while waiting for completion.");
                        }
                        const fallbackAttemptId =
                            observedAttemptId ||
                            activeAttemptId ||
                            (typeof window !== "undefined" ? localStorage.getItem("uask.activeAttemptId") : null);
                        if (fallbackAttemptId) {
                            try {
                                const statusRes = await fetch(`/api/v1/attempt/${fallbackAttemptId}`);
                                if (statusRes.status === 404) {
                                    throw new Error("Solve attempt not found. Please run Solve again.");
                                }
                                if (statusRes.ok) {
                                    const statusData = await statusRes.json();
                                    if (statusData.status === "success") {
                                        localStorage.removeItem("uask.activeAttemptId");
                                        localStorage.removeItem("uask.activeQuery");
                                        clearPersistedSolveOverlayState();
                                        setStreamingActive(false);
                                        markPipelineCompleted();
                                        shouldTerminateStream = true;
                                        await reader.cancel().catch(() => undefined);
                                        const sessionId = normalizeSessionId(statusData.session_id);
                                        if (sessionId) {
                                            setTimeout(() => router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, sessionId)), 200);
                                        }
                                        break;
                                    }
                                    if (statusData.status === "failure") {
                                        throw new Error(statusData.error_message || "Solve failed");
                                    }
                                    if (statusData.status === "ambiguous") {
                                        throw new Error("Clarification is disabled. Please submit one clear question.");
                                    }
                                }
                            } catch (statusErr) {
                                const statusMessage = statusErr instanceof Error ? statusErr.message : "";
                                if (statusMessage && statusMessage !== "Failed to fetch") {
                                    throw statusErr;
                                }
                            }
                        } else if (Date.now() - streamStartedAt > streamNoMetaHardTimeoutMs) {
                            throw new Error("Solve stream disconnected before attempt metadata was received.");
                        }
                        // Keep waiting; transient SSE idle windows are expected.
                        continue;
                    }
                    throw readErr;
                }

                const { done, value } = readChunk;
                if (value) {
                    accumulatedBuffer += decoder.decode(value, { stream: !done });
                }
                if (done) {
                    // Flush any trailing SSE payload that arrived with stream EOF.
                    if (accumulatedBuffer && !accumulatedBuffer.endsWith("\n")) {
                        accumulatedBuffer += "\n";
                    }
                }

                const lines = accumulatedBuffer.split('\n');
                accumulatedBuffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (!trimmedLine) continue;

                    if (trimmedLine.startsWith('event: ')) {
                        currentEvent = trimmedLine.slice(7).trim();
                    } else if (trimmedLine.startsWith('data: ')) {
                        let data: Record<string, unknown>;
                        try {
                            data = JSON.parse(trimmedLine.slice(6)) as Record<string, unknown>;
                        } catch (e) {
                            console.error("Error parsing SSE data", e);
                            continue;
                        }

                        const fallbackEventType = typeof data?.type === "string" ? data.type : "";
                        const eventType = currentEvent || fallbackEventType;
                        if (eventType === "meta") {
                            setStreamingMeta(data as StreamingRuntimeMeta);
                            if (typeof data.attempt_id === "string" && data.attempt_id) {
                                setActiveAttemptId(data.attempt_id);
                                observedAttemptId = data.attempt_id;
                                localStorage.setItem("uask.activeAttemptId", data.attempt_id);
                                localStorage.setItem("uask.activeQuery", textToSolve);
                                hydrateOverlayPersistence({
                                    attemptId: data.attempt_id,
                                    startTimeMs: solveStartedAt,
                                });
                            }
                            const parsedMeta = buildRuntimeMetaFromPayload(data, requestedMode);
                            setStreamingMeta((prev) => ({ ...(prev || {}), ...parsedMeta }));
                            if (parsedMeta.request_id) {
                                hydrateOverlayPersistence({
                                    requestId: parsedMeta.request_id,
                                    startTimeMs: solveStartedAt,
                                });
                            }
                        } else if (eventType === "delta") {
                            setStreamingActive(true);
                            hydrateOverlayPersistence({ streamingActive: true });
                        } else if (eventType === "stage") {
                            const stageName = typeof data?.name === "string" ? data.name : "";
                            setCurrentStage(stageName);
                            const mapped = mapBackendEventToOverlayStage(stageName);
                            if (mapped) {
                                applyPipelineStage(mapped);
                            }
                        } else if (eventType === "telemetry") {
                            setStreamingTelemetry((data?.telemetry as StreamingTelemetry) ?? (data as StreamingTelemetry));
                        } else if (eventType === "done") {
                            const doneOk = Boolean(data.ok);
                            if (doneOk) {
                                setSolveProgress(100);
                                localStorage.removeItem("uask.activeAttemptId");
                                localStorage.removeItem("uask.activeQuery");
                                clearPersistedSolveOverlayState();
                                setStreamingActive(false);
                                markPipelineCompleted();
                                const sessionId = normalizeSessionId(data.session_id);
                                if (sessionId) {
                                    setTimeout(() => router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, sessionId)), 500);
                                } else {
                                    const fallbackAttemptId = observedAttemptId || activeAttemptId;
                                    if (fallbackAttemptId) {
                                        fetch(`/api/v1/attempt/${fallbackAttemptId}`)
                                            .then((r) => (r.ok ? r.json() : null))
                                            .then((statusData) => {
                                                const recoveredSessionId = normalizeSessionId(statusData?.session_id);
                                                if (recoveredSessionId) {
                                                    router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, recoveredSessionId));
                                                }
                                            })
                                            .catch(() => undefined);
                                    } else {
                                        recoverSessionFromHistory()
                                            .then((recoveredSessionId) => {
                                                if (recoveredSessionId) {
                                                    router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, recoveredSessionId));
                                                }
                                            })
                                            .catch(() => undefined);
                                    }
                                }
                            } else {
                                const errorObj = (data.error ?? {}) as Record<string, unknown>;
                                localStorage.removeItem("uask.activeAttemptId");
                                localStorage.removeItem("uask.activeQuery");
                                clearPersistedSolveOverlayState();
                                setStreamingActive(false);
                                if (errorObj.code === "ambiguous_response") {
                                    throw new Error("Clarification is disabled. Please submit one clear question.");
                                }
                                applyPipelineStage(currentStageKey, true);
                                if (typeof errorObj.request_id === "string" && errorObj.request_id) {
                                    setStreamingMeta((prev) => ({ ...(prev || {}), request_id: errorObj.request_id as string }));
                                }
                                const details = errorObj.details as Record<string, unknown> | undefined;
                                const providerMessage =
                                    (typeof details?.message === "string" && details.message) ||
                                    (typeof (details?.provider_details as Record<string, unknown> | undefined)?.message === "string" &&
                                        ((details?.provider_details as Record<string, unknown>).message as string)) ||
                                    "";
                                const requestId = typeof errorObj.request_id === "string" ? errorObj.request_id : undefined;
                                const fullMessage = [
                                    (typeof errorObj.message === "string" && errorObj.message) || "Solve failed",
                                    providerMessage ? `provider: ${providerMessage}` : "",
                                    requestId ? `request_id: ${requestId}` : "",
                                ]
                                    .filter(Boolean)
                                    .join(" | ");
                                setLastSolveError({
                                    code: typeof errorObj.code === "string" ? errorObj.code : undefined,
                                    message: typeof errorObj.message === "string" ? errorObj.message : "Solve failed",
                                    request_id: requestId,
                                    details,
                                });
                                throw new Error(fullMessage);
                            }
                            shouldTerminateStream = true;
                            await reader.cancel().catch(() => undefined);
                            break;
                        }
                    }
                }

                if (shouldTerminateStream) break;
                if (done) break;
            }

            // If stream closed without an explicit `done` event, recover from attempt status.
            if (!shouldTerminateStream) {
                const fallbackAttemptId =
                    observedAttemptId ||
                    activeAttemptId ||
                    (typeof window !== "undefined" ? localStorage.getItem("uask.activeAttemptId") : null);
                if (fallbackAttemptId) {
                    const statusRes = await fetch(`/api/v1/attempt/${fallbackAttemptId}`);
                    if (statusRes.ok) {
                        const statusData = await statusRes.json();
                        if (statusData.status === "success") {
                            localStorage.removeItem("uask.activeAttemptId");
                            localStorage.removeItem("uask.activeQuery");
                            clearPersistedSolveOverlayState();
                            setStreamingActive(false);
                            markPipelineCompleted();
                            const sessionId = normalizeSessionId(statusData.session_id);
                            if (sessionId) {
                                setTimeout(() => router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, sessionId)), 200);
                            } else {
                                const recoveredSessionId = await recoverSessionFromHistory();
                                if (recoveredSessionId) {
                                    setTimeout(() => router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, recoveredSessionId)), 200);
                                }
                            }
                            shouldTerminateStream = true;
                        } else if (statusData.status === "failure") {
                            throw new Error(statusData.error_message || "Solve failed");
                        } else if (statusData.status === "ambiguous") {
                            throw new Error("Clarification is disabled. Please submit one clear question.");
                        }
                    }
                } else {
                    const recoveredSessionId = await recoverSessionFromHistory();
                    if (recoveredSessionId) {
                        setTimeout(() => router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, recoveredSessionId)), 200);
                        shouldTerminateStream = true;
                    }
                }
            }
        } catch (err) {
            console.error("[SOLVER_STREAM] Error:", err);
            clearPersistedSolveOverlayState();
            setStreamingActive(false);
            pushToast({
                type: "error",
                title: "Solve failed",
                message: (err as Error).message || "Failed to generate solution.",
            });
        } finally {
            setStreamingActive(false);
            setIsSolving(false);
            setSolveStartTime(null);
        }
    };

    const handleClarify = async () => {
        if (!activeAttemptId || !clarificationResponse.trim() || isSolving) return;

        const clarifyStartedAt = Date.now();
        setIsSolving(true);
        setSolveStartTime(clarifyStartedAt);
        setCurrentStage("Calling AI Core");
        setStreamingActive(false);
        applyPipelineStage("calling_ai_core");
        hydrateOverlayPersistence({
            attemptId: activeAttemptId,
            startTimeMs: clarifyStartedAt,
            currentStage: "calling_ai_core",
            streamingActive: false,
        });

        try {
            const userId = localStorage.getItem("user_id") || "1";
            const res = await fetch(`/api/v1/solve/clarify`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    attempt_id: activeAttemptId,
                    user_id: userId,
                    user_response: clarificationResponse
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Clarification failed");
            }

            const data = await res.json();
            const clarifiedSessionId = normalizeSessionId(data.session_id);
            if (data.status === "success" && clarifiedSessionId) {
                setSolveProgress(100);
                localStorage.removeItem("uask.activeAttemptId");
                localStorage.removeItem("uask.activeQuery");
                clearPersistedSolveOverlayState();
                setTimeout(() => router.push(resolveSessionRouteByTier(effectiveSolveTierRef.current, clarifiedSessionId)), 500);
            } else if (data.status === "ambiguous") {
                setClarificationHistory(prev => [...prev, clarificationResponse]);
                setClarificationMessage(data.clarifier_question || "Still ambiguous. Please provide more detail.");
                setClarificationResponse("");
                applyPipelineStage("plotting_coordinates");
            } else {
                localStorage.removeItem("uask.activeAttemptId");
                localStorage.removeItem("uask.activeQuery");
                clearPersistedSolveOverlayState();
                throw new Error(data.error || "Ambiguity resolution failed.");
            }
        } catch (err) {
            console.error("[CLARIFY] Error:", err);
            clearPersistedSolveOverlayState();
            pushToast({
                type: "error",
                title: "Clarification failed",
                message: (err as Error).message || "Failed to clarify.",
            });
        } finally {
            setStreamingActive(false);
            setIsSolving(false);
            setSolveStartTime(null);
        }
    };
    useEffect(() => {
        if (!isSolving || !solveStartTime) {
            setSolveProgress(0);
            return;
        }

        const tick = setInterval(() => {
            const elapsed = Date.now() - solveStartTime;

            // Artificial progress bar logic adjusted for streaming
            if (elapsed < 15000) {
                const p = Math.min(95, 5 + Math.floor(elapsed / 200) * 1.5);
                setSolveProgress(p);
            } else {
                setSolveProgress(98);
            }
        }, 250); // 250ms tick as requested (Part F1)

        return () => clearInterval(tick);
    }, [isSolving, solveStartTime]);

    const [elapsedNow, setElapsedNow] = useState<number>(Date.now());
    useEffect(() => {
        if (!isSolving || !solveStartTime) return;
        setElapsedNow(Date.now());
        const timer = window.setInterval(() => setElapsedNow(Date.now()), 100);
        return () => window.clearInterval(timer);
    }, [isSolving, solveStartTime]);

    const elapsedMs = solveStartTime ? Math.max(0, elapsedNow - solveStartTime) : 0;
    const formatElapsed = (ms: number) => {
        const totalTenths = Math.floor(ms / 100);
        const minutes = Math.floor(totalTenths / 600);
        const seconds = Math.floor((totalTenths % 600) / 10);
        const tenths = totalTenths % 10;
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths}`;
    };

    // pipelineStages is now a state variable defined at the top


    return (
        <div dir={uiDirection} className="solve-ui bg-background-light dark:bg-background-dark min-h-screen text-slate-900 dark:text-slate-100 font-display transition-colors duration-200">
            <DashboardNavBar />

            <main className="max-w-6xl mx-auto px-4 py-5 md:py-7">
                {/* Hand-Drawn Title Section */}
                <header className="mb-7 text-center">
                    <h2 className="sketch-title mb-1 flex items-center justify-center gap-2">
                        New Solve
                        <span className="text-xs font-black px-2 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-lg border border-blue-200 dark:border-blue-800 rotate-3 tracking-tighter">
                            uask AI v1.0
                        </span>
                    </h2>
                    <p className="sketch-subtitle mx-auto max-w-2xl px-4">
                        Select your preferred input method and define the context for the best tutor results.
                    </p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    {/* Main Interaction Area */}
                    <div className="lg:col-span-8 space-y-6">

                        {/* Tier-Aware Controls Section */}
                        <div className={`${tierSectionColor} dark:bg-slate-900 rounded-3xl shadow-lg border border-slate-200 dark:border-slate-800 p-5 md:p-6 relative overflow-hidden transition-colors duration-1000`}>
                            <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-cyan-50/70 via-white/0 to-blue-50/60 dark:from-cyan-900/10 dark:via-transparent dark:to-blue-900/10" />
                            <div className="absolute right-4 top-4 z-10">
                                <p className="inline-flex items-center gap-2 rounded-lg border border-amber-200 dark:border-amber-700/40 bg-amber-50 dark:bg-amber-900/20 px-3 py-1.5 text-xs text-amber-800 dark:text-amber-200">
                                    <span className="material-symbols-outlined text-[14px]">rule</span>
                                    Max Tasks per Question: <span className="font-black">{MAX_TASKS_PER_QUESTION}</span>
                                </p>
                            </div>
                            <div className="relative grid grid-cols-1 md:grid-cols-12 gap-4 md:gap-6 items-stretch">
                                <div className="md:col-span-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white/85 dark:bg-slate-950/60 p-4">
                                    <p className="text-[10px] font-black uppercase tracking-[0.25em] text-slate-500">Goal</p>
                                    <button className="mt-3 w-full px-4 py-3 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-white font-black tracking-tight shadow-md shadow-blue-500/20">
                                        <span className="material-symbols-outlined text-[20px]">bolt</span>
                                        <span className="text-base">Solve</span>
                                    </button>
                                    <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Fast math assistant mode with credit-aware answers.</p>
                                </div>

                                <div className="md:col-span-9 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white/85 dark:bg-slate-950/60 p-4 md:p-5">
                                    <div className="mb-3 flex flex-wrap items-center gap-2">
                                        <span className="inline-flex items-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-600 dark:text-slate-200">
                                            Tier
                                        </span>
                                        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ${effectiveSolveTier === "FINAL" ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200"}`}>
                                            {effectiveSolveTier === "FINAL" ? "Final Answer" : effectiveSolveTier === "STANDARD" ? "Detailed Steps" : "Steps & Plot"}
                                        </span>
                                    </div>

                                    {readyWallet && estimate && (
                                        <div className="space-y-2">
                                            <CostPreview
                                                perQuestionCost={estimate.per_question_credits}
                                                questionCount={estimatedQuestionCount}
                                                breakdown={estimateBreakdown}
                                                creditsRemaining={readyWallet.computed_balance}
                                            />
                                        </div>
                                    )}

                                    <SegmentedControl
                                        options={[
                                            {
                                                value: "FINAL",
                                                label: "Final Answer",
                                                icon: "bolt",
                                                disabled: !canAffordTier("FINAL") || explicitTaskCountCapped > SHORT_FINAL_MAX_TASKS,
                                                tooltip: explicitTaskCountCapped > SHORT_FINAL_MAX_TASKS
                                                    ? `More than ${SHORT_FINAL_MAX_TASKS} tasks requires Standard tier.`
                                                    : (!canAffordTier("FINAL") ? `Need ${Number(tierEstimateByTier.FINAL || 0).toFixed(2)} credits.` : undefined),
                                            },
                                            {
                                                value: "SHORT_STEPS",
                                                label: "Steps & Plot",
                                                icon: "bolt",
                                                disabled: !canAffordTier("SHORT_STEPS") || explicitTaskCountCapped > SHORT_FINAL_MAX_TASKS,
                                                tooltip: explicitTaskCountCapped > SHORT_FINAL_MAX_TASKS
                                                    ? `More than ${SHORT_FINAL_MAX_TASKS} tasks requires Standard tier.`
                                                    : (!canAffordTier("SHORT_STEPS") ? `Need ${Number(tierEstimateByTier.SHORT_STEPS || 0).toFixed(2)} credits.` : undefined),
                                            },
                                            {
                                                value: "STANDARD",
                                                label: "Detailed",
                                                icon: "tune",
                                                disabled: !canAffordTier("STANDARD"),
                                                tooltip: !canAffordTier("STANDARD") ? `Need ${Number(tierEstimateByTier.STANDARD || 0).toFixed(2)} credits.` : undefined,
                                            },
                                        ]}
                                        value={selectedSolveTier}
                                        onChange={(v) => {
                                            if (v === "SHORT_STEPS" || v === "FINAL" || v === "STANDARD") {
                                                if (explicitTaskCountCapped > SHORT_FINAL_MAX_TASKS && (v === "SHORT_STEPS" || v === "FINAL")) {
                                                    setSelectedSolveTier("STANDARD");
                                                    if (typeof window !== "undefined") {
                                                        localStorage.setItem("uask.solveTier", "STANDARD");
                                                    }
                                                    return;
                                                }
                                                setSelectedSolveTier(v as SolveTier);
                                                if (typeof window !== "undefined") {
                                                    localStorage.setItem("uask.solveTier", v);
                                                }
                                            }
                                        }}
                                        size="sm"
                                        className="solve-segmented mt-3"
                                    />
                                    {explicitTaskCountRaw > 0 && (
                                        <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">
                                            Detected tasks: <span className="font-semibold">{explicitTaskCountRaw}</span> (max {MAX_TASKS_PER_QUESTION})
                                        </p>
                                    )}
                                </div>
                            </div>
                        </div>





                        {/* Plot Mode Section - Global with Larger Font & Random Light BG */}
                        <div className={`flex flex-col gap-3 px-6 py-4 ${plotModeColor} dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 transition-colors duration-1000`}>
                            <div className="flex items-center gap-4">
                                <span className="material-symbols-outlined text-primary text-2xl">area_chart</span>
                                <span className="text-lg font-bold text-slate-800 dark:text-slate-100 whitespace-nowrap">
                                    Plot Mode
                                </span>

                                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mx-4 flex-1 text-center truncate">
                                    {graphMode === 'off' && "No plots will be generated"}
                                    {graphMode === 'auto' && "AI will generate plots when helpful"}
                                    {graphMode === 'on' && "Force plot generation when possible"}
                                </p>

                                <div className="flex bg-white/50 dark:bg-slate-800 rounded-lg p-1.5 shrink-0 shadow-sm border border-slate-200/50 dark:border-slate-700">
                                    {(['off', 'auto', 'on'] as const).map((mode) => (
                                        <button
                                            key={mode}
                                            type="button"
                                            onClick={() => {
                                                if ((isPlotLockedByTier || !tierFeatureGates.allow_plot) && mode !== "off") return;
                                                setGraphMode(mode);
                                            }}
                                            disabled={(isPlotLockedByTier || !tierFeatureGates.allow_plot) && mode !== "off"}
                                            className={`px-4 py-1.5 text-sm font-bold rounded-md transition-all ${graphMode === mode
                                                ? "bg-white dark:bg-slate-600 text-primary shadow-md scale-105"
                                                : (isPlotLockedByTier || !tierFeatureGates.allow_plot) && mode !== "off"
                                                    ? "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                                                    : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-700/50"
                                                }`}
                                        >
                                            {mode.charAt(0).toUpperCase() + mode.slice(1)}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            {(isPlotLockedByTier || !tierFeatureGates.allow_plot) && (
                                <p className="text-xs text-slate-500 dark:text-slate-400 text-right">
                                    Plot mode is forced OFF for Final Answer tier and disabled when feature gates block plots.
                                </p>
                            )}
                        </div>

                        {/* Input Mode Tabs */}
                        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl shadow-black/5 border border-slate-200 dark:border-slate-800 transition-colors">
                            <div className="flex p-4 gap-4 justify-center border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/20">
                                <button
                                    onClick={() => setActiveTab('text')}
                                    className={`solve-tab solve-tab--text ${activeTab === 'text' ? 'solve-tab--active' : ''}`}
                                >
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-1 solve-tab-icon">
                                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" style={{ strokeDasharray: '40, 4' }} />
                                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                                    </svg>
                                    <span className="solve-tab-label">Text</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('snap')}
                                    className={`solve-tab solve-tab--snap ${activeTab === 'snap' ? 'solve-tab--active dashed-sketch-border' : ''}`}
                                >
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-1 solve-tab-icon">
                                        <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" style={{ strokeDasharray: '50, 5' }} />
                                        <circle cx="12" cy="13" r="4" strokeDasharray="2,2" />
                                    </svg>
                                    <span className="solve-tab-label">Snap & Solve</span>
                                </button>
                                <button
                                    onClick={() => setActiveTab('voice')}
                                    className={`solve-tab solve-tab--voice ${activeTab === 'voice' ? 'solve-tab--active circle-sketch' : ''}`}
                                >
                                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mb-1 solve-tab-icon">
                                        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" style={{ strokeDasharray: '30, 3' }} />
                                        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                                        <line x1="12" y1="19" x2="12" y2="22" />
                                        <line x1="8" y1="22" x2="16" y2="22" />
                                    </svg>
                                    <span className="solve-tab-label">Voice</span>
                                </button>
                            </div>

                            {/* Tab Content */}
                            <div className="p-6">
                                {isClarifying && (
                                    <div className="mb-6 animate-in fade-in slide-in-from-top-4 duration-500">
                                        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-6 shadow-sm">
                                            <div className="flex items-start gap-4 mb-4">
                                                <div className="mt-1 bg-amber-100 dark:bg-amber-900/40 p-2 rounded-lg">
                                                    <span className="material-symbols-outlined text-amber-600 dark:text-amber-400">help_center</span>
                                                </div>
                                                <div className="flex-1">
                                                    <h3 className="text-lg font-bold text-amber-900 dark:text-amber-100 mb-1">Clarification Needed</h3>
                                                    <p className="text-amber-800/80 dark:text-amber-200/80 text-sm leading-relaxed">
                                                        {clarificationMessage}
                                                    </p>
                                                </div>
                                            </div>

                                            {clarificationHistory.length > 0 && (
                                                <div className="mb-4 pl-12 space-y-2 opacity-60">
                                                    {clarificationHistory.map((hist, i) => (
                                                        <div key={i} className="text-xs italic border-l-2 border-amber-200 dark:border-amber-800 pl-3 py-1">
                                                            &ldquo;{hist}&rdquo;
                                                        </div>
                                                    ))}
                                                </div>
                                            )}

                                            <div className="pl-12">
                                                <textarea
                                                    value={clarificationResponse}
                                                    onChange={(e) => setClarificationResponse(e.target.value)}
                                                    placeholder="Provide more detail here..."
                                                    className="w-full bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-800 rounded-lg p-3 text-slate-700 dark:text-slate-200 outline-none focus:ring-2 focus:ring-amber-500/20 transition-all resize-none min-h-[100px]"
                                                />
                                                <div className="mt-4 flex gap-3">
                                                    <button
                                                        onClick={handleClarify}
                                                        disabled={isSolving || !clarificationResponse.trim()}
                                                        className="bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-amber-600/20 transition-all flex items-center gap-2"
                                                    >
                                                        {isSolving ? "Submitting..." : "Send Clarification"}
                                                        <span className="material-symbols-outlined text-sm">send</span>
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            setIsClarifying(false);
                                                            localStorage.removeItem("uask.activeAttemptId");
                                                            localStorage.removeItem("uask.activeQuery");
                                                            setActiveAttemptId(null);
                                                        }}
                                                        className="text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/40 px-4 py-2 rounded-lg font-medium transition-colors text-sm"
                                                    >
                                                        Cancel
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}


                                {activeTab === 'snap' && (
                                    <div className="space-y-3">
                                        {useSnapSolveUploadPanelV2 ? (
                                            <SnapSolveInputPanel
                                                tier={selectedSolveTier}
                                                requestedMode={(selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL") ? "minimal" : "detailed"}
                                                onResolveText={(text, featureOverrides) => {
                                                    setQuery(text);
                                                    setMathValidityConfirmed(false);
                                                    if (mathInputRef.current) {
                                                        mathInputRef.current.setValue(text);
                                                    }
                                                    return handleSolve(text, {
                                                        ocr_used: true,
                                                        ocr_engine: "openai",
                                                        ...(featureOverrides || {}),
                                                    });
                                                }}
                                            />
                                        ) : (
                                            <SnapSolveV2
                                                onUseText={(text) => {
                                                    setQuery(text);
                                                    setMathValidityConfirmed(false);
                                                    setActiveTab("text");
                                                }}
                                                onSolveText={(text) => {
                                                    setQuery(text);
                                                    setMathValidityConfirmed(false);
                                                    if (mathInputRef.current) {
                                                        mathInputRef.current.setValue(text);
                                                    }
                                                    handleSolve(text);
                                                }}
                                                requestedMode={(selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL") ? "minimal" : "detailed"}
                                            />
                                        )}
                                    </div>
                                )}

                                {activeTab === 'text' && (
                                    <div className="flex flex-col gap-6 relative">
                                        {/* Input Mode Selector (Expression / Word Problem / Graphing) */}


                                        {/* Include Graph Toggle */}


                                        {/* Math Symbol Mode Bar */}
                                        <div className="flex items-center gap-2">
                                            <div className="flex-1 flex gap-2 overflow-x-auto pb-2 scrollbar-hide items-center">
                                                {MODES.slice(0, 5).map(mode => (
                                                    <button
                                                        key={mode.id}
                                                        onClick={() => {
                                                            setActiveMode(mode.id === activeMode ? null : mode.id);
                                                            setIsSeeAllOpen(false);
                                                        }}
                                                        className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-all border ${activeMode === mode.id
                                                            ? 'bg-primary text-white border-primary shadow-lg shadow-primary/25'
                                                            : 'bg-white dark:bg-slate-900 text-slate-500 border-slate-200 dark:border-slate-700 hover:border-primary/50'
                                                            }`}
                                                    >
                                                        {mode.label}
                                                    </button>
                                                ))}
                                            </div>

                                            {/* See All Dropdown */}
                                            <div className="relative pb-2">
                                                <button
                                                    onClick={() => setIsSeeAllOpen(!isSeeAllOpen)}
                                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold whitespace-nowrap transition-all border ${isSeeAllOpen || MODES.slice(5).some(m => m.id === activeMode)
                                                        ? 'bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-600 shadow-sm'
                                                        : 'bg-white dark:bg-slate-900 text-slate-500 border-slate-200 dark:border-slate-700 hover:border-primary/50'
                                                        }`}
                                                >
                                                    <span>See All</span>
                                                    <span className={`material-symbols-outlined text-lg transition-transform ${isSeeAllOpen ? 'rotate-180' : ''}`}>expand_more</span>
                                                </button>

                                                {isSeeAllOpen && (
                                                    <div className="absolute top-full right-0 mt-2 w-56 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.2)] z-[100] overflow-hidden animate-in fade-in zoom-in-95 duration-100 origin-top-right">
                                                        <div className="max-h-80 overflow-y-auto custom-scrollbar">
                                                            {MODES.slice(5).map((mode) => (
                                                                <button
                                                                    key={mode.id}
                                                                    onClick={() => {
                                                                        setActiveMode(mode.id);
                                                                        setIsSeeAllOpen(false);
                                                                    }}
                                                                    className={`w-full py-4 text-center transition-colors border-b border-slate-50 dark:border-slate-800/50 last:border-0 font-bold text-slate-700 dark:text-slate-200 hover:bg-primary/5 hover:text-primary dark:hover:bg-primary/10 ${activeMode === mode.id ? 'bg-primary/5 text-primary' : ''}`}
                                                                >
                                                                    {mode.label.toLowerCase()}
                                                                </button>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        <div className="relative group z-10">
                                            <div className={`bg-white dark:bg-slate-900 border rounded-xl transition-all shadow-sm flex flex-col min-h-[190px] ${inputError
                                                ? 'border-red-500 ring-1 ring-red-500 bg-red-50/10'
                                                : activeMode
                                                    ? 'border-primary ring-1 ring-primary'
                                                    : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                                                }`}>

                                                {/* Suggestions Dropdown (Combobox) */}
                                                {activeMode && (
                                                    <div className="absolute top-full left-0 right-0 mt-2 bg-amber-50 dark:bg-slate-900 border border-amber-100 dark:border-slate-800 rounded-xl shadow-xl overflow-hidden z-50">
                                                        <div className="bg-amber-100/40 dark:bg-slate-800/50 px-4 py-2 border-b border-amber-100 dark:border-slate-800 text-xs font-bold text-slate-500 uppercase tracking-widest flex justify-between">
                                                            <span>{MODES.find(m => m.id === activeMode)?.label} Templates</span>
                                                            <span className="text-[10px]">Select to insert</span>
                                                        </div>
                                                        <div className="max-h-64 overflow-y-auto p-1">
                                                            {MODES.find(m => m.id === activeMode)?.suggestions.map((suggestion, idx) => (
                                                                <button
                                                                    key={idx}
                                                                    onClick={() => handleSuggestionClick(suggestion)}
                                                                    className="w-full text-left px-4 py-3 rounded-lg hover:bg-amber-100/60 hover:text-primary dark:hover:bg-primary/10 transition-colors flex items-center gap-3 group/item"
                                                                >
                                                                    <span className="w-8 h-8 rounded bg-amber-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 group-hover/item:text-primary transition-colors text-xs font-mono">
                                                                        TeX
                                                                    </span>
                                                                    <div className="flex-1 font-medium text-slate-700 dark:text-slate-200">
                                                                        <MathRendererMJX content={`\\(${suggestion.title}\\)`} inline className="pointer-events-none" />
                                                                    </div>
                                                                    <span className="material-symbols-outlined text-slate-300 group-hover/item:text-primary text-sm opacity-0 group-hover/item:opacity-100 transition-all">
                                                                        arrow_forward
                                                                    </span>
                                                                </button>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                {mathModeEnabled ? (
                                                    <MathInput
                                                        ref={mathInputRef}
                                                        value={query}
                                                        onChange={(value) => {
                                                            // Enforce character limit
                                                            if (textInputMaxChars <= 0 || value.length <= textInputMaxChars) {
                                                                setQuery(value);
                                                                setConfirmedBatchQuestions([]);
                                                                setMultiQuestionConfirmed(false);
                                                                setMathValidityConfirmed(false);
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        maxLength={textInputMaxChars || undefined}
                                                        onPaste={(pastedText) => {
                                                            const effectiveText =
                                                                textInputMaxChars > 0 && pastedText.length > textInputMaxChars
                                                                    ? pastedText.slice(0, textInputMaxChars)
                                                                    : pastedText;
                                                            if (textInputMaxChars > 0 && pastedText.length > textInputMaxChars) {
                                                                setInputError(`Pasted text was truncated to ${textInputMaxChars} characters.`);
                                                            }
                                                            // Preserve raw prose/math mixed text by switching to free text mode.
                                                            setMathModeEnabled(false);
                                                            setQuery(effectiveText);
                                                            setConfirmedBatchQuestions([]);
                                                            setMultiQuestionConfirmed(false);
                                                            setMathValidityConfirmed(false);
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            const autoSplits = autoSplitQuestions(pastedText);
                                                            if (checkResult.isMultiple || autoSplits.length > 1) {
                                                                setSuggestedSplits(autoSplits);
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        className="flex-1 p-2 min-h-[180px]"
                                                    />
                                                ) : (
                                                    <textarea
                                                        data-testid="solve-query-textarea"
                                                        value={query}
                                                        onChange={(event) => {
                                                            const value = event.target.value;
                                                            // Enforce character limit
                                                            if (textInputMaxChars <= 0 || value.length <= textInputMaxChars) {
                                                                setQuery(value);
                                                                setConfirmedBatchQuestions([]);
                                                                setMultiQuestionConfirmed(false);
                                                                if (inputError) setInputError(null);
                                                            }
                                                        }}
                                                        onPaste={(event) => {
                                                            const pastedText = event.clipboardData.getData('text');
                                                            if (textInputMaxChars > 0 && pastedText.length > textInputMaxChars) {
                                                                event.preventDefault();
                                                                const truncated = pastedText.slice(0, textInputMaxChars);
                                                                setQuery(truncated);
                                                                setInputError(`Pasted text was truncated to ${textInputMaxChars} characters.`);
                                                            }
                                                            setConfirmedBatchQuestions([]);
                                                            setMultiQuestionConfirmed(false);
                                                            setMathValidityConfirmed(false);
                                                            // Check for multi-question on paste
                                                            const checkResult = detectMultiQuestion(pastedText);
                                                            const autoSplits = autoSplitQuestions(pastedText);
                                                            if (checkResult.isMultiple || autoSplits.length > 1) {
                                                                setSuggestedSplits(autoSplits);
                                                                setTimeout(() => setShowSplitModal(true), 500);
                                                            }
                                                        }}
                                                        maxLength={textInputMaxChars || undefined}
                                                        className={`flex-1 p-4 ${freeTypeColor} dark:bg-transparent outline-none text-slate-700 dark:text-slate-200 text-lg leading-relaxed resize-none min-h-[180px] transition-colors duration-500 rounded-t-xl`}
                                                        style={{
                                                            whiteSpace: 'pre-wrap',
                                                            overflowWrap: 'break-word',
                                                            wordBreak: 'normal',
                                                            hyphens: 'auto',
                                                        }}
                                                        placeholder="Type your question..."
                                                    />
                                                )}

                                                {/* Token/Character Status */}
                                                <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-800">
                                                    <InputStatus
                                                        text={query}
                                                        tokenEstimate={tokenEstimate}
                                                        maxInputTokens={textInputMaxTokens}
                                                        maxInputChars={textInputMaxChars}
                                                        multiQuestionResult={multiQuestionResult}
                                                        isConfirmed={multiQuestionConfirmed}
                                                        onSplitClick={() => {
                                                            setSuggestedSplits(autoSplitQuestions(query));
                                                            setShowSplitModal(true);
                                                        }}
                                                    />
                                                </div>

                                                {/* Action Bar inside Input */}
                                                <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 rounded-b-xl">
                                                    <div className="flex items-center gap-3 text-xs text-slate-400">
                                                        <span className="material-symbols-outlined text-sm">keyboard</span>
                                                        <span>{mathModeEnabled ? "Math Mode Active" : "Free Type Mode"}</span>
                                                        <button
                                                            type="button"
                                                            onClick={() => setMathModeEnabled(enabled => !enabled)}
                                                            data-testid="math-mode-toggle"
                                                            className={`relative w-10 h-5 rounded-full transition-colors ${mathModeEnabled ? "bg-primary" : "bg-slate-300 dark:bg-slate-700"}`}
                                                        >
                                                            <div className={`absolute top-1 left-1 size-3 bg-white rounded-full transition-transform ${mathModeEnabled ? "translate-x-5" : ""}`}></div>
                                                        </button>
                                                    </div>
                                                    <div className="flex flex-1 flex-col items-center">
                                                        <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                                            Using YouAsk AI
                                                        </span>
                                                        {isSolving && (
                                                            <div className="mt-1 h-1 w-24 rounded-full bg-emerald-100 dark:bg-emerald-900/40 overflow-hidden">
                                                                <div className="h-full w-full bg-emerald-500 animate-pulse"></div>
                                                            </div>
                                                        )}
                                                    </div>
                                                    {inputError && (
                                                        <div className="flex flex-col gap-1 mt-1">
                                                            <span className="text-xs text-red-500 font-medium">{inputError}</span>
                                                            {(inputError === INPUT_ERROR_BLOCKED || inputError === INPUT_ERROR_NOT_MATH) && (
                                                                <button
                                                                    onClick={() => {
                                                                        setMathValidityConfirmed(true);
                                                                        setInputError(null);
                                                                    }}
                                                                    className="text-xs font-bold text-primary hover:underline self-start flex items-center gap-1"
                                                                >
                                                                    <span className="material-symbols-outlined text-[14px]">check_circle</span>
                                                                    This is a valid math question
                                                                </button>
                                                            )}
                                                        </div>
                                                    )}
                                                    {mathValidityConfirmed && !inputError && (
                                                        <div className="flex items-center gap-1.5 mt-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium animate-in fade-in duration-300">
                                                            <span className="material-symbols-outlined text-[14px]">verified_user</span>
                                                            Validity confirmed
                                                        </div>
                                                    )}
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={handleClear}
                                                            className="flex items-center gap-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 px-4 py-2 rounded-lg font-medium transition-colors text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                                                        >
                                                            <span className="material-symbols-outlined text-sm">backspace</span>
                                                            Clear
                                                        </button>
                                                        <button
                                                            onClick={() => handleSolve()}
                                                            data-testid="solve-submit-button"
                                                            disabled={isSolving || isInputTooShort(query) || !!tokenBlockReason || !!taskBlockReason || isBlockingInputError(inputError) || !hasEnoughCredits}
                                                            title={taskBlockReason || tokenBlockReason || creditBlockReason || undefined}
                                                            className="relative flex items-center gap-2 bg-primary hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-bold transition-all shadow-lg shadow-primary/25 text-sm overflow-hidden"
                                                        >
                                                            {isSolving && (
                                                                <div className="absolute inset-0">
                                                                    <div className="h-full bg-white/20 transition-all" style={{ width: `${solveProgress}%` }}></div>
                                                                </div>
                                                            )}
                                                            {isSolving ? `Solving... ${solveProgress}%` : 'Solve'}
                                                            <span className="material-symbols-outlined text-sm">auto_awesome</span>
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Live Math Preview */}
                                        <div className="mt-6">
                                            <LiveMathPreview content={query} />
                                        </div>
                                    </div>
                                )}
                                {(!isClarifying && activeTab === 'voice') && (
                                    <div className="flex flex-col gap-6 items-center justify-center min-h-[400px]">
                                        {voiceStage === 'idle' && (
                                            <div className="text-center space-y-6">
                                                <div
                                                    onClick={startRecording}
                                                    className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center text-primary cursor-pointer hover:scale-110 transition-all hover:bg-primary/20 group mx-auto"
                                                >
                                                    <span className="material-symbols-outlined text-4xl group-hover:animate-pulse">mic</span>
                                                </div>
                                                <div>
                                                    <h3 className="text-lg font-bold">Tap to Start</h3>
                                                    <p className="text-sm text-slate-500">I&apos;ll transcribe your math speech into LaTeX.</p>
                                                    <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mt-2">
                                                        Using YouAsk voice AI to script
                                                    </p>
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'recording' && (
                                            <div className="h-64 flex flex-col items-center justify-center space-y-8 animate-in fade-in duration-300">
                                                <div className="flex gap-1.5 h-16 items-center">
                                                    {[...Array(20)].map((_, i) => (
                                                        <div
                                                            key={i}
                                                            className="w-1 bg-primary rounded-full animate-voice-bar"
                                                            style={{
                                                                height: `${20 + Math.random() * 80}%`,
                                                                animationDelay: `${i * 0.05}s`
                                                            }}
                                                        />
                                                    ))}
                                                </div>
                                                <div className="text-center space-y-4">
                                                    <div className="text-4xl font-mono font-bold text-slate-800 dark:text-slate-100">
                                                        00:{recordingTime.toString().padStart(2, '0')}
                                                    </div>
                                                    <button
                                                        onClick={stopRecording}
                                                        className="bg-red-500 hover:bg-red-600 text-white px-8 py-3 rounded-full font-bold flex items-center gap-2 transition-all hover:scale-105 active:scale-95 shadow-lg shadow-red-500/20"
                                                    >
                                                        <span className="material-symbols-outlined">stop_circle</span>
                                                        Stop Recording
                                                    </button>
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'processing' && (
                                            <div className="h-64 flex flex-col items-center justify-center space-y-6 animate-in fade-in duration-300">
                                                <div className="relative size-20">
                                                    <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                                                    <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                                                    <div className="absolute inset-0 flex items-center justify-center">
                                                        <span className="material-symbols-outlined text-primary text-3xl animate-pulse">auto_awesome</span>
                                                    </div>
                                                </div>
                                                <div className="text-center">
                                                    <h3 className="text-xl font-bold dark:text-white">AI Transcribing...</h3>
                                                    <p className="text-sm text-slate-500">Normalizing your math for the tutor.</p>
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'review' && (
                                            <div className="space-y-8 animate-in slide-in-from-bottom-4 duration-500">
                                                {/* Ambiguity Clarifier Integration */}
                                                {voiceArtifact?.clarifier_question && (
                                                    <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-900/30 rounded-2xl p-6 space-y-4 shadow-sm">
                                                        <div className="flex items-start gap-4 text-amber-800 dark:text-amber-200">
                                                            <div className="size-10 bg-amber-100 dark:bg-amber-900/50 rounded-full flex items-center justify-center shrink-0">
                                                                <span className="material-symbols-outlined">help_center</span>
                                                            </div>
                                                            <div className="space-y-1">
                                                                <p className="text-[10px] font-black uppercase tracking-tight opacity-60">Help us clarify your intent</p>
                                                                <p className="text-lg font-bold leading-tight">{voiceArtifact.clarifier_question.question}</p>
                                                            </div>
                                                        </div>
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 ml-14">
                                                            {voiceArtifact.clarifier_question.options.map((opt: ClarifierOption, idx: number) => {
                                                                const isSelected = query === opt.value;
                                                                return (
                                                                    <button
                                                                        key={idx}
                                                                        onClick={() => {
                                                                            setQuery(opt.value);
                                                                            if (mathInputRef.current) mathInputRef.current.setValue(opt.value);
                                                                        }}
                                                                        className={`px-6 py-4 rounded-xl border-2 font-bold text-sm transition-all flex flex-col items-center justify-center gap-2 ${isSelected
                                                                            ? 'bg-amber-100 dark:bg-amber-900/30 border-amber-400 text-amber-950 dark:text-amber-50 shadow-inner'
                                                                            : 'bg-white dark:bg-slate-900 border-amber-200 dark:border-amber-800/50 text-amber-700 dark:text-amber-300 hover:border-amber-400'
                                                                            }`}
                                                                    >
                                                                        <span className="text-base">
                                                                            <MathRenderer content={opt.label} mode="inline" />
                                                                        </span>
                                                                        <span className="text-[9px] uppercase tracking-widest opacity-60">
                                                                            {isSelected ? 'Selected' : 'Use this interpretation'}
                                                                        </span>
                                                                    </button>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}

                                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-4">
                                                    {/* Editable Transcript Pane */}
                                                    <div className="space-y-4">
                                                        <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                                            Using YouAsk voice AI to script
                                                        </p>
                                                        <div className="flex items-center justify-between px-1">
                                                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                                                <span className="material-symbols-outlined text-sm">notes</span>
                                                                Editable Transcript
                                                            </label>
                                                            <span className="material-symbols-outlined text-slate-300 text-lg">edit</span>
                                                        </div>
                                                        <div className="relative min-h-[320px] bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 flex flex-col">
                                                            <textarea
                                                                value={query}
                                                                onChange={(e) => setQuery(e.target.value)}
                                                                className="flex-1 bg-transparent outline-none text-slate-700 dark:text-slate-200 text-lg leading-relaxed resize-none"
                                                                placeholder="Transcribed text appears here..."
                                                            />
                                                            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 text-[9px] font-black text-slate-400 uppercase tracking-widest flex justify-between items-center">
                                                                <span>Subject: {voiceSubject}</span>
                                                                <span className="text-primary italic">Spoken Text</span>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Live Math Preview Pane */}
                                                    <div className="space-y-4">
                                                        <div className="flex items-center justify-between px-1">
                                                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                                                <span className="material-symbols-outlined text-sm">functions</span>
                                                                Live Math Preview
                                                            </label>
                                                            <div className="flex items-center gap-3">
                                                                <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Formatting</span>
                                                                <button
                                                                    onClick={() => setFormattingEnabled(!formattingEnabled)}
                                                                    className={`relative w-10 h-5 rounded-full transition-colors ${formattingEnabled ? 'bg-primary' : 'bg-slate-300 dark:bg-slate-700'}`}
                                                                >
                                                                    <div className={`absolute top-1 left-1 size-3 bg-white rounded-full transition-transform ${formattingEnabled ? 'translate-x-5' : ''}`}></div>
                                                                </button>
                                                            </div>
                                                        </div>
                                                        <div className="relative min-h-[320px] bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden flex flex-col items-center justify-center p-8 text-white math-grid-bg">
                                                            <div className="relative z-10 w-full text-center space-y-4">
                                                                <div className="text-3xl font-bold p-8 flex items-center justify-center min-h-[160px]">
                                                                    {formattingEnabled ? (
                                                                        <MathRenderer content={query || ""} mode="block" dynamic />
                                                                    ) : (
                                                                        <span className="font-mono text-xl opacity-80 break-all">{query}</span>
                                                                    )}
                                                                </div>
                                                                <p className="text-[11px] font-mono text-slate-500 opacity-60 max-w-xs mx-auto truncate">
                                                                    {query}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Bottom Action Bar */}
                                                <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                                                    <button
                                                        onClick={() => setVoiceStage('idle')}
                                                        className="flex-1 px-8 py-4 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all active:scale-95"
                                                    >
                                                        <span className="material-symbols-outlined text-xl">refresh</span>
                                                        Try Again
                                                    </button>
                                                    <button
                                                        onClick={handleConfirmVoice}
                                                        disabled={isSolving || isBlockingInputError(inputError)}
                                                        className="relative flex-[2] px-8 py-5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-2xl font-black text-xl shadow-[0_10px_40px_-10px_rgba(37,99,235,0.4)] flex items-center justify-center gap-3 transition-all active:scale-[0.98] disabled:opacity-50 overflow-hidden"
                                                    >
                                                        {isSolving && (
                                                            <div className="absolute inset-0">
                                                                <div className="h-full bg-white/20 transition-all" style={{ width: `${solveProgress}%` }}></div>
                                                            </div>
                                                        )}
                                                        {isSolving ? (
                                                            <>
                                                                <div className="size-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></div>
                                                                <span>SOLVING... {solveProgress}%</span>
                                                            </>
                                                        ) : (
                                                            <>
                                                                <span>CONFIRM & SOLVE</span>
                                                                <span className="material-symbols-outlined animate-pulse">auto_awesome</span>
                                                            </>
                                                        )}
                                                    </button>
                                                    {inputError && (
                                                        <div className="text-xs text-red-500 font-medium">
                                                            {inputError}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {voiceStage === 'error' && (
                                            <div className="text-center space-y-6">
                                                <div className="w-16 h-16 bg-red-100 dark:bg-red-900/30 text-red-500 rounded-full flex items-center justify-center mx-auto">
                                                    <span className="material-symbols-outlined text-3xl">error</span>
                                                </div>
                                                <div>
                                                    <h3 className="text-lg font-bold">Something went wrong</h3>
                                                    <p className="text-sm text-slate-500">I couldn&apos;t process your audio right now.</p>
                                                </div>
                                                <button onClick={() => setVoiceStage('idle')} className="text-primary font-bold hover:underline">Try Again</button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>


                    </div>

                    {/* Sidebar */}
                    <div className="lg:col-span-4 space-y-6">
                        <TransferAndNotificationsPanel
                            onInfo={(message) =>
                                pushToast({
                                    type: "info",
                                    title: "Credits",
                                    message,
                                })
                            }
                        />

                        {/* Tips Sidebar - Photo */}
                        {activeTab === 'snap' && (
                            <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                                <h3 className="text-primary font-bold flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined">lightbulb</span>
                                    Good Photo Tips
                                </h3>
                                <ul className="space-y-4">
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Ensure good lighting.</strong> Avoid shadows covering the equations or variables.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Focus on one problem.</strong> Crop the image to show only the relevant task.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Include diagrams.</strong> If the problem references a graph, make sure it&apos;s in the shot.</p>
                                    </li>
                                </ul>
                            </div>
                        )}

                        {/* Tips Sidebar - Voice */}
                        {activeTab === 'voice' && (
                            <div className="bg-purple-50 dark:bg-purple-900/10 border border-purple-200 dark:border-purple-800 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                                <h3 className="text-purple-600 dark:text-purple-400 font-bold flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined">mic</span>
                                    Voice Input Tips
                                </h3>
                                <ul className="space-y-4">
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-purple-600 text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Speak clearly.</strong> Ensure you are in a quiet environment for best accuracy.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-purple-600 text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Be specific.</strong> State variables and operations explicitly (e.g., &quot;x squared&quot;).</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-purple-600 text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Review the math.</strong> Check the generated LaTeX before clicking Solve.</p>
                                    </li>
                                </ul>
                            </div>
                        )}

                        {/* Tips Sidebar - Text */}
                        {activeTab === 'text' && (
                            <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                                <h3 className="text-primary font-bold flex items-center gap-2 mb-4">
                                    <span className="material-symbols-outlined">lightbulb</span>
                                    Good Math Tips
                                </h3>
                                <ul className="space-y-4">
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">1</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Use clear notation.</strong> Type standard math symbols or use the helper tools.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">2</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>One problem at a time.</strong> Keep questions focused for the best answer.</p>
                                    </li>
                                    <li className="flex gap-3">
                                        <span className="w-5 h-5 bg-primary text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">3</span>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed"><strong>Check your variables.</strong> define any unusual terms or constants.</p>
                                    </li>
                                </ul>
                            </div>
                        )}

                        {/* Online Users Widget */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <span className="relative flex h-3 w-3">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                    </span>
                                    Online Students
                                </h3>
                                {isPublic && <span className="text-xs font-bold text-slate-500">{onlineUsers.length} Active</span>}
                            </div>

                            {!isPublic ? (
                                <div className="text-center py-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                                    <p className="text-sm text-slate-500 mb-3 px-4">Turn on Public Profile to see and connect with peers.</p>
                                    <button
                                        onClick={() => router.push('/dashboard')}
                                        className="text-primary text-xs font-bold hover:underline"
                                    >
                                        Go to Settings
                                    </button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {onlineUsers.length === 0 ? (
                                        <p className="text-sm text-slate-500 italic">No one else is public right now.</p>
                                    ) : (
                                        onlineUsers.slice(0, 5).map((u) => (
                                            <div key={u.id} className="flex items-center gap-3">
                                                <div
                                                    className="w-8 h-8 rounded-full bg-cover bg-center border border-slate-200 dark:border-slate-700"
                                                    style={{ backgroundImage: `url('${u.avatar_url || 'https://lh3.googleusercontent.com/aida-public/AB6AXuD_gpHP7vJM1mkTxszlDYSYslefzDpqT7kS3EUblVETFcyH2Sl2xHETdTN_AcqdawcLn0mOa7LR69Ol1T3hAFSvpJss7LzshfwXBbhjMZqOGSH9S1nVdhEO1aeexaHXJAn_VqN1tFoPVazJP1aq1rARcjsg7F4-pStNL1jl7KEpohReYVX52pfbq3YO6IKCX71lAo42c76k2H4WrKWI5r79xsjqMPNL1zZPzcajFKkIs40bZTGM732P1j_aCdcr67zOQ2bNSaRrATQz'}')` }}
                                                />
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-semibold truncate text-slate-900 dark:text-slate-100">{u.full_name}</p>
                                                    <p className="text-[10px] text-slate-500 truncate">
                                                        {u.learning_interests && u.learning_interests.length > 0
                                                            ? u.learning_interests.slice(0, 2).join(", ")
                                                            : "Studying Math"}
                                                    </p>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Recent Solutions - Always visible */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-all animate-in fade-in slide-in-from-right-4 duration-500">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <span className="material-symbols-outlined text-slate-400">history</span>
                                    Recent History
                                </h3>
                                <button
                                    type="button"
                                    onClick={() => router.push("/dashboard?tab=history")}
                                    className="text-primary text-xs font-semibold hover:underline"
                                >
                                    View All
                                </button>
                            </div>
                            <div className="space-y-3">
                                {history.length === 0 ? (
                                    <div className="text-center py-6 text-slate-400 text-sm italic">
                                        <p>No history found.</p>
                                        <p className="text-xs mt-1">Start solving to see items here.</p>
                                    </div>
                                ) : (
                                    history.slice(0, 3).map((session) => (
                                        <div
                                            key={session.id}
                                            onClick={() => router.push(resolveHistorySessionRoute(session))}
                                            className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 hover:border-primary/30 transition-colors cursor-pointer group"
                                        >
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-[10px] uppercase font-bold text-slate-400 bg-slate-100 dark:bg-slate-700/50 px-1.5 py-0.5 rounded">
                                                    #{session.id}
                                                </span>
                                                <span className="text-[10px] text-slate-400 ml-auto">
                                                    {new Date(session.created_at).toLocaleDateString()}
                                                </span>
                                            </div>
                                            <div className="text-sm font-medium text-slate-900 dark:text-slate-200 line-clamp-2 min-h-[1.25rem]">
                                                <MathRenderer content={session.title || "Untitled Session"} mode="prose" />
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Student Context Card */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 transition-colors">
                            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">
                                <span className="material-symbols-outlined text-primary">school</span>
                                Your School & Tier
                            </h3>
                            {readyWallet ? (
                                <div className="space-y-2 text-sm">
                                    <p className="text-slate-700 dark:text-slate-300">
                                        <span className="font-semibold">School:</span>{" "}
                                        {userProfile?.school_name || "Not set"}
                                    </p>
                                    <p className="text-slate-700 dark:text-slate-300">
                                        <span className="font-semibold">Location:</span>{" "}
                                        {[userProfile?.profile_province_state, userProfile?.profile_country].filter(Boolean).join(", ") || "Not set"}
                                    </p>
                                    <p className="text-slate-700 dark:text-slate-300">
                                        <span className="font-semibold">Program Tier:</span> {readyWallet.effective_tier}
                                    </p>
                                    {walletPrograms.length > 0 && (
                                        <div className="text-xs text-slate-500">
                                            Active programs: {walletPrograms.map(p => p.program_name || p.program_slug).filter(Boolean).join(", ")}
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-500">Wallet and school info are loading.</p>
                            )}
                        </div>



                        {/* Credits Callout */}
                        <div className="relative overflow-hidden bg-slate-900 rounded-xl p-6 text-white group">
                            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/20 blur-3xl -mr-16 -mt-16 group-hover:bg-primary/40 transition-colors"></div>
                            <div className="relative z-10">
                                <h4 className="text-lg font-bold mb-2">Need More Credits?</h4>
                                <p className="text-slate-400 text-sm mb-4">Top up your wallet to keep solving with your preferred tier.</p>
                                <button
                                    onClick={() => router.push("/billing")}
                                    className="w-full bg-white text-slate-900 font-bold py-2.5 rounded-lg text-sm hover:bg-slate-100 transition-colors"
                                >
                                    View Wallet & Packs
                                </button>
                            </div>
                        </div>

                    </div>
                </div>
            </main>

            {batchSolveResult && (
                <section className="max-w-7xl mx-auto px-4 pb-10">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-semibold text-slate-900 dark:text-slate-100">Batch Results</h3>
                            <div className="text-xs text-slate-500">
                                request_id: {batchSolveResult.request_id || "-"} | attempt_id: {batchSolveResult.attempt_id || "-"}
                            </div>
                        </div>
                        <div className="space-y-3">
                            {batchSolveResult.items.map((item, idx) => {
                                const isRefusal = Boolean(item.refusal?.is_refusal);
                                return (
                                    <div key={`${item.question_id || idx}`} className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
                                        <div className="text-xs text-slate-500 mb-1">
                                            Q{item.question_index ?? idx + 1} ({item.question_id || `q${idx + 1}`})
                                        </div>
                                        {isRefusal ? (
                                            <div className="text-sm text-amber-700 dark:text-amber-300">
                                                Refusal: {item.refusal?.reason || "Unable to answer this item safely."}
                                            </div>
                                        ) : (
                                            <div className="text-sm text-slate-800 dark:text-slate-100 whitespace-pre-wrap">
                                                {formatBatchFinalAnswer(item.final_answer) || "No final answer returned."}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </section>
            )}

            <footer className="max-w-7xl mx-auto px-4 py-8 border-t border-slate-200 dark:border-slate-800 text-center">
                <p className="text-slate-400 text-xs font-medium">© {new Date().getFullYear()} YouAsk AI LLM Math Solver Labs. All rights reserved.</p>
            </footer>

            {
                isSolving && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/75 p-6 backdrop-blur-sm animate-in fade-in duration-200">
                        <div
                            dir={uiDirection}
                            role="dialog"
                            aria-modal="true"
                            aria-label="Solving Problem Progress"
                            className="relative w-full max-w-4xl overflow-hidden rounded-[28px] border border-white/30 bg-white/12 p-7 text-white shadow-2xl backdrop-blur-2xl md:p-10"
                        >
                            <div className="pointer-events-none absolute inset-0 opacity-35 [background-image:linear-gradient(rgba(255,255,255,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.12)_1px,transparent_1px)] [background-size:22px_22px]" />
                            <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-sky-300/20 blur-3xl" />
                            <div className="pointer-events-none absolute -bottom-20 -left-12 h-64 w-64 rounded-full bg-emerald-300/15 blur-3xl" />

                            {/* Header */}
                            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12 relative z-10">
                                <div>
                                    <h1 className="text-3xl font-semibold tracking-tight">{t("solvingMathProblem")}</h1>
                                    <p className="mt-1 text-sm uppercase tracking-[0.18em] text-slate-200/80">{t("advancedNeuralComputation")}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-[11px] uppercase tracking-[0.2em] text-slate-200/70">{t("elapsedTime")}</p>
                                    <p className="mt-1 text-4xl font-semibold text-cyan-100">{formatElapsed(elapsedMs)}s</p>
                                </div>
                            </div>

                            {/* Pipeline Grid */}
                            <div className="relative z-10 mt-8 grid grid-cols-1 gap-3 md:grid-cols-2">
                                {pipelineStages.map((stage) => {
                                    const isCompleted = stage.status === "completed";
                                    const isActive = stage.status === "active";
                                    const isPending = stage.status === "pending";
                                    return (
                                        <div
                                            key={stage.key}
                                            className={[
                                                "flex items-center gap-3 rounded-2xl border px-4 py-3 transition-all",
                                                isCompleted ? "border-emerald-300/60 bg-emerald-400/10" : "",
                                                isActive ? "border-sky-300/70 bg-sky-400/15 shadow-[0_0_26px_rgba(56,189,248,0.35)] motion-safe:animate-pulse" : "",
                                                isPending ? "border-white/15 bg-white/5 opacity-55" : "",
                                                stage.status === "failed" ? "border-rose-400/60 bg-rose-500/10 text-rose-200" : "",
                                            ].join(" ").trim()}
                                        >
                                            <span
                                                className={[
                                                    "material-symbols-outlined text-[22px]",
                                                    isCompleted ? "text-emerald-300" : isActive ? "text-sky-200" : "text-slate-300/70",
                                                ].join(" ")}
                                            >
                                                {isCompleted ? "check_circle" : stage.icon}
                                            </span>
                                            <div>
                                                <p className={isCompleted ? "font-semibold text-emerald-100" : isActive ? "font-semibold text-sky-100" : "text-slate-100/80"}>
                                                    {stage.label}
                                                </p>
                                                <p className="text-xs text-slate-200/70">{stage.description}</p>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Footer / Streaming Status */}
                            <div className="relative z-10 mt-8 flex flex-col gap-4 border-t border-white/20 pt-5 md:flex-row md:items-end md:justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="flex h-10 items-end gap-1.5">
                                        {[38, 74, 46, 86, 52, 70, 44].map((h, i) => (
                                            <div
                                                key={i}
                                                className={[
                                                    "w-1.5 rounded-sm bg-cyan-200 transition-opacity",
                                                    streamingActive ? "opacity-95 motion-safe:animate-voice-bar motion-reduce:animate-none" : "opacity-25",
                                                ].join(" ")}
                                                style={{ height: `${h}%`, animationDelay: `${i * 0.08}s` }}
                                            />
                                        ))}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className={`h-2.5 w-2.5 rounded-full ${streamingActive ? "bg-cyan-300 motion-safe:animate-pulse" : "bg-slate-400"}`} />
                                        <span className={`text-sm font-semibold uppercase tracking-[0.18em] ${streamingActive ? "text-cyan-100" : "text-slate-300"}`}>
                                            {streamingActive ? "STREAMING ACTIVE" : "STREAMING IDLE"}
                                        </span>
                                    </div>
                                </div>
                                <div className="text-right text-xs text-slate-200/70">
                                    <div>{currentStage || pipelineStages.find((stage) => stage.status === "active")?.label || "Preparing Engine"}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Split Modal for multiple questions */}
            <SplitModal
                isOpen={showSplitModal}
                onClose={() => setShowSplitModal(false)}
                onDismiss={() => {
                    const bundle = buildTaskBundleFromText(query, suggestedSplits);
                    setTaskBundleTasks(bundle.tasks);
                    setSelectedTaskIds(bundle.selected_task_ids);
                    setTaskUserAction("combined_solution");
                    setConfirmedBatchQuestions([]);
                    setMultiQuestionConfirmed(true);
                    setTaskConfirmSnapshot(String(query || "").trim());
                    setRequiresTaskReconfirm(false);
                    setMathValidityConfirmed(false);
                    setInputError(null);
                    setShowSplitModal(false);
                }}
                splits={suggestedSplits}
                perTaskCredits={estimate?.per_task_credits}
                totalEstimatedCredits={estimate?.estimated_total_credits ?? estimate?.total_credits ?? null}
                combinedModeMessage={"Solving as one combined solution. Pricing remains workload-based."}
                reconfirmMessage={requiresTaskReconfirm ? "You changed the question after confirmation. Please confirm again to recalculate credits." : null}
                onSelectQuestion={(question) => {
                    const bundle = buildTaskBundleFromText(query, suggestedSplits);
                    const picked = bundle.tasks.find((t) => t.task_text === question) || bundle.tasks[0];
                    const pickedId = picked ? [picked.task_id] : bundle.selected_task_ids.slice(0, 1);
                    setTaskBundleTasks(bundle.tasks);
                    setSelectedTaskIds(pickedId);
                    setTaskUserAction("solve_one");
                    setConfirmedBatchQuestions([]);
                    setMultiQuestionConfirmed(true);
                    setTaskConfirmSnapshot(String(query || "").trim());
                    setRequiresTaskReconfirm(false);
                    setMathValidityConfirmed(false);
                    setInputError(null);
                    setShowSplitModal(false);
                    setTimeout(() => {
                        void handleSolve();
                    }, 0);
                }}
                onConfirmSingleQuestion={() => {
                    const bundle = buildTaskBundleFromText(query, suggestedSplits);
                    setTaskBundleTasks(bundle.tasks);
                    setSelectedTaskIds(bundle.selected_task_ids);
                    setTaskUserAction("combined_solution");
                    setConfirmedBatchQuestions([]);
                    setMultiQuestionConfirmed(true);
                    setTaskConfirmSnapshot(String(query || "").trim());
                    setRequiresTaskReconfirm(false);
                    setInputError(null);
                    setShowSplitModal(false);
                }}
                onConfirmSelectedQuestions={(selectedQuestions) => {
                    const picked = selectedQuestions
                        .map((q) => q.trim())
                        .filter((q) => q.length > 0);
                    if (picked.length === 0) return;
                    const bundle = buildTaskBundleFromText(query, suggestedSplits);
                    const selectedIds = bundle.tasks
                        .filter((t) => picked.includes(t.task_text))
                        .map((t) => t.task_id);
                    setTaskBundleTasks(bundle.tasks);
                    setSelectedTaskIds(selectedIds.length > 0 ? selectedIds : bundle.selected_task_ids);
                    setTaskUserAction("confirm_selected");
                    setConfirmedBatchQuestions([]);
                    setMultiQuestionConfirmed(true);
                    setTaskConfirmSnapshot(String(query || "").trim());
                    setRequiresTaskReconfirm(false);
                    setMathValidityConfirmed(false);
                    setInputError(null);
                    setShowSplitModal(false);
                }}
            />

            <ThemeToggle />
        </div >
    );
}
