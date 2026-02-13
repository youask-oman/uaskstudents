import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ShareSolutionModal from "@/components/share/ShareSolutionModal";

const pushToastMock = jest.fn();

jest.mock("@/components/ui/ToastProvider", () => ({
  useToastOptional: () => ({ pushToast: pushToastMock }),
}));

describe("ShareSolutionModal", () => {
  beforeEach(() => {
    pushToastMock.mockReset();
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: (key: string) => (key === "token" ? "test-token" : null),
      },
      writable: true,
    });
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
    (global.fetch as jest.Mock | undefined)?.mockReset?.();
  });

  test("loads state and can copy generated public link", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          attempt_id: "att-1",
          visibility: "PRIVATE",
          share_url: null,
          revoked: false,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          attempt_id: "att-1",
          visibility: "PUBLIC",
          share_url: "http://localhost:3000/share/abc",
          revoked: false,
        }),
      });
    global.fetch = fetchMock as unknown as typeof fetch;

    render(<ShareSolutionModal open={true} attemptId="att-1" onClose={() => { }} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/shares/attempt/att-1",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
        }),
      );
    });

    const publicLabel = screen.getByText("Public");
    fireEvent.click(publicLabel.closest("button") as HTMLButtonElement);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/shares/attempt/att-1",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Copy Link" }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("http://localhost:3000/share/abc");
      expect(pushToastMock).toHaveBeenCalled();
    });
  });
});
