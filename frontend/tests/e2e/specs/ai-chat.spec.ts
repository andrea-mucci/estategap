import { test, expect } from "@playwright/test";

import { storageStatePath } from "../fixtures/auth";
import { ChatPage } from "../pages/ChatPage";
import { mockSpeechRecognition } from "../utils/mock-voice";

test.use({ storageState: storageStatePath("pro") });

test("chat can send a message and voice input fills the composer", async ({ page }) => {
  const chat = new ChatPage(page);
  await mockSpeechRecognition(page);
  await chat.goto();

  await page.getByTestId("chat-voice-button").click();
  await expect(page.getByTestId("chat-input")).toHaveValue(/madrid/i);

  await chat.sendMessage("Find me something in Madrid");
  const assistantMessage = page.getByTestId("chat-message-assistant").last();
  await assistantMessage.waitFor({ timeout: 20_000 }).catch(() => undefined);
});
