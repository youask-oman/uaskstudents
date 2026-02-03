import React, { StrictMode } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import RichTextElementEditor from "@/components/math-canvas/RichTextElementEditor";

type EventName = "blur";

const listeners: Record<EventName, Set<() => void>> = {
  blur: new Set(),
};

const editorState: { text: string; html: string; json: Record<string, unknown> } = {
  text: "",
  html: "<p></p>",
  json: {},
};

const mockEditor = {
  on: (name: EventName, handler: () => void) => {
    listeners[name].add(handler);
  },
  off: (name: EventName, handler: () => void) => {
    listeners[name].delete(handler);
  },
  getText: () => editorState.text,
  getHTML: () => editorState.html,
  getJSON: () => editorState.json,
};

const trigger = (event: EventName) => {
  for (const handler of listeners[event]) handler();
};

jest.mock("@tiptap/react", () => ({
  __esModule: true,
  useEditor: jest.fn(() => mockEditor),
  EditorContent: ({ onKeyDown }: { onKeyDown?: (event: React.KeyboardEvent<HTMLDivElement>) => void }) => (
    <div data-testid="editor-content" tabIndex={0} onKeyDown={onKeyDown} />
  ),
}));

describe("RichTextElementEditor commit guards", () => {
  beforeEach(() => {
    listeners.blur.clear();
    editorState.text = "Initial";
    editorState.html = "<p>Initial</p>";
    editorState.json = { type: "doc" };
  });

  test("does not commit during hydration/mount and commits only on changed content", () => {
    const onCommit = jest.fn();

    render(
      <StrictMode>
        <RichTextElementEditor
          elementId="step-1"
          initialText="Initial"
          initialHtml="<p>Initial</p>"
          initialJson={{ type: "doc" }}
          onCommit={onCommit}
          onActivate={() => {}}
          onRequestClose={() => {}}
        />
      </StrictMode>,
    );

    expect(onCommit).not.toHaveBeenCalled();

    act(() => {
      trigger("blur");
    });
    expect(onCommit).not.toHaveBeenCalled();

    editorState.text = "Changed";
    editorState.html = "<p>Changed</p>";
    editorState.json = { type: "doc", changed: true };

    act(() => {
      trigger("blur");
    });
    expect(onCommit).toHaveBeenCalledTimes(1);

    act(() => {
      trigger("blur");
    });
    expect(onCommit).toHaveBeenCalledTimes(1);
  });

  test("shortcut commit is also deduped when content is unchanged", () => {
    const onCommit = jest.fn();

    render(
      <RichTextElementEditor
        elementId="step-2"
        initialText="Initial"
        initialHtml="<p>Initial</p>"
        initialJson={{ type: "doc" }}
        onCommit={onCommit}
        onActivate={() => {}}
        onRequestClose={() => {}}
      />,
    );

    const editorContent = screen.getByTestId("editor-content");

    fireEvent.keyDown(editorContent, { key: "Enter", ctrlKey: true });
    expect(onCommit).not.toHaveBeenCalled();

    editorState.text = "Updated once";
    editorState.html = "<p>Updated once</p>";
    editorState.json = { type: "doc", updated: true };

    fireEvent.keyDown(editorContent, { key: "Enter", ctrlKey: true });
    expect(onCommit).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(editorContent, { key: "Enter", ctrlKey: true });
    expect(onCommit).toHaveBeenCalledTimes(1);
  });
});

