package repository

import "errors"

var (
	ErrNotFound          = errors.New("not found")
	ErrConflict          = errors.New("conflict")
	ErrAlertLimitReached = errors.New("alert limit reached")
)
