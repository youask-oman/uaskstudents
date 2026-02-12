import React, { forwardRef } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SnapSolveInputPanel from "@/components/snap_solve/SnapSolveInputPanel";

jest.mock("react-markdown", () => {
    const MockMarkdown = ({ children }: { children: React.ReactNode }) => <div>{children}</div>;
    MockMarkdown.displayName = "MockMarkdown";
    return MockMarkdown;
});
jest.mock("remark-math", () => ({}));
jest.mock("rehype-katex", () => ({}));

jest.mock("@/components/snap_solve/SketchCanvas", () => {
    const MockSketchCanvas = forwardRef((_props: unknown, ref: React.Ref<unknown>) => {
        React.useImperativeHandle(ref, () => ({
            clear: jest.fn(),
            hasContent: () => true,
            exportAsFile: async () => new File(["sketch"], "sketch.png", { type: "image/png" }),
        }));
        return <div data-testid="mock-sketch-canvas" />;
    });
    MockSketchCanvas.displayName = "MockSketchCanvas";
    return MockSketchCanvas;
});

describe("SnapSolveInputPanel", () => {
    beforeEach(() => {
        jest.restoreAllMocks();
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ocr_attempt_id: "ocr-1",
                status: "completed",
                extracted_text: "x^2 = 9",
                cache_hit: false,
                billing: { hold_applied: true, hold_amount: 2 },
            }),
        }) as unknown as typeof fetch;
        Object.defineProperty(URL, "createObjectURL", {
            writable: true,
            value: jest.fn(() => "blob:test"),
        });
        Object.defineProperty(URL, "revokeObjectURL", {
            writable: true,
            value: jest.fn(),
        });
    });

    afterEach(async () => {
        await act(async () => { });
    });

    test("paste handler converts clipboard image to upload file", async () => {
        render(<SnapSolveInputPanel />);
        const file = new File(["abc"], "clip.png", { type: "image/png" });
        const pasteEvent = new Event("paste", { bubbles: true }) as Event & {
            clipboardData: DataTransfer;
        };
        Object.defineProperty(pasteEvent, "clipboardData", {
            value: {
                items: [
                    {
                        type: "image/png",
                        getAsFile: () => file,
                    },
                ],
            },
        });

        await act(async () => {
            window.dispatchEvent(pasteEvent);
        });

        await waitFor(() => {
            expect(screen.getByText(/Selected:/)).toBeInTheDocument();
        });
    });

    test("image upload extracts questions and renders plain + latex previews above input", async () => {
        const fetchMock = jest
            .fn()
            .mockResolvedValue({
                ok: true,
                json: async () => ({
                    ocr_attempt_id: "ocr-1",
                    status: "completed",
                    extracted_text: "\\\\text{Solve } x^2 = 9",
                    cache_hit: false,
                    billing: { hold_applied: true, hold_amount: 2 },
                }),
            });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "equation.png", { type: "image/png" })] },
            });
        });

        expect(screen.getByRole("button", { name: "Extract" })).toBeInTheDocument();

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        await waitFor(() => {
            expect(screen.getByTestId("snap-image-extract-plain")).toHaveTextContent(/Solve/);
            expect(screen.getByTestId("snap-image-extract-latex")).toHaveTextContent(/Solve/);
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/api/v1/ocr/extract?user_id="),
            expect.objectContaining({ method: "POST" })
        );
    });

    test("uses structured OCR questions and keeps them as separate numbered items", async () => {
        const fetchMock = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ocr_attempt_id: "ocr-structured-1",
                status: "completed",
                extracted_text: "fallback text",
                structured_json: {
                    questions: [
                        { id: "q1", text: "\\sqrt{3x+4}=2", latex: "\\sqrt{3x+4}=2" },
                        { id: "q2", text: "x=2\\sqrt{x-1}", latex: "x=2\\sqrt{x-1}" },
                    ],
                },
                cache_hit: false,
                billing: { hold_applied: true, hold_amount: 2 },
            }),
        });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "multi.png", { type: "image/png" })] },
            });
        });

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        await waitFor(() => {
            expect(screen.getByTestId("snap-image-extract-plain")).toHaveTextContent("1. \\sqrt{3x+4}=2");
            expect(screen.getByTestId("snap-image-extract-plain")).toHaveTextContent("2. x=2\\sqrt{x-1}");
        });

        const questionInput = screen.getByTestId("snap-question-input") as HTMLTextAreaElement;
        expect(questionInput.value).toContain("1) \\sqrt{3x+4}=2");
        expect(questionInput.value).toContain("2) x=2\\sqrt{x-1}");
    });

    test("image mode solves selected extracted questions in one batch call", async () => {
        const fetchMock = jest.fn().mockImplementation(async (input: RequestInfo | URL) => {
            const url = typeof input === "string" ? input : String(input);
            if (url.includes("/api/v1/ocr/extract")) {
                return {
                    ok: true,
                    json: async () => ({
                        ocr_attempt_id: "ocr-structured-2",
                        status: "completed",
                        extracted_text: "fallback text",
                        structured_json: {
                            questions: [
                                { id: "q1", text: "x+1=2", latex: "x+1=2" },
                                { id: "q2", text: "x^2=9", latex: "x^2=9" },
                            ],
                        },
                        cache_hit: false,
                        billing: { hold_applied: true, hold_amount: 2 },
                    }),
                };
            }
            if (url.includes("/api/v1/math/solve_text_batch")) {
                return {
                    ok: true,
                    json: async () => ({
                        ok: true,
                        request_id: "req-batch",
                        attempt_id: "attempt-batch",
                        requested_mode: "free_minimal",
                        schema_name: "solve_free_minimal_v1",
                        response_language: "en",
                        question_count: 2,
                        telemetry: { latency_ms: 10 },
                        solutions: [
                            { question_id: "q1", final_answer: { answer_text: "x=1", answer_latex: "x=1" } },
                            { question_id: "q2", final_answer: { answer_text: "x=3 or x=-3", answer_latex: "x=\\pm 3" } },
                        ],
                    }),
                };
            }
            return {
                ok: true,
                json: async () => ({}),
            };
        });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "multi-solve.png", { type: "image/png" })] },
            });
        });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        await waitFor(() => {
            expect(screen.getByText("Extracted Questions")).toBeInTheDocument();
            expect(screen.getByText("Solve selected questions individually")).toBeInTheDocument();
        });

        await act(async () => {
            fireEvent.click(screen.getByText("Solve selected questions individually"));
        });

        await waitFor(() => {
            expect(screen.getByText("Solved Results")).toBeInTheDocument();
        });

        const solveCalls = fetchMock.mock.calls.filter(
            (call) => typeof call[0] === "string" && call[0].includes("/api/v1/math/solve_text_batch")
        );
        expect(solveCalls).toHaveLength(1);
    });

    test("select all and clear selection controls toggle extracted question selection", async () => {
        const fetchMock = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ocr_attempt_id: "ocr-select-controls",
                status: "completed",
                extracted_text: "fallback text",
                structured_json: {
                    questions: [
                        { id: "q1", text: "x+1=2", latex: "x+1=2" },
                        { id: "q2", text: "x^2=9", latex: "x^2=9" },
                    ],
                },
                cache_hit: false,
                billing: { hold_applied: true, hold_amount: 2 },
            }),
        });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "select-controls.png", { type: "image/png" })] },
            });
        });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        const solveBtn = await screen.findByText("Solve selected questions individually");
        expect(solveBtn).not.toBeDisabled();

        await act(async () => {
            fireEvent.click(screen.getByTestId("snap-clear-selection-btn"));
        });
        expect(solveBtn).toBeDisabled();

        await act(async () => {
            fireEvent.click(screen.getByTestId("snap-select-all-btn"));
        });
        expect(solveBtn).not.toBeDisabled();
    });

    test("supports selecting OpenAI OCR extraction engine", async () => {
        const fetchMock = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ocr_attempt_id: "ocr-2",
                status: "completed",
                extracted_text: "x^2=9",
                cache_hit: false,
                billing: { hold_applied: true, hold_amount: 3 },
            }),
        });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "equation.png", { type: "image/png" })] },
            });
        });
        fireEvent.change(screen.getByRole("combobox"), { target: { value: "openai" } });
        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        const extractCall = fetchMock.mock.calls.find(
            (call) => typeof call[0] === "string" && call[0].includes("/api/v1/ocr/extract")
        );
        expect(extractCall).toBeTruthy();
        const requestInit = (extractCall?.[1] || {}) as RequestInit;
        const form = requestInit.body as FormData;
        expect(form.get("engine")).toBe("openai");
    });

    test("auto engine maps to pix2text for billing-safe extract", async () => {
        const fetchMock = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ocr_attempt_id: "ocr-3",
                status: "completed",
                extracted_text: "x=2",
                cache_hit: false,
                billing: { hold_applied: true, hold_amount: 2 },
            }),
        });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "equation.png", { type: "image/png" })] },
            });
        });
        fireEvent.change(screen.getByRole("combobox"), { target: { value: "auto" } });

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        const extractCall = fetchMock.mock.calls.find(
            (call) => typeof call[0] === "string" && call[0].includes("/api/v1/ocr/extract")
        );
        expect(extractCall).toBeTruthy();
        const requestInit = (extractCall?.[1] || {}) as RequestInit;
        const form = requestInit.body as FormData;
        expect(form.get("engine")).toBe("pix2text");
    });

    test("hides OpenAI engine option when runtime config disables it", async () => {
        const fetchMock = jest
            .fn()
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    local_engine_enabled: true,
                    openai_engine_enabled: false,
                    default_engine: "pix2text",
                }),
            })
            .mockResolvedValue({
                ok: true,
                json: async () => ({
                    ocr_attempt_id: "ocr-4",
                    status: "completed",
                    extracted_text: "x=3",
                    cache_hit: false,
                    billing: { hold_applied: true, hold_amount: 2 },
                }),
            });
        global.fetch = fetchMock as unknown as typeof fetch;

        render(<SnapSolveInputPanel />);
        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith("/api/v1/ocr/engines");
        });

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "equation.png", { type: "image/png" })] },
            });
        });

        expect(screen.queryByRole("option", { name: "OpenAI (gpt-5-mini)" })).not.toBeInTheDocument();
    });

    test("paste handler supports clipboard files image payloads", async () => {
        render(<SnapSolveInputPanel />);
        const file = new File(["abc"], "clip-file.png", { type: "image/png" });
        const pasteEvent = new Event("paste", { bubbles: true }) as Event & {
            clipboardData: DataTransfer;
        };
        Object.defineProperty(pasteEvent, "clipboardData", {
            value: {
                items: [],
                files: [file],
            },
        });

        await act(async () => {
            window.dispatchEvent(pasteEvent);
        });

        await waitFor(() => {
            expect(screen.getByText(/clip-file\.png|Selected:/)).toBeInTheDocument();
        });
    });

    test("clear resets upload, question, result, and error state", async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                answer_markdown: "ok",
                answer_latex: null,
                meta: { mode: "upload", mime: "image/png", latency_ms: 10 },
            }),
        }) as unknown as typeof fetch;

        render(<SnapSolveInputPanel />);
        const input = screen.getByTestId("snap-upload-input") as HTMLInputElement;
        const question = screen.getByTestId("snap-question-input") as HTMLTextAreaElement;
        const submit = screen.getByTestId("snap-submit-btn");
        const clear = screen.getByTestId("snap-clear-btn");
        const file = new File(["img"], "test.png", { type: "image/png" });

        fireEvent.change(input, { target: { files: [file] } });
        fireEvent.change(question, { target: { value: "Find x" } });
        fireEvent.click(submit);

        await waitFor(() => {
            expect(screen.getByText(/Mode:/)).toBeInTheDocument();
        });

        fireEvent.click(clear);

        expect(question.value).toBe("");
        expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument();
        expect(screen.queryByText(/Mode:/)).not.toBeInTheDocument();
    });

    test("submit disabled rules update based on input", () => {
        render(<SnapSolveInputPanel />);
        const submit = screen.getByTestId("snap-submit-btn");
        const question = screen.getByTestId("snap-question-input") as HTMLTextAreaElement;
        const input = screen.getByTestId("snap-upload-input") as HTMLInputElement;

        expect(submit).toBeDisabled();

        fireEvent.change(question, { target: { value: "Explain this" } });
        expect(submit).not.toBeDisabled();

        fireEvent.change(question, { target: { value: "" } });
        expect(submit).toBeDisabled();

        const file = new File(["img"], "test.png", { type: "image/png" });
        fireEvent.change(input, { target: { files: [file] } });
        expect(submit).not.toBeDisabled();
    });

    test("submit works from sketch tab and renders markdown response", async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                answer_markdown: "## Result\n\n$y=x^2$",
                answer_latex: "y=x^2",
                meta: { mode: "sketch", mime: "image/png", latency_ms: 22 },
            }),
        }) as unknown as typeof fetch;

        render(<SnapSolveInputPanel />);
        fireEvent.click(screen.getByTestId("snap-subtab-sketch"));
        fireEvent.change(screen.getByTestId("snap-question-input"), { target: { value: "drawn question" } });
        fireEvent.click(screen.getByTestId("snap-submit-btn"));

        await waitFor(() => {
            expect(screen.getByText(/Mode: sketch/)).toBeInTheDocument();
            expect(screen.getByText(/## Result/)).toBeInTheDocument();
        });
    });

    test("paste listener is detached on unmount", () => {
        const addSpy = jest.spyOn(window, "addEventListener");
        const removeSpy = jest.spyOn(window, "removeEventListener");
        const { unmount } = render(<SnapSolveInputPanel />);
        unmount();
        expect(addSpy).toHaveBeenCalledWith("paste", expect.any(Function));
        expect(removeSpy).toHaveBeenCalledWith("paste", expect.any(Function));
    });
});
