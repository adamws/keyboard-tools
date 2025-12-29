package kicad

import "errors"

// Validation errors - these indicate bad input
var (
	ErrInvalidLayout          = errors.New("invalid layout in task request")
	ErrInvalidSettings        = errors.New("invalid settings in task request")
	ErrInvalidFootprintFormat = errors.New("invalid footprint format")
	ErrInvalidLayoutMetadata  = errors.New("invalid layout metadata")
)
