import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CanvasWorkspace from "@/components/math-canvas/CanvasWorkspace";
import { buildInitialDocumentState, documentReducer } from "@/components/math-canvas/documentModel";

jest.mock("@/components/math-canvas/LatexEditor", () => ({
  __esModule: true,
  default: function MockLatexEditor({
    initialValue,
    onInsert,
    onClose,
  }: {
    initialValue: string;
    onInsert: (latex: string) => void;
    onClose: () => void;
  }) {
    const [value, setValue] = React.useState(initialValue);
    return (
      <div data-testid="mock-latex-editor">
        <textarea
          placeholder="\\frac{d}{dx}(x^2) = 2x"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <button type="button" onClick={() => onInsert(value)}>
          Insert
        </button>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    );
  },
}));

jest.mock("@/components/math-canvas/GraphEditor", () => ({
  __esModule: true,
  default: function MockGraphEditor({
    onInsert,
    onClose,
  }: {
    onInsert: (payload: {
      title: string;
      xLabel: string;
      yLabel: string;
      points: Array<{ x: number; y: number }>;
    }) => void;
    onClose: () => void;
  }) {
    const [value, setValue] = React.useState("y=x");
    return (
      <div data-testid="mock-graph-editor">
        <input
          aria-label="Function input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <button
          type="button"
          onClick={() =>
            onInsert({
              title: value,
              xLabel: "x",
              yLabel: "y",
              points: [
                { x: -1, y: -1 },
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ],
            })
          }
        >
          Insert Plot
        </button>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
    );
  },
}));

jest.mock("@/components/math/MathRendererSwitch", () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <span data-testid="mock-math">{content}</span>,
}));

jest.mock("@/components/workspace/VisualRenderer", () => ({
  __esModule: true,
  default: ({ visual }: { visual: Record<string, unknown> }) => (
    <div data-testid="mock-visual">{String(visual.title || "plot")}</div>
  ),
}));

jest.mock("@/components/math-canvas/RichTextElementEditor", () => {
  return {
    __esModule: true,
    default: ({
      initialText,
    }: {
      initialText: string;
    }) => {
      return <div data-testid="mock-rich-editor">{initialText}</div>;
    },
  };
});

function WorkspaceHarness() {
  const [state, dispatch] = React.useReducer(
    documentReducer,
    buildInitialDocumentState([
      {
        id: "page-1",
        blocks: [],
        elements: [],
      },
    ])
  );

  return <CanvasWorkspace sessionId="1" state={state} dispatch={dispatch} />;
}

describe("CanvasWorkspace toolbox", () => {
  beforeAll(() => {
    jest
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockImplementation(
        () =>
          ({
            x: 0,
            y: 0,
            width: 800,
            height: 640,
            top: 0,
            left: 0,
            right: 800,
            bottom: 640,
            toJSON: () => ({}),
          }) as DOMRect
      );
  });

  afterAll(() => {
    jest.restoreAllMocks();
  });

  test.skip("supports math/text/shape/compass/ruler/graph/eraser/palette flows", async () => {
    const { container } = render(<WorkspaceHarness />);
    const canvas = screen.getByTestId("paper-canvas-page-1");

    fireEvent.click(screen.getByRole("button", { name: "Equation (LaTeX)" }));
    fireEvent.change(screen.getByPlaceholderText("\\frac{d}{dx}(x^2) = 2x"), {
      target: { value: "x^2+1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Insert" }));

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="math"]').length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    fireEvent.mouseDown(canvas, { button: 0, clientX: 56, clientY: 64 });

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Block / Highlight" }));
    fireEvent.mouseDown(canvas, { button: 0, clientX: 180, clientY: 180 });
    fireEvent.mouseMove(window, { clientX: 320, clientY: 260 });
    fireEvent.mouseUp(window, { clientX: 320, clientY: 260 });

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="shape"]').length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Compass (Circle/Arc)" }));
    fireEvent.mouseDown(canvas, { button: 0, clientX: 260, clientY: 280 });
    fireEvent.mouseMove(window, { clientX: 320, clientY: 340 });
    fireEvent.mouseUp(window, { clientX: 320, clientY: 340 });

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="circle"]').length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Ruler (Line/Measure)" }));
    fireEvent.mouseDown(canvas, { button: 0, clientX: 220, clientY: 220 });
    fireEvent.mouseMove(window, { clientX: 360, clientY: 250, shiftKey: true });
    fireEvent.mouseUp(window, { clientX: 360, clientY: 250, shiftKey: true });

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="line"]').length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Plot Graph" }));
    fireEvent.change(screen.getByLabelText("Function input"), { target: { value: "y = x" } });
    fireEvent.click(screen.getByRole("button", { name: "Insert Plot" }));

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="plot"]').length).toBe(1);
    });

    const textElement = container.querySelector('[data-element-type="text"]') as HTMLElement;
    fireEvent.mouseDown(textElement, { button: 0, clientX: 120, clientY: 140 });
    fireEvent.click(screen.getByRole("button", { name: "Colors / Style" }));
    fireEvent.change(screen.getByLabelText("Text color"), { target: { value: "#ff0000" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to Selection" }));

    await waitFor(() => {
      const textBody = textElement.querySelector("div");
      expect(textBody?.getAttribute("style") || "").toContain("color");
    });

    const shapeElement = container.querySelector('[data-element-type="shape"]') as HTMLElement;
    fireEvent.click(screen.getByRole("button", { name: "Eraser" }));
    fireEvent.mouseDown(shapeElement, { button: 0, clientX: 200, clientY: 200 });

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="shape"]').length).toBe(0);
    });
  });

  test.skip("supports copy/cut/paste and undo/redo controls", async () => {
    const { container } = render(<WorkspaceHarness />);
    const canvas = screen.getByTestId("paper-canvas-page-1");

    fireEvent.click(screen.getByRole("button", { name: "Text" }));
    fireEvent.mouseDown(canvas, { button: 0, clientX: 80, clientY: 82 });

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(1);
    });

    const textElement = container.querySelector('[data-element-type="text"]') as HTMLElement;
    fireEvent.mouseDown(textElement, { button: 0, clientX: 100, clientY: 100 });

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    fireEvent.click(screen.getByRole("button", { name: "Paste" }));

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(2);
    });

    fireEvent.click(screen.getByRole("button", { name: "Cut" }));

    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(2);
    });

    fireEvent.click(screen.getByRole("button", { name: "Redo" }));
    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(1);
    });

    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(2);
    });

    fireEvent.keyDown(window, { key: "y", ctrlKey: true });
    await waitFor(() => {
      expect(container.querySelectorAll('[data-element-type="text"]').length).toBe(1);
    });
  });

  test("exposes tooltip titles + aria labels on toolbar icons", () => {
    render(<WorkspaceHarness />);
    const textButton = screen.getByRole("button", { name: "Text" });
    const graphButton = screen.getByRole("button", { name: "Plot Graph" });
    const pasteButton = screen.getByRole("button", { name: "Paste" });

    expect(textButton).toHaveAttribute("title", "Text");
    expect(graphButton).toHaveAttribute("title", "Plot Graph");
    expect(pasteButton).toHaveAttribute("title", "Paste");
  });

});
