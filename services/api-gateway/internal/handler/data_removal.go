package handler

import (
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/estategap/services/api-gateway/internal/respond"
	"github.com/google/uuid"
)

type DataRemovalRequestHandler struct{}

func NewDataRemovalRequestHandler() *DataRemovalRequestHandler {
	return &DataRemovalRequestHandler{}
}

func (h *DataRemovalRequestHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name        string `json:"name"`
		Email       string `json:"email"`
		SubjectType string `json:"subject_type"`
		Description string `json:"description"`
		RightsType  string `json:"rights_type"`
	}
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, r, http.StatusBadRequest, "invalid request body")
		return
	}

	req.Name = strings.TrimSpace(req.Name)
	req.Email = strings.TrimSpace(strings.ToLower(req.Email))
	req.SubjectType = strings.TrimSpace(req.SubjectType)
	req.Description = strings.TrimSpace(req.Description)
	req.RightsType = strings.TrimSpace(req.RightsType)

	if req.Name == "" || !validateEmail(req.Email) || req.SubjectType == "" || req.Description == "" || req.RightsType == "" {
		writeError(w, r, http.StatusBadRequest, "name, email, subject_type, description, and rights_type are required")
		return
	}

	requestID := uuid.NewString()
	slog.Info(
		"data removal request received",
		"request_id",
		requestID,
		"email",
		req.Email,
		"subject_type",
		req.SubjectType,
		"rights_type",
		req.RightsType,
	)

	respond.JSON(w, http.StatusAccepted, map[string]string{
		"request_id":  requestID,
		"status":      "received",
		"received_at": time.Now().UTC().Format(time.RFC3339),
	})
}
