import fs from "node:fs";
import path from "node:path";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { routing } from "@/i18n/routing";

type PrivacyPageProps = {
  params: Promise<{ locale: string }>;
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

function loadPrivacyMarkdown(locale: string) {
  const contentDir = path.join(process.cwd(), "src", "content", "privacy");
  const preferredPath = path.join(contentDir, `${locale}.md`);
  const fallbackPath = path.join(contentDir, "en.md");

  if (fs.existsSync(preferredPath)) {
    return fs.readFileSync(preferredPath, "utf8");
  }

  return fs.readFileSync(fallbackPath, "utf8");
}

export default async function PrivacyPage({ params }: PrivacyPageProps) {
  const { locale } = await params;
  const content = loadPrivacyMarkdown(locale);

  return (
    <main className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <Card>
        <CardHeader>
          <CardTitle>Privacy policy</CardTitle>
        </CardHeader>
        <CardContent>
          <article className="prose prose-slate max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </article>
        </CardContent>
      </Card>
    </main>
  );
}
