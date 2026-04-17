package repository

import (
	"strings"
	"testing"

	"github.com/google/uuid"
)

func TestFloatCursorRoundTrip(t *testing.T) {
	t.Parallel()

	wantID := uuid.MustParse("11111111-1111-1111-1111-111111111111")
	wantValue := 1234.5678

	cursor := encodeFloatCursor(wantValue, wantID)
	gotValue, gotID, err := decodeFloatCursor(cursor)
	if err != nil {
		t.Fatalf("decodeFloatCursor() error = %v", err)
	}

	if gotID != wantID {
		t.Fatalf("decodeFloatCursor() id = %s, want %s", gotID, wantID)
	}
	if gotValue != wantValue {
		t.Fatalf("decodeFloatCursor() value = %f, want %f", gotValue, wantValue)
	}
}

func TestDecodeFloatCursorRejectsInvalidPayload(t *testing.T) {
	t.Parallel()

	if _, _, err := decodeFloatCursor("not-base64"); err == nil {
		t.Fatal("decodeFloatCursor() expected error for invalid base64 payload")
	}

	cursor := encodeFloatCursor(1, uuid.New())
	invalid := cursor[:len(cursor)/2]
	if _, _, err := decodeFloatCursor(invalid); err == nil {
		t.Fatal("decodeFloatCursor() expected error for truncated cursor")
	}

	if _, _, err := decodeFloatCursor("aW52YWxpZHxwYXlsb2Fk"); err == nil || !strings.Contains(err.Error(), "invalid") {
		t.Fatalf("decodeFloatCursor() unexpected error = %v", err)
	}
}
