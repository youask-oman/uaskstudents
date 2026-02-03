import {
  buildInitialDocumentState,
  createElementId,
  documentReducer,
} from "@/components/math-canvas/documentModel";
import { CanvasElement } from "@/components/math-canvas/types";

const pageId = "page-test";

const buildText = (id: string, text: string): CanvasElement => ({
  id,
  type: "text",
  pageId,
  x: 20,
  y: 30,
  width: 180,
  height: 60,
  zIndex: 1,
  style: {
    color: "#111827",
    strokeColor: "#1f2937",
    strokeWidth: 2,
    fillColor: "transparent",
    fontSize: 16,
  },
  createdAt: 1,
  updatedAt: 1,
  text,
});

describe("documentModel reducer", () => {
  test("supports insert + undo + redo", () => {
    const initial = buildInitialDocumentState([
      {
        id: pageId,
        blocks: [],
        elements: [],
      },
    ]);

    const inserted = documentReducer(initial, {
      type: "INSERT_ELEMENT",
      pageId,
      element: buildText("t-1", "hello"),
    });

    expect(inserted.pages[0].elements).toHaveLength(1);
    expect(inserted.past).toHaveLength(1);

    const undone = documentReducer(inserted, { type: "UNDO" });
    expect(undone.pages[0].elements).toHaveLength(0);

    const redone = documentReducer(undone, { type: "REDO" });
    expect(redone.pages[0].elements).toHaveLength(1);
    expect(redone.pages[0].elements[0].id).toBe("t-1");
  });

  test("supports copy, cut and paste with new IDs", () => {
    const initial = buildInitialDocumentState([
      {
        id: pageId,
        blocks: [],
        elements: [buildText("t-1", "origin")],
      },
    ]);

    const selected = documentReducer(initial, {
      type: "SELECT_ELEMENTS",
      elementIds: ["t-1"],
    });
    const copied = documentReducer(selected, { type: "COPY_SELECTION" });
    expect(copied.clipboard?.elements).toHaveLength(1);

    const pasted = documentReducer(copied, { type: "PASTE_CLIPBOARD" });
    expect(pasted.pages[0].elements).toHaveLength(2);
    const pastedElement = pasted.pages[0].elements.find((entry) => entry.id !== "t-1");
    expect(pastedElement).toBeTruthy();
    expect(pastedElement?.x).toBeGreaterThan(20);

    const reselected = documentReducer(pasted, {
      type: "SELECT_ELEMENTS",
      elementIds: ["t-1"],
    });
    const cut = documentReducer(reselected, { type: "CUT_SELECTION" });
    expect(cut.pages[0].elements.some((entry) => entry.id === "t-1")).toBe(false);
    expect(cut.clipboard?.elements[0].id).toBe("t-1");
  });

  test("applies style updates to selected elements", () => {
    const initial = buildInitialDocumentState([
      {
        id: pageId,
        blocks: [],
        elements: [buildText(createElementId(), "a"), buildText(createElementId(), "b")],
      },
    ]);

    const ids = initial.pages[0].elements.map((entry) => entry.id);
    const styled = documentReducer(initial, {
      type: "APPLY_STYLE",
      elementIds: ids,
      style: {
        color: "#ef4444",
        fontSize: 22,
      },
    });

    styled.pages[0].elements.forEach((element) => {
      expect(element.style.color).toBe("#ef4444");
      expect(element.style.fontSize).toBe(22);
    });
  });
});
