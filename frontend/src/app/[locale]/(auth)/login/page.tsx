"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale, useTranslations } from "next-intl";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/routing";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") ?? `/${locale}/dashboard`;
  const [errorMessage, setErrorMessage] = useState("");
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  return (
    <main className="grid min-h-screen place-items-center px-4 py-12">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>{t("signInHeading")}</CardTitle>
          <CardDescription>{t("login")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            onSubmit={form.handleSubmit(async (values) => {
              setErrorMessage("");

              const result = await signIn("credentials", {
                email: values.email,
                password: values.password,
                redirect: false,
              });

              if (result?.error) {
                setErrorMessage(t("loginError"));
                return;
              }

              router.push(callbackUrl);
              router.refresh();
            })}
          >
            <div className="space-y-2">
              <Label htmlFor="email">{t("email")}</Label>
              <Input id="email" type="email" {...form.register("email")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t("password")}</Label>
              <Input id="password" type="password" {...form.register("password")} />
              <p className="text-xs text-slate-500">{t("passwordHint")}</p>
            </div>

            {errorMessage ? <p className="text-sm text-rose-600">{errorMessage}</p> : null}

            <Button className="w-full" type="submit">
              {t("submitLogin")}
            </Button>
            <Button
              className="w-full"
              onClick={async () => {
                await signIn("google", { callbackUrl: `/${locale}/dashboard` });
              }}
              type="button"
              variant="outline"
            >
              {t("loginWithGoogle")}
            </Button>
            <p className="text-sm text-slate-500">
              {t("dontHaveAccount")}{" "}
              <Link className="font-semibold text-teal-700" href="/register">
                {t("register")}
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
