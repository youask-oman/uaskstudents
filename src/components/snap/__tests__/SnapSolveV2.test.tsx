import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react";
import SnapSolveV2 from "../SnapSolveV2";

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
            json: async () => ({ extracted_text: "x + 1", questions: [] }),
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
