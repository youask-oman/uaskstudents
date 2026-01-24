import React from "react";
import { act, render, screen } from "@testing-library/react";
import ChatPage from "../../app/chat/[id]/page";

jest.mock("better-react-mathjax", () => ({
    MathJax: ({ children }: { children: React.ReactNode }) => (
        <span data-mathjax>{children}</span>
    ),
    MathJaxContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe("Math rendering integration", () => {
    beforeEach(() => {
        Object.defineProperty(window, "localStorage", {
            value: window.localStorage,
            writable: true,
        });
        window.localStorage.setItem("user_id", "1");

        global.fetch = jest.fn(async (input: RequestInfo | URL) => {
            const url = input.toString();
            if (url.includes("/api/v1/sessions/")) {
                return {
                    ok: true,
                    json: async () => ({
                        id: "test-1",
                        title: "Test Session",
                        created_at: new Date().toISOString(),
                        messages: [
                            {
                                role: "assistant",
                                created_at: new Date().toISOString(),
                                structured_data: {
                                    problem: {
                                        original_text: "Find x",
                                        normalized_text: "\\\\sqrt{x+5} = x - 1",
                                    },
                                    classification: { topic: "Algebra", difficulty: "Medium" },
                                    steps: [
                                        {
                                            index: 1,
                                            title: "Simplify",
                                            explanation: "Let \\\\(x=2\\\\) then continue.",
                                            math_latex: "\\\\begin{aligned} x+5 &= 7 \\\\ x &= 2 \\\\end{aligned}",
                                            rules_used: [],
                                        },
                                    ],
                                    final_answer: {
                                        answer_latex: "x=2",
                                        answer_text: "x = 2",
                                    },
                                    verification: {
                                        method: "check",
                                        work_latex: "x+5=7",
                                        conclusion: "ok",
                                    },
                                    visuals: { plots: [] },
                                    quality: { confidence: 0.9, common_mistakes: [], next_practice: [] },
                                    assumptions: [],
                                },
                            },
                        ],
                    }),
                } as Response;
            }
            return { ok: true, json: async () => ({ usage: { questions_count: 0 }, tokens_used: 0 }) } as Response;
        }) as jest.Mock;
    });

    test("renders mixed prose and math without mashed words", async () => {
        const params = Promise.resolve({ id: "test-1" });
        let container: HTMLElement;

        await act(async () => {
            const rendered = render(
                <React.Suspense fallback={<div>loading</div>}>
                    <ChatPage params={params} />
                </React.Suspense>
            );
            container = rendered.container;
        });

        await screen.findAllByText("Simplify");

        const text = container!.textContent || "";
        expect(text).toContain("Let \\\\(x=2\\\\) then continue.");
        expect(text).toContain("\\[");
    });
});
