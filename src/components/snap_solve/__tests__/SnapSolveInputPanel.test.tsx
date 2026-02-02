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
        Object.defineProperty(URL, "createObjectURL", {
            writable: true,
            value: jest.fn(() => "blob:test"),
        });
        Object.defineProperty(URL, "revokeObjectURL", {
            writable: true,
            value: jest.fn(),
        });
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
