import { NextResponse } from "next/server";

const WHISPER_API_URL =
  process.env.WHISPER_API_URL ?? "https://api.openai.com/v1/audio/transcriptions";

export async function POST(request: Request) {
  const apiKey = process.env.WHISPER_API_KEY;

  if (!apiKey) {
    return NextResponse.json(
      { error: "WHISPER_API_KEY is not configured." },
      { status: 500 },
    );
  }

  const incoming = await request.formData();
  const file = incoming.get("file");

  if (!(file instanceof Blob)) {
    return NextResponse.json({ error: "Audio file is required." }, { status: 400 });
  }

  const formData = new FormData();
  formData.append("file", file, "voice-input.webm");
  formData.append("model", "whisper-1");

  const response = await fetch(WHISPER_API_URL, {
    body: formData,
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    method: "POST",
  });

  if (!response.ok) {
    const errorText = await response.text();
    return NextResponse.json({ error: errorText }, { status: response.status });
  }

  const payload = (await response.json()) as { text?: string };
  return NextResponse.json({
    text: payload.text ?? "",
  });
}
