import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <Card>
        <CardHeader>
          <CardTitle>Terms of service</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-7 text-slate-600">
          <p>
            EstateGap is provided as a workflow platform for property sourcing and market analysis. Subscription tiers define available coverage, alert volume, and access to premium capabilities such as exports and integrations.
          </p>
          <p>
            Use of the service must remain consistent with applicable laws, portal terms, and the contractual limits of the plan you are on. Reach out to the team for enterprise, API, or compliance-specific terms.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
