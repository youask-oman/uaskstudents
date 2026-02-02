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
            hasContent: () => false,
            exportAsFile: async () => new File(["sketch"], "sketch.png", { type: "image/png" }),
        }));
        return <div data-testid="mock-sketch-canvas" />;
    });
    MockSketchCanvas.displayName = "MockSketchCanvas";
    return MockSketchCanvas;
});

jest.mock("@/components/snap_solve/pdf/PdfCropViewer", () => {
    return function MockPdfCropViewer({
        onCropChange,
    }: {
        onCropChange: (crop: { x: number; y: number; width: number; height: number }, render: { width: number; height: number }) => void;
    }) {
        return (
            <div data-testid="mock-pdf-crop-viewer">
                <button onClick={() => onCropChange({ x: 10, y: 12, width: 50, height: 40 }, { width: 900, height: 1200 })}>
                    set crop
                </button>
            </div>
        );
    };
});

function jsonResponse(payload: unknown, ok = true) {
    return {
        ok,
        json: async () => payload,
    } as unknown as Response;
}

function pageImageResponse() {
    return {
        ok: true,
        blob: async () => new Blob(["png"], { type: "image/png" }),
        headers: {
            get: (key: string) => {
                if (key === "X-Page-Width") return "900";
                if (key === "X-Page-Height") return "1200";
                return null;
            },
        },
    } as unknown as Response;
}

describe("SnapSolveInputPanel PDF mode", () => {
    beforeEach(() => {
        jest.restoreAllMocks();
        Object.defineProperty(URL, "createObjectURL", {
            writable: true,
            value: jest.fn(() => "blob:pdf"),
        });
        Object.defineProperty(URL, "revokeObjectURL", {
            writable: true,
            value: jest.fn(),
        });
    });

    afterEach(async () => {
        await act(async () => { });
    });

    test("PDF upload enters PDF mode and shows page controls", async () => {
        global.fetch = jest
            .fn()
            .mockResolvedValueOnce(jsonResponse({ pdf_id: "pdf_1", page_count: 3 }))
            .mockResolvedValue(pageImageResponse()) as unknown as typeof fetch;

        render(<SnapSolveInputPanel />);
        const input = screen.getByTestId("snap-upload-input") as HTMLInputElement;
        const pdf = new File(["%PDF-1.4"], "sample.pdf", { type: "application/pdf" });
        await act(async () => {
            fireEvent.change(input, { target: { files: [pdf] } });
        });

        await waitFor(() => {
            expect(screen.getByText("Page")).toBeInTheDocument();
            expect(screen.getByDisplayValue("1")).toBeInTheDocument();
            expect(screen.getByText("/ 3")).toBeInTheDocument();
        });
    });

    test("page navigation updates current page", async () => {
        global.fetch = jest
            .fn()
            .mockResolvedValueOnce(jsonResponse({ pdf_id: "pdf_2", page_count: 2 }))
            .mockResolvedValue(pageImageResponse()) as unknown as typeof fetch;

        render(<SnapSolveInputPanel />);
        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["%PDF-1.4"], "nav.pdf", { type: "application/pdf" })] },
            });
        });

        await waitFor(() => expect(screen.getByDisplayValue("1")).toBeInTheDocument());
        await act(async () => {
            fireEvent.click(screen.getByText("Next"));
        });
        expect(screen.getByDisplayValue("2")).toBeInTheDocument();
    });

    test("extract crop sends crop payload", async () => {
        const fetchMock = jest
            .fn()
            .mockResolvedValueOnce(jsonResponse({ pdf_id: "pdf_3", page_count: 1 }))
            .mockResolvedValueOnce(pageImageResponse())
            .mockResolvedValueOnce(jsonResponse({ extracted_questions: [], meta: {} }));
        global.fetch = fetchMock as unknown as typeof fetch;

        render(<SnapSolveInputPanel />);
        await act(async () => {
            fireEvent.change(screen.getByTestId("snap-upload-input"), {
                target: { files: [new File(["%PDF-1.4"], "crop.pdf", { type: "application/pdf" })] },
            });
        });

        await waitFor(() => expect(screen.getByTestId("mock-pdf-crop-viewer")).toBeInTheDocument());
        await act(async () => {
            fireEvent.click(screen.getByText("set crop"));
        });
        await waitFor(() => expect(screen.getByText("Extract Crop")).not.toBeDisabled());
        await act(async () => {
            fireEvent.click(screen.getByText("Extract Crop"));
        });

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                "/api/v1/snap-solve/pdf/extract",
                expect.objectContaining({
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                })
            );
        });

        const extractCall = fetchMock.mock.calls.find((call) => call[0] === "/api/v1/snap-solve/pdf/extract");
        expect(extractCall).toBeDefined();
        const body = JSON.parse((extractCall?.[1] as RequestInit).body as string);
        expect(body.mode).toBe("crop");
        expect(body.crop).toEqual({ x: 10, y: 12, width: 50, height: 40 });
        expect(body.image_render).toMatchObject({ width: 900, height: 1200, scale: 1.5 });
    });
});
