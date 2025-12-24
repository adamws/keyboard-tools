package common

// Progress represents task progress information sent from worker to server via asynq/Redis.
// This struct must maintain binary compatibility for JSON serialization.
type Progress struct {
	Percentage int    `json:"percentage"`
	Message    string `json:"message,omitempty"`
}
