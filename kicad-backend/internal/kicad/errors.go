package kicad

import "errors"

// Validation errors (non-retriable) - these indicate bad input
var (
	ErrInvalidLayout          = errors.New("invalid layout in task request")
	ErrInvalidSettings        = errors.New("invalid settings in task request")
	ErrInvalidFootprintFormat = errors.New("invalid footprint format")
	ErrInvalidLayoutMetadata  = errors.New("invalid layout metadata")
	ErrInvalidLayoutJSON      = errors.New("invalid layout JSON structure")
)

// IsValidationError checks if an error is a validation error (non-retriable)
func IsValidationError(err error) bool {
	return errors.Is(err, ErrInvalidLayout) ||
		errors.Is(err, ErrInvalidSettings) ||
		errors.Is(err, ErrInvalidFootprintFormat) ||
		errors.Is(err, ErrInvalidLayoutMetadata) ||
		errors.Is(err, ErrInvalidLayoutJSON)
}
