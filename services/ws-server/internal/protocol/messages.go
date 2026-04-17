package protocol

import "encoding/json"

type Envelope struct {
	Type      string          `json:"type"`
	SessionID string          `json:"session_id,omitempty"`
	Payload   json.RawMessage `json:"payload"`
}

type ChatMessagePayload struct {
	UserMessage string `json:"user_message"`
	CountryCode string `json:"country_code,omitempty"`
}

type ImageFeedbackPayload struct {
	ListingID string `json:"listing_id"`
	Action    string `json:"action"`
}

type CriteriaConfirmPayload struct {
	Confirmed bool   `json:"confirmed"`
	Notes     string `json:"notes,omitempty"`
}

type TextChunkPayload struct {
	Text           string `json:"text"`
	ConversationID string `json:"conversation_id"`
	IsFinal        bool   `json:"is_final"`
}

type ChipsPayload struct {
	Options []ChipOption `json:"options"`
}

type ChipOption struct {
	Label string `json:"label"`
	Value string `json:"value"`
}

type ImageCarouselPayload struct {
	Listings []CarouselItem `json:"listings"`
}

type CarouselItem struct {
	ListingID string   `json:"listing_id"`
	Title     string   `json:"title"`
	PriceEUR  float64  `json:"price_eur"`
	AreaM2    float64  `json:"area_m2"`
	City      string   `json:"city"`
	PhotoURLs []string `json:"photo_urls"`
	DealScore float64  `json:"deal_score,omitempty"`
}

type CriteriaSummaryPayload struct {
	ConversationID string          `json:"conversation_id"`
	Criteria       json.RawMessage `json:"criteria"`
	ReadyToSearch  bool            `json:"ready_to_search"`
}

type SearchResultsPayload struct {
	ConversationID string          `json:"conversation_id"`
	TotalCount     int             `json:"total_count"`
	Listings       []SearchListing `json:"listings"`
}

type SearchListing struct {
	ListingID   string  `json:"listing_id"`
	Title       string  `json:"title,omitempty"`
	PriceEUR    float64 `json:"price_eur,omitempty"`
	AreaM2      float64 `json:"area_m2,omitempty"`
	Bedrooms    *int    `json:"bedrooms,omitempty"`
	City        string  `json:"city,omitempty"`
	DealScore   float64 `json:"deal_score,omitempty"`
	DealTier    int     `json:"deal_tier,omitempty"`
	ImageURL    string  `json:"image_url,omitempty"`
	AnalysisURL string  `json:"analysis_url,omitempty"`
}

type DealAlertPayload struct {
	EventID     string  `json:"event_id"`
	ListingID   string  `json:"listing_id"`
	Title       string  `json:"title"`
	Address     string  `json:"address"`
	PriceEUR    float64 `json:"price_eur"`
	AreaM2      float64 `json:"area_m2"`
	DealScore   float64 `json:"deal_score"`
	DealTier    int     `json:"deal_tier"`
	PhotoURL    string  `json:"photo_url,omitempty"`
	AnalysisURL string  `json:"analysis_url,omitempty"`
	RuleName    string  `json:"rule_name"`
	TriggeredAt string  `json:"triggered_at"`
}

type ErrorPayload struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func MarshalEnvelope(messageType, sessionID string, payload any) ([]byte, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	raw, err := json.Marshal(Envelope{
		Type:      messageType,
		SessionID: sessionID,
		Payload:   body,
	})
	if err != nil {
		return nil, err
	}
	return raw, nil
}
