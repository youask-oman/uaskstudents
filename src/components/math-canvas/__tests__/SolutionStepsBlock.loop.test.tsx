import React, { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import SolutionStepsBlock from "@/components/math-canvas/SolutionStepsBlock";

const mockEditorRender = jest.fn();

jest.mock("@/components/math/MathJaxRenderer", () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <span data-testid="mock-math">{content}</span>,
}));

jest.mock("@/components/math-canvas/RichTextElementEditor", () => ({
  __esModule: true,
  default: function MockRichTextElementEditor({
    initialText,
    initialHtml,
    initialJson,
    onCommit,
  }: {
    initialText: string;
    initialHtml?: string;
    initialJson?: Record<string, unknown>;
    onCommit: (payload: { text: string; richTextHtml?: string; richTextJson?: Record<string, unknown> }) => void;
  }) {
    mockEditorRender();

    React.useEffect(() => {
      onCommit({
        text: initialText || "",
        richTextHtml: initialHtml,
        richTextJson: initialJson,
      });
    }, [initialHtml, initialJson, initialText, onCommit]);

    return (
      <button
        type="button"
        data-testid="mock-step-editor"
        onClick={() =>
          onCommit({
            text: "Edited explanation",
            richTextHtml: "<p>Edited explanation</p>",
            richTextJson: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Edited explanation" }] }] },
          })
        }
      >
        commit-edit
      </button>
    );
  },
}));

describe("SolutionStepsBlock loop guards", () => {
  beforeEach(() => {
    mockEditorRender.mockClear();
  });

  test("does not trigger a max-depth loop when editor commits unchanged payload on mount", async () => {
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    render(
      <StrictMode>
        <SolutionStepsBlock
          editable
          steps={[{ title: "Step 1", explanation: "Original explanation" }]}
          result="x = 2"
        />
      </StrictMode>,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);

    await waitFor(() => expect(screen.getByTestId("mock-step-editor")).toBeInTheDocument());

    // StrictMode may double-invoke mounts; this should still stay bounded.
    expect(mockEditorRender.mock.calls.length).toBeLessThan(8);
    expect(errorSpy.mock.calls.some((call) => String(call[0]).includes("Maximum update depth exceeded"))).toBe(false);

    errorSpy.mockRestore();
  });

  test("applies one committed edit and saves without repeated commit churn", async () => {
    const onChange = jest.fn();

    render(
      <StrictMode>
        <SolutionStepsBlock
          editable
          steps={[{ title: "Step 1", explanation: "Original explanation" }]}
          result="x = 2"
          onChange={onChange}
        />
      </StrictMode>,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    await waitFor(() => expect(screen.getByTestId("mock-step-editor")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("mock-step-editor"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onChange).toHaveBeenCalledTimes(1);
    const payload = onChange.mock.calls[0][0];
    expect(payload.steps[0].explanation).toBe("Edited explanation");
    expect(payload.steps[0].explanationRichHtml).toContain("Edited explanation");
  });
});
