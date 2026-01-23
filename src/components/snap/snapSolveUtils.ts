export type CropArea = {
    x: number;
    y: number;
    width: number;
    height: number;
};

export type CropMeta = {
    pageNumber: number;
    crop: CropArea | null;
    rotation: number;
};

export function clamp(value: number, min: number, max: number) {
    return Math.min(Math.max(value, min), max);
}

export async function hashBytes(data: ArrayBuffer): Promise<string> {
    const digest = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(digest));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function buildRequestHash(fileBytes: ArrayBuffer, meta: CropMeta): Promise<string> {
    const metaBytes = new TextEncoder().encode(JSON.stringify(meta));
    const merged = new Uint8Array(fileBytes.byteLength + metaBytes.byteLength);
    merged.set(new Uint8Array(fileBytes), 0);
    merged.set(metaBytes, fileBytes.byteLength);
    return hashBytes(merged.buffer);
}

export function createImage(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.addEventListener("load", () => resolve(image));
        image.addEventListener("error", reject);
        image.setAttribute("crossOrigin", "anonymous");
        image.src = url;
    });
}

export function getRotatedSize(width: number, height: number, rotation: number) {
    const radians = (rotation * Math.PI) / 180;
    const sin = Math.abs(Math.sin(radians));
    const cos = Math.abs(Math.cos(radians));
    return {
        width: width * cos + height * sin,
        height: width * sin + height * cos,
    };
}

export async function getCroppedImageBlob({
    imageSrc,
    crop,
    rotation,
    maxEdge,
    quality,
    fullPage,
}: {
    imageSrc: string;
    crop: CropArea | null;
    rotation: number;
    maxEdge: number;
    quality: number;
    fullPage: boolean;
}): Promise<Blob> {
    const image = await createImage(imageSrc);
    const { width: rotW, height: rotH } = getRotatedSize(image.width, image.height, rotation);

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas context unavailable");
    canvas.width = rotW;
    canvas.height = rotH;

    ctx.translate(rotW / 2, rotH / 2);
    ctx.rotate((rotation * Math.PI) / 180);
    ctx.translate(-image.width / 2, -image.height / 2);
    ctx.drawImage(image, 0, 0);

    const cropArea = fullPage || !crop
        ? { x: 0, y: 0, width: rotW, height: rotH }
        : crop;

    const scale = Math.min(1, maxEdge / Math.max(cropArea.width, cropArea.height));
    const outputCanvas = document.createElement("canvas");
    outputCanvas.width = Math.round(cropArea.width * scale);
    outputCanvas.height = Math.round(cropArea.height * scale);

    const outCtx = outputCanvas.getContext("2d");
    if (!outCtx) throw new Error("Output canvas unavailable");
    outCtx.drawImage(
        canvas,
        cropArea.x,
        cropArea.y,
        cropArea.width,
        cropArea.height,
        0,
        0,
        outputCanvas.width,
        outputCanvas.height
    );

    return new Promise((resolve, reject) => {
        outputCanvas.toBlob(
            (blob) => {
                if (!blob) {
                    reject(new Error("Failed to create blob"));
                    return;
                }
                resolve(blob);
            },
            "image/jpeg",
            quality
        );
    });
}

export function loadCache(): Record<string, any> {
    try {
        const raw = localStorage.getItem("snapSolveV2Cache");
        return raw ? JSON.parse(raw) : {};
    } catch {
        return {};
    }
}

export function saveCache(cache: Record<string, any>) {
    try {
        localStorage.setItem("snapSolveV2Cache", JSON.stringify(cache));
    } catch {
        // ignore storage errors
    }
}

export function blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const result = reader.result;
            if (typeof result !== "string") {
                reject(new Error("Failed to encode image"));
                return;
            }
            const commaIndex = result.indexOf(",");
            resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
        };
        reader.onerror = () => reject(new Error("Failed to read image"));
        reader.readAsDataURL(blob);
    });
}
