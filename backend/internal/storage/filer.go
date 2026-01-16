package storage

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

// FilerUploader handles uploading files to SeaweedFS Filer
type FilerUploader struct {
	httpClient *http.Client
	filerURL   string
	ttl        string
}

// NewFilerUploader creates a new FilerUploader
func NewFilerUploader(filerURL string) *FilerUploader {
	return &FilerUploader{
		httpClient: &http.Client{
			Timeout: 5 * time.Minute, // 5-minute timeout for large file uploads
		},
		filerURL: filerURL,
		ttl:      "1h", // 1-hour TTL for uploaded files
	}
}

// uploadFile uploads a file to SeaweedFS Filer using multipart/form-data
func (u *FilerUploader) uploadFile(ctx context.Context, path string, data io.Reader, contentType string) error {
	// Create multipart form
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile("file", filepath.Base(path))
	if err != nil {
		return fmt.Errorf("failed to create form file: %w", err)
	}

	if _, err := io.Copy(part, data); err != nil {
		return fmt.Errorf("failed to copy data: %w", err)
	}

	writer.Close()

	// Build URL with TTL parameter
	url := fmt.Sprintf("%s/%s?ttl=%s", u.filerURL, path, u.ttl)

	req, err := http.NewRequestWithContext(ctx, "POST", url, body)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := u.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("upload failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("upload failed with status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	return nil
}

// UploadZip uploads a ZIP file from a memory buffer
func (u *FilerUploader) UploadZip(ctx context.Context, taskID string, zipBuffer *bytes.Buffer) error {
	path := fmt.Sprintf("%s/%s.zip", taskID, taskID)
	return u.uploadFile(ctx, path, zipBuffer, "application/zip")
}

// UploadSVG uploads an SVG file with proper content type
func (u *FilerUploader) UploadSVG(ctx context.Context, taskID, name, filePath string) error {
	// Read file contents
	fileData, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read SVG file: %w", err)
	}

	path := fmt.Sprintf("%s/%s.svg", taskID, name)
	return u.uploadFile(ctx, path, bytes.NewReader(fileData), "image/svg+xml")
}

// UploadToStorage uploads all project files to Filer
func (u *FilerUploader) UploadToStorage(ctx context.Context, taskID, workDir string) error {
	// Create ZIP archive in memory
	zipBuffer, err := CreateZipInMemory(workDir)
	if err != nil {
		return fmt.Errorf("failed to create ZIP: %w", err)
	}

	// Upload ZIP file
	if err := u.UploadZip(ctx, taskID, zipBuffer); err != nil {
		return err
	}

	// Upload SVG renders
	logPath := filepath.Join(workDir, "logs")
	svgFiles := []string{"front", "back", "schematic"}

	for _, name := range svgFiles {
		svgPath := filepath.Join(logPath, name+".svg")
		if err := u.UploadSVG(ctx, taskID, name, svgPath); err != nil {
			return err
		}
	}

	return nil
}
