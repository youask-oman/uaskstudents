import { Editor } from "@tiptap/core";
import { applyStyleToEditor, buildRichTextExtensions, getActiveStyle } from "@/components/math-canvas/rich-text/config";

describe("rich text style mapping", () => {
  test("maps Title to h1 and Body to paragraph", () => {
    const editor = new Editor({
      extensions: buildRichTextExtensions(),
      content: "<p>Hello</p>",
    });

    expect(applyStyleToEditor(editor, "title")).toBe(true);
    expect(editor.getHTML()).toContain("<h1");
    expect(editor.getHTML()).toContain("rt-title");
    expect(getActiveStyle(editor)).toBe("title");

    expect(applyStyleToEditor(editor, "body")).toBe(true);
    expect(editor.getHTML()).toContain("<p>");
    expect(getActiveStyle(editor)).toBe("body");
  });
});

