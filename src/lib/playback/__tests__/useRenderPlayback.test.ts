import { act, renderHook } from "@testing-library/react";
import { useRenderPlayback } from "@/lib/playback/useRenderPlayback";

describe("useRenderPlayback", () => {
  test("applies events in order and reaches final answer", () => {
    jest.useFakeTimers();
    const events = [
      { id: "1", at_ms: 0, type: "MESSAGE_START" as const, payload: {} },
      { id: "2", at_ms: 0, type: "QUESTION_SET" as const, payload: { text: "Q?" } },
      { id: "3", at_ms: 10, type: "STEP_START" as const, payload: { step_index: 1, title: "Step 1" } },
      { id: "4", at_ms: 20, type: "BLOCK_APPEND_TEXT" as const, payload: { step_index: 1, block_id: "b1", chunk: "hello" } },
      { id: "5", at_ms: 30, type: "FINAL_ANSWER_SET" as const, payload: { answer_text: "done" } },
      { id: "6", at_ms: 40, type: "MESSAGE_END" as const, payload: {} },
    ];
    const { result } = renderHook(() => useRenderPlayback(events));

    act(() => {
      jest.advanceTimersByTime(100);
    });

    expect(result.current.state.questionText).toBe("Q?");
    expect(result.current.state.steps[0]?.blocks[0]?.text).toContain("hello");
    expect(result.current.state.finalAnswer?.answer_text).toBe("done");
    expect(result.current.state.isComplete).toBe(true);
    jest.useRealTimers();
  });
});
