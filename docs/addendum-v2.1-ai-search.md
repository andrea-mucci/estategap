# Functional Requirements — Addendum v2.1

**Project:** Undervalued Property Detection & Alert System — Multi-Country Platform  
**Version:** 2.1 (addendum to v2.0)  
**Date:** April 2026  
**Status:** Draft  
**Scope:** This addendum adds three major changes to v2.0:
1. **§12 NEW** — AI Conversational Search ("¿Qué estás buscando?")
2. **§1.9 UPDATED** — Expanded property types (residential + commercial + land + industrial)
3. **§1A.4 UPDATED** — Enhanced multi-language portal support

Requirement IDs use the prefix `FR-AI-` for the new AI section, and `FR-*-xxx AMENDED` for changes to existing requirements.

---

## 12. AI Conversational Search — "¿Qué estás buscando?"

### 12.1 Overview & Concept

- **FR-AI-001** — The system shall provide an **AI-powered conversational search assistant** as the **primary entry point** of the user interface. The main screen shall feature a prominent text input with the placeholder "¿Qué estás buscando?" (localized to the user's language) and a microphone button for voice input.
- **FR-AI-002** — The assistant's purpose is to guide the user from a vague or aspirational idea (e.g., "Busco un loft luminoso cerca de la playa en Barcelona por menos de 300k") to a fully defined, structured search query — through a natural, guided conversation.
- **FR-AI-003** — The conversation shall feel like a brainstorming session with a knowledgeable real estate advisor: the assistant asks clarifying questions, suggests options the user may not have considered, provides market context, and shows visual references to align on style/taste.

### 12.2 Conversation Flow

- **FR-AI-010** — The assistant shall follow a progressive refinement flow. At each step, it shall determine which search dimensions are still undefined and ask about the most impactful ones first. The core dimensions are:

| Priority | Dimension | Example Questions |
|---|---|---|
| 1 | **Intent** | Are you looking to buy, rent, or invest? |
| 2 | **Property type** | Residential (flat, house, villa)? Commercial (office, retail)? Industrial (warehouse, factory)? Land? |
| 3 | **Location** | Which country, city, or area? Do you have a preferred neighborhood? How important is proximity to transit/coast/center? |
| 4 | **Budget** | What's your maximum budget? Are you flexible if the deal is exceptional? |
| 5 | **Size & layout** | How much space do you need? How many bedrooms/bathrooms? Open plan or traditional? |
| 6 | **Condition** | New build, move-in ready, or open to renovation projects? |
| 7 | **Must-haves** | Elevator, parking, terrace, garden, storage, specific orientation, energy rating? |
| 8 | **Nice-to-haves** | Views, natural light, quiet street, community pool, concierge? |
| 9 | **Deal appetite** | Only undervalued deals (high deal score)? Or any matching property? |
| 10 | **Urgency** | Actively buying now, or monitoring the market for the right opportunity? |

- **FR-AI-011** — The assistant shall **not** ask all dimensions sequentially like a form. It shall adapt the conversation dynamically based on the user's initial message. If the user provides a rich description (e.g., "3-bedroom flat in Madrid Centro, max 400k, needs elevator, I want a deal"), the assistant shall acknowledge what it already knows, confirm assumptions, and only ask about missing dimensions.
- **FR-AI-012** — The assistant shall limit itself to **one question per message** (two at most if closely related), to keep the conversation natural and not overwhelming.
- **FR-AI-013** — The assistant shall offer **suggested quick-reply options** (as tappable chips/buttons) alongside each question, so the user can tap instead of typing. Example: "What condition are you open to?" → chips: `New build` `Move-in ready` `Needs renovation` `Any`.
- **FR-AI-014** — The assistant shall be able to handle **multi-turn corrections and changes**. If the user says "Actually, forget Barcelona, let's look at Valencia instead", the assistant shall update the criteria accordingly without restarting.

### 12.3 Visual References & Style Discovery

- **FR-AI-020** — During the conversation, the assistant shall be able to show **reference images** to help the user articulate their taste and style preferences. These images are not listings — they are curated visual examples.
- **FR-AI-021** — Visual references shall be triggered when the user expresses subjective preferences, such as:
  - "I want something modern" → show modern interior/exterior photos
  - "Industrial loft style" → show loft examples
  - "Traditional Mediterranean house" → show villa examples
  - "I want lots of natural light" → show bright, airy interiors
- **FR-AI-022** — The system shall maintain a **visual reference library** organized by tags (style: modern/classic/industrial/minimalist/rustic; feature: terrace/garden/pool/views/open-plan; type: flat/house/loft/penthouse/commercial). Images shall be sourced from royalty-free image libraries or generated.
- **FR-AI-023** — The assistant shall present images as a **horizontal carousel** (3–5 images) within the chat flow, with the question: "Something like this?" or "Which of these is closer to what you have in mind?"
- **FR-AI-024** — The user shall be able to tap/click on an image to say "yes, like this" or "no, not this", and the assistant shall refine its understanding accordingly.
- **FR-AI-025** — In later phases, when the system has accumulated listing photos, the assistant may also show **real listing photos** as examples (e.g., "Properties like this have been selling in your target zone recently").

### 12.4 Voice Input

- **FR-AI-030** — The system shall support **voice input** via a microphone button next to the text input field.
- **FR-AI-031** — Voice input shall use a **speech-to-text (STT) engine** to transcribe the user's spoken message into text before sending it to the AI assistant. Supported STT providers:
  - Web: Web Speech API (browser-native, free) as default, with fallback to Whisper API (OpenAI) or Deepgram for higher accuracy.
  - Mobile: Native platform STT (iOS Speech Framework / Android SpeechRecognizer) as primary, cloud STT as fallback.
- **FR-AI-032** — Voice input shall support all **UI languages** of the platform (at minimum: Spanish, English, French, Italian, German, Portuguese).
- **FR-AI-033** — The transcribed text shall be displayed in the input field before sending, allowing the user to review and edit it.
- **FR-AI-034** — The system shall display a visual indicator (waveform or pulsing dot) while recording, and shall auto-stop after 2 seconds of silence or when the user taps the stop button.

### 12.5 AI Backend (LLM Integration)

- **FR-AI-040** — The conversational AI shall be powered by a **Large Language Model (LLM)** accessed via API. The system shall implement a **provider-agnostic abstraction layer** (`BaseLLMProvider`) supporting multiple backends:
  - **Anthropic Claude** (claude-sonnet or claude-opus) — recommended default for quality and multilingual ability.
  - **OpenAI GPT** (gpt-4o or later) — alternative provider.
  - **Self-hosted open-source** (Llama 3, Mistral, Qwen) via vLLM/Ollama — for cost control at scale.
- **FR-AI-041** — The active LLM provider shall be configurable at the system level via environment variable or admin panel, without code changes.
- **FR-AI-042** — The LLM shall receive a **system prompt** that includes:
  - Role definition: expert real estate advisor and search assistant.
  - Available property types, countries, and features (injected from the portal registry).
  - The current user's language preference.
  - Instructions for the progressive refinement flow (§12.2).
  - Output format instructions: the LLM shall output both the conversational response AND a structured JSON object representing the current search criteria state.
- **FR-AI-043** — The LLM's response shall be parsed into two components:
  1. **Chat message** (natural language) — displayed to the user.
  2. **Criteria state** (structured JSON) — used internally to track which dimensions are defined and which are pending. Example:
  
```json
{
  "status": "refining",
  "confidence": 0.7,
  "criteria": {
    "intent": "buy",
    "property_type": ["flat"],
    "country": "ES",
    "city": "Barcelona",
    "neighborhoods": null,
    "max_price_eur": 300000,
    "min_area_m2": null,
    "bedrooms_min": 2,
    "bedrooms_max": null,
    "condition": ["good", "new_build"],
    "must_have": ["elevator", "natural_light"],
    "nice_to_have": ["terrace", "sea_views"],
    "deal_score_min_tier": null,
    "style_tags": ["modern", "luminous"]
  },
  "pending_dimensions": ["size", "budget_flexibility", "deal_appetite"],
  "suggested_chips": ["50-70 m²", "70-90 m²", "90+ m²", "No preference"],
  "show_visual_references": {
    "trigger": "style_tags",
    "query": "modern luminous apartment interior"
  }
}
```

- **FR-AI-044** — The system shall maintain **conversation state** per session, sending the full conversation history to the LLM on each turn (or using a sliding window for long conversations).
- **FR-AI-045** — The system shall enforce **token limits and cost controls**: max conversation length (e.g., 20 turns), max tokens per response, and a per-user daily API call budget (configurable by subscription tier).

### 12.6 Criteria Finalization & Search Launch

- **FR-AI-050** — The assistant shall determine when enough criteria have been gathered to launch a meaningful search. The minimum viable criteria are: **property type + country/city + at least one of (budget OR area)**.
- **FR-AI-051** — When the criteria are sufficiently defined, the assistant shall present a **summary card** showing all defined criteria in a structured, visual format. Example:

```
┌──────────────────────────────────────────────┐
│  🔍 Your Search Criteria                     │
│                                              │
│  🏠 Type:      Flat (buy)                    │
│  📍 Location:  Barcelona, Eixample/Gràcia    │
│  💰 Budget:    Max €300,000                  │
│  📐 Size:      60–90 m², 2+ bedrooms         │
│  ✅ Must-have: Elevator, balcony             │
│  ⭐ Style:     Modern, luminous              │
│  🎯 Deals:     Tier 1 & 2 only              │
│                                              │
│  [✏️ Edit]  [🚀 Search Now & Create Alert]   │
└──────────────────────────────────────────────┘
```

- **FR-AI-052** — The user shall be able to **edit** any field in the summary card before launching, either by tapping on it (opens inline edit) or by telling the assistant in natural language ("change the budget to 350k").
- **FR-AI-053** — When the user confirms (taps "Search Now & Create Alert"), the system shall simultaneously:
  1. **Execute an immediate search** against the current listing database and display matching results ranked by deal score.
  2. **Create an alert rule** with the defined criteria, set to the user's preferred notification frequency (default: instant for Tier 1–2 deals, daily digest for Tier 3).
- **FR-AI-054** — After showing results, the assistant shall offer follow-up actions:
  - "I found 47 properties. 3 are Tier 1 deals. Want me to show those first?"
  - "Want me to also search in neighboring areas?"
  - "Should I widen the budget to €350k? I see 12 more interesting options."
- **FR-AI-055** — The system shall save the conversation history so the user can return to it later, refine criteria, or start a new branch ("Same but for Valencia instead").

### 12.7 Contextual Intelligence

- **FR-AI-060** — The assistant shall have access to **real-time market context** and use it proactively during the conversation:
  - Zone median prices: "In Eixample, the median is €4,200/m². Your budget of €300k gets you about 70 m² there."
  - Deal availability: "Right now there are 5 Tier 1 deals in Gràcia matching your criteria."
  - Trend data: "Prices in this zone have risen 8% in the last 6 months."
  - Comparative insights: "For that budget, you could get 90 m² in Poble Sec instead of 65 m² in Eixample."
- **FR-AI-061** — The assistant shall be able to **suggest alternative locations** when the user's budget doesn't match their size/quality expectations in the target zone.
- **FR-AI-062** — The assistant shall proactively inform the user about market dynamics that affect their search: "This type of property moves fast in this area — I recommend setting up instant alerts so you don't miss anything."

### 12.8 Property Type Coverage

- **FR-AI-070** — The conversational search shall support **all property types** tracked by the platform:

| Category | Subtypes |
|---|---|
| **Residential** | Flat/apartment, penthouse, duplex, triplex, studio, loft, house, villa, chalet, townhouse, country house (finca/mas/cortijo), mobile home |
| **Land** | Urban land (buildable), rustic land (agricultural), developable land (with planning permission) |
| **Commercial** | Retail premises (local comercial), office space, hotel/hospitality, restaurant/bar premises |
| **Industrial** | Warehouse (nave industrial), factory, logistics/distribution center, workshop |
| **Other** | Garage/parking space, storage unit (trastero), building (entire), share/co-investment |

- **FR-AI-071** — The assistant shall adapt its questions based on property type. Examples:
  - **Residential:** bedrooms, bathrooms, floor, elevator, orientation, community fees.
  - **Commercial:** usable area, frontage (meters of storefront), ceiling height, foot traffic zone, license type.
  - **Industrial:** total area, plot size, loading docks, ceiling height, power supply (kW), access for trucks.
  - **Land:** plot size, buildability index (edificabilidad), urban classification (urbano/urbanizable/rústico), services (water/electricity/sewage).
- **FR-AI-072** — The deal scoring model shall have **type-specific features** for each category (e.g., ceiling height matters for industrial, frontage for retail, buildability for land).

### 12.9 Multi-Language Conversation

- **FR-AI-080** — The assistant shall **detect the user's language automatically** from their first message and respond in the same language throughout the conversation.
- **FR-AI-081** — The assistant shall support conversations in at minimum: Spanish, English, French, Italian, German, Portuguese, Dutch, and Polish.
- **FR-AI-082** — The user shall be able to **switch languages mid-conversation** by simply writing in a different language. The assistant shall adapt seamlessly.
- **FR-AI-083** — Technical real estate terminology shall be correctly handled per language (e.g., "piso" in Spanish = "flat" in English = "appartement" in French = "appartamento" in Italian = "Wohnung" in German).

### 12.10 Conversation Persistence & History

- **FR-AI-090** — Each conversation shall be stored with: user ID, timestamps, full message history, criteria state snapshots at each turn, and the final search/alert created (if any).
- **FR-AI-091** — The user shall be able to view their conversation history and **resume any past conversation** to refine or branch the search.
- **FR-AI-092** — The system shall show a list of the user's recent conversations in a sidebar or drawer, with a preview snippet (e.g., "Flat in Barcelona, <€300k — 3 days ago").
- **FR-AI-093** — The user shall be able to start a **new conversation** at any time from the main input field.

### 12.11 Subscription Tier Integration

- **FR-AI-100** — Conversational search access shall be gated by subscription tier:
  - **Free:** 3 conversations/day, max 10 turns each, no voice input, no visual references.
  - **Basic:** 10 conversations/day, max 20 turns, voice input enabled, visual references enabled.
  - **Pro / Global / API:** Unlimited conversations, unlimited turns, all features.
- **FR-AI-101** — When a free-tier user hits their conversation limit, the system shall prompt them to upgrade, while also offering the traditional filter-based search as a fallback.

---

## Amended Requirements from v2.0

### §1.9 AMENDED — Expanded Property Types in Unified Schema

Replace the `Type` row in the FR-ACQ-040 table with:

| Category | Fields |
|---|---|
| **Type** | Property category (**residential / commercial / industrial / land / other**), property subtype (flat, house, villa, office, warehouse, retail, urban land, rustic land, etc.), furnished status, **commercial license type (if applicable)** |

Add new rows:

| Category | Fields |
|---|---|
| **Commercial-specific** | Frontage (m), ceiling height (m), usable vs. total area, foot traffic zone rating, license/activity type, smoke extraction, accessibility compliance |
| **Industrial-specific** | Plot size, built area, ceiling height, loading docks (count), power supply (kW), three-phase electricity, truck access, bridge crane |
| **Land-specific** | Plot size (m²), buildability index (m² buildable / m² plot), urban classification (urban/developable/rustic), planning status (approved plan Y/N), services available (water/electricity/sewage/gas), slope/topography |

### §1A.4 AMENDED — Enhanced Multi-Language Portal Support

Replace FR-I18N-030 through FR-I18N-033 with expanded versions:

- **FR-I18N-030** — The web application UI shall be fully translated into at minimum: **English, Spanish, French, Italian, German, Portuguese, Dutch, Polish, Swedish, and Greek**. Additional languages may be added via i18n JSON files without code changes.
- **FR-I18N-031** — The system shall use a **standard i18n framework** (e.g., next-intl for Next.js) with externalized string files (one JSON per language), enabling community-contributed translations.
- **FR-I18N-032** — Listing descriptions shall be stored in their original language. The system shall offer **on-demand machine translation** (via DeepL API as primary, Google Translate as fallback) to the user's preferred language. The translated text shall be cached to avoid repeated API calls.
- **FR-I18N-033** — Zone names, property types, condition labels, and feature names shall use a **canonical English taxonomy** internally, mapped to localized display names per language via a translation table.
- **FR-I18N-034** — Email, Telegram, WhatsApp, and push notification templates shall be maintained in all supported UI languages.
- **FR-I18N-035** — The AI conversational assistant shall auto-detect user language and respond accordingly (see §12.9).
- **FR-I18N-036** — The user shall be able to set their preferred language in their profile settings. This setting shall affect: UI language, alert language, default translation target for descriptions, and AI conversation language.
- **FR-I18N-037** — All date/time formatting shall follow the user's locale conventions (e.g., DD/MM/YYYY for Europe, MM/DD/YYYY for US).
- **FR-I18N-038** — Number formatting shall follow locale conventions (e.g., €300.000 in Spain, €300,000 in UK, $300,000 in US).

### §3.1 AMENDED — Model Expansion for Non-Residential

Add to FR-MOD-002:

- **FR-MOD-002A** — For **commercial properties**, the model shall additionally use: frontage, foot traffic estimate, commercial zone type, and ceiling height as features.
- **FR-MOD-002B** — For **industrial properties**, the model shall additionally use: plot size, loading dock count, power supply capacity, ceiling height, and highway access distance.
- **FR-MOD-002C** — For **land**, the model shall additionally use: buildability index, urban classification, services availability, and distance to urban center.
- **FR-MOD-002D** — The system shall train **separate models per property category** (residential, commercial, industrial, land) since the value drivers are fundamentally different.

### §6.1 AMENDED — Updated Subscription Tiers

Replace FR-SUB-002 with:

- **FR-SUB-002** — The system shall support the following subscription tiers:
  - **Free:** Listings >48h old, basic filter search, 1 country, 3 AI conversations/day (10 turns max, no voice/images), no alerts.
  - **Basic (€19/mo):** Real-time listings, 3 alert profiles, 5 zones, 1 country, 10 AI conversations/day (20 turns, voice + images), email + Telegram alerts.
  - **Pro (€49/mo):** Unlimited alerts/zones, up to 3 countries, unlimited AI conversations, all notification channels, deal explainability, comps, portfolio tracker.
  - **Global (€89/mo):** All countries, cross-country comparison, unlimited everything, priority AI (faster model).
  - **API (€149/mo):** Everything in Global + RESTful API access, higher rate limits, bulk exports, webhook alerts.

---

## Appendix F: AI Conversation Examples

### Example 1 — Residential (Spanish user)

```
USER:  Busco un piso luminoso cerca de la playa en Barcelona, 
       menos de 300 mil

AI:    ¡Buena elección! Barcelona tiene varias zonas cerca de la 
       playa. Para afinar la búsqueda:

       ¿Qué tamaño necesitas y cuántas habitaciones?

       [50-70 m²]  [70-90 m²]  [90+ m²]  [Me da igual]

USER:  70-90 con 2 habitaciones mínimo

AI:    Perfecto, 70-90 m² con 2+ habitaciones. En Barceloneta y 
       Poblenou el m² está entre €4.500-5.200, así que con €300k 
       podrías encontrar 58-66 m². 

       Para llegar a 70+ m² cerca de la playa, tienes dos opciones:
       • Subir presupuesto a ~€370k
       • Mirar zonas un poco más alejadas como Sant Martí o 
         Badalona (playa a 10-15 min)

       ¿Qué prefieres?

       [Subir presupuesto]  [Zonas más alejadas]  [Ambas opciones]

USER:  Ambas opciones, y que sea para reformar también

AI:    Genial, abrir a reforma es inteligente — suele haber chollos 
       buenos ahí. ¿Algún requisito imprescindible?

       [Ascensor]  [Terraza]  [Parking]  [Ninguno especial]

USER:  Ascensor sí o sí, terraza sería ideal

AI:    Entendido. Un último detalle: ¿quieres que te avise solo 
       cuando haya verdaderos chollos (precio muy por debajo del 
       mercado) o de cualquier piso que encaje?

       [Solo chollos (Tier 1-2)]  [Todos los que encajen]

USER:  Solo chollos

AI:    ¡Perfecto! Aquí tienes el resumen:

       ┌────────────────────────────────────────┐
       │  🔍 Tu Búsqueda                        │
       │                                        │
       │  🏠 Piso (compra)                      │
       │  📍 Barcelona: Barceloneta, Poblenou,  │
       │     Sant Martí, Badalona               │
       │  💰 Hasta €370,000                     │
       │  📐 70-90 m², 2+ hab                   │
       │  🔧 A reformar incluido                │
       │  ✅ Ascensor obligatorio               │
       │  ⭐ Terraza (deseable)                 │
       │  🎯 Solo Tier 1 y 2 (infravalorados)   │
       │                                        │
       │  [✏️ Editar]  [🚀 Buscar + Alertar]    │
       └────────────────────────────────────────┘
```

### Example 2 — Industrial (English user)

```
USER:  I need a warehouse near Valencia port, at least 500m², 
       with truck access

AI:    Got it — industrial warehouse near Valencia port. 
       A few things to narrow it down:

       What's your budget range?

       [Under €200k]  [€200-500k]  [€500k-1M]  [Over €1M]

USER:  200-500k

AI:    Good range for that area. The Polígono Industrial del 
       Puerto zone has several options. Do you need any of these?

       [Loading docks]  [3-phase power]  [Office space inside]  
       [High ceiling (6m+)]

USER:  Loading docks and high ceiling definitely

AI:    Noted. One more: are you buying to use, or as 
       an investment (to rent out)?

       [Own use]  [Investment/rental]  [Both options]

USER:  Investment

AI:    Smart — industrial rental yields in Valencia port area are 
       around 7-8%, well above residential. Here's your search:

       ┌──────────────────────────────────────────┐
       │  🔍 Your Search                          │
       │                                          │
       │  🏭 Warehouse (buy for investment)        │
       │  📍 Valencia: port industrial zones       │
       │  💰 €200,000 – €500,000                  │
       │  📐 500+ m²                               │
       │  ✅ Loading docks, ceiling 6m+            │
       │  🚛 Truck access required                 │
       │  🎯 All matching (deal score ranked)      │
       │                                          │
       │  [✏️ Edit]  [🚀 Search + Set Alert]       │
       └──────────────────────────────────────────┘
```

### Example 3 — Land with visual references (French user)

```
USER:  Je cherche un terrain pour construire une maison dans 
       le sud de la France

AI:    Beau projet ! Le sud de la France offre beaucoup de 
       possibilités. Pour orienter la recherche :

       Quel département ou zone vous intéresse ?

       [Var/Côte d'Azur]  [Bouches-du-Rhône]  [Hérault]  
       [Pyrénées-Orientales]  [Autre]

USER:  Hérault, pas trop loin de Montpellier

AI:    Bon choix — les terrains autour de Montpellier vont de 
       150€/m² en périphérie à 400€/m² dans les communes 
       proches. Quelle surface de terrain cherchez-vous ?

       [300-500 m²]  [500-1000 m²]  [1000+ m²]

USER:  500-1000 m², je veux du calme avec vue

AI:    Pour du calme avec vue dans l'Hérault, voici des styles 
       qui marchent bien sur ce type de terrain :

       [📷 Carousel: 4 images of houses built on Hérault 
        hillside plots — modern Mediterranean, traditional 
        mas, contemporary villa, rustic stone]

       Quel style vous parle le plus ?

USER:  [taps on modern Mediterranean photo]

AI:    Excellent goût ! Pour une maison méditerranéenne 
       moderne sur 500-1000 m², le terrain seul coûte 
       généralement €80k-180k dans la zone Montpellier +20km.

       Budget pour le terrain ?

       [Moins de €100k]  [€100-150k]  [€150-200k]  [Flexible]

USER:  100-150k

AI:    Voici votre recherche :

       ┌──────────────────────────────────────────┐
       │  🔍 Votre Recherche                      │
       │                                          │
       │  🌍 Terrain constructible (achat)         │
       │  📍 Hérault, rayon 20km de Montpellier   │
       │  💰 €100,000 – €150,000                  │
       │  📐 500 – 1,000 m²                        │
       │  🏗️ Urbanisable, viabilisé souhaité       │
       │  ⭐ Vue dégagée, zone calme              │
       │  🎯 Deals Tier 1-3                        │
       │                                          │
       │  [✏️ Modifier]  [🚀 Chercher + Alerter]   │
       └──────────────────────────────────────────┘
```

---

## Appendix G: AI Conversational Search — Technical Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  [🎤]  "¿Qué estás buscando?"              [Send ➤]  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│           ┌──────────────┴──────────────┐                   │
│           │     Voice?                  │                   │
│           │  ┌────────────────────────┐ │                   │
│           │  │ STT Engine             │ │                   │
│           │  │ (Web Speech / Whisper) │ │                   │
│           │  └──────────┬─────────────┘ │                   │
│           │             │ text          │                   │
│           └─────────────┼───────────────┘                   │
│                         ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Conversation Manager                     │  │
│  │                                                       │  │
│  │  • Maintains session state                            │  │
│  │  • Builds LLM prompt (system + history + context)     │  │
│  │  • Injects market data (zone stats, deal counts)      │  │
│  │  • Parses response → chat message + criteria JSON     │  │
│  │  • Triggers visual references when indicated          │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                  │
│           ┌──────────────┴──────────────┐                   │
│           ▼                             ▼                   │
│  ┌─────────────────┐          ┌──────────────────┐         │
│  │  LLM Provider   │          │  Market Context  │         │
│  │  (configurable) │          │  Service         │         │
│  │                 │          │                  │         │
│  │  • Claude API   │          │  • Zone stats    │         │
│  │  • OpenAI API   │          │  • Deal counts   │         │
│  │  • Self-hosted  │          │  • Price trends  │         │
│  └─────────────────┘          │  • Comparisons   │         │
│                               └──────────────────┘         │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  When criteria complete:                              │  │
│  │                                                       │  │
│  │  criteria JSON ──→ Search Engine ──→ Instant Results  │  │
│  │                ──→ Alert Engine  ──→ Auto-create Rule  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Key integrations:**
- LLM receives: system prompt + conversation history + real-time zone stats + available property types per country.
- LLM returns: natural language response + structured criteria JSON + optional visual reference trigger.
- Criteria JSON is validated against the platform's taxonomy and fed directly to the Search API.
- Alert rule is created from the finalized criteria JSON using the existing `POST /alerts/rules` endpoint.
