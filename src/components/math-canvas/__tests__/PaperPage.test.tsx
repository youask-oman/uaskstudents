import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PaperPage from "@/components/math-canvas/PaperPage";
import { CanvasPageData } from "@/components/math-canvas/types";

const buildTextPage = (): CanvasPageData => ({
  id: "page-1",
  blocks: [],
  elements: [
    {
      id: "text-1",
      type: "text",
      pageId: "page-1",
      x: 40,
      y: 40,
      width: 260,
      height: 90,
      zIndex: 1,
      style: {
        color: "#000000",
        strokeColor: "#000000",
        strokeWidth: 1,
        fillColor: "transparent",
        fontSize: 16,
      },
      createdAt: 1,
      updatedAt: 1,
      text: "Double-click to edit",
    },
  ],
});

const baseProps = (page: CanvasPageData) => ({
  page,
  index: 0,
  active: true,
  activeTool: "text" as const,
  selectedElementIds: [],
  onActivate: jest.fn(),
  onSelectElements: jest.fn(),
  onInsertElement: jest.fn(),
  onMoveElements: jest.fn(),
  onResizeElement: jest.fn(),
  onDeleteElements: jest.fn(),
  onRequestMathEdit: jest.fn(),
  onCommitText: jest.fn(),
  onUpdateBlock: jest.fn(),
  onDeleteBlock: jest.fn(),
});

describe("PaperPage text editing", () => {
  test("opens inline text editor when text tool clicks an existing text element", () => {
    const page = buildTextPage();
    const props = baseProps(page);
    const { container } = render(<PaperPage {...props} />);

    const textElement = container.querySelector("[data-element-id='text-1']");
    expect(textElement).not.toBeNull();
    fireEvent.pointerDown(textElement as Element, { button: 0, clientX: 120, clientY: 120 });

    expect(screen.getByDisplayValue("Double-click to edit")).toBeInTheDocument();
  });

  test("double-click still opens editor when not in text tool", () => {
    const page = buildTextPage();
    const props = { ...baseProps(page), activeTool: "math" as const };
    const { container } = render(<PaperPage {...props} />);

    const textElement = container.querySelector("[data-element-id='text-1']");
    expect(textElement).not.toBeNull();
    fireEvent.doubleClick(textElement as Element);

    expect(screen.getByDisplayValue("Double-click to edit")).toBeInTheDocument();
  });
});
