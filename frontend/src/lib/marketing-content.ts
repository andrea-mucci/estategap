import type { AppLocale } from "@/i18n/routing";

type MarketingMessages = {
  landing: {
    meta: {
      title: string;
      description: string;
    };
    nav: {
      login: string;
      cta: string;
    };
    hero: {
      eyebrow: string;
      headline: string;
      subheadline: string;
      primaryCta: string;
      secondaryCta: string;
      proofPoints: string[];
      cardLabel: string;
      cardTitle: string;
      cardMetricLabel: string;
      cardMetricValue: string;
      cardSecondaryMetricLabel: string;
      cardSecondaryMetricValue: string;
    };
    features: {
      eyebrow: string;
      title: string;
      intro: string;
      items: Array<{
        title: string;
        body: string;
        metric: string;
      }>;
    };
    pricing: {
      eyebrow: string;
      title: string;
      subtitle: string;
      planLabel: string;
      priceLabel: string;
      bestForLabel: string;
      includesLabel: string;
      contactLabel: string;
      monthSuffix: string;
      tiers: Record<
        "free" | "basic" | "pro" | "global" | "api",
        {
          name: string;
          audience: string;
          cta: string;
          features: string[];
        }
      >;
    };
    testimonials: {
      eyebrow: string;
      title: string;
      items: Array<{
        quote: string;
        author: string;
        role: string;
        company: string;
      }>;
    };
    faq: {
      eyebrow: string;
      title: string;
      items: Array<{
        question: string;
        answer: string;
      }>;
    };
    footer: {
      privacy: string;
      terms: string;
      contact: string;
      github: string;
      tagline: string;
    };
  };
  onboarding: {
    step1: {
      title: string;
      body: string;
      hint: string;
    };
    step2: {
      title: string;
      body: string;
      hint: string;
    };
    step3: {
      title: string;
      body: string;
      hint: string;
    };
    skip: string;
    finish: string;
    saveAlert: string;
    skipSetup: string;
    upgrade: {
      title: string;
      body: string;
      stayFree: string;
      upgradePro: string;
      getGlobal: string;
      tiers: Record<
        "free" | "pro" | "global",
        {
          name: string;
          features: string[];
        }
      >;
    };
  };
};

const enMessages: MarketingMessages = {
  landing: {
    meta: {
      title: "EstateGap | AI property search, deal alerts, and market intelligence",
      description:
        "Search European property deals with AI, compare pricing across markets, and launch real-time alerts in minutes.",
    },
    nav: {
      login: "Sign in",
      cta: "Start for free",
    },
    hero: {
      eyebrow: "AI-guided property intelligence",
      headline: "Source the next investment-grade property before the market catches up.",
      subheadline:
        "EstateGap turns plain-language briefs into cross-border deal flow, live scoring, and instant alerts for the listings that actually matter.",
      primaryCta: "Start for free",
      secondaryCta: "See how it works",
      proofPoints: [
        "30+ portals mapped into one search layer",
        "Real-time deal scoring on every listing",
        "Shared workflow for sourcing, alerts, and dashboard review",
      ],
      cardLabel: "Live market pulse",
      cardTitle: "Madrid, Barcelona, and Milan surfaced in one brief.",
      cardMetricLabel: "Qualified matches",
      cardMetricValue: "148",
      cardSecondaryMetricLabel: "New alerts today",
      cardSecondaryMetricValue: "12",
    },
    features: {
      eyebrow: "Built for repeatable sourcing",
      title: "One flow for discovery, qualification, and follow-through.",
      intro:
        "Move from idea to shortlist without stitching together portals, spreadsheets, and ad-hoc alert tools.",
      items: [
        {
          title: "Natural-language search that gets specific fast",
          body:
            "Describe cities, budget bands, yield targets, and property profiles in plain English. EstateGap translates that into structured search criteria.",
          metric: "Fewer filter clicks",
        },
        {
          title: "Deal signals that help you triage sooner",
          body:
            "Every listing is ranked with pricing context, quality signals, and comparables so you can spend time on the strongest opportunities first.",
          metric: "Priority by signal, not guesswork",
        },
        {
          title: "Alerts that inherit the work you already did",
          body:
            "Promote a strong search into a reusable alert instead of rebuilding it from scratch each time a market changes.",
          metric: "Search once, monitor continuously",
        },
        {
          title: "A dashboard that keeps momentum visible",
          body:
            "Track new supply, price drops, and tier-one deals by country so you can spot momentum before it becomes obvious.",
          metric: "Live country snapshots",
        },
      ],
    },
    pricing: {
      eyebrow: "Pricing",
      title: "Choose the level that matches your sourcing pace.",
      subtitle:
        "Start with a lightweight workflow, then unlock more territory and automation as your pipeline grows.",
      planLabel: "Plan",
      priceLabel: "Price",
      bestForLabel: "Best for",
      includesLabel: "Includes",
      contactLabel: "Contact sales",
      monthSuffix: "/month",
      tiers: {
        free: {
          name: "Free",
          audience: "Testing one market and learning the workflow.",
          cta: "Start for free",
          features: ["1 country", "3 live alerts", "Dashboard access"],
        },
        basic: {
          name: "Basic",
          audience: "Solo investors validating a focused buying thesis.",
          cta: "Choose Basic",
          features: ["3 countries", "10 live alerts", "Saved search handoff"],
        },
        pro: {
          name: "Pro",
          audience: "Teams sourcing across multiple cities every week.",
          cta: "Choose Pro",
          features: ["10 countries", "Unlimited alerts", "Priority refresh cadence"],
        },
        global: {
          name: "Global",
          audience: "Cross-border operators covering Europe at scale.",
          cta: "Choose Global",
          features: ["All supported countries", "Shared team workflows", "Advanced exports"],
        },
        api: {
          name: "API",
          audience: "Internal tooling, BI stacks, and custom integrations.",
          cta: "Talk to sales",
          features: ["Custom ingestion", "Dedicated support", "Usage-based access"],
        },
      },
    },
    testimonials: {
      eyebrow: "Used by fast-moving buyers",
      title: "Teams use EstateGap when timing matters more than browsing.",
      items: [
        {
          quote:
            "We stopped chasing portals one by one. EstateGap gives us a shortlist before our morning stand-up starts.",
          author: "Nadia Voss",
          role: "Acquisitions Lead",
          company: "Northline Capital",
        },
        {
          quote:
            "The alert handoff from search to monitoring is the first time our sourcing workflow has felt continuous instead of patched together.",
          author: "Pablo Serrano",
          role: "Investment Manager",
          company: "Velada Partners",
        },
        {
          quote:
            "The dashboard made it obvious where new supply and price drops were accelerating. That changed where we focused immediately.",
          author: "Claire Martin",
          role: "Founder",
          company: "Rive Gauche Living",
        },
      ],
    },
    faq: {
      eyebrow: "FAQ",
      title: "Straight answers for how the workflow fits together.",
      items: [
        {
          question: "Do I need to build every search with filters?",
          answer:
            "No. You can start with a natural-language brief, then refine the structured criteria only where precision matters.",
        },
        {
          question: "Can I turn a good search into an alert?",
          answer:
            "Yes. The onboarding flow is designed to move from chat discovery into an alert setup so recurring monitoring stays aligned with the original brief.",
        },
        {
          question: "Is the landing page localized for every market?",
          answer:
            "Each supported locale ships with a dedicated page variant, canonical metadata, hreflang tags, and sitemap entries for search discovery.",
        },
        {
          question: "What happens when my team needs more coverage?",
          answer:
            "Upgrade paths are built into the product. You can move from Free to Pro or Global without rebuilding your searches or alerts.",
        },
      ],
    },
    footer: {
      privacy: "Privacy policy",
      terms: "Terms of service",
      contact: "Contact",
      github: "GitHub",
      tagline: "AI-assisted property sourcing for teams that need signal, speed, and repeatability.",
    },
  },
  onboarding: {
    step1: {
      title: "Start with a plain-language brief",
      body:
        "Describe the market, budget, or property profile you want. EstateGap turns that into structured sourcing criteria.",
      hint: "Send one search prompt to keep the tour moving.",
    },
    step2: {
      title: "Turn the brief into a reusable alert",
      body:
        "Capture the strongest criteria as an alert so fresh deals can find you instead of the other way around.",
      hint: "Save the alert or skip this setup to continue.",
    },
    step3: {
      title: "Use the dashboard to spot momentum",
      body:
        "This is where new listings, price drops, and tier-one deals surface first once your search is live.",
      hint: "Finish the tour to review upgrade options.",
    },
    skip: "Skip tour",
    finish: "Finish tour",
    saveAlert: "Save alert",
    skipSetup: "Skip setup",
    upgrade: {
      title: "Keep the momentum or unlock more coverage",
      body:
        "Stay on Free to keep exploring, or move up to unlock more alerts, broader country coverage, and faster sourcing loops.",
      stayFree: "Stay on Free",
      upgradePro: "Upgrade to Pro",
      getGlobal: "Get Global",
      tiers: {
        free: {
          name: "Free",
          features: ["1 country", "3 live alerts", "Core dashboard"],
        },
        pro: {
          name: "Pro",
          features: ["10 countries", "Unlimited alerts", "Priority refresh"],
        },
        global: {
          name: "Global",
          features: ["Full market coverage", "Team workflows", "Advanced exports"],
        },
      },
    },
  },
};

const esMessages: MarketingMessages = {
  landing: {
    meta: {
      title: "EstateGap | búsqueda inmobiliaria con IA, alertas y señales de mercado",
      description:
        "Busca oportunidades inmobiliarias en Europa con IA, compara precios entre mercados y activa alertas en tiempo real en minutos.",
    },
    nav: {
      login: "Iniciar sesión",
      cta: "Empieza gratis",
    },
    hero: {
      eyebrow: "Inteligencia inmobiliaria guiada por IA",
      headline: "Encuentra la próxima propiedad con potencial antes de que el mercado reaccione.",
      subheadline:
        "EstateGap convierte un briefing en lenguaje natural en flujo de oportunidades, scoring en vivo y alertas inmediatas para los anuncios que sí importan.",
      primaryCta: "Empieza gratis",
      secondaryCta: "Ver cómo funciona",
      proofPoints: [
        "Más de 30 portales unificados en una sola búsqueda",
        "Scoring en tiempo real para cada anuncio",
        "Un solo flujo para búsqueda, alertas y revisión en dashboard",
      ],
      cardLabel: "Pulso del mercado en vivo",
      cardTitle: "Madrid, Barcelona y Milán en un único briefing.",
      cardMetricLabel: "Coincidencias cualificadas",
      cardMetricValue: "148",
      cardSecondaryMetricLabel: "Alertas nuevas hoy",
      cardSecondaryMetricValue: "12",
    },
    features: {
      eyebrow: "Diseñado para captar oportunidades de forma repetible",
      title: "Un solo flujo para descubrir, filtrar y actuar.",
      intro:
        "Pasa de una idea a una shortlist sin saltar entre portales, hojas de cálculo y herramientas de alertas improvisadas.",
      items: [
        {
          title: "Búsqueda en lenguaje natural que aterriza rápido",
          body:
            "Describe ciudades, presupuestos, objetivos de rentabilidad y tipologías en lenguaje normal. EstateGap lo traduce a criterios estructurados.",
          metric: "Menos fricción al filtrar",
        },
        {
          title: "Señales de oportunidad para priorizar antes",
          body:
            "Cada anuncio se ordena con contexto de precio, señales de calidad y comparables para que dediques tiempo a las mejores opciones.",
          metric: "Prioriza por señal, no por intuición",
        },
        {
          title: "Alertas que aprovechan el trabajo ya hecho",
          body:
            "Convierte una búsqueda sólida en una alerta reutilizable en lugar de reconstruirla cada vez que cambia el mercado.",
          metric: "Busca una vez, monitoriza siempre",
        },
        {
          title: "Un dashboard que mantiene el ritmo visible",
          body:
            "Sigue nuevas entradas, bajadas de precio y deals de nivel uno por país para detectar impulso antes de que sea evidente.",
          metric: "Visión instantánea por país",
        },
      ],
    },
    pricing: {
      eyebrow: "Precios",
      title: "Elige el nivel que encaja con tu ritmo de captación.",
      subtitle:
        "Empieza con un flujo ligero y desbloquea más mercados y automatización cuando tu pipeline lo necesite.",
      planLabel: "Plan",
      priceLabel: "Precio",
      bestForLabel: "Ideal para",
      includesLabel: "Incluye",
      contactLabel: "Hablar con ventas",
      monthSuffix: "/mes",
      tiers: {
        free: {
          name: "Free",
          audience: "Probar un mercado y entender el flujo.",
          cta: "Empieza gratis",
          features: ["1 país", "3 alertas activas", "Acceso al dashboard"],
        },
        basic: {
          name: "Basic",
          audience: "Inversores que validan una tesis concreta.",
          cta: "Elegir Basic",
          features: ["3 países", "10 alertas activas", "Traspaso desde búsquedas guardadas"],
        },
        pro: {
          name: "Pro",
          audience: "Equipos que trabajan varios mercados cada semana.",
          cta: "Elegir Pro",
          features: ["10 países", "Alertas ilimitadas", "Actualización prioritaria"],
        },
        global: {
          name: "Global",
          audience: "Operadores transfronterizos con cobertura europea.",
          cta: "Elegir Global",
          features: ["Todos los países soportados", "Flujos compartidos de equipo", "Exportaciones avanzadas"],
        },
        api: {
          name: "API",
          audience: "Integraciones internas, BI y automatizaciones propias.",
          cta: "Hablar con ventas",
          features: ["Ingesta personalizada", "Soporte dedicado", "Acceso por uso"],
        },
      },
    },
    testimonials: {
      eyebrow: "Equipos que se mueven rápido",
      title: "EstateGap se usa cuando el timing importa más que navegar anuncios.",
      items: [
        {
          quote:
            "Dejamos de perseguir portales uno por uno. EstateGap nos entrega una shortlist antes de empezar la reunión del día.",
          author: "Nadia Voss",
          role: "Responsable de adquisiciones",
          company: "Northline Capital",
        },
        {
          quote:
            "El salto de búsqueda a alerta es la primera vez que nuestro flujo de captación se siente continuo y no improvisado.",
          author: "Pablo Serrano",
          role: "Investment Manager",
          company: "Velada Partners",
        },
        {
          quote:
            "El dashboard nos mostró dónde se aceleraban la oferta nueva y las rebajas. Eso cambió nuestro foco de inmediato.",
          author: "Claire Martin",
          role: "Fundadora",
          company: "Rive Gauche Living",
        },
      ],
    },
    faq: {
      eyebrow: "Preguntas frecuentes",
      title: "Respuestas directas sobre cómo encaja el flujo.",
      items: [
        {
          question: "¿Tengo que construir cada búsqueda con filtros manuales?",
          answer:
            "No. Puedes empezar con un briefing en lenguaje natural y refinar solo los criterios estructurados que realmente necesiten precisión.",
        },
        {
          question: "¿Puedo convertir una buena búsqueda en una alerta?",
          answer:
            "Sí. El onboarding está pensado para pasar del descubrimiento en chat a una alerta reutilizable sin rehacer el trabajo.",
        },
        {
          question: "¿Cada locale tiene su propia página indexable?",
          answer:
            "Sí. Cada versión soportada incluye metadata específica, etiquetas hreflang y entradas dedicadas en el sitemap.",
        },
        {
          question: "¿Qué ocurre cuando mi equipo necesita más cobertura?",
          answer:
            "Las rutas de upgrade están integradas. Puedes pasar de Free a Pro o Global sin reconstruir búsquedas ni alertas.",
        },
      ],
    },
    footer: {
      privacy: "Privacidad",
      terms: "Términos del servicio",
      contact: "Contacto",
      github: "GitHub",
      tagline: "Captación inmobiliaria asistida por IA para equipos que necesitan señal, velocidad y repetibilidad.",
    },
  },
  onboarding: {
    step1: {
      title: "Empieza con un briefing en lenguaje natural",
      body:
        "Describe el mercado, el presupuesto o el perfil de propiedad que buscas. EstateGap lo traduce en criterios estructurados.",
      hint: "Envía una búsqueda para continuar con el tour.",
    },
    step2: {
      title: "Convierte el briefing en una alerta reutilizable",
      body:
        "Guarda los criterios más útiles como alerta para que las nuevas oportunidades te encuentren a ti.",
      hint: "Guarda la alerta o salta este paso para continuar.",
    },
    step3: {
      title: "Usa el dashboard para detectar impulso",
      body:
        "Aquí es donde aparecen antes las nuevas entradas, bajadas de precio y deals de nivel uno una vez activa tu búsqueda.",
      hint: "Termina el tour para revisar opciones de upgrade.",
    },
    skip: "Saltar tour",
    finish: "Terminar tour",
    saveAlert: "Guardar alerta",
    skipSetup: "Saltar configuración",
    upgrade: {
      title: "Sigue avanzando o desbloquea más cobertura",
      body:
        "Quédate en Free para seguir explorando o sube de plan para abrir más alertas, más países y un ritmo de captación mayor.",
      stayFree: "Seguir con Free",
      upgradePro: "Subir a Pro",
      getGlobal: "Ir a Global",
      tiers: {
        free: {
          name: "Free",
          features: ["1 país", "3 alertas activas", "Dashboard básico"],
        },
        pro: {
          name: "Pro",
          features: ["10 países", "Alertas ilimitadas", "Actualización prioritaria"],
        },
        global: {
          name: "Global",
          features: ["Cobertura completa", "Flujos de equipo", "Exportaciones avanzadas"],
        },
      },
    },
  },
};

const frMessages: MarketingMessages = {
  landing: {
    meta: {
      title: "EstateGap | recherche immobilière IA, alertes et intelligence marché",
      description:
        "Recherchez des opportunités immobilières en Europe avec l'IA, comparez les prix entre marchés et activez des alertes en quelques minutes.",
    },
    nav: {
      login: "Se connecter",
      cta: "Commencer gratuitement",
    },
    hero: {
      eyebrow: "Intelligence immobilière pilotée par l'IA",
      headline: "Repérez le prochain actif à fort potentiel avant que le marché ne s'ajuste.",
      subheadline:
        "EstateGap transforme un brief en langage naturel en flux d'opportunités, scoring en direct et alertes immédiates sur les annonces qui comptent vraiment.",
      primaryCta: "Commencer gratuitement",
      secondaryCta: "Voir le fonctionnement",
      proofPoints: [
        "30+ portails réunis dans une seule recherche",
        "Scoring en temps réel sur chaque annonce",
        "Un seul flux pour la recherche, les alertes et le tableau de bord",
      ],
      cardLabel: "Pouls du marché",
      cardTitle: "Madrid, Barcelone et Milan dans un seul brief.",
      cardMetricLabel: "Opportunités qualifiées",
      cardMetricValue: "148",
      cardSecondaryMetricLabel: "Nouvelles alertes aujourd'hui",
      cardSecondaryMetricValue: "12",
    },
    features: {
      eyebrow: "Pensé pour une prospection répétable",
      title: "Un flux unique pour découvrir, qualifier et agir.",
      intro:
        "Passez d'une idée à une shortlist sans jongler entre portails, tableurs et outils d'alertes bricolés.",
      items: [
        {
          title: "Une recherche en langage naturel qui devient vite précise",
          body:
            "Décrivez villes, budgets, objectifs de rendement et profils de biens en langage clair. EstateGap les convertit en critères structurés.",
          metric: "Moins de friction dans les filtres",
        },
        {
          title: "Des signaux de deal pour prioriser plus tôt",
          body:
            "Chaque annonce est classée avec contexte prix, signaux qualité et comparables pour concentrer votre temps sur les meilleures pistes.",
          metric: "Priorité à la donnée, pas à l'intuition",
        },
        {
          title: "Des alertes qui réutilisent le travail déjà fait",
          body:
            "Transformez une bonne recherche en alerte réutilisable au lieu de la reconstruire à chaque variation du marché.",
          metric: "Chercher une fois, surveiller en continu",
        },
        {
          title: "Un dashboard qui rend le momentum visible",
          body:
            "Suivez les nouvelles annonces, baisses de prix et deals premium par pays pour détecter les inflexions avant le reste du marché.",
          metric: "Vue pays en direct",
        },
      ],
    },
    pricing: {
      eyebrow: "Tarifs",
      title: "Choisissez le niveau adapté à votre rythme de sourcing.",
      subtitle:
        "Commencez avec un flux léger puis débloquez plus de marchés et d'automatisation à mesure que votre pipeline grandit.",
      planLabel: "Offre",
      priceLabel: "Prix",
      bestForLabel: "Idéal pour",
      includesLabel: "Comprend",
      contactLabel: "Contacter l'équipe",
      monthSuffix: "/mois",
      tiers: {
        free: {
          name: "Free",
          audience: "Tester un marché et comprendre le flux.",
          cta: "Commencer gratuitement",
          features: ["1 pays", "3 alertes actives", "Accès dashboard"],
        },
        basic: {
          name: "Basic",
          audience: "Investisseurs solos avec une thèse ciblée.",
          cta: "Choisir Basic",
          features: ["3 pays", "10 alertes actives", "Relais depuis les recherches"],
        },
        pro: {
          name: "Pro",
          audience: "Équipes actives sur plusieurs villes chaque semaine.",
          cta: "Choisir Pro",
          features: ["10 pays", "Alertes illimitées", "Rafraîchissement prioritaire"],
        },
        global: {
          name: "Global",
          audience: "Opérateurs transfrontaliers couvrant toute l'Europe.",
          cta: "Choisir Global",
          features: ["Tous les pays supportés", "Flux collaboratifs", "Exports avancés"],
        },
        api: {
          name: "API",
          audience: "BI, outils internes et intégrations sur mesure.",
          cta: "Parler aux ventes",
          features: ["Ingestion personnalisée", "Support dédié", "Accès à l'usage"],
        },
      },
    },
    testimonials: {
      eyebrow: "Utilisé par des équipes qui bougent vite",
      title: "EstateGap est choisi quand le timing compte plus que la simple navigation.",
      items: [
        {
          quote:
            "Nous avons arrêté de courir après les portails un par un. EstateGap nous livre une shortlist avant notre premier point d'équipe.",
          author: "Nadia Voss",
          role: "Responsable acquisitions",
          company: "Northline Capital",
        },
        {
          quote:
            "Le passage de la recherche à l'alerte est la première fois que notre workflow paraît continu au lieu d'être bricolé.",
          author: "Pablo Serrano",
          role: "Investment Manager",
          company: "Velada Partners",
        },
        {
          quote:
            "Le dashboard a rendu évident où l'offre neuve et les baisses de prix accéléraient. Cela a changé notre priorité immédiatement.",
          author: "Claire Martin",
          role: "Fondatrice",
          company: "Rive Gauche Living",
        },
      ],
    },
    faq: {
      eyebrow: "FAQ",
      title: "Des réponses claires sur la façon dont le flux s'assemble.",
      items: [
        {
          question: "Dois-je construire chaque recherche avec des filtres ?",
          answer:
            "Non. Vous pouvez partir d'un brief en langage naturel puis ne raffiner que les critères structurés réellement utiles.",
        },
        {
          question: "Puis-je transformer une bonne recherche en alerte ?",
          answer:
            "Oui. Le parcours d'onboarding est conçu pour passer du chat à une alerte réutilisable sans refaire le travail.",
        },
        {
          question: "Chaque locale a-t-elle sa propre page indexable ?",
          answer:
            "Oui. Chaque version supportée dispose d'une metadata dédiée, de balises hreflang et d'entrées distinctes dans le sitemap.",
        },
        {
          question: "Que se passe-t-il quand l'équipe a besoin de plus de couverture ?",
          answer:
            "Les upgrades sont intégrés au produit. Vous pouvez passer de Free à Pro ou Global sans reconstruire recherches et alertes.",
        },
      ],
    },
    footer: {
      privacy: "Confidentialité",
      terms: "Conditions d'utilisation",
      contact: "Contact",
      github: "GitHub",
      tagline: "Prospection immobilière assistée par IA pour les équipes qui ont besoin de signal, de vitesse et de méthode.",
    },
  },
  onboarding: {
    step1: {
      title: "Commencez avec un brief en langage naturel",
      body:
        "Décrivez le marché, le budget ou le profil de bien recherché. EstateGap le traduit en critères structurés.",
      hint: "Envoyez une première recherche pour continuer.",
    },
    step2: {
      title: "Transformez le brief en alerte réutilisable",
      body:
        "Enregistrez les meilleurs critères sous forme d'alerte pour laisser les nouvelles opportunités venir à vous.",
      hint: "Enregistrez l'alerte ou sautez cette étape pour continuer.",
    },
    step3: {
      title: "Servez-vous du dashboard pour repérer le momentum",
      body:
        "C'est ici que les nouvelles annonces, baisses de prix et deals premium apparaissent dès que votre recherche tourne.",
      hint: "Terminez le tour pour voir les options d'upgrade.",
    },
    skip: "Passer le tour",
    finish: "Terminer le tour",
    saveAlert: "Enregistrer l'alerte",
    skipSetup: "Passer cette étape",
    upgrade: {
      title: "Continuez avec Free ou débloquez plus de couverture",
      body:
        "Restez sur Free pour explorer, ou montez en gamme pour ouvrir plus d'alertes, plus de pays et un rythme de sourcing plus fort.",
      stayFree: "Rester sur Free",
      upgradePro: "Passer à Pro",
      getGlobal: "Choisir Global",
      tiers: {
        free: {
          name: "Free",
          features: ["1 pays", "3 alertes actives", "Dashboard de base"],
        },
        pro: {
          name: "Pro",
          features: ["10 pays", "Alertes illimitées", "Rafraîchissement prioritaire"],
        },
        global: {
          name: "Global",
          features: ["Couverture complète", "Flux collaboratifs", "Exports avancés"],
        },
      },
    },
  },
};

const localeMessages: Partial<Record<AppLocale, MarketingMessages>> = {
  en: enMessages,
  es: esMessages,
  fr: frMessages,
};

export function getMarketingMessages(locale: string): MarketingMessages {
  return localeMessages[locale as AppLocale] ?? enMessages;
}
