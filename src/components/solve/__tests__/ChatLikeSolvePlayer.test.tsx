import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import ChatLikeSolvePlayer from "@/components/solve/ChatLikeSolvePlayer";

jest.mock("@/components/math/UnifiedMathRenderer", () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <span data-testid="math-render">{content}</span>,
}));

jest.mock("@/components/math/MarkdownMathContent", () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <span data-testid="md-render">{content}</span>,
}));

jest.mock("@/components/solve/BlockRenderer", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/solve/TypingIndicator", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/plot/PlotCard", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/code/CodeBlock", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/lib/playback/useRenderPlayback", () => ({
  __esModule: true,
  useRenderPlayback: () => ({
    state: {
      questionText: "Angles of elevation from A,B,C are 30\\u00B0,45\\u00B0,60\\u00B0. Find AB:BC.",
      steps: [],
      finalAnswer: {
        answer_text: "AB:BC = \\u221A3 : 1 option(c)",
        answer_latex: "\\sqrt{3}:1",
        values: [
          {
            label: "AB:BC",
            value: "\\sqrt{3};:1",
            value_latex: "\\sqrt{3}:1",
          },
        ],
      },
      plot: null,
      pythonCode: "",
      isTyping: false,
      isComplete: true,
      activeStepIndex: null,
    },
    replay: jest.fn(),
    skipToEnd: jest.fn(),
  }),
}));

describe("ChatLikeSolvePlayer math rendering decode", () => {
  it("decodes escaped math text and routes it through math renderer", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ render_events: [] }),
    } as Response);

    render(<ChatLikeSolvePlayer messageId="msg-1" fallbackContent="fallback" />);

    await waitFor(() => {
      expect(screen.getAllByTestId("math-render").length).toBeGreaterThan(0);
    });

    const rendered = screen.getAllByTestId("math-render").map((node) => node.textContent || "");
    expect(rendered.join(" ")).toContain("√3");
    expect(rendered.join(" ")).not.toContain("\\u221A3");
  });
});

