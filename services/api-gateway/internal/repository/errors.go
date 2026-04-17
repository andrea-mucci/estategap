package repository

import "errors"

var (
	ErrNotFound          = errors.New("not found")
	ErrForbidden         = errors.New("forbidden")
	ErrConflict          = errors.New("conflict")
	ErrInvalidInput      = errors.New("invalid input")
	ErrValidation        = errors.New("validation")
	ErrLimitReached      = errors.New("limit reached")
	ErrAlertLimitReached = errors.New("alert limit reached")
)
