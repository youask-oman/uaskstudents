import React from "react";
import { render, screen } from "@testing-library/react";
import SolutionStepsBlock from "@/components/math-canvas/SolutionStepsBlock";

beforeAll(() => {
  class MockResizeObserver {
    observe() {}
    disconnect() {}
    unobserve() {}
  }
  (global as unknown as { ResizeObserver: typeof MockResizeObserver }).ResizeObserver = MockResizeObserver;
});

jest.mock("@/components/math/MathJaxRenderer", () => ({
  __esModule: true,
  default: ({ content }: { content: string }) => <span>{content}</span>,
}));

jest.mock("@/components/math-canvas/TypingPlaybackMessage", () => ({
  __esModule: true,
  default: ({ fallbackContent }: { fallbackContent: string }) => <div>{fallbackContent}</div>,
}));

describe("SolutionStepsBlock duplicate question guard", () => {
  test("renders duplicated question text only once in short paper mode", () => {
    const problemText = "If the patient tests positive on the first test, find the probability they actually have the disease.";
    render(
      <SolutionStepsBlock
        shortPaper
        steps={[]}
        originalProblem={problemText}
        shortSections={[
          {
            heading: "Question Q1",
            label: "Question Q1",
            steps: [{ index: 1, kind: "text", raw: problemText, blocks: [] }],
          },
          {
            heading: "Main",
            label: "Main",
            steps: [{ index: 1, kind: "text", raw: "Use Bayes theorem.", blocks: [] }],
          },
        ]}
        result="0.3896"
      />,
    );

    expect(screen.getAllByText(problemText)).toHaveLength(1);
    expect(screen.getByText("Use Bayes theorem.")).toBeInTheDocument();
  });
});
