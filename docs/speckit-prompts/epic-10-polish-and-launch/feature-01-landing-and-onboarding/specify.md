# Feature: Landing Page & User Onboarding

## /specify prompt

```
Build the public marketing landing page and new user onboarding flow.

## What
1. Landing page (estategap.com, public, no auth required): hero section with headline + demo video/animation, feature highlights (AI search, deal scoring, multi-country, real-time alerts), pricing table (Free/Basic/Pro/Global/API tiers), testimonials/social proof section, FAQ accordion, CTA buttons to sign up. SEO optimized. Multilingual (EN/ES/FR at minimum).

2. Onboarding flow (shown after first registration): guided 3-step tour. Step 1: "What are you looking for?" → redirect to AI chat for first conversation. Step 2: "Set up your first alert" → show alert creation form pre-filled from chat criteria. Step 3: "Explore the dashboard" → highlight key dashboard features with tooltip overlays. Skippable at any step. Shows subscription upgrade prompt at end.

## Acceptance Criteria
- Landing page Lighthouse: performance > 90, SEO > 95, accessibility > 90
- Page load < 2s on 3G connection
- CTA links correctly to registration flow
- Responsive design (mobile/tablet/desktop)
- Onboarding completes in < 2 minutes
- Skip button works at every step
- First conversation triggers AI chat correctly
```
