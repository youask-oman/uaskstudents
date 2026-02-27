import { extractBatchSolutionsFromSessionMessages, normalizeAssistantMessage } from "@/components/math-canvas/normalizer";
import { SessionMessage } from "@/components/math-canvas/types";

describe("math-canvas normalizer", () => {
  test("parses extreme structured payload with nested solution/plot/verification", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "",
      structured_data: {
        question: {
          raw_text: "x^2 = 9",
          normalized_text: "x^2 = 9",
          assumptions: [],
          constraints: [],
        },
        solution: {
          status: "ok",
          steps: [
            {
              step_id: 1,
              title: "Start",
              explanation: "Move to square root form.",
              math: ["x^2=9"],
              result: null,
              attach_plot_hint: null,
            },
            {
              step_id: 2,
              title: "Solve",
              explanation: "Take square roots.",
              math: ["x=\\pm 3"],
              result: "x=\\pm 3",
              attach_plot_hint: true,
            },
          ],
          final_answer: {
            value: "x = -3 or x = 3",
            latex: "x=\\pm 3",
            units: null,
          },
          key_idea: null,
          notes: [],
        },
        plot: {
          plot_needed: true,
          plot_reason: "Show roots on curve",
          plot_specs: [
            {
              plot_id: "root_plot",
              library: "plotly",
              spec: {
                data: [
                  { type: "scatter", mode: "lines", x: [-3, -2, -1, 0, 1, 2, 3], y: [0, -5, -8, -9, -8, -5, 0] },
                ],
                layout: { title: "y=x^2-9" },
              },
              attach_to_step_id: 2,
            },
          ],
        },
        verification: {
          requested: true,
          status: "verified",
          checks: [
            { check_id: "domain", verdict: "pass", message: "All reals", related_step_id: 1, evidence_math: ["x\\in\\mathbb{R}"] },
            { check_id: "algebra", verdict: "pass", message: "Transform is valid", related_step_id: 2, evidence_math: ["x^2=9"] },
            { check_id: "sub", verdict: "pass", message: "Substitute roots", related_step_id: 2, evidence_math: ["3^2=9"] },
          ],
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 1);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.recognizedLatex).toBe("x^2 = 9");
    expect(solutionItem.payload.steps).toHaveLength(2);
    expect(solutionItem.payload.steps[0].mathLatex).toContain("x^2=9");
    expect(solutionItem.payload.result).toContain("x=\\pm 3");
    expect(solutionItem.payload.verificationChecks).toHaveLength(3);

    const chartItems = normalized.items.filter((item) => item.type === "chart");
    expect(chartItems).toHaveLength(1);
  });

  test("parses free-form markdown steps and latex lines", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: `
**Step 1: Isolate the radical**
\\[
x = 2\\sqrt{x-1}
\\]
**Step 2: Square both sides**
\\[
x^2 = 4(x-1)
\\]
**Step 3: Rearrange**
\\[
x^2-4x+4=0
\\]
**Step 4: Factor**
\\[
(x-2)^2=0
\\]
Final answer: x = 2
      `,
    };

    const normalized = normalizeAssistantMessage(assistant, 1);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.steps.length).toBeGreaterThanOrEqual(4);
    expect(solutionItem.payload.result).toContain("x = 2");
  });

  test("parses direct plotly JSON from assistant text", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: `
\`\`\`json
{
  "data": [
    { "type": "scatter", "mode": "lines", "x": [-2,-1,0,1,2], "y": [4,1,0,1,4] }
  ],
  "layout": {
    "title": "y = x^2",
    "xaxis": { "title": "x" },
    "yaxis": { "title": "y" }
  }
}
\`\`\`
      `,
    };

    const normalized = normalizeAssistantMessage(assistant, 2);
    const chartItems = normalized.items.filter((item) => item.type === "chart");
    expect(chartItems.length).toBeGreaterThanOrEqual(1);
  });

  test("parses malformed plotly-like block from freeform text", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: `
**Plotly JSON:**
\`\`\`json
{
  "data": [
    {"type": " scatter", "x": [1,1.5,2,2.5,3], "y": [0,0.866,1.732,2.291,2.598], "name": "y=2 sqrt(x-1)"}
  ],
  " layout": {" title": "Solution plot"}
}
\`\`\`
      `,
    };

    const normalized = normalizeAssistantMessage(assistant, 3);
    const chartItems = normalized.items.filter((item) => item.type === "chart");
    expect(chartItems.length).toBeGreaterThanOrEqual(1);
  });

  test("fills missing structured final answer from content fallback", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: `
**Step 1: Solve**
\\[
x = 11
\\]
**Final Answer:**
\\[
\\boxed{x = 11}
\\]
      `,
      structured_data: {
        output_format: "freeform",
        extracted_answer: "(2) Sub",
        solution: {
          steps: [{ step_id: 1, title: "Solve", explanation: "Do algebra." }],
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 4);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.result).toContain("x = 11");
  });

  test("keeps prose lines with inline math as explanation text", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: `
Step 1: Verify identity
To verify the identity, we can consider a specific value of \\(x\\). Let's choose \\(x = 0\\):
\\[
\\sin^2(0) + \\cos^2(0) = 1
\\]
      `,
    };

    const normalized = normalizeAssistantMessage(assistant, 5);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.steps[0].explanation).toContain("specific value");
    expect(solutionItem.payload.steps[0].mathLatex).toContain("\\sin^2(0)");
  });

  test("does not inject content-derived plots when solution_doc parse_status is ok", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: `
\`\`\`json
{
  "data": [
    { "type": "scatter", "mode": "lines", "x": [-2,-1,0,1,2], "y": [4,1,0,1,4] }
  ],
  "layout": { "title": "fallback plot" }
}
\`\`\`
      `,
      structured_data: {
        solution_doc: {
          parse_status: "ok",
          recognized_problem: { text: "x^2=4" },
          domain_constraints: [],
          steps: [{ k: 1, title: "Solve Equation", body_markdown: "Use square roots." }],
          plots: [],
          verification: ["Substitute x=2 and x=-2."],
          final_answer: { text: "x = -2 or x = 2", latex: "x \\in \\{-2,2\\}" },
          autocorrect: { applied: false },
          raw_fallback: "",
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 6);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.steps).toHaveLength(1);
    expect(solutionItem.payload.plots || []).toHaveLength(0);
    const chartItems = normalized.items.filter((item) => item.type === "chart");
    expect(chartItems).toHaveLength(0);
  });

  test("parses visuals.plots with plotly_json payload into chart items", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "",
      structured_data: {
        solution: {
          steps: [{ step_id: 1, title: "Graph", explanation: "Render the function." }],
          final_answer: { value: "y=x^2", latex: "y=x^2" },
        },
        visuals: {
          should_visualize: true,
          plots: [
            {
              plot_id: "p1",
              plotly_json: {
                data: [
                  { type: "scatter", mode: "lines", x: [-2, -1, 0, 1, 2], y: [4, 1, 0, 1, 4] },
                ],
                layout: {
                  title: "y = x^2",
                  xaxis: { title: "x" },
                  yaxis: { title: "y" },
                },
              },
            },
          ],
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 8);
    const chartItems = normalized.items.filter((item) => item.type === "chart");
    expect(chartItems).toHaveLength(1);
  });

  test("parses visuals.plots series x/y arrays into chart items", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "",
      structured_data: {
        solution: {
          steps: [{ step_id: 1, title: "Plot", explanation: "Use the generated plot payload." }],
          final_answer: { value: "x = -2, 2", latex: "x=\\pm2" },
        },
        visuals: {
          should_visualize: true,
          plots: [
            {
              title: "Graph of y=x^2-4",
              x_label: "x",
              y_label: "y",
              series: [
                {
                  mode: "markers",
                  name: "roots",
                  x: [-2, 2],
                  y: [0, 0],
                },
              ],
            },
          ],
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 9);
    const chartItems = normalized.items.filter((item) => item.type === "chart");
    expect(chartItems).toHaveLength(1);
  });

  test("parses v2 item blocks, task_results, and final_answer values", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "",
      structured_data: {
        schema_name: "youask_math_openai_v2",
        schema_version: "v2",
        items: [
          {
            question_id: "q1",
            question_text: "Solve x+1=3",
            question_summary: "Linear equation",
            steps: [
              {
                index: 1,
                title: "Solve",
                blocks: [
                  { kind: "text", content: "Subtract 1 from both sides." },
                  { kind: "math", content: "x+1=3 \\Rightarrow x=2" },
                ],
              },
            ],
            results: {
              task_results: [
                {
                  task_index: 1,
                  task_label: "Final result",
                  result_text: "x = 2",
                  result_latex: "x=2",
                },
              ],
            },
            final_answer: {
              answer_text: "x = 2",
              answer_latex: "x=2",
              values: [
                { key: "x", text: "2", latex: "2", number: 2, unit: null },
              ],
            },
            refusal: { is_refusal: false, refusal_code: null, refusal_message: null },
            clarification: { needs_clarification: false, questions: [], note: null },
            classification: { domain: "algebra", detected_tasks: ["solve"] },
            plot: {
              should_visualize: false,
              python_code: null,
              notes: null,
              recipe: {
                kind: "none",
                title: null,
                x_label: null,
                y_label: null,
                x_domain: { min: null, max: null },
                y_domain: { min: null, max: null },
                grid: null,
                axes_lines: null,
                legend: null,
                series: [],
                points: [],
                shapes: [],
                layers: [],
              },
            },
            quality: { confidence: 0.9, assumptions: [], warnings: [] },
            domain_mode: "reals",
            task_count: 1,
            tasks: [{ task_index: 1, task_label: "Solve" }],
          },
        ],
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 10);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.originalProblem).toBe("Solve x+1=3");
    expect(solutionItem.payload.steps.length).toBeGreaterThanOrEqual(2);
    expect(solutionItem.payload.steps[0].explanation).toContain("Subtract 1");
    expect(solutionItem.payload.steps[0].mathLatex).toContain("x=2");
    expect(solutionItem.payload.steps[1].title).toBe("Final result");
    expect(solutionItem.payload.finalAnswer?.values?.[0]?.label).toBe("x");
    expect(solutionItem.payload.finalAnswer?.values?.[0]?.value_latex).toBe("2");
    expect(solutionItem.payload.finalAnswer?.values?.[0]?.value).toBe(2);
  });

  test("parses final-tier minimal item answer_text/answer_latex without final_answer wrapper", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "",
      structured_data: {
        items: [
          {
            question_id: "q1",
            question_text: "Full question text",
            status: "ok",
            answer_text: "Full answer text",
            answer_latex: "x=1",
          },
        ],
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 11);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.originalProblem).toBe("Full question text");
    expect(solutionItem.payload.finalAnswer?.answer_text).toBe("Full answer text");
    expect(solutionItem.payload.finalAnswer?.answer_latex).toBe("x=1");
  });

  test("extracts batch solutions from items[] when solutions[] is absent", () => {
    const messages: SessionMessage[] = [
      {
        role: "assistant",
        content: "",
        structured_data: {
          mode: "batch_text_solve",
          items: [
            {
              question_id: "q1",
              question_text: "Question one full text",
              answer_text: "Answer one",
              answer_latex: "x=1",
            },
            {
              question_id: "q2",
              question_text: "Question two full text",
              answer_text: "Answer two",
              answer_latex: "x=2",
            },
          ],
        },
      },
    ];

    const out = extractBatchSolutionsFromSessionMessages(messages);
    expect(out).toHaveLength(2);
    expect(out[0]?.questionId).toBe("q1");
    expect(out[0]?.questionText).toBe("Question one full text");
    expect(out[0]?.solution.finalAnswer?.answer_text).toBe("Answer one");
    expect(out[1]?.questionId).toBe("q2");
    expect(out[1]?.questionText).toBe("Question two full text");
    expect(out[1]?.solution.finalAnswer?.answer_text).toBe("Answer two");
  });

  test("captures recipe expression for equation-style rendering", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "",
      structured_data: {
        visuals: {
          should_visualize: true,
          plots: [
            {
              title: "Graph of y=x^2-4",
              x_label: "x",
              y_label: "y",
              recipe: { expr: "y=x^2-4" },
              series: [{ x: [-2, 0, 2], y: [0, -4, 0] }],
            },
          ],
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 10);
    const chart = normalized.items.find((item) => item.type === "chart");
    expect(chart).toBeDefined();
    if (!chart || chart.type !== "chart") return;
    expect(chart.payload.expressionLatex).toBe("y=x^2-4");
  });

  test("falls back to content extraction when solution_doc is partial with no meaningful content", () => {
    const assistant: SessionMessage = {
      role: "assistant",
      content: "# Recognized Problem\nSolve x+1=3\n\nFinal Answer: x=2",
      structured_data: {
        solution_doc: {
          parse_status: "partial",
          recognized_problem: { text: "Solve x+1=3" },
          domain_constraints: [],
          steps: [],
          plots: [],
          verification: [],
          final_answer: { text: "", latex: "" },
          autocorrect: { applied: false },
        },
      },
    };

    const normalized = normalizeAssistantMessage(assistant, 7);
    const solutionItem = normalized.items.find((item) => item.type === "math_solution");
    expect(solutionItem).toBeDefined();
    if (!solutionItem || solutionItem.type !== "math_solution") return;
    expect(solutionItem.payload.steps.length).toBeGreaterThan(0);
    expect(solutionItem.payload.result).toContain("x=2");
  });
});
