import Bold from "@tiptap/extension-bold";
import BulletList from "@tiptap/extension-bullet-list";
import type { Editor } from "@tiptap/core";
import Heading from "@tiptap/extension-heading";
import Italic from "@tiptap/extension-italic";
import Link from "@tiptap/extension-link";
import ListItem from "@tiptap/extension-list-item";
import OrderedList from "@tiptap/extension-ordered-list";
import { Table } from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import StarterKit from "@tiptap/starter-kit";
import type { RichTextStyleOption } from "../types";

export interface RichTextStyleOptionItem {
  label: string;
  value: RichTextStyleOption;
}

export const RICH_TEXT_STYLE_OPTIONS: RichTextStyleOptionItem[] = [
  { label: "Title", value: "title" },
  { label: "Subtitle", value: "subtitle" },
  { label: "Heading", value: "heading" },
  { label: "Subheading", value: "subheading" },
  { label: "Section", value: "section" },
  { label: "Subsection", value: "subsection" },
  { label: "Body", value: "body" },
];

const STYLE_TO_HEADING: Record<Exclude<RichTextStyleOption, "body">, { level: 1 | 2 | 3 | 4 | 5 | 6; className?: string }> =
  {
    title: { level: 1, className: "rt-title" },
    subtitle: { level: 2, className: "rt-subtitle" },
    heading: { level: 3 },
    subheading: { level: 4 },
    section: { level: 5 },
    subsection: { level: 6 },
  };

export type RichTextListOption = "none" | "bulleted" | "numbered";

export const RICH_TEXT_LIST_OPTIONS: Array<{ label: string; value: RichTextListOption }> = [
  { label: "Bulleted list", value: "bulleted" },
  { label: "Numbered list", value: "numbered" },
];

const StyledHeading = Heading.extend({
  addAttributes() {
    return {
      ...(this.parent?.() || {}),
      class: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute("class"),
        renderHTML: (attributes: Record<string, unknown>) => {
          if (!attributes.class) return {};
          return { class: String(attributes.class) };
        },
      },
    };
  },
});

export const buildRichTextExtensions = () => [
  StarterKit.configure({
    heading: false,
    bold: false,
    italic: false,
    link: false,
    bulletList: false,
    orderedList: false,
    listItem: false,
  }),
  StyledHeading.configure({ levels: [1, 2, 3, 4, 5, 6] }),
  Bold,
  Italic,
  BulletList,
  OrderedList,
  ListItem,
  Link.configure({
    openOnClick: false,
    autolink: false,
    HTMLAttributes: {
      target: "_blank",
      rel: "noopener noreferrer nofollow",
    },
  }),
  Table.configure({
    resizable: true,
  }),
  TableRow,
  TableHeader,
  TableCell,
];

export const getActiveStyle = (editor: Editor | null): RichTextStyleOption => {
  if (!editor) return "body";
  if (editor.isActive("heading", { level: 1 })) return "title";
  if (editor.isActive("heading", { level: 2 })) return "subtitle";
  if (editor.isActive("heading", { level: 3 })) return "heading";
  if (editor.isActive("heading", { level: 4 })) return "subheading";
  if (editor.isActive("heading", { level: 5 })) return "section";
  if (editor.isActive("heading", { level: 6 })) return "subsection";
  return "body";
};

export const applyStyleToEditor = (editor: Editor, style: RichTextStyleOption): boolean => {
  if (style === "body") {
    if (!editor.can().chain().focus().setParagraph().run()) return false;
    return editor.chain().focus().setParagraph().run();
  }
  const config = STYLE_TO_HEADING[style];
  if (!editor.can().chain().focus().setNode("heading", { level: config.level, class: config.className || null }).run()) {
    return false;
  }
  return editor.chain().focus().setNode("heading", { level: config.level, class: config.className || null }).run();
};

export const getActiveListMode = (editor: Editor | null): RichTextListOption => {
  if (!editor) return "none";
  if (editor.isActive("bulletList")) return "bulleted";
  if (editor.isActive("orderedList")) return "numbered";
  return "none";
};
