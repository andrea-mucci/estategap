"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const dataRemovalSchema = z.object({
  name: z.string().trim().min(2, "Name is required."),
  email: z.string().trim().email("A valid email is required."),
  subject_type: z.enum(["agent", "landlord", "other"]),
  description: z.string().trim().min(20, "Please describe the request in at least 20 characters."),
  rights_type: z.enum(["access", "deletion", "portability", "rectification", "objection"]),
});

type DataRemovalValues = z.infer<typeof dataRemovalSchema>;

const COPY: Record<string, { title: string; subtitle: string; success: string }> = {
  de: {
    title: "Datenentfernung anfordern",
    subtitle: "Senden Sie eine DSGVO-Anfrage, wenn Daten eines Maklers, Vermieters oder Dritten entfernt oder geprüft werden sollen.",
    success: "Ihre Anfrage wurde erfasst.",
  },
  en: {
    title: "Request data removal",
    subtitle: "Submit a GDPR request when agent, landlord, or other third-party data should be reviewed or removed.",
    success: "Your request has been recorded.",
  },
  es: {
    title: "Solicitar eliminación de datos",
    subtitle: "Envía una solicitud RGPD cuando debamos revisar o eliminar datos de agentes, propietarios u otros terceros.",
    success: "Hemos recibido tu solicitud.",
  },
  fr: {
    title: "Demander la suppression de données",
    subtitle: "Envoyez une demande RGPD pour faire examiner ou supprimer des données d’agent, de bailleur ou d’un autre tiers.",
    success: "Votre demande a bien été enregistrée.",
  },
  it: {
    title: "Richiedi la rimozione dei dati",
    subtitle: "Invia una richiesta GDPR quando i dati di un agente, locatore o altro soggetto terzo devono essere verificati o rimossi.",
    success: "La richiesta e stata registrata.",
  },
  pt: {
    title: "Pedir remoção de dados",
    subtitle: "Envie um pedido RGPD quando dados de agente, senhorio ou outro terceiro tiverem de ser revistos ou removidos.",
    success: "O pedido foi registado.",
  },
};

function fieldError(error?: string) {
  return error ? <p className="mt-1 text-xs text-rose-600">{error}</p> : null;
}

export default function DataRemovalPage() {
  const locale = useLocale();
  const copy = COPY[locale] ?? COPY.en;
  const [requestID, setRequestID] = useState("");
  const [submitError, setSubmitError] = useState("");

  const form = useForm<DataRemovalValues>({
    resolver: zodResolver(dataRemovalSchema),
    defaultValues: {
      name: "",
      email: "",
      subject_type: "agent",
      description: "",
      rights_type: "deletion",
    },
  });

  return (
    <main className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">
      <Card>
        <CardHeader>
          <CardTitle>{copy.title}</CardTitle>
          <CardDescription>{copy.subtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            onSubmit={form.handleSubmit(async (values) => {
              setRequestID("");
              setSubmitError("");

              const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080").replace(
                /\/$/,
                "",
              );

              const response = await fetch(`${baseUrl}/api/v1/data-removal-requests`, {
                body: JSON.stringify(values),
                headers: {
                  "Content-Type": "application/json",
                },
                method: "POST",
              });

              const payload = (await response.json().catch(() => ({}))) as {
                error?: string;
                request_id?: string;
              };

              if (!response.ok) {
                setSubmitError(payload.error ?? "We could not submit the request.");
                return;
              }

              setRequestID(payload.request_id ?? "");
              form.reset();
            })}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label htmlFor="requester-name">Requester name</Label>
                <Input id="requester-name" {...form.register("name")} />
                {fieldError(form.formState.errors.name?.message)}
              </div>

              <div>
                <Label htmlFor="requester-email">Email</Label>
                <Input id="requester-email" type="email" {...form.register("email")} />
                {fieldError(form.formState.errors.email?.message)}
              </div>

              <div>
                <Label htmlFor="subject-type">Subject type</Label>
                <Select id="subject-type" {...form.register("subject_type")}>
                  <option value="agent">Agent</option>
                  <option value="landlord">Landlord</option>
                  <option value="other">Other</option>
                </Select>
                {fieldError(form.formState.errors.subject_type?.message)}
              </div>

              <div>
                <Label htmlFor="rights-type">GDPR right</Label>
                <Select id="rights-type" {...form.register("rights_type")}>
                  <option value="deletion">Deletion / erasure</option>
                  <option value="access">Access</option>
                  <option value="portability">Portability</option>
                  <option value="rectification">Rectification</option>
                  <option value="objection">Objection</option>
                </Select>
                {fieldError(form.formState.errors.rights_type?.message)}
              </div>
            </div>

            <div>
              <Label htmlFor="request-description">Request details</Label>
              <Textarea
                id="request-description"
                placeholder="Describe the data, listing, or profile that should be removed or reviewed."
                {...form.register("description")}
              />
              {fieldError(form.formState.errors.description?.message)}
            </div>

            {submitError ? <p className="text-sm text-rose-600">{submitError}</p> : null}
            {requestID ? (
              <p className="rounded-3xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                {copy.success} Reference: <span className="font-semibold">{requestID}</span>
              </p>
            ) : null}

            <div className="flex justify-end">
              <Button disabled={form.formState.isSubmitting} type="submit">
                {form.formState.isSubmitting ? "Submitting…" : "Submit request"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
