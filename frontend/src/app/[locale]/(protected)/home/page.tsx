import { ChatInput } from "@/components/chat/ChatInput";
import { ChatPanel } from "@/components/chat/ChatPanel";

export default function HomePage() {
  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <ChatPanel />
      <div className="space-y-4">
        <ChatInput />
      </div>
    </div>
  );
}
