import { SessionMessage } from "@/components/math-canvas/types";

export const DEMO_BATCH_MESSAGES: SessionMessage[] = [
  {
    id: "demo-batch-user",
    role: "user",
    content: [
      "Solve the selected questions:",
      "- (q1) Solve for x: sqrt(3x + 4) = 2",
      "- (q2) Solve for x: x = 2*sqrt(x - 1)",
      "- (q3) Solve for x: (5x - 2)^(1/3) = 2",
      "- (q4) Simplify: (2x^3 y^2) / (4 x y)",
      "- (q5) Factor completely: x^2 - 5x + 6",
      "- (q6) Solve the system: { 2x + y = 7, x - y = 1 }",
      "- (q7) Find the derivative: d/dx (x^3 * ln(x))",
    ].join("\n"),
    created_at: new Date().toISOString(),
  },
  {
    id: "demo-batch-assistant",
    role: "assistant",
    content: "Batch solve result",
    structured_data: {
      mode: "batch_text_solve",
      requested_mode: "free_minimal",
      response_language: "en",
      question_count: 7,
      solutions: [
        {
          question_id: "q3",
          steps: [{ title: "Cube both sides", explanation: "(5x - 2) = 8" }],
          final_answer: { answer_text: "x = 2", answer_latex: "x=2", values: [] },
        },
        {
          question_id: "q1",
          steps: [{ title: "Square both sides", explanation: "3x + 4 = 4" }],
          final_answer: { answer_text: "x = 0", answer_latex: "x=0", values: [] },
        },
        {
          question_id: "q7",
          steps: [{ title: "Use product rule", explanation: "f' = 3x^2 ln(x) + x^2" }],
          final_answer: {
            answer_text: "d/dx(x^3 ln x) = 3x^2 ln x + x^2",
            answer_latex: "\\frac{d}{dx}(x^3\\ln x)=3x^2\\ln x + x^2",
            values: [],
          },
        },
        {
          question_id: "q2",
          steps: [{ title: "Square and solve", explanation: "x^2 = 4x - 4 => (x-2)^2=0" }],
          final_answer: { answer_text: "x = 2", answer_latex: "x=2", values: [] },
        },
        {
          question_id: "q5",
          steps: [{ title: "Find factors", explanation: "x^2 - 5x + 6 = (x-2)(x-3)" }],
          final_answer: { answer_text: "(x - 2)(x - 3)", answer_latex: "(x-2)(x-3)", values: [] },
        },
        {
          question_id: "q4",
          steps: [{ title: "Cancel common factors", explanation: "2/4=1/2, x^3/x=x^2, y^2/y=y" }],
          final_answer: { answer_text: "(x^2 y)/2", answer_latex: "\\frac{x^2 y}{2}", values: [] },
        },
        {
          question_id: "q6",
          steps: [{ title: "Eliminate y", explanation: "Add equations to get 3x = 8, so x = 8/3" }],
          final_answer: {
            answer_text: "x = 8/3, y = 5/3",
            answer_latex: "x=\\frac{8}{3},\\;y=\\frac{5}{3}",
            values: [],
          },
        },
      ],
    },
    created_at: new Date().toISOString(),
    model_used: "fixture",
  },
];
