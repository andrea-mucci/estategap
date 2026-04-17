# API Contract: Translation

**Service**: Go API Gateway (proxies to DeepL API)  
**Base Path**: `/api/v1/translate`  
**Auth**: Bearer JWT (required)

---

## POST /api/v1/translate

Translate a text string to the target language. Results are cached in Redis by the gateway.

**Request body**:
```json
{
  "text": "Precioso piso en el centro de Madrid con vistas espectaculares...",
  "target_lang": "EN-GB"
}
```

**`target_lang` values** (DeepL language codes):

| Browser locale | DeepL code |
|----------------|-----------|
| `en` | `EN-GB` |
| `es` | `ES` |
| `fr` | `FR` |
| `de` | `DE` |
| `it` | `IT` |
| `pt` | `PT-PT` |
| `nl` | `NL` |
| `pl` | `PL` |
| `sv` | `SV` |
| `el` | `EL` |

**Response 200**:
```json
{
  "translated_text": "Beautiful apartment in the center of Madrid with spectacular views...",
  "source_lang": "ES",
  "target_lang": "EN-GB",
  "cached": false
}
```

**`cached: true`** is returned when the response was served from the Redis translation cache.

---

## Caching

- **Cache key**: `translate:{sha256(text + ":" + target_lang)}` in Redis
- **TTL**: 7 days (translations of property descriptions are stable)
- **Cache scope**: Global (not per-user) — safe since translation has no PII

---

## Rate Limiting

- 50 translation requests per user per hour (enforced at API gateway level)
- Response `429` with `Retry-After` header when exceeded

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Missing `text` or `target_lang`, or `target_lang` not in supported list |
| 401 | Missing or invalid JWT |
| 429 | Rate limit exceeded |
| 502 | DeepL API unavailable |
| 500 | Internal server error |

**On 502**: Frontend shows error toast ("Translation unavailable. Try again later.") and keeps original text visible.

---

## Frontend Integration

```ts
// hooks/useTranslate.ts
const { mutate: translate, isPending } = useMutation({
  mutationFn: ({ text, targetLang }: { text: string; targetLang: string }) =>
    apiClient.POST('/api/v1/translate', { body: { text, target_lang: targetLang } }),
  onSuccess: (data) => setTranslatedText(data.translated_text),
  onError: () => toast.error('Translation unavailable. Try again later.'),
})

// Derive target lang from next-intl locale
const locale = useLocale()
const deepLLang = LOCALE_TO_DEEPL[locale] ?? 'EN-GB'
```
