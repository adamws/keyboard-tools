package web

import (
	"fmt"
	"math"
	"regexp"
)

type kleJsonLayout struct {
	Meta kleMetadata `json:"meta"`
	Keys []kleKey    `json:"keys"`
}

type kleMetadata struct {
	Author      string        `json:"author"`
	Backcolor   string        `json:"backcolor"`
	Background  kleBackground `json:"background"`
	Name        string        `json:"name"`
	Notes       string        `json:"notes"`
	Radii       string        `json:"radii"`
	SwitchBrand string        `json:"switchBrand"`
	SwitchMount string        `json:"switchMount"`
	SwitchType  string        `json:"switchType"`
}

type kleBackground struct {
	Name  string `json:"name"`
	Style string `json:"style"`
}

type kleKey struct {
	Color         string         `json:"color"`
	Labels        []string       `json:"labels"`
	TextColor     []string       `json:"textColor"`
	TextSize      []float64      `json:"textSize"`
	DefaultText   kleDefaultText `json:"default"`
	X             float64        `json:"x"`
	Y             float64        `json:"y"`
	Width         float64        `json:"width"`
	Height        float64        `json:"height"`
	X2            float64        `json:"x2"`
	Y2            float64        `json:"y2"`
	Width2        float64        `json:"width2"`
	Height2       float64        `json:"height2"`
	RotationX     float64        `json:"rotation_x"`
	RotationY     float64        `json:"rotation_y"`
	RotationAngle float64        `json:"rotation_angle"`
	Decal         bool           `json:"decal"`
	Ghost         bool           `json:"ghost"`
	Stepped       bool           `json:"stepped"`
	Nub           bool           `json:"nub"`
	Profile       string         `json:"profile"`
	Sm            string         `json:"sm"`
	Sb            string         `json:"sb"`
	St            string         `json:"st"`
}

type kleDefaultText struct {
	TextColor string `json:"textColor"`
	TextSize  int64  `json:"textSize"`
}

// checks if all keys contains valid row-column assignment
func areKeysAnnotated(keys []kleKey) bool {
	re, _ := regexp.Compile(`^\d+\,\d+$`)
	for _, key := range keys {
		matrixPositionLabel := ""
		if len(key.Labels) != 0 {
			matrixPositionLabel = key.Labels[0]
		}
		if !re.Match([]byte(matrixPositionLabel)) {
			return false
		}
	}
	return true
}

func getKeyCenter(key kleKey) (float64, float64) {
	x := key.X + (key.Width / 2)
	y := key.Y + (key.Height / 2)

	rotOrginX := key.RotationX
	rotOrginY := key.RotationY
	angle := 1 * key.RotationAngle
	angleRad := angle * math.Pi / 180

	x = x - rotOrginX
	y = y - rotOrginY

	x1 := (x * math.Cos(angleRad)) - (y * math.Sin(angleRad))
	y1 := (x * math.Sin(angleRad)) + (y * math.Cos(angleRad))

	x = x1 + rotOrginX
	y = y1 + rotOrginY

	return x, y
}

func annotateKeys(keys []kleKey) {
	for i, key := range keys {
		x, y := getKeyCenter(key)
		key.Labels = []string{fmt.Sprintf("%d,%d", int(y), int(x))}
		keys[i] = key
	}
}
