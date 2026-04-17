import type { Page } from "@playwright/test";

export async function mockSpeechRecognition(page: Page, transcript = "3 bedroom apartment in Madrid") {
  await page.addInitScript((mockTranscript) => {
    class MockSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "en";
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        setTimeout(() => {
          this.onresult?.({
            results: [
              [
                {
                  transcript: mockTranscript,
                },
              ],
            ],
          });
          this.onend?.();
        }, 100);
      }

      stop() {}
      abort() {}
    }

    const target = window as Window & {
      SpeechRecognition?: unknown;
      webkitSpeechRecognition?: unknown;
    };
    target.SpeechRecognition = MockSpeechRecognition;
    target.webkitSpeechRecognition = MockSpeechRecognition;
  }, transcript);
}
