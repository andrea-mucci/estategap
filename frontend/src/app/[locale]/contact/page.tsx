import { Mail, MessageSquareText } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function ContactPage({
  searchParams,
}: {
  searchParams?: Promise<{ subject?: string }> | {
    subject?: string;
  };
}) {
  const params = searchParams ? await Promise.resolve(searchParams) : undefined;
  const subject = params?.subject ?? "general";

  return (
    <main className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <Card>
        <CardHeader>
          <CardTitle>Talk to the EstateGap team</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5 text-sm leading-7 text-slate-600">
          <p>
            Tell us what you're trying to unlock, and we'll point you to the right plan, integration path, or support workflow.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            <a
              className="rounded-[24px] border border-slate-200 bg-slate-50 p-5 transition hover:border-teal-300 hover:bg-teal-50"
              href={`mailto:sales@estategap.com?subject=${encodeURIComponent(subject)}`}
            >
              <Mail className="h-5 w-5 text-teal-700" />
              <p className="mt-4 font-semibold text-slate-950">sales@estategap.com</p>
              <p className="mt-2">Best for pricing, team onboarding, and API access.</p>
            </a>
            <a
              className="rounded-[24px] border border-slate-200 bg-slate-50 p-5 transition hover:border-teal-300 hover:bg-teal-50"
              href="https://github.com/estategap"
              rel="noreferrer"
              target="_blank"
            >
              <MessageSquareText className="h-5 w-5 text-teal-700" />
              <p className="mt-4 font-semibold text-slate-950">GitHub</p>
              <p className="mt-2">Explore the public project footprint and implementation context.</p>
            </a>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
