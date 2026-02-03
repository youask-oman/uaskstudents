import {
  CanvasBlock,
  CanvasDocumentState,
  CanvasElement,
  CanvasPageData,
  ClipboardPayload,
  DocumentSnapshot,
  ElementStyle,
  SelectionState,
  ToolType,
} from "./types";

const HISTORY_LIMIT = 120;

export const DEFAULT_ELEMENT_STYLE: ElementStyle = {
  color: "#1e293b",
  strokeColor: "#1e293b",
  strokeWidth: 2,
  fillColor: "#eaf2ff",
  fontSize: 18,
};

const cloneElement = (element: CanvasElement): CanvasElement => ({
  ...element,
  style: { ...element.style },
  ...(element.type === "plot" ? { points: element.points.map((point) => ({ ...point })) } : {}),
  ...(element.type === "text" && element.richTextJson
    ? {
        richTextJson: JSON.parse(JSON.stringify(element.richTextJson)) as Record<string, unknown>,
      }
    : {}),
});

const cloneBlock = (block: CanvasBlock): CanvasBlock => {
  if (block.type === "recognition") {
    return { ...block };
  }
  if (block.type === "text") {
    return { ...block };
  }
  return {
    ...block,
    steps: block.steps.map((step) => ({ ...step })),
    verificationChecks: block.verificationChecks
      ? block.verificationChecks.map((check) => ({ ...check }))
      : undefined,
  };
};

const clonePage = (page: CanvasPageData): CanvasPageData => ({
  ...page,
  blocks: page.blocks ? page.blocks.map(cloneBlock) : undefined,
  elements: page.elements.map(cloneElement),
});

const cloneSnapshot = (snapshot: DocumentSnapshot): DocumentSnapshot => ({
  pages: snapshot.pages.map(clonePage),
  activePageId: snapshot.activePageId,
  selection: { elementIds: [...snapshot.selection.elementIds] },
});

export const createPageId = () => `page-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
export const createElementId = () => `el-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

const buildSnapshot = (state: CanvasDocumentState): DocumentSnapshot => ({
  pages: state.pages.map(clonePage),
  activePageId: state.activePageId,
  selection: { elementIds: [...state.selection.elementIds] },
});

const commitSnapshot = (
  state: CanvasDocumentState,
  patch: Partial<Pick<CanvasDocumentState, "pages" | "activePageId" | "selection">>
): CanvasDocumentState => {
  const nextSnapshot: DocumentSnapshot = {
    pages: patch.pages ? patch.pages.map(clonePage) : state.pages.map(clonePage),
    activePageId: patch.activePageId ?? state.activePageId,
    selection: patch.selection ? { elementIds: [...patch.selection.elementIds] } : { elementIds: [...state.selection.elementIds] },
  };
  const previous = buildSnapshot(state);
  const nextPast = [...state.past, previous];
  if (nextPast.length > HISTORY_LIMIT) nextPast.shift();
  return {
    ...state,
    ...nextSnapshot,
    past: nextPast,
    future: [],
  };
};

const findPageIndex = (pages: CanvasPageData[], pageId: string) => pages.findIndex((page) => page.id === pageId);

const updatePage = (
  pages: CanvasPageData[],
  pageId: string,
  updater: (page: CanvasPageData) => CanvasPageData
): CanvasPageData[] => pages.map((page) => (page.id === pageId ? updater(page) : page));

const updateBlockInPage = (
  pages: CanvasPageData[],
  pageId: string,
  blockId: string,
  updater: (block: CanvasBlock) => CanvasBlock
): CanvasPageData[] =>
  updatePage(pages, pageId, (page) => ({
    ...page,
    blocks: (page.blocks || []).map((block) => (block.id === blockId ? updater(block) : block)),
  }));

const removeBlockFromPage = (pages: CanvasPageData[], pageId: string, blockId: string): CanvasPageData[] =>
  updatePage(pages, pageId, (page) => ({
    ...page,
    blocks: (page.blocks || []).filter((block) => block.id !== blockId),
  }));

const updateElementInPages = (
  pages: CanvasPageData[],
  elementId: string,
  updater: (element: CanvasElement) => CanvasElement
): CanvasPageData[] =>
  pages.map((page) => ({
    ...page,
    elements: page.elements.map((element) => (element.id === elementId ? updater(element) : element)),
  }));

const updateElementsInPages = (
  pages: CanvasPageData[],
  elementIds: Set<string>,
  updater: (element: CanvasElement) => CanvasElement
): CanvasPageData[] =>
  pages.map((page) => ({
    ...page,
    elements: page.elements.map((element) => (elementIds.has(element.id) ? updater(element) : element)),
  }));

const removeElementsFromPages = (pages: CanvasPageData[], elementIds: Set<string>): CanvasPageData[] =>
  pages.map((page) => ({
    ...page,
    elements: page.elements.filter((element) => !elementIds.has(element.id)),
  }));

export const createClipboardFromSelection = (
  pages: CanvasPageData[],
  selection: SelectionState,
  activePageId: string
): ClipboardPayload | null => {
  if (selection.elementIds.length === 0) return null;
  const page = pages.find((entry) => entry.id === activePageId);
  if (!page) return null;
  const selected = page.elements.filter((element) => selection.elementIds.includes(element.id));
  if (selected.length === 0) return null;
  return {
    sourcePageId: activePageId,
    elements: selected.map(cloneElement),
  };
};

export const normalizePages = (pages: CanvasPageData[]): CanvasPageData[] =>
  pages.map((page) => ({
    ...page,
    blocks: page.blocks ? [...page.blocks] : undefined,
    elements: page.elements ? [...page.elements] : [],
  }));

export const buildInitialDocumentState = (pages: CanvasPageData[], activeTool: ToolType = "text"): CanvasDocumentState => {
  const normalizedPages = normalizePages(pages);
  const activePageId = normalizedPages[0]?.id || createPageId();
  const safePages =
    normalizedPages.length > 0
      ? normalizedPages
      : [
          {
            id: activePageId,
            blocks: [],
            elements: [],
          },
        ];
  return {
    pages: safePages,
    activePageId,
    activeTool,
    selection: { elementIds: [] },
    clipboard: null,
    past: [],
    future: [],
  };
};

export type DocumentAction =
  | { type: "SET_TOOL"; tool: ToolType }
  | { type: "SET_ACTIVE_PAGE"; pageId: string }
  | { type: "SELECT_ELEMENTS"; elementIds: string[] }
  | { type: "ADD_PAGE"; page?: CanvasPageData; setActive?: boolean }
  | { type: "INSERT_ELEMENT"; pageId: string; element: CanvasElement; select?: boolean }
  | { type: "INSERT_ELEMENTS"; pageId: string; elements: CanvasElement[]; select?: boolean }
  | { type: "UPDATE_ELEMENT"; elementId: string; updater: (element: CanvasElement) => CanvasElement }
  | { type: "MOVE_ELEMENTS"; elementIds: string[]; dx: number; dy: number }
  | { type: "RESIZE_ELEMENT"; elementId: string; width: number; height: number; x?: number; y?: number }
  | { type: "DELETE_ELEMENTS"; elementIds: string[] }
  | {
      type: "SET_TEXT_CONTENT";
      elementId: string;
      text: string;
      richTextHtml?: string;
      richTextJson?: Record<string, unknown>;
    }
  | { type: "SET_MATH_LATEX"; elementId: string; latexRaw: string }
  | { type: "UPDATE_BLOCK"; pageId: string; blockId: string; updater: (block: CanvasBlock) => CanvasBlock }
  | { type: "DELETE_BLOCK"; pageId: string; blockId: string }
  | { type: "APPLY_STYLE"; elementIds: string[]; style: Partial<ElementStyle> }
  | { type: "SET_CLIPBOARD"; clipboard: ClipboardPayload | null }
  | { type: "COPY_SELECTION" }
  | { type: "CUT_SELECTION" }
  | { type: "PASTE_CLIPBOARD"; targetPageId?: string; offset?: { x: number; y: number } }
  | { type: "UNDO" }
  | { type: "REDO" }
  | { type: "RESET"; state: CanvasDocumentState };

export const documentReducer = (state: CanvasDocumentState, action: DocumentAction): CanvasDocumentState => {
  switch (action.type) {
    case "SET_TOOL":
      return { ...state, activeTool: action.tool };
    case "SET_ACTIVE_PAGE":
      return { ...state, activePageId: action.pageId, selection: { elementIds: [] } };
    case "SELECT_ELEMENTS":
      return { ...state, selection: { elementIds: [...action.elementIds] } };
    case "SET_CLIPBOARD":
      return { ...state, clipboard: action.clipboard };
    case "ADD_PAGE": {
      const nextPage = action.page ?? { id: createPageId(), blocks: [], elements: [] };
      const nextPages = [...state.pages, clonePage(nextPage)];
      const next = commitSnapshot(state, {
        pages: nextPages,
        activePageId: action.setActive === false ? state.activePageId : nextPage.id,
        selection: { elementIds: [] },
      });
      return next;
    }
    case "INSERT_ELEMENT": {
      const nextPages = updatePage(state.pages, action.pageId, (page) => ({
        ...page,
        elements: [...page.elements, cloneElement(action.element)],
      }));
      return commitSnapshot(state, {
        pages: nextPages,
        activePageId: action.pageId,
        selection: { elementIds: action.select === false ? state.selection.elementIds : [action.element.id] },
      });
    }
    case "INSERT_ELEMENTS": {
      const nextPages = updatePage(state.pages, action.pageId, (page) => ({
        ...page,
        elements: [...page.elements, ...action.elements.map(cloneElement)],
      }));
      const selectedIds = action.select === false ? state.selection.elementIds : action.elements.map((entry) => entry.id);
      return commitSnapshot(state, {
        pages: nextPages,
        activePageId: action.pageId,
        selection: { elementIds: selectedIds },
      });
    }
    case "UPDATE_ELEMENT": {
      const nextPages = updateElementInPages(state.pages, action.elementId, (element) => {
        const updated = action.updater(element);
        return { ...updated, updatedAt: Date.now() };
      });
      return commitSnapshot(state, { pages: nextPages });
    }
    case "MOVE_ELEMENTS": {
      const ids = new Set(action.elementIds);
      if (ids.size === 0) return state;
      const nextPages = updateElementsInPages(state.pages, ids, (element) => ({
        ...element,
        x: Math.round((element.x + action.dx) * 10) / 10,
        y: Math.round((element.y + action.dy) * 10) / 10,
        updatedAt: Date.now(),
      }));
      return commitSnapshot(state, { pages: nextPages });
    }
    case "RESIZE_ELEMENT": {
      const nextPages = updateElementInPages(state.pages, action.elementId, (element) => ({
        ...element,
        width: Math.max(24, action.width),
        height: Math.max(24, action.height),
        x: action.x ?? element.x,
        y: action.y ?? element.y,
        updatedAt: Date.now(),
      }));
      return commitSnapshot(state, { pages: nextPages });
    }
    case "DELETE_ELEMENTS": {
      const ids = new Set(action.elementIds);
      if (ids.size === 0) return state;
      const nextPages = removeElementsFromPages(state.pages, ids);
      return commitSnapshot(state, {
        pages: nextPages,
        selection: { elementIds: [] },
      });
    }
    case "SET_TEXT_CONTENT": {
      const nextPages = updateElementInPages(state.pages, action.elementId, (element) =>
        element.type === "text"
          ? {
              ...element,
              text: action.text,
              richTextHtml: action.richTextHtml,
              richTextJson: action.richTextJson,
              updatedAt: Date.now(),
            }
          : element
      );
      return commitSnapshot(state, { pages: nextPages });
    }
    case "SET_MATH_LATEX": {
      const nextPages = updateElementInPages(state.pages, action.elementId, (element) =>
        element.type === "math" ? { ...element, latexRaw: action.latexRaw, updatedAt: Date.now() } : element
      );
      return commitSnapshot(state, { pages: nextPages });
    }
    case "UPDATE_BLOCK": {
      const nextPages = updateBlockInPage(state.pages, action.pageId, action.blockId, action.updater);
      return commitSnapshot(state, { pages: nextPages });
    }
    case "DELETE_BLOCK": {
      const nextPages = removeBlockFromPage(state.pages, action.pageId, action.blockId);
      return commitSnapshot(state, { pages: nextPages });
    }
    case "APPLY_STYLE": {
      const ids = new Set(action.elementIds);
      if (ids.size === 0) return state;
      const nextPages = updateElementsInPages(state.pages, ids, (element) => ({
        ...element,
        style: {
          ...element.style,
          ...action.style,
        },
        updatedAt: Date.now(),
      }));
      return commitSnapshot(state, { pages: nextPages });
    }
    case "COPY_SELECTION": {
      const clipboard = createClipboardFromSelection(state.pages, state.selection, state.activePageId);
      return { ...state, clipboard };
    }
    case "CUT_SELECTION": {
      const clipboard = createClipboardFromSelection(state.pages, state.selection, state.activePageId);
      if (!clipboard) return state;
      const ids = new Set(clipboard.elements.map((element) => element.id));
      const nextPages = removeElementsFromPages(state.pages, ids);
      return commitSnapshot(
        {
          ...state,
          clipboard,
        },
        {
          pages: nextPages,
          selection: { elementIds: [] },
        }
      );
    }
    case "PASTE_CLIPBOARD": {
      if (!state.clipboard || state.clipboard.elements.length === 0) return state;
      const targetPageId = action.targetPageId ?? state.activePageId;
      const pageIndex = findPageIndex(state.pages, targetPageId);
      if (pageIndex < 0) return state;
      const offset = action.offset ?? { x: 12, y: 12 };
      const now = Date.now();
      const clones = state.clipboard.elements.map((element, index) => ({
        ...cloneElement(element),
        id: createElementId(),
        pageId: targetPageId,
        x: element.x + offset.x + index * 2,
        y: element.y + offset.y + index * 2,
        createdAt: now + index,
        updatedAt: now + index,
        zIndex: state.pages[pageIndex].elements.length + index + 1,
      }));
      const nextPages = updatePage(state.pages, targetPageId, (page) => ({
        ...page,
        elements: [...page.elements, ...clones],
      }));
      return commitSnapshot(state, {
        pages: nextPages,
        activePageId: targetPageId,
        selection: { elementIds: clones.map((element) => element.id) },
      });
    }
    case "UNDO": {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1];
      const remainingPast = state.past.slice(0, -1);
      const currentSnapshot = buildSnapshot(state);
      return {
        ...state,
        ...cloneSnapshot(previous),
        past: remainingPast,
        future: [currentSnapshot, ...state.future],
      };
    }
    case "REDO": {
      if (state.future.length === 0) return state;
      const [nextSnapshot, ...remainingFuture] = state.future;
      const currentSnapshot = buildSnapshot(state);
      const nextPast = [...state.past, currentSnapshot];
      if (nextPast.length > HISTORY_LIMIT) nextPast.shift();
      return {
        ...state,
        ...cloneSnapshot(nextSnapshot),
        past: nextPast,
        future: remainingFuture,
      };
    }
    case "RESET":
      return action.state;
    default:
      return state;
  }
};
