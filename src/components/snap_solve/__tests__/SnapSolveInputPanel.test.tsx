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
                ok: true,
                is_math_page: true,
                notes: [],
                questions: [],
                cache_hit: false,
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
                    ok: true,
                    is_math_page: true,
                    notes: [],
                    cache_hit: false,
                    questions: [{ id: "q1", text: "\\\\text{Solve } x^2 = 9", confidence: 0.9, is_valid_math: true }],
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
            expect.stringContaining("/api/v1/extract_questions?user_id="),
            expect.objectContaining({ method: "POST" })
        );
    });

    test("supports selecting OpenAI OCR extraction engine", async () => {
        const fetchMock = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ok: true,
                is_math_page: true,
                notes: ["Refined with OpenAI OCR"],
                cache_hit: false,
                questions: [{ id: "q1", text: "x^2=9", confidence: 0.9, is_valid_math: true }],
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

        const requestInit = fetchMock.mock.calls[0][1] as RequestInit;
        const form = requestInit.body as FormData;
        expect(form.get("ocr_engine_choice")).toBe("openai");
    });

    test("auto-retries with OpenAI OCR when Pix2Text output looks garbled", async () => {
        const fetchMock = jest
            .fn()
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    ok: true,
                    is_math_page: true,
                    notes: ["Extracted using Pix2Text (Local)"],
                    questions: [{ id: "q1", text: "## 2x 2Nx", confidence: 0.8, is_valid_math: true }],
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    ok: true,
                    is_math_page: true,
                    notes: ["Extracted with OpenAI OCR vision OCR."],
                    questions: [{ id: "q1", text: "x=2\\sqrt{x-1}", confidence: 0.93, is_valid_math: true }],
                }),
            });
        global.fetch = fetchMock as unknown as typeof fetch;
        render(<SnapSolveInputPanel />);

        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["img"], "equation.png", { type: "image/png" })] },
            });
        });
        fireEvent.change(screen.getByRole("combobox"), { target: { value: "pix2text" } });

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Extract" }));
        });

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledTimes(2);
            expect(screen.getByTestId("snap-image-extract-plain")).toHaveTextContent(/x=2\\sqrt\{x-1\}/);
        });

        const retryForm = (fetchMock.mock.calls[1][1] as RequestInit).body as FormData;
        expect(retryForm.get("ocr_engine_choice")).toBe("openai");
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
