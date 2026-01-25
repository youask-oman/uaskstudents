import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react";
import SnapSolveV2 from "../SnapSolveV2";
import type { CropArea } from "../snapSolveUtils";

jest.mock("@/components/math/UnifiedMathRenderer", () => ({
    __esModule: true,
    default: ({ content }: { content: string }) => <span>{content}</span>,
}));

jest.mock("../CropWorkspace", () => {
    type CropWorkspaceProps = {
        onCropComplete: (area: CropArea) => void;
    };

    const CropWorkspaceMock = ({ onCropComplete }: CropWorkspaceProps) => {
        React.useEffect(() => {
            onCropComplete({ x: 0, y: 0, width: 100, height: 50 });
        }, [onCropComplete]);
        return <div data-testid="crop-workspace" />;
    };

    return {
        __esModule: true,
        default: CropWorkspaceMock,
    };
});

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
        const fetchResponse = {
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
        };
        global.fetch = jest.fn().mockResolvedValue(fetchResponse) as jest.MockedFunction<typeof global.fetch>;
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
