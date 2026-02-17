"use client";

import DashboardNavBar from "@/components/DashboardNavBar";
import { useState, useEffect, useRef, useMemo } from "react";
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
import { fetchApi } from "@/lib/api";
import {
    buildSolveBatchPayload,
    getSolveBatchCap,
    mapSolveBatchErrorMessage,
    resolveSolveBatchMode,
    resolveSolveBatchTier,
} from "@/lib/solve-batch";
import { SolveBatchResponse, SolveBatchResponseSchema } from "@/lib/contracts";

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

interface DebugAttemptDetails {
    billing?: {
        credits_charged?: number;
        credits_after?: number;
    };
}

const ALL_SOLVE_TIERS: SolveTier[] = ["SHORT_STEPS", "FINAL", "STANDARD", "RESEARCH"];

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

export default function DashboardPage() {
    const { pushToast } = useToast();
    const useSnapSolveUploadPanelV2 = process.env.NEXT_PUBLIC_SNAP_SOLVE_UPLOAD_PANEL_V2 !== "false";
    const devToolsEnabled = process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_ENABLE_DEV_TOOLS === "true";
    const mapTierToApi = (tier: SolveTier) => {
        if (tier === "SHORT_STEPS") return "short_steps";
        if (tier === "FINAL") return "final";
        return tier.toLowerCase();
    };
    const normalizeTierLabel = (tier?: string) => {
        const raw = (tier || "").trim().toLowerCase();
        if (raw === "three_step" || raw === "free" || raw === "short_steps") return "SHORT_STEPS";
        if (raw === "short" || raw === "final") return "FINAL";
        if (raw === "standard" || raw === "student_standard") return "STANDARD";
        if (raw === "research" || raw === "enterprise") return "RESEARCH";
        return tier || "-";
    };
    const formatDebugNumber = (value?: number) => (value === undefined ? "-" : Number(value));
    const [activeTab, setActiveTab] = useState<'text' | 'snap' | 'voice'>('text');
    const [history, setHistory] = useState<ChatSession[]>([]);
    const [query, setQuery] = useState("sqrt(x+5) = x - 1");
    const [isSolving, setIsSolving] = useState(false);
    const [onlineUsers, setOnlineUsers] = useState<ActiveUser[]>([]);
    const [isPublic, setIsPublic] = useState(false);
    const [debugSimTokens, setDebugSimTokens] = useState({
        input_tokens: 2000,
        output_tokens: 1000,
        cached_tokens: 250,
        model: "gpt-5-mini",
        provider: "openai_simulated",
    });
    const [debugForceError, setDebugForceError] = useState(false);
    const [reuseIdempotencyKey, setReuseIdempotencyKey] = useState(true);
    const [lastIdempotencyKey, setLastIdempotencyKey] = useState<string | null>(null);
    const [stayOnSolveResult, setStayOnSolveResult] = useState(false);
    const [debugAttemptDetails, setDebugAttemptDetails] = useState<DebugAttemptDetails | null>(null);
    const [lastSolveError, setLastSolveError] = useState<{ code?: string; message?: string; request_id?: string; details?: unknown } | null>(null);
    const [batchSolveResult, setBatchSolveResult] = useState<SolveBatchResponse | null>(null);

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
    const [confirmedBatchQuestions, setConfirmedBatchQuestions] = useState<string[]>([]);
    const [mathValidityConfirmed, setMathValidityConfirmed] = useState(false);

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
    const [streamingContent, setStreamingContent] = useState("");
    const [currentStage, setCurrentStage] = useState("");
    const [streamingTelemetry, setStreamingTelemetry] = useState<StreamingTelemetry | null>(null);
    const [streamingMeta, setStreamingMeta] = useState<StreamingRuntimeMeta | null>(null);
    const [runtimeDebugMeta, setRuntimeDebugMeta] = useState<StreamingRuntimeMeta | null>(null);
    const [showRuntimeDebug, setShowRuntimeDebug] = useState(false);
    const [runtimeDebugLoading, setRuntimeDebugLoading] = useState(false);
    const [runtimeDebugError, setRuntimeDebugError] = useState<string | null>(null);
    const [solveStartTime, setSolveStartTime] = useState<number | null>(null);

    // Phase 1: Clarification States
    const [isClarifying, setIsClarifying] = useState(false);
    const [clarificationMessage, setClarificationMessage] = useState("");
    const [clarificationResponse, setClarificationResponse] = useState("");
    const [activeAttemptId, setActiveAttemptId] = useState<string | null>(null);
    const [clarificationHistory, setClarificationHistory] = useState<string[]>([]);
    const [preferredLanguage, setPreferredLanguage] = useState<string>("en");
    const uiDirection = preferredLanguage === "ar" ? "rtl" : "ltr";
    const t = (key: string, vars?: Record<string, string | number>) => translateSolveText(preferredLanguage, key, vars);

    const [pipelineStages, setPipelineStages] = useState<TimelineStep[]>([
        { key: "attempt_created", label: t("semanticExtraction"), description: t("parsingMathSymbols"), status: "pending", icon: "barcode_reader" },
        { key: "calling_ai_core", label: t("neuralReasoning"), description: t("mappingLogicalSteps"), status: "pending", icon: "psychology" },
        { key: "schema_validate", label: t("strictValidation"), description: t("checkingSchema"), status: "pending", icon: "verified_user" },
        { key: "completed", label: t("packetDelivery"), description: t("assemblingResponse"), status: "pending", icon: "network_check" },
    ]);
    const [rotatingPipelineIndex, setRotatingPipelineIndex] = useState(0);

    useEffect(() => {
        if (!isSolving) {
            setRotatingPipelineIndex(0);
            return;
        }
        const intervalId = setInterval(() => {
            setRotatingPipelineIndex((prev) => (prev + 1) % pipelineStages.length);
        }, 3000);
        return () => clearInterval(intervalId);
    }, [isSolving, pipelineStages.length]);

    useEffect(() => {
        setPipelineStages((prev) =>
            prev.map((stage) => {
                if (stage.key === "attempt_created") {
                    return {
                        ...stage,
                        label: t("semanticExtraction"),
                        description: stage.status === "pending" ? t("parsingMathSymbols") : stage.description,
                    };
                }
                if (stage.key === "calling_ai_core") {
                    return {
                        ...stage,
                        label: t("neuralReasoning"),
                        description: stage.status === "pending" ? t("mappingLogicalSteps") : stage.description,
                    };
                }
                if (stage.key === "schema_validate") {
                    return {
                        ...stage,
                        label: t("strictValidation"),
                        description: stage.status === "pending" ? t("checkingSchema") : stage.description,
                    };
                }
                if (stage.key === "completed") {
                    return {
                        ...stage,
                        label: t("packetDelivery"),
                        description: stage.status === "pending" ? t("assemblingResponse") : stage.description,
                    };
                }
                return stage;
            })
        );
    }, [preferredLanguage]);

    // SSE / Polling Event Listener
    useEffect(() => {
        if (!activeAttemptId || !isSolving) return;
        const tr = (key: string, vars?: Record<string, string | number>) =>
            translateSolveText(preferredLanguage, key, vars);

        let eventSource: EventSource | null = null;
        let pollInterval: NodeJS.Timeout | null = null;
        const channel = `/api/v1/attempt/${activeAttemptId}/events`;

        const updateStep = (key: string, status: "pending" | "active" | "completed" | "failed", description?: string) => {
            setPipelineStages(prev => prev.map(s => {
                if (s.key === key) return { ...s, status, description: description || s.description };
                // If this step is completed, make previous steps completed too if they aren't
                return s;
            }));
        };

        type BackendEvent = { phase?: string; status?: string; metadata?: Record<string, unknown> };
        const handleBackendEvent = (data: BackendEvent) => {
            const { phase, status, metadata } = data;

            if (phase === "attempt_created") {
                updateStep("attempt_created", "completed", tr("extractionComplete"));
                updateStep("calling_ai_core", "active", tr("initializingReasoning"));
            } else if (phase === "calling_ai_core_start") {
                updateStep("calling_ai_core", "active", tr("callingProvider", { provider: String(metadata?.provider || "AI") }));
            } else if (phase === "calling_ai_core_done") {
                updateStep("calling_ai_core", "completed", tr("reasoningComplete"));
                updateStep("schema_validate", "active", tr("validatingOutput"));
            } else if (phase === "schema_validate_start") {
                updateStep("schema_validate", "active", tr("validatingSchema"));
            } else if (phase === "schema_validate_done") {
                if (status === "success") {
                    updateStep("schema_validate", "completed", tr("validationSuccessful"));
                    updateStep("completed", "active", tr("streamingResults"));
                } else {
                    updateStep("schema_validate", "active", tr("schemaInvalidRepair"));
                }
            } else if (phase === "schema_repair_start") {
                updateStep("schema_validate", "active", tr("attemptingRepair"));
            } else if (phase === "schema_repair_done") {
                if (status === "success") {
                    updateStep("schema_validate", "completed", tr("repairSuccessful"));
                    updateStep("completed", "active", tr("streamingResults"));
                } else {
                    updateStep("schema_validate", "failed", tr("validationFailed"));
                }
            } else if (phase === "completed_success") {
                updateStep("completed", "completed", tr("solveComplete"));
            } else if (phase === "completed_failure") {
                updateStep("completed", "failed", tr("solveFailed"));
            } else if (phase === "clarification_needed") {
                updateStep("completed", "active", tr("clarificationRequested"));
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
                        // Map status to stages (simplified polling fallback)
                        if (data.status === "success") {
                            setPipelineStages(prev => prev.map(s => ({ ...s, status: "completed" })));
                            if (pollInterval) clearInterval(pollInterval);
                        } else if (data.status === "failure") {
                            setPipelineStages(prev => prev.map(s => s.status === "completed" ? s : { ...s, status: "failed" }));
                            if (pollInterval) clearInterval(pollInterval);
                        } else if (data.status === "ambiguous") {
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
    }, [activeAttemptId, isSolving, preferredLanguage]);

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
    const [selectedSolveTier, setSelectedSolveTier] = useState<SolveTier>("STANDARD");
    const isPlotLockedByTier = selectedSolveTier === "FINAL";
    const resolveSessionRoute = (sessionId: string | number) =>
        selectedSolveTier === "FINAL" ? `/chat_final/${sessionId}` : `/chat/${sessionId}`;
    const resolveHistorySessionRoute = (session: ChatSession) => {
        const telemetry = session?.telemetry;
        const rawTier =
            telemetry?.tier_effective ||
            telemetry?.effective_tier ||
            telemetry?.tier_requested ||
            telemetry?.tier ||
            "";
        return String(rawTier).trim().toUpperCase() === "FINAL"
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
    const hasMultipleQuestions = !multiQuestionConfirmed && multiQuestionResult.isMultiple && multiQuestionResult.confidence !== 'low';
    const tokenBlockReason = !tokenPolicyReady
        ? "Token policy unavailable. Please refresh."
        : isInputTooLong
            ? "Input too long. Please split into smaller parts."
            : isRequestTooLarge
                ? "Request too large for AI context. Please shorten."
                : hasMultipleQuestions
                    ? "Multiple questions detected. One at a time please."
                    : null;

    const router = useRouter();
    const walletReady = walletLoaded && !walletError && !!walletSummary;
    const readyWallet = walletReady ? walletSummary : null;
    const estimatedQuestionCount = activeTab === "text"
        ? Math.max(1, multiQuestionResult.suggestedSplits.length || 1)
        : 1;
    const estimatedSolveCost = useMemo(() => {
        if (!estimate) return null;
        return estimate.per_question_credits * estimatedQuestionCount;
    }, [estimate, estimatedQuestionCount]);
    const maxQuestionsAllowed = useMemo(() => {
        const raw = Number(estimate?.max_questions_allowed ?? 0);
        return Number.isFinite(raw) && raw > 0 ? Math.trunc(raw) : null;
    }, [estimate?.max_questions_allowed]);
    const estimateBreakdown = useMemo(() => {
        if (!estimate?.breakdown) return undefined;
        const raw = estimate.breakdown as Record<string, unknown>;
        if (typeof raw.tier_base === "number") {
            return {
                tier_base: raw.tier_base as number,
                ocr: Number(raw.ocr || 0),
                voice: Number(raw.voice || 0),
                verify: Number(raw.verify || 0),
                plot: Number(raw.plot || 0),
                asset_type_addon: Number(raw.asset_type_addon || 0),
            };
        }
        const addons = (raw.addons && typeof raw.addons === "object") ? raw.addons as Record<string, unknown> : {};
        return {
            tier_base: Number(raw.base || 0),
            ocr: Number(addons.ocr || 0),
            voice: Number(addons.voice || 0),
            verify: Number(addons.verify || 0),
            plot: Number(addons.plot || 0),
            asset_type_addon: Number(addons.asset_type_addon || 0),
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

    useEffect(() => {
        const stored = typeof window !== "undefined" ? localStorage.getItem("uask.solveTier") : null;
        if (stored === "SHORT_STEPS" || stored === "STANDARD" || stored === "RESEARCH" || stored === "FINAL") {
            setSelectedSolveTier(stored);
        }
    }, []);

    useEffect(() => {
        if (!walletReady) return;
        const stored = typeof window !== "undefined" ? localStorage.getItem("uask.solveTier") : null;
        const defaultTier: SolveTier =
            stored === "SHORT_STEPS" || stored === "STANDARD" || stored === "RESEARCH" || stored === "FINAL"
                ? stored
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
    }, [tokenPolicyReady, walletReady, readyWallet, activeTab, estimatedQuestionCount, graphMode]);

    useEffect(() => {
        if (!readyWallet) return;
        const selectedTierBlockedByCredits = !canAffordTier(selectedSolveTier);
        if (!selectedTierBlockedByCredits) return;

        const fallbackOrder: SolveTier[] = ["STANDARD", "FINAL", "SHORT_STEPS", "RESEARCH"];
        const fallback = fallbackOrder.find((tier) => {
            return canAffordTier(tier);
        }) || "SHORT_STEPS";
        setSelectedSolveTier(fallback);
        if (typeof window !== "undefined") {
            localStorage.setItem("uask.solveTier", fallback);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [readyWallet?.computed_balance, tierEstimateByTier, selectedSolveTier]);

    useEffect(() => {
        if (!tokenPolicyReady) return;
        const runEstimate = async () => {
            try {
                const inputType = activeTab === "snap" ? "snap" : activeTab === "voice" ? "voice" : "text";
                const response = await fetchCreditsEstimate({
                    tier: selectedSolveTier,
                    input_type: inputType,
                    asset_type: activeTab === "snap" ? "image" : "none",
                    question_count: estimatedQuestionCount,
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
    }, [tokenPolicyReady, selectedSolveTier, activeTab, estimatedQuestionCount, graphMode, tierFeatureGates.allow_plot, isPlotLockedByTier]);

    useEffect(() => {
        if (isPlotLockedByTier && graphMode !== "off") {
            setGraphMode("off");
        }
    }, [isPlotLockedByTier, graphMode]);

    useEffect(() => {
        const userId = localStorage.getItem("user_id");
        if (!userId) return;
        const requestedMode = (selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL") ? "minimal" : "detailed";
        void fetchSolveRuntimeMeta(userId, selectedSolveTier, requestedMode)
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
    }, [selectedSolveTier, graphMode, isPlotLockedByTier]);

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

                try {
                    setIsSolving(true);
                    setCurrentStage(t("restoringSession"));
                    setSolveStartTime(Date.now());

                    const res = await fetch(`/api/v1/attempt/${savedAttemptId}`);
                    if (!res.ok) throw new Error("Failed to fetch attempt");

                    const data = await res.json();
                    if (data.status === "success" && data.session_id) {
                        // Already solved
                        localStorage.removeItem("uask.activeAttemptId");
                        localStorage.removeItem("uask.activeQuery");
                        router.push(resolveSessionRoute(data.session_id));
                    } else if (data.status === "ambiguous") {
                        setIsClarifying(true);
                        setClarificationMessage(data.error_message || "Clarification needed.");
                    } else if (data.status === "failure") {
                        localStorage.removeItem("uask.activeAttemptId");
                        localStorage.removeItem("uask.activeQuery");
                        pushToast({
                            type: "error",
                            title: "Previous attempt failed",
                            message: data.error_message || "Unknown error",
                        });
                        setIsSolving(false);
                        setSolveStartTime(null);
                    } else if (data.status === "pending" || data.status === "processing") {
                        setIsSolving(true);
                        // SSE listener will take over
                    } else {
                        setIsSolving(false);
                        setSolveStartTime(null);
                    }
                } catch (e) {
                    console.error("[RESTORE] Failed:", e);
                    localStorage.removeItem("uask.activeAttemptId");
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
    }, [router, pushToast]);

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
        const userId = localStorage.getItem("user_id") || "1";
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

    const handleDebugRuntimeMeta = async () => {
        if (isSolving) return;
        const userId = localStorage.getItem("user_id") || "1";
        const requestedMode = (selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL") ? "minimal" : "detailed";

        setRuntimeDebugLoading(true);
        setRuntimeDebugError(null);
        try {
            const runtimeMeta = await fetchSolveRuntimeMeta(userId, selectedSolveTier, requestedMode);
            setRuntimeDebugMeta(runtimeMeta);
            setShowRuntimeDebug(true);
        } catch (err) {
            console.error("[RUNTIME_DEBUG] Failed to load solve runtime metadata:", err);
            setRuntimeDebugError((err as Error).message || "Failed to fetch runtime metadata");
            setShowRuntimeDebug(true);
        } finally {
            setRuntimeDebugLoading(false);
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

    const handleSolveTextBatch = async (questionsToSolve: string[], sharedContext?: string) => {
        if (isSolving) return;
        const userId = localStorage.getItem("user_id") || "1";
        const requestedMode = (selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL") ? "minimal" : "detailed";
        const batchMode = resolveSolveBatchMode(selectedSolveTier, requestedMode);
        const batchTier = resolveSolveBatchTier(selectedSolveTier);
        const cap = maxQuestionsAllowed ?? getSolveBatchCap(batchMode);
        const trimmedQuestions = questionsToSolve.map((q) => q.trim()).filter((q) => q.length > 0);

        if (trimmedQuestions.length === 0) {
            pushToast({
                type: "error",
                title: "Nothing to solve",
                message: "No valid questions were detected for batch solve.",
            });
            return;
        }

        if (trimmedQuestions.length > cap) {
            const message = mapSolveBatchErrorMessage("TOO_MANY_QUESTIONS", cap);
            pushToast({
                type: "error",
                title: "Selection too large",
                message,
            });
            return;
        }

        setIsSolving(true);
        setSolveStartTime(Date.now());
        setCurrentStage(t("batchSolving"));
        setStreamingContent("");
        setStreamingTelemetry(null);
        setStreamingMeta(null);
        setLastSolveError(null);
        setBatchSolveResult(null);
        setPipelineStages(prev =>
            prev.map(step =>
                step.key === "attempt_created"
                    ? { ...step, status: "completed", description: t("extractionComplete") }
                    : step.key === "calling_ai_core"
                        ? { ...step, status: "active", description: t("solvingProgress", { current: 0, total: trimmedQuestions.length }) }
                        : { ...step, status: "pending" }
            )
        );

        let stageTick: number | null = null;
        const stageStart = Date.now();
        stageTick = window.setInterval(() => {
            const elapsedSec = Math.floor((Date.now() - stageStart) / 1000);
            const estimatedCurrent = Math.min(trimmedQuestions.length, Math.max(1, elapsedSec + 1));
            setPipelineStages(prev =>
                prev.map(step =>
                    step.key === "calling_ai_core"
                        ? { ...step, status: "active", description: t("solvingProgress", { current: estimatedCurrent, total: trimmedQuestions.length }) }
                        : step
                )
            );
        }, 1000);

        try {
            const normalizeQuestionForBatch = (q: string): string => {
                const raw = String(q || "").trim();
                const ctx = String(sharedContext || "").trim();
                if (!ctx) return raw;
                const startsWithQuestionHeader =
                    /^(?:question\s*\d+\b|q\d+\b|\d+[.)]\s+|part\s*\(?[a-zivx0-9]+\)?\b)/i.test(raw);
                const contextLooksLikeQuestionHeader =
                    /(?:\bquestion\s*\d+\b|\bmultiple[-\s]*choice\b|\bfinal answer\b)/i.test(ctx);
                if (startsWithQuestionHeader || contextLooksLikeQuestionHeader) return raw;
                if (raw.toLowerCase().startsWith(ctx.toLowerCase())) return raw;
                return `${ctx} ${raw}`.trim();
            };

            const payload = buildSolveBatchPayload({
                selectedQuestions: trimmedQuestions.map((text, index) => ({
                    question_id: `q${index + 1}`,
                    text: normalizeQuestionForBatch(text),
                })),
                mode: batchMode,
                tier: batchTier,
            });
            const createIdempotencyKey = () =>
                typeof crypto !== "undefined" && "randomUUID" in crypto
                    ? crypto.randomUUID()
                    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

            const response = await fetchApi(`/api/v1/solve_questions_batch?user_id=${encodeURIComponent(userId)}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    tier: selectedSolveTier,
                    mode: "SOLVE",
                    graph_mode: (isPlotLockedByTier || !tierFeatureGates.allow_plot) ? "OFF" : graphMode.toUpperCase(),
                    domain_mode: "reals",
                    preferred_response_language: "English",
                    questions_json: payload.questions.map((q, idx) => ({
                        question_id: q.question_id || `q${idx + 1}`,
                        question_text: q.text,
                    })),
                    idempotency_key: createIdempotencyKey(),
                }),
            });

            const raw = await response.json().catch(() => ({}));
            if (!response.ok) {
                const errorObj = raw?.error && typeof raw.error === "object" ? raw.error : null;
                const detailObj = raw?.detail && typeof raw.detail === "object" ? raw.detail : null;
                const detail = detailObj || errorObj || raw;
                const code =
                    (typeof detail?.code === "string" ? detail.code : undefined) ||
                    (typeof errorObj?.code === "string" ? errorObj.code : undefined);
                const detailPayload =
                    (detailObj?.details && typeof detailObj.details === "object" ? detailObj.details : null) ||
                    (errorObj?.details && typeof errorObj.details === "object" ? errorObj.details : null) ||
                    (detail?.details && typeof detail.details === "object" ? detail.details : null);
                const requestId =
                    detail?.request_id ||
                    errorObj?.request_id ||
                    raw?.request_id ||
                    undefined;
                const maxAllowed = typeof detail?.max_allowed === "number" ? detail.max_allowed : cap;
                let message = mapSolveBatchErrorMessage(code, maxAllowed, detailPayload);
                let title = "Batch solve failed";
                if (response.status === 402) {
                    title = "Insufficient credits";
                    message = "Not enough credits. Please buy credits and retry.";
                } else if (response.status === 409) {
                    title = "Already processed";
                    message = "This request was already processed. No additional charge applied.";
                } else if (response.status >= 500) {
                    title = "Provider timeout";
                    message = "Provider timeout. You were NOT charged. Retry with a new request.";
                }
                pushToast({
                    type: "error",
                    title,
                    message: requestId ? `${message} (request_id: ${requestId})` : message,
                });
                return;
            }

            const parsed = SolveBatchResponseSchema.parse(raw);
            setBatchSolveResult(parsed);

            setPipelineStages(prev =>
                prev.map(step =>
                    step.key === "calling_ai_core"
                        ? { ...step, status: "completed", description: t("reasoningComplete") }
                        : step.key === "schema_validate"
                            ? { ...step, status: "completed", description: t("validationSuccessful") }
                            : step.key === "completed"
                                ? { ...step, status: "completed", description: t("batchPackagedForChat") }
                                : step
                )
            );
            setShowSplitModal(false);
            pushToast({
                type: "success",
                title: "Batch solve complete",
                message: `Solved ${trimmedQuestions.length} question(s) in one request.`,
            });
            const batchSessionId = parsed.session_id != null ? String(parsed.session_id) : "";
            if (batchSessionId) {
                const target = selectedSolveTier === "FINAL"
                    ? `/chat_final/${batchSessionId}`
                    : `/edit/${batchSessionId}`;
                setTimeout(() => router.push(target), 350);
            }
        } catch (err) {
            pushToast({
                type: "error",
                title: "Batch solve failed",
                message: (err as Error).message || "Request failed.",
            });
        } finally {
            if (stageTick !== null) window.clearInterval(stageTick);
            setIsSolving(false);
            setSolveStartTime(null);
        }
    };

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

        const userId = localStorage.getItem("user_id") || "1";
        const mathFieldValue = mathModeEnabled && mathInputRef.current?.getValue
            ? mathInputRef.current.getValue()
            : "";
        const textToSolve = textOverride ?? (mathFieldValue.trim() ? mathFieldValue : query);

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

        if (activeTab === "text") {
            const splitCandidates = (
                multiQuestionConfirmed && confirmedBatchQuestions.length > 0
                    ? confirmedBatchQuestions
                    : autoSplitQuestions(textToSolve)
            )
                .map((q) => q.trim())
                .filter((q) => q.length > 0);

            if (!multiQuestionConfirmed && splitCandidates.length > 1) {
                setSuggestedSplits(splitCandidates);
                setShowSplitModal(true);
                return;
            }

            if (multiQuestionConfirmed && splitCandidates.length > 1) {
                const sharedContext = extractSharedContext(textToSolve);
                await handleSolveTextBatch(splitCandidates, sharedContext);
                return;
            }
        }

        setIsSolving(true);
        setStreamingContent("");
        setCurrentStage(t("initializing"));
        setStreamingTelemetry(null);
        setStreamingMeta(null);
        setSolveStartTime(Date.now());
        setLastSolveError(null);

        // Reset Phase 1 Clarification
        setIsClarifying(false);
        setClarificationMessage("");
        setClarificationResponse("");
        setClarificationHistory([]);
        setActiveAttemptId(null);

        const createIdempotencyKey = () =>
            typeof crypto !== "undefined" && "randomUUID" in crypto
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

        try {
            const streamCandidates = ["/api/v1/solve_v3_stream"];
            const requestedMode = (selectedSolveTier === "SHORT_STEPS" || selectedSolveTier === "FINAL") ? "minimal" : "detailed";
            const idempotencyKey = (devToolsEnabled && reuseIdempotencyKey && lastIdempotencyKey)
                ? lastIdempotencyKey
                : createIdempotencyKey();
            setLastIdempotencyKey(idempotencyKey);

            void fetchSolveRuntimeMeta(userId, selectedSolveTier, requestedMode)
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
                            requested_mode: requestedMode,
                            tier: mapTierToApi(selectedSolveTier),
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
                            idempotency_key: idempotencyKey,
                            ...(devToolsEnabled ? {
                                debug_simulated_tokens: debugSimTokens,
                                debug_force_error: debugForceError
                            } : {})
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

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                accumulatedBuffer += decoder.decode(value, { stream: true });
                const lines = accumulatedBuffer.split('\n');
                accumulatedBuffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (!trimmedLine) continue;

                    if (trimmedLine.startsWith('event: ')) {
                        currentEvent = trimmedLine.slice(7).trim();
                    } else if (trimmedLine.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(trimmedLine.slice(6));
                            if (currentEvent === "meta") {
                                setStreamingMeta(data);
                                if (data.attempt_id) {
                                    setActiveAttemptId(data.attempt_id);
                                    localStorage.setItem("uask.activeAttemptId", data.attempt_id);
                                }
                                const parsedMeta = buildRuntimeMetaFromPayload(data, requestedMode);
                                setStreamingMeta((prev) => ({ ...(prev || {}), ...parsedMeta }));
                                if (parsedMeta.request_id) {
                                    localStorage.setItem("uask.activeAttemptId", parsedMeta.request_id);
                                    localStorage.setItem("uask.activeQuery", textToSolve);
                                    setActiveAttemptId(parsedMeta.request_id);
                                }
                            } else if (currentEvent === "delta") {
                                setStreamingContent((prev) => prev + data.text);
                            } else if (currentEvent === "stage") {
                                setCurrentStage(data.name);
                            } else if (currentEvent === "telemetry") {
                                setStreamingTelemetry(data?.telemetry ?? data);
                            } else if (currentEvent === "done") {
                                if (data.ok) {
                                    setSolveProgress(100);
                                    localStorage.removeItem("uask.activeAttemptId");
                                    localStorage.removeItem("uask.activeQuery");
                                    if (devToolsEnabled && stayOnSolveResult) {
                                        if (streamingMeta?.attempt_id) {
                                            try {
                                                const attemptRes = await fetch(`/api/v1/attempt/${streamingMeta.attempt_id}`, {
                                                    method: "GET",
                                                    credentials: "include",
                                                });
                                                if (attemptRes.ok) {
                                                    const attemptPayload = await attemptRes.json();
                                                    setDebugAttemptDetails(attemptPayload);
                                                }
                                            } catch {
                                                // ignore debug fetch failures
                                            }
                                        }
                                    } else {
                                        setTimeout(() => router.push(resolveSessionRoute(data.session_id)), 500);
                                    }
                                } else if (data.error?.code === "ambiguous_response") {
                                    localStorage.removeItem("uask.activeAttemptId");
                                    localStorage.removeItem("uask.activeQuery");
                                    throw new Error("Clarification is disabled. Please submit one clear question.");
                                } else {
                                    localStorage.removeItem("uask.activeAttemptId");
                                    localStorage.removeItem("uask.activeQuery");
                                    if (data.error?.request_id) {
                                        setStreamingMeta((prev) => ({ ...(prev || {}), request_id: data.error.request_id }));
                                    }
                                    const details = data.error?.details;
                                    const providerMessage =
                                        (typeof details?.message === "string" && details.message) ||
                                        (typeof details?.provider_details?.message === "string" && details.provider_details.message) ||
                                        "";
                                    const requestId = data.error?.request_id;
                                    const fullMessage = [
                                        data.error?.message || "Solve failed",
                                        providerMessage ? `provider: ${providerMessage}` : "",
                                        requestId ? `request_id: ${requestId}` : "",
                                    ]
                                        .filter(Boolean)
                                        .join(" | ");
                                    setLastSolveError({
                                        code: data.error?.code,
                                        message: data.error?.message,
                                        request_id: requestId,
                                        details,
                                    });
                                    throw new Error(fullMessage);
                                }
                            }
                        } catch (e) {
                            console.error("Error parsing SSE data", e);
                        }
                    }
                }
            }
        } catch (err) {
            console.error("[SOLVER_STREAM] Error:", err);
            pushToast({
                type: "error",
                title: "Solve failed",
                message: (err as Error).message || "Failed to generate solution.",
            });
        } finally {
            setIsSolving(false);
            setSolveStartTime(null);
        }
    };

    const handleClarify = async () => {
        if (!activeAttemptId || !clarificationResponse.trim() || isSolving) return;

        setIsSolving(true);
        setSolveStartTime(Date.now());
        setCurrentStage(t("resolvingAmbiguity"));

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
            if (data.status === "success" && data.session_id) {
                setSolveProgress(100);
                localStorage.removeItem("uask.activeAttemptId");
                localStorage.removeItem("uask.activeQuery");
                setTimeout(() => router.push(resolveSessionRoute(data.session_id)), 500);
            } else if (data.status === "ambiguous") {
                setClarificationHistory(prev => [...prev, clarificationResponse]);
                setClarificationMessage(data.clarifier_question || "Still ambiguous. Please provide more detail.");
                setClarificationResponse("");
            } else {
                localStorage.removeItem("uask.activeAttemptId");
                localStorage.removeItem("uask.activeQuery");
                throw new Error(data.error || "Ambiguity resolution failed.");
            }
        } catch (err) {
            console.error("[CLARIFY] Error:", err);
            pushToast({
                type: "error",
                title: "Clarification failed",
                message: (err as Error).message || "Failed to clarify.",
            });
        } finally {
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
                        <div className={`${tierSectionColor} dark:bg-slate-900 rounded-2xl shadow-xl border-2 border-slate-300 dark:border-slate-800 p-6 sketch-container relative transition-colors duration-1000`} style={{ filter: 'url(#handWobble) url(#roughpaper)' }}>
                            <div className="flex flex-col md:flex-row gap-8 items-center justify-between">
                                {/* Goal Section */}
                                <div className="flex flex-col gap-2">
                                    <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500 ml-1">Goal</h3>
                                    <button className="wobbly-button px-6 py-2 flex items-center gap-2 bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 hover:bg-slate-50 transition-all" style={{ filter: 'url(#handWobble) url(#roughpaper)' }}>
                                        <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-xl hand-drawn-icon">bolt</span>
                                        <span className="font-bold text-lg tracking-tight">Solve</span>
                                    </button>
                                </div>

                                {/* Tier Selector Section */}
                                <div className="flex flex-col gap-2 flex-grow w-full max-w-[620px]">
                                    <div className="mb-1 flex flex-col items-start gap-1">
                                        <h3 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500 ml-1">Tier</h3>
                                        {readyWallet && estimate && (
                                            <div className="w-full max-w-full">
                                                <CostPreview
                                                    perQuestionCost={estimate.per_question_credits}
                                                    questionCount={estimatedQuestionCount}
                                                    breakdown={estimateBreakdown}
                                                    creditsRemaining={readyWallet.computed_balance}
                                                />
                                                {maxQuestionsAllowed && (
                                                    <p className="mt-2 inline-flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs text-amber-800">
                                                        <span className="material-symbols-outlined text-[14px]">rule</span>
                                                        Max questions per request: <span className="font-bold">{maxQuestionsAllowed}</span>
                                                    </p>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                    <SegmentedControl
                                        options={[
                                            {
                                                value: "SHORT_STEPS",
                                                label: "Short Steps",
                                                icon: "bolt",
                                                disabled: !canAffordTier("SHORT_STEPS"),
                                                tooltip: !canAffordTier("SHORT_STEPS") ? `Need ${Number(tierEstimateByTier.SHORT_STEPS || 0).toFixed(2)} credits.` : undefined,
                                            },
                                            {
                                                value: "FINAL",
                                                label: "Final Answer",
                                                icon: "bolt",
                                                disabled: !canAffordTier("FINAL"),
                                                tooltip: !canAffordTier("FINAL") ? `Need ${Number(tierEstimateByTier.FINAL || 0).toFixed(2)} credits.` : undefined,
                                            },
                                            {
                                                value: "STANDARD",
                                                label: "Standard",
                                                icon: "school",
                                                disabled: !canAffordTier("STANDARD"),
                                                tooltip: !canAffordTier("STANDARD") ? `Need ${Number(tierEstimateByTier.STANDARD || 0).toFixed(2)} credits.` : undefined,
                                            },
                                            {
                                                value: "RESEARCH",
                                                label: "Research",
                                                icon: "science",
                                                disabled: !canAffordTier("RESEARCH"),
                                                tooltip: !canAffordTier("RESEARCH")
                                                    ? `Need ${Number(tierEstimateByTier.RESEARCH || 0).toFixed(2)} credits.`
                                                    : undefined,
                                            },
                                        ]}
                                        value={selectedSolveTier}
                                        onChange={(v) => {
                                            if (v === "SHORT_STEPS" || v === "STANDARD" || v === "RESEARCH" || v === "FINAL") {
                                                setSelectedSolveTier(v as SolveTier);
                                                if (typeof window !== "undefined") {
                                                    localStorage.setItem("uask.solveTier", v);
                                                }
                                            }
                                        }}
                                        size="sm"
                                        className="solve-segmented"
                                    />
                                </div>
                            </div>

                            {/* Decorative Flourish */}
                            <div className="absolute -top-4 -right-4 opacity-10 pointer-events-none hidden lg:block">
                                <svg width="100" height="100" viewBox="0 0 100 100" fill="none" className="stroke-slate-400">
                                    <path d="M10 20C30 15 80 10 90 30C100 50 20 80 10 70C0 60 50 40 80 50" strokeWidth="2" strokeLinecap="round" />
                                </svg>
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
                                                requestedMode={selectedSolveTier === "RESEARCH" ? "detailed" : "minimal"}
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
                                                            disabled={isSolving || isInputTooShort(query) || !!tokenBlockReason || isBlockingInputError(inputError) || !hasEnoughCredits}
                                                            title={tokenBlockReason || creditBlockReason || undefined}
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

                                        <div className="mt-8 flex justify-end">
                                            <button
                                                type="button"
                                                onClick={handleDebugRuntimeMeta}
                                                disabled={isSolving || runtimeDebugLoading}
                                                className="flex items-center gap-2 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 px-3 py-1.5 rounded-lg font-semibold transition-colors text-xs hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <span className="material-symbols-outlined text-sm">bug_report</span>
                                                {runtimeDebugLoading ? "Loading..." : "Debug"}
                                            </button>
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

            {devToolsEnabled && (
                <section className="max-w-7xl mx-auto px-4 pb-10">
                    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 text-sm">
                        <div className="flex items-center justify-between gap-4 mb-3">
                            <h3 className="font-semibold text-slate-900 dark:text-slate-100">Simulated Solve Debug (DEV)</h3>
                            <div className="text-xs text-slate-500">Controlled tokens, idempotency, and error simulation</div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                                Input Tokens
                                <input
                                    type="number"
                                    className="mt-1 w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-2 py-1"
                                    value={debugSimTokens.input_tokens}
                                    onChange={(e) => setDebugSimTokens((prev) => ({ ...prev, input_tokens: Number(e.target.value) }))}
                                />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                                Output Tokens
                                <input
                                    type="number"
                                    className="mt-1 w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-2 py-1"
                                    value={debugSimTokens.output_tokens}
                                    onChange={(e) => setDebugSimTokens((prev) => ({ ...prev, output_tokens: Number(e.target.value) }))}
                                />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                                Cached Tokens
                                <input
                                    type="number"
                                    className="mt-1 w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-2 py-1"
                                    value={debugSimTokens.cached_tokens}
                                    onChange={(e) => setDebugSimTokens((prev) => ({ ...prev, cached_tokens: Number(e.target.value) }))}
                                />
                            </label>
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                                Model
                                <input
                                    type="text"
                                    className="mt-1 w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-2 py-1"
                                    value={debugSimTokens.model}
                                    onChange={(e) => setDebugSimTokens((prev) => ({ ...prev, model: e.target.value }))}
                                />
                            </label>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                            <label className="text-xs text-slate-600 dark:text-slate-300">
                                Provider
                                <input
                                    type="text"
                                    className="mt-1 w-full rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-2 py-1"
                                    value={debugSimTokens.provider}
                                    onChange={(e) => setDebugSimTokens((prev) => ({ ...prev, provider: e.target.value }))}
                                />
                            </label>
                            <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 mt-6">
                                <input
                                    type="checkbox"
                                    checked={debugForceError}
                                    onChange={(e) => setDebugForceError(e.target.checked)}
                                />
                                Force Error
                            </label>
                            <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 mt-6">
                                <input
                                    type="checkbox"
                                    checked={reuseIdempotencyKey}
                                    onChange={(e) => setReuseIdempotencyKey(e.target.checked)}
                                />
                                Reuse Idempotency Key
                            </label>
                            <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 mt-6">
                                <input
                                    type="checkbox"
                                    checked={stayOnSolveResult}
                                    onChange={(e) => setStayOnSolveResult(e.target.checked)}
                                />
                                Stay On Result
                            </label>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-600 dark:text-slate-300">
                            <div>
                                <div>Attempt ID: {streamingMeta?.attempt_id || "-"}</div>
                                <div>Request ID: {streamingMeta?.request_id || "-"}</div>
                                <div>Tier Selected (UI): {normalizeTierLabel(selectedSolveTier)}</div>
                                <div>
                                    Tier: {normalizeTierLabel(streamingMeta?.tier_effective || streamingMeta?.effective_tier)}
                                    {" / requested "}
                                    {normalizeTierLabel(streamingMeta?.tier_requested)}
                                </div>
                                <div>Credits Charged: {formatDebugNumber(debugAttemptDetails?.billing?.credits_charged)}</div>
                                <div>Credits After: {formatDebugNumber(debugAttemptDetails?.billing?.credits_after)}</div>
                                <div>Error Code: {lastSolveError?.code ?? "-"}</div>
                                <div>Error Request ID: {lastSolveError?.request_id ?? "-"}</div>
                                <div>Error Message: {lastSolveError?.message ?? "-"}</div>
                            </div>
                            <div>
                                <div>Input Tokens: {streamingTelemetry?.input_tokens ?? "-"}</div>
                                <div>Output Tokens: {streamingTelemetry?.output_tokens ?? "-"}</div>
                                <div>Cached Tokens: {streamingTelemetry?.cached_tokens ?? "-"}</div>
                                <div>Total Tokens: {streamingTelemetry?.total_tokens ?? "-"}</div>
                                <div>Model: {streamingTelemetry?.model ?? "-"}</div>
                            </div>
                        </div>
                    </div>
                </section>
            )}

            <footer className="max-w-7xl mx-auto px-4 py-8 border-t border-slate-200 dark:border-slate-800 text-center">
                <p className="text-slate-400 text-xs font-medium">© {new Date().getFullYear()} YouAsk AI LLM Math Solver Labs. All rights reserved.</p>
            </footer>

            {
                showRuntimeDebug && (
                    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm">
                        <div className="w-full max-w-xl rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-xl">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Solve Runtime Debug</h3>
                                <button
                                    type="button"
                                    onClick={() => setShowRuntimeDebug(false)}
                                    className="text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                                >
                                    Close
                                </button>
                            </div>
                            {runtimeDebugError ? (
                                <p className="text-xs text-red-500">{runtimeDebugError}</p>
                            ) : (
                                <div className="space-y-1.5 text-xs text-slate-600 dark:text-slate-300">
                                    <div>
                                        Tier Selected (UI): {normalizeTierLabel(selectedSolveTier)}
                                    </div>
                                    <div>
                                        Tier Effective: {normalizeTierLabel(runtimeDebugMeta?.effective_tier || runtimeDebugMeta?.tier_effective || selectedSolveTier)}
                                    </div>
                                    <div>
                                        Tier Requested: {normalizeTierLabel(runtimeDebugMeta?.tier_requested || selectedSolveTier)}
                                    </div>
                                    <div>Mode: {runtimeDebugMeta?.mode_family || "SOLVE"}</div>
                                    <div>LLM Provider: {runtimeDebugMeta?.provider || "openai"}</div>
                                    <div>Model: {runtimeDebugMeta?.model || "unknown"}</div>
                                    <div>Prompt Binding ID: {runtimeDebugMeta?.prompt_binding_id || "-"}</div>
                                    <div>Global System Prompt ID: {runtimeDebugMeta?.global_system_prompt_id || "-"}</div>
                                    <div>Developer Prompt ID: {runtimeDebugMeta?.developer_prompt_id || "-"}</div>
                                    <div>Output Schema ID: {runtimeDebugMeta?.output_schema_id || "-"}</div>
                                    <div>Request ID: {runtimeDebugMeta?.request_id || "-"}</div>
                                    {runtimeDebugMeta?.token_config && (
                                        <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                                            <div className="font-semibold mb-1">Token Config:</div>
                                            <div>Max Output: {runtimeDebugMeta.token_config.max_output_tokens ?? "Auto"}</div>
                                            <div>Max Input: {runtimeDebugMeta.token_config.max_input_tokens ?? "Auto"}</div>
                                            <div>Temp: {runtimeDebugMeta.token_config.temperature ?? "Default"}</div>
                                            <div>Top P: {runtimeDebugMeta.token_config.top_p ?? "Default"}</div>
                                            <div>Timeout: {runtimeDebugMeta.token_config.timeout_ms ? `${runtimeDebugMeta.token_config.timeout_ms}ms` : "Default"}</div>
                                            <div>Trim: {runtimeDebugMeta.token_config.trim_strategy ?? "None"}</div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )
            }

            {
                isSolving && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/90 backdrop-blur-sm animate-in fade-in duration-300">
                        <div dir={uiDirection} className="relative w-full max-w-4xl p-8 md:p-12 text-white chalkboard-texture chalk-border shadow-2xl overflow-hidden">
                            {/* Decorative Elements */}
                            <div className="dust-smudge w-40 h-40 -top-10 -left-10 opacity-30"></div>
                            <div className="dust-smudge w-64 h-32 bottom-20 right-10 opacity-20"></div>
                            <div className="absolute top-1/4 right-12 opacity-10 pointer-events-none select-none text-4xl font-sketch">★</div>
                            <div className="absolute bottom-1/4 left-1/4 opacity-10 pointer-events-none select-none text-6xl font-sketch -rotate-12">∫</div>

                            {/* Header */}
                            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12 relative z-10">
                                <div className="flex items-center gap-5">
                                    <div className="w-16 h-16 flex items-center justify-center text-white text-3xl font-architects wobbly-chalk rotate-[-2deg]">
                                        Σ
                                    </div>
                                    <div>
                                        <h1 className="text-3xl md:text-4xl font-architects tracking-wide text-white/90">{t("solvingMathProblem")}</h1>
                                        <p className="font-hand text-lg opacity-60 tracking-widest mt-1 uppercase">{t("advancedNeuralComputation")}</p>
                                    </div>
                                </div>
                                <div className="text-right font-hand">
                                    <p className="text-xs uppercase opacity-50 tracking-widest">{t("elapsedTime")}</p>
                                    <div className="text-5xl font-architects cyan-glow flex items-baseline">
                                        {formatElapsed(elapsedMs)}<span className="text-xl ml-1">s</span>
                                    </div>
                                </div>
                            </div>

                            {/* Pipeline Grid */}
                            <div className="mb-12 relative z-10">
                                <div className="flex items-center gap-2 mb-8 opacity-80">
                                    <span className="material-symbols-outlined text-2xl">refresh</span>
                                    <h2 className="font-hand text-xl uppercase tracking-[0.2em]">{t("systemPipelineState")}</h2>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    {(() => {
                                        const activeIndex = pipelineStages.findIndex(s => s.label === currentStage || s.key === currentStage);
                                        const visualActiveIndex = isSolving
                                            ? rotatingPipelineIndex
                                            : activeIndex;
                                        return pipelineStages.map((stage, index) => {
                                            const isCompleted = (visualActiveIndex !== -1 && index < visualActiveIndex) || stage.status === 'completed';
                                            const effectiveActive = (visualActiveIndex !== -1 && index === visualActiveIndex) || stage.status === 'active';

                                            return (
                                                <div key={stage.key} className={`flex items-start gap-4 p-5 wobbly-chalk transition-all cursor-default group ${effectiveActive ? 'border-white/70 bg-slate-100/10' : isCompleted ? 'border-white/60 bg-white/5' : 'border-white/20 opacity-60'}`}>
                                                    <div className={`w-12 h-12 flex items-center justify-center transition-colors ${effectiveActive || isCompleted ? 'text-white' : 'text-white/70'}`}>
                                                        <span className="material-symbols-outlined text-4xl bg-clip-text">
                                                            {stage.icon}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <h3 className={`font-architects text-xl transition-colors ${effectiveActive || isCompleted ? 'text-white' : 'text-white/90'}`}>
                                                            {stage.label}
                                                        </h3>
                                                        <p className="font-hand text-lg opacity-50">{stage.description}</p>
                                                    </div>
                                                    {effectiveActive && <div className="ml-auto w-2 h-2 rounded-full bg-cyan-400 animate-pulse self-center"></div>}
                                                    {isCompleted && <div className="ml-auto material-symbols-outlined text-emerald-400 self-center">check</div>}
                                                </div>
                                            );
                                        })
                                    })()}
                                </div>
                            </div>

                            {/* Footer / Streaming Status */}
                            <div className="pt-8 mt-4 border-t border-dashed border-white/20 flex flex-col md:flex-row justify-between items-end gap-6 relative z-10">
                                <div className="flex items-center gap-6">
                                    {/* Animated Bars */}
                                    <div className="flex items-end gap-1.5 h-12">
                                        {[40, 85, 45, 100, 55, 75, 40].map((h, i) => (
                                            <div
                                                key={i}
                                                className="w-1.5 bg-chalk-cyan rounded-sm cyan-bar-glow animate-voice-bar"
                                                style={{ height: `${h}%`, animationDelay: `${i * 0.1}s` }}
                                            ></div>
                                        ))}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <div className="w-2.5 h-2.5 bg-chalk-cyan rounded-full cyan-bar-glow animate-pulse"></div>
                                            <span className="font-hand text-xl font-bold uppercase tracking-widest text-chalk-cyan cyan-glow">{t("streamingActive")}</span>
                                        </div>
                                        <p className="font-hand text-sm opacity-50">{t("packetDeliveryRealtime")}</p>
                                    </div>
                                </div>
                                <div className="text-right space-y-1">
                                    <p className="font-sketch italic opacity-40 text-lg">{t("solutionGenerationInProgress")}</p>
                                    <div className="flex flex-col items-end gap-1">
                                        <p className="font-hand text-sm uppercase opacity-50 tracking-tighter">v4.0.1 Stable • {streamingContent ? t("encryptedStream") : t("secureStream")}</p>
                                        <button
                                            onClick={() => setShowRuntimeDebug(true)}
                                            className="font-hand text-sm font-bold opacity-70 cursor-pointer hover:text-white transition-colors border-b border-dashed border-white/30"
                                        >
                                            ▶ {t("debugRuntime")}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Corner Icon */}
                            <div className="absolute top-4 right-4 w-10 h-10 rounded-lg flex items-center justify-center opacity-30 hover:opacity-100 transition-opacity cursor-help">
                                <span className="material-symbols-outlined text-white">auto_fix_high</span>
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
                    const forceAll = suggestedSplits
                        .map((q) => q.trim())
                        .filter((q) => q.length > 0);
                    if (forceAll.length === 0) {
                        setShowSplitModal(false);
                        return;
                    }
                    const sharedContext = extractSharedContext(query);
                    const formatted = buildConfirmedInputText(forceAll, sharedContext);
                    setConfirmedBatchQuestions(forceAll);
                    setMultiQuestionConfirmed(true);
                    setMathValidityConfirmed(false);
                    setInputError(null);
                    setMathModeEnabled(false);
                    setQuery(formatted);
                    setShowSplitModal(false);
                }}
                splits={suggestedSplits}
                onSelectQuestion={(question) => {
                    const sharedContext = extractSharedContext(query);
                    const selectedText = buildConfirmedInputText([question], sharedContext);
                    setMathModeEnabled(false);
                    setQuery(selectedText);
                    setConfirmedBatchQuestions([]);
                    setMultiQuestionConfirmed(false);
                    setMathValidityConfirmed(false);
                    setShowSplitModal(false);
                }}
                onConfirmSingleQuestion={() => {
                    setMathModeEnabled(false);
                    setConfirmedBatchQuestions([]);
                    setMultiQuestionConfirmed(true);
                    setShowSplitModal(false);
                }}
                onConfirmSelectedQuestions={(selectedQuestions) => {
                    const picked = selectedQuestions
                        .map((q) => q.trim())
                        .filter((q) => q.length > 0);
                    if (picked.length === 0) return;
                    const sharedContext = extractSharedContext(query);
                    const formatted = buildConfirmedInputText(picked, sharedContext);
                    setConfirmedBatchQuestions(picked);
                    setMultiQuestionConfirmed(true);
                    setMathValidityConfirmed(false);
                    setInputError(null);
                    setMathModeEnabled(false);
                    setQuery(formatted);
                    setShowSplitModal(false);
                }}
            />

            <ThemeToggle />
        </div >
    );
}
