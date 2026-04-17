import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <Card>
        <CardHeader>
          <CardTitle>Privacy policy</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-7 text-slate-600">
          <p>
            EstateGap stores account information, workflow preferences, and sourcing activity needed to operate the platform. We keep data access scoped to authenticated sessions and retain only what is required for product delivery, billing, and support.
          </p>
          <p>
            Sensitive credentials, third-party portal secrets, and infrastructure access remain separated from end-user content. Contact the team if you need a current data processing overview for procurement or compliance review.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
