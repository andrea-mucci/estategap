import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "./ChatInput";

vi.mock("@/components/chat/VoiceInput", () => ({
  VoiceInput: () => null,
}));

describe("ChatInput", () => {
  it("submits the typed message on form submission", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<ChatInput onSend={onSend} />);

    await user.type(screen.getByRole("textbox", { name: "placeholder" }), "Find deals in Madrid");
    await user.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() => {
      expect(onSend).toHaveBeenCalledWith("Find deals in Madrid");
    });
  });
});
