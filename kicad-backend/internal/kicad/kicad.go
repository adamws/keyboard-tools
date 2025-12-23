package kicad

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// Constants for SVG export templates and library paths
const (
	SVGTemplateFront    = "F.Cu,F.SilkS,Edge.Cuts"
	SVGTemplateBack     = "B.Cu,B.SilkS,Edge.Cuts"
	SwitchesLibraryPath = "/footprints/com_github_perigoso_keyswitch-kicad-library/"
	DiodeLibraryPath    = "/usr/share/kicad/footprints/"
)

// RunKBPlacer runs the kbplacer tool to generate KiCad PCB and schematic files
func RunKBPlacer(
	pcbPath string,
	layoutPath string,
	routeSwitchesWithDiodes bool,
	routeRowsAndColumns bool,
	switchFootprint string,
	diodeFootprint string,
	logPath string,
) error {
	// Build command arguments
	args := []string{
		"-m", "kbplacer",
		"--pcb-file", pcbPath,
		"--create-sch-file",
		"--create-pcb-file",
		"--switch-footprint", switchFootprint,
		"--diode-footprint", diodeFootprint,
		"--layout", layoutPath,
		"--log-level", "INFO",
	}

	// Add conditional flags
	if routeSwitchesWithDiodes {
		args = append(args, "--route-switches-with-diodes")
	}
	if routeRowsAndColumns {
		args = append(args, "--route-rows-and-columns")
	}

	// Create command
	cmd := exec.Command("python3", args...)

	// Open log file for output
	log.Printf("kcplbaer logpath: %s", logPath)
	logFile, err := os.Create(logPath)
	if err != nil {
		return fmt.Errorf("failed to create log file: %w", err)
	}
	defer logFile.Close()

	// Redirect stdout and stderr to log file
	cmd.Stdout = logFile
	cmd.Stderr = logFile

	// Run command
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("kbplacer failed: %w", err)
	}

	return nil
}

func GetKicad3rdPartyPath() (string, error) {
	dirname, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	src := filepath.Join(dirname, ".local/share/kicad/9.0/3rdparty")
	return src, nil
}

// BundleSwitchFootprints copies switch footprint library into the project
func BundleSwitchFootprints(projectPath string, libNickname string) error {
	kicad3rdParty, err := GetKicad3rdPartyPath()
	if err != nil {
		return fmt.Errorf("failed to get KiCad 3rd party path: %w", err)
	}

	src := filepath.Join(kicad3rdParty, SwitchesLibraryPath, libNickname+".pretty")
	dst := filepath.Join(projectPath, "footprints", libNickname+".pretty")

	// Create destination directory
	if err := os.MkdirAll(dst, 0755); err != nil {
		return fmt.Errorf("failed to create footprints directory: %w", err)
	}

	// Copy directory contents
	if err := copyDir(src, dst); err != nil {
		return fmt.Errorf("failed to copy footprint library: %w", err)
	}

	// Write fp-lib-table file
	fpLibTablePath := filepath.Join(projectPath, "fp-lib-table")
	fpLibTableContent := fmt.Sprintf(`(fp_lib_table
   (version 7)
   (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/footprints/%s.pretty")(options "")(descr ""))
)
`, libNickname, libNickname)

	if err := os.WriteFile(fpLibTablePath, []byte(fpLibTableContent), 0644); err != nil {
		return fmt.Errorf("failed to write fp-lib-table: %w", err)
	}

	return nil
}

// RunKiCadSVG exports PCB to SVG format
func RunKiCadSVG(pcbFile string, layers string, outputFile string) error {
	args := []string{
		"pcb", "export", "svg",
		"--layers", layers,
		"--exclude-drawing-sheet",
		"--fit-page-to-board",
		"--mode-single",
		"-o", outputFile,
		pcbFile,
	}

	cmd := exec.Command("kicad-cli", args...)

	// Run command
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("kicad-cli svg export failed: %w", err)
	}

	return nil
}

// GenerateRender generates front and back SVG renders of the PCB
func GenerateRender(pcbPath string, logPath string) error {
	logDir := filepath.Dir(logPath)

	// Generate front render
	frontSVG := filepath.Join(logDir, "front.svg")
	if err := RunKiCadSVG(pcbPath, SVGTemplateFront, frontSVG); err != nil {
		return fmt.Errorf("failed to generate front render: %w", err)
	}

	// Generate back render
	backSVG := filepath.Join(logDir, "back.svg")
	if err := RunKiCadSVG(pcbPath, SVGTemplateBack, backSVG); err != nil {
		return fmt.Errorf("failed to generate back render: %w", err)
	}

	return nil
}

// GenerateSchematicImage exports schematic to SVG
func GenerateSchematicImage(schematicPath string, logPath string) error {
	schematicDir := filepath.Dir(schematicPath)
	logDir := filepath.Dir(logPath)

	args := []string{
		"sch", "export", "svg",
		"--exclude-drawing-sheet",
		"--output", schematicDir,
		schematicPath,
	}

	cmd := exec.Command("kicad-cli", args...)

	// Run command (don't check error yet, we'll verify output file exists)
	_ = cmd.Run()

	// Check if output file was created
	name := strings.TrimSuffix(filepath.Base(schematicPath), filepath.Ext(schematicPath))
	expectedResult := filepath.Join(schematicDir, name+".svg")

	if _, err := os.Stat(expectedResult); os.IsNotExist(err) {
		return fmt.Errorf("failed to generate schematic image")
	}

	// Copy to logs directory
	targetPath := filepath.Join(logDir, "schematic.svg")
	if err := copyFile(expectedResult, targetPath); err != nil {
		return fmt.Errorf("failed to copy schematic image: %w", err)
	}

	return nil
}

// CreateWorkDir creates a temporary work directory with task ID prefix
func CreateWorkDir(taskID string) (string, error) {
	workDir, err := os.MkdirTemp("", taskID)
	log.Printf("Created workdir: %s", workDir)
	if err != nil {
		return "", fmt.Errorf("failed to create work directory: %w", err)
	}

	absPath, err := filepath.Abs(workDir)
	if err != nil {
		return "", fmt.Errorf("failed to get absolute path: %w", err)
	}

	return absPath, nil
}

// GetProjectName returns a sanitized project name from layout name
func GetProjectName(layoutName string) string {
	if layoutName == "" {
		return "keyboard"
	}
	return SanitizeFilename(layoutName)
}

// CreateKicadWorkDir creates the KiCad project directory
func CreateKicadWorkDir(workDir string, projectName string) (string, error) {
	projectDirName := SanitizeFilepath(projectName)
	projectDir := filepath.Join(workDir, projectDirName)

	if err := os.Mkdir(projectDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create project directory: %w", err)
	}

	absPath, err := filepath.Abs(projectDir)
	if err != nil {
		return "", fmt.Errorf("failed to get absolute path: %w", err)
	}

	return absPath, nil
}

// CreateLogDir creates the logs directory
func CreateLogDir(workDir string) (string, error) {
	logDir := filepath.Join(workDir, "logs")

	if err := os.Mkdir(logDir, 0755); err != nil {
		return "", fmt.Errorf("failed to create log directory: %w", err)
	}

	absPath, err := filepath.Abs(logDir)
	if err != nil {
		return "", fmt.Errorf("failed to get absolute path: %w", err)
	}

	return absPath, nil
}

// NewPCB is the main entry point for generating a KiCad PCB project
func NewPCB(taskID string, taskRequest map[string]interface{}) (string, error) {
	// Extract layout and settings from request
	layout, ok := taskRequest["layout"].(map[string]interface{})
	if !ok {
		return "", ErrInvalidLayout
	}

	settings, ok := taskRequest["settings"].(map[string]interface{})
	if !ok {
		return "", ErrInvalidSettings
	}

	// Parse settings
	switchFootprintSetting, _ := settings["switchFootprint"].(string)
	diodeFootprintSetting, _ := settings["diodeFootprint"].(string)
	routing, _ := settings["routing"].(string)

	// Split footprint settings into library nickname and footprint name
	// Format: "lib_nickname:footprint"
	switchParts := strings.SplitN(switchFootprintSetting, ":", 2)
	if len(switchParts) != 2 {
		return "", fmt.Errorf("%w: switchFootprint must be in format 'lib:footprint'", ErrInvalidFootprintFormat)
	}
	switchLibNickname := switchParts[0]
	switchFp := switchParts[1]

	diodeParts := strings.SplitN(diodeFootprintSetting, ":", 2)
	if len(diodeParts) != 2 {
		return "", fmt.Errorf("%w: diodeFootprint must be in format 'lib:footprint'", ErrInvalidFootprintFormat)
	}
	diodeLibNickname := diodeParts[0]
	diodeFp := diodeParts[1]

	// Construct full footprint paths
	kicad3rdParty, err := GetKicad3rdPartyPath()
	switchFootprint := kicad3rdParty + SwitchesLibraryPath + switchLibNickname + ".pretty:" + switchFp
	diodeFootprint := DiodeLibraryPath + diodeLibNickname + ".pretty:" + diodeFp

	fmt.Printf("switch_footprint=%s diode_footprint=%s\n", switchFootprint, diodeFootprint)

	// Determine routing options
	routeSwitchesWithDiodes := routing == "Switch-Diode only" || routing == "Full"
	routeRowsAndColumns := routing == "Full"

	// Create work directory
	workDir, err := CreateWorkDir(taskID)
	if err != nil {
		return "", err
	}

	// Get project name from layout metadata
	meta, ok := layout["meta"].(map[string]interface{})
	if !ok {
		return "", ErrInvalidLayoutMetadata
	}
	layoutName, _ := meta["name"].(string)
	projectName := GetProjectName(layoutName)

	// Create project directory
	projectFullPath, err := CreateKicadWorkDir(workDir, projectName)
	if err != nil {
		return "", err
	}

	// Create log directory
	logDir, err := CreateLogDir(workDir)
	if err != nil {
		return "", err
	}
	logPath := filepath.Join(logDir, "build.log")

	// Define file paths
	schFile := filepath.Join(projectFullPath, projectName+".kicad_sch")
	pcbFile := filepath.Join(projectFullPath, projectName+".kicad_pcb")
	layoutFile := filepath.Join(projectFullPath, projectName+".json")

	// Write layout JSON file
	layoutJSON, err := json.MarshalIndent(layout, "", "  ")
	if err != nil {
		return "", fmt.Errorf("failed to marshal layout JSON: %w", err)
	}
	if err := os.WriteFile(layoutFile, layoutJSON, 0644); err != nil {
		return "", fmt.Errorf("failed to write layout file: %w", err)
	}

	// Run kbplacer to generate PCB and schematic
	if err := RunKBPlacer(
		pcbFile,
		layoutFile,
		routeSwitchesWithDiodes,
		routeRowsAndColumns,
		switchFootprint,
		diodeFootprint,
		logPath,
	); err != nil {
		return "", err
	}

	// Bundle switch footprints
	if err := BundleSwitchFootprints(projectFullPath, switchLibNickname); err != nil {
		return "", err
	}

	// Generate schematic image
	if err := GenerateSchematicImage(schFile, logPath); err != nil {
		return "", err
	}

	// Generate renders
	if err := GenerateRender(pcbFile, logPath); err != nil {
		return "", err
	}

	return workDir, nil
}

// Helper function to copy a file
func copyFile(src, dst string) error {
	input, err := os.ReadFile(src)
	if err != nil {
		return err
	}

	err = os.WriteFile(dst, input, 0644)
	if err != nil {
		return err
	}

	return nil
}

// Helper function to copy a directory recursively
func copyDir(src string, dst string) error {
	return filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Get relative path
		relPath, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}

		targetPath := filepath.Join(dst, relPath)

		if info.IsDir() {
			return os.MkdirAll(targetPath, info.Mode())
		}

		return copyFile(path, targetPath)
	})
}
