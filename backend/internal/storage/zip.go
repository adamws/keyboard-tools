package storage

import (
	"archive/zip"
	"bytes"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// CreateZipInMemory creates a ZIP archive in memory from a source directory
func CreateZipInMemory(sourceDir string) (*bytes.Buffer, error) {
	zipBuffer := new(bytes.Buffer)
	zipWriter := zip.NewWriter(zipBuffer)
	defer zipWriter.Close()

	// Get the source path for relative path calculation
	sourcePath, err := filepath.Abs(sourceDir)
	if err != nil {
		return nil, fmt.Errorf("failed to get absolute path: %w", err)
	}

	// Walk the directory tree
	err = filepath.Walk(sourcePath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Skip directories (only add files)
		if info.IsDir() {
			return nil
		}

		// Get relative path for archive
		relPath, err := filepath.Rel(sourcePath, path)
		if err != nil {
			return fmt.Errorf("failed to get relative path: %w", err)
		}

		// Create entry in ZIP
		writer, err := zipWriter.Create(relPath)
		if err != nil {
			return fmt.Errorf("failed to create zip entry: %w", err)
		}

		// Open and copy file contents
		file, err := os.Open(path)
		if err != nil {
			return fmt.Errorf("failed to open file: %w", err)
		}
		defer file.Close()

		_, err = io.Copy(writer, file)
		if err != nil {
			return fmt.Errorf("failed to copy file to zip: %w", err)
		}

		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("failed to create zip: %w", err)
	}

	return zipBuffer, nil
}
