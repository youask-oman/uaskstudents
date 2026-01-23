import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react";
import SnapSolveV2 from "../SnapSolveV2";

jest.mock("@/components/math/UnifiedMathRenderer", () => ({
    __esModule: true,
    default: ({ content }: { content: string }) => <span>{content}</span>,
}));

jest.mock("../CropWorkspace", () => ({
    __esModule: true,
    default: ({ onCropComplete }: { onCropComplete: (area: any) => void }) => {
        React.useEffect(() => {
            onCropComplete({ x: 0, y: 0, width: 100, height: 50 });
        }, [onCropComplete]);
        return <div data-testid="crop-workspace" />;
    },
}));

jest.mock("../snapSolveUtils", () => ({
    ...jest.requireActual("../snapSolveUtils"),
    getCroppedImageBlob: jest.fn().mockResolvedValue(new Blob(["x"], { type: "image/jpeg" })),
    buildRequestHash: jest.fn().mockResolvedValue("hash"),
    hashBytes: jest.fn().mockResolvedValue("filehash"),
    loadCache: jest.fn().mockReturnValue({}),
    saveCache: jest.fn(),
}));

describe("SnapSolveV2", () => {
    beforeEach(() => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                ok: true,
                is_math_page: true,
                notes: [],
                questions: [
                    { id: "q1", text: "x + 1", confidence: 0.9, is_valid_math: true }
                ],
                cache_hit: false
            }),
        }) as any;
        global.URL.createObjectURL = jest.fn().mockReturnValue("blob:preview");
        global.URL.revokeObjectURL = jest.fn();
    });

    it("uploads an image and sends OCR request", async () => {
        const onUseText = jest.fn();
        const onSolveText = jest.fn();
        const { container, getByText } = render(
            <SnapSolveV2 onUseText={onUseText} onSolveText={onSolveText} />
        );
        const input = container.querySelector("input[type='file']") as HTMLInputElement;

        const file = new File(["image"], "test.png", { type: "image/png" });
        fireEvent.change(input, { target: { files: [file] } });

        fireEvent.click(getByText("Send to AI"));

        await waitFor(() => {
            expect(global.fetch).toHaveBeenCalled();
        });
    });
});
