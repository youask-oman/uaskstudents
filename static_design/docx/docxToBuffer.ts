// lib/export/docx/docxToBuffer.ts
import { Packer, Document } from "docx";

export async function docxToBuffer(doc: Document): Promise<Buffer> {
    const uint8 = await Packer.toBuffer(doc);
    return Buffer.from(uint8);
}
