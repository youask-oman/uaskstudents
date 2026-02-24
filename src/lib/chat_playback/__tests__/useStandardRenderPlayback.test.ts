import { act, renderHook } from "@testing-library/react";
import { useStandardRenderPlayback } from "@/lib/chat_playback/useStandardRenderPlayback";
import { StandardRenderEvent } from "@/lib/chat_playback/types";

describe("useStandardRenderPlayback", () => {
  test("skipToEnd renders full state", () => {
    jest.useFakeTimers();
    const events: StandardRenderEvent[] = [
      { id: "1", at_ms: 0, type: "MESSAGE_START", payload: {} },
      { id: "2", at_ms: 5, type: "QUESTION_APPEND_TEXT", payload: { chunk: "Hello" } },
      { id: "3", at_ms: 10, type: "STEP_START", payload: { step_index: 1, title: "Step 1" } },
      { id: "4", at_ms: 15, type: "BLOCK_APPEND_TEXT", payload: { step_index: 1, block_id: "b1", chunk: "world" } },
      { id: "5", at_ms: 20, type: "MESSAGE_END", payload: {} },
    ];

    const { result } = renderHook(() => useStandardRenderPlayback(events));
    act(() => {
      result.current.skipToEnd();
    });

    expect(result.current.state.questionText).toBe("Hello");
    expect(result.current.state.steps[0]?.blocks[0]?.text).toBe("world");
    expect(result.current.state.isComplete).toBe(true);
    jest.useRealTimers();
  });

  test("stop clears playback state", () => {
    jest.useFakeTimers();
    const events: StandardRenderEvent[] = [
      { id: "1", at_ms: 0, type: "MESSAGE_START", payload: {} },
      { id: "2", at_ms: 5, type: "QUESTION_APPEND_TEXT", payload: { chunk: "Hello" } },
      { id: "3", at_ms: 15, type: "MESSAGE_END", payload: {} },
    ];
    const { result } = renderHook(() => useStandardRenderPlayback(events));

    act(() => {
      jest.advanceTimersByTime(20);
    });
    expect(result.current.state.questionText).toBe("Hello");

    act(() => {
      result.current.stop();
    });
    expect(result.current.state.questionText).toBe("");
    expect(result.current.state.steps).toHaveLength(0);
    expect(result.current.state.isComplete).toBe(false);
    jest.useRealTimers();
  });
});

