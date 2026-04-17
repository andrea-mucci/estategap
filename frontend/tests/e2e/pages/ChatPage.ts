import type { Page } from "@playwright/test";

export class ChatPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/en/chat");
  }

  async sendMessage(text: string) {
    await this.page.getByTestId("chat-input").fill(text);
    await this.page.getByTestId("chat-send-button").click();
  }

  waitForAssistantResponse() {
    return this.page.getByTestId("chat-message-assistant").last().waitFor();
  }

  clickChip(label: string) {
    return this.page.getByRole("button", { name: label }).click();
  }

  confirmCriteria() {
    return this.page.getByRole("button", { name: /confirm/i }).click();
  }

  getResultCount() {
    return this.page.getByTestId("search-results-count").textContent();
  }

  getStreamedText() {
    return this.page.getByTestId("chat-message-assistant").last().textContent();
  }
}
