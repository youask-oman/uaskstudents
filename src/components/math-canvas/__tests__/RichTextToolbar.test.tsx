import React from "react";
import { Editor } from "@tiptap/core";
import { fireEvent, render, screen } from "@testing-library/react";
import RichTextToolbar from "@/components/math-canvas/RichTextToolbar";
import { buildRichTextExtensions } from "@/components/math-canvas/rich-text/config";

const buildEditor = () =>
  new Editor({
    extensions: buildRichTextExtensions(),
    content: "<p>Hello world</p>",
    editable: true,
  });

describe("RichTextToolbar integration", () => {
  test("disables controls when no active text editor", () => {
    render(
      <RichTextToolbar
        activeEditor={null}
        canExport={false}
        exportingDocx={false}
        savingVersion={false}
        onExportPdf={() => { }}
        onExportDocx={() => { }}
        onSaveVersion={() => { }}
        onAddPage={() => { }}
        onDeletePage={() => { }}
        canDeletePage={false}
        onInsertImage={() => { }}
      />
    );
    expect(screen.getByLabelText("Bold")).toBeDisabled();
  });

  test("applies style, bold/italic, list, link, and table commands", () => {
    const editor = buildEditor();
    editor.commands.focus();
    editor.commands.setTextSelection({ from: 1, to: 5 });
    render(
      <RichTextToolbar
        activeEditor={editor}
        canExport={false}
        exportingDocx={false}
        savingVersion={false}
        onExportPdf={() => { }}
        onExportDocx={() => { }}
        onSaveVersion={() => { }}
        onAddPage={() => { }}
        onDeletePage={() => { }}
        canDeletePage={true}
        onInsertImage={() => { }}
      />
    );


    fireEvent.click(screen.getByLabelText("Bold"));
    expect(editor.isActive("bold")).toBe(true);

    fireEvent.click(screen.getByLabelText("Italic"));
    expect(editor.isActive("italic")).toBe(true);

    fireEvent.click(screen.getByLabelText("Bulleted list"));
    expect(editor.getHTML()).toContain("<ul>");

    fireEvent.click(screen.getByLabelText("Link"));
    fireEvent.change(screen.getByPlaceholderText("https://example.com"), {
      target: { value: "uask.ai/docs" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(editor.getAttributes("link").href).toMatch(/^https:\/\/uask\.ai\/docs/);

    fireEvent.click(screen.getByLabelText("Table"));
    fireEvent.click(screen.getByRole("button", { name: "Insert 3x3 table" }));
    expect(editor.getHTML()).toContain("<table");
  });
});
