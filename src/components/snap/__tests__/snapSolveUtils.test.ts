import * as utils from "../snapSolveUtils";

describe("getCroppedImageBlob", () => {
    it("returns a jpeg blob", async () => {
        jest.spyOn(utils, "createImage").mockResolvedValue({
            width: 200,
            height: 100,
        } as HTMLImageElement);

        const mockCtx = {
            translate: jest.fn(),
            rotate: jest.fn(),
            drawImage: jest.fn(),
        } as unknown as CanvasRenderingContext2D;

        const originalCreateElement = document.createElement.bind(document);
        jest.spyOn(document, "createElement").mockImplementation((tagName: string) => {
            if (tagName === "canvas") {
                return {
                    width: 0,
                    height: 0,
                    getContext: () => mockCtx,
                    toBlob: (cb: (b: Blob | null) => void) =>
                        cb(new Blob(["x"], { type: "image/jpeg" })),
                } as unknown as HTMLCanvasElement;
            }
            return originalCreateElement(tagName);
        });

        const blob = await utils.getCroppedImageBlob({
            imageSrc: "data:image/jpeg;base64,AA",
            crop: { x: 0, y: 0, width: 100, height: 50 },
            rotation: 0,
            maxEdge: 1600,
            quality: 0.8,
            fullPage: false,
        });

        expect(blob.type).toBe("image/jpeg");
        (utils.createImage as jest.Mock).mockRestore();
        (document.createElement as jest.Mock).mockRestore();
    });
});
