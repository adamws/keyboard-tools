package kicad

import (
	"strings"
)

// SanitizeFilename removes illegal characters from filenames
// Replacement for Python's pathvalidate.sanitize_filename
func SanitizeFilename(filename string) string {
	// Characters that are illegal in filenames on most filesystems
	illegalChars := []string{"/", "\\", ":", "*", "?", "\"", "<", ">", "|"}

	result := filename
	for _, char := range illegalChars {
		result = strings.ReplaceAll(result, char, "")
	}

	// Remove directory traversal sequences
	result = strings.ReplaceAll(result, "..", "")

	// Trim whitespace
	result = strings.TrimSpace(result)

	return result
}

// SanitizeFilepath sanitizes a filepath for safe use
// Replacement for Python's pathvalidate.sanitize_filepath
func SanitizeFilepath(filepath string) string {
	// For filepath, we need to preserve path separators on the target OS
	// but still remove dangerous sequences

	result := filepath

	// Remove directory traversal
	result = strings.ReplaceAll(result, "..", "")

	// Remove absolute path markers at the beginning (if not intended)
	result = strings.TrimPrefix(result, "/")
	result = strings.TrimPrefix(result, "\\")

	// Trim whitespace
	result = strings.TrimSpace(result)

	return result
}
