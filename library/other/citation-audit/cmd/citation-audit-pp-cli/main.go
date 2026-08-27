// pp-citation-audit — Thin client for Kapowsin Citation Audit Server
// Checks what 13 AI models actually recommend when buyers ask for your industry in your city.
// Thin wrapper over http://localhost:8421 (or CITATION_AUDIT_URL)
//
// Commands:
//   pp-citation-audit health
//   pp-citation-audit check "Company Name" --city Tacoma --industry "real estate"
//   pp-citation-audit audit "Company Name" --city Tacoma --industry "real estate" --owners "Alice,Bob"
//   pp-citation-audit version
//
// Env:
//   CITATION_AUDIT_URL   (default http://localhost:8421)
//   CITATION_AUDIT_TOKEN (default kapowsin-assessment-2026)
//
// Build: go build -o pp-citation-audit .
// Install (after publishing): go install github.com/kapowsin/printing-press-library/library/other/citation-audit/cmd/citation-audit-pp-cli@latest

package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	defaultServerURL = "http://localhost:8421"
	defaultToken     = "kapowsin-assessment-2026"
	version          = "1.0.0"
)

var (
	serverURL string
	useJSON   bool
	token     string
)

// ANSI colors
const (
	reset  = "\033[0m"
	bold   = "\033[1m"
	green  = "\033[92m"
	blue   = "\033[94m"
	yellow = "\033[93m"
	red    = "\033[91m"
	gray   = "\033[90m"
)

func gradeColor(grade string) string {
	g := strings.ToUpper(strings.TrimSpace(grade))
	switch {
	case strings.HasPrefix(g, "A"):
		return green
	case strings.HasPrefix(g, "B"):
		return blue
	case strings.HasPrefix(g, "C"):
		return yellow
	default:
		return red
	}
}

func printHeader(company, city, state string) {
	fmt.Println()
	fmt.Printf("%s%s%s\n", bold, strings.Repeat("=", 58), reset)
	fmt.Printf("%s  AI Citation Audit — %s%s\n", bold, company, reset)
	fmt.Printf("  %s, %s\n", city, state)
	fmt.Printf("%s%s%s\n", bold, strings.Repeat("=", 58), reset)
	fmt.Println()
}

func cmdHealth() {
	url := serverURL + "/api/citation-audit/health"
	client := &http.Client{Timeout: 8 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		fmt.Printf("❌ Cannot reach server at %s: %v\n", serverURL, err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		fmt.Printf("⚠️  Server responded but invalid JSON: %s\n", string(body))
		return
	}

	if status, ok := data["status"].(string); ok && status == "ok" {
		models := 13
		if m, ok := data["models_available"].(float64); ok {
			models = int(m)
		}
		v := "1.0.0"
		if ver, ok := data["version"].(string); ok {
			v = ver
		}
		fmt.Printf("✅ Server healthy — %d models available (v%s)\n", models, v)
	} else {
		fmt.Printf("⚠️  Server responded but status: %s\n", string(body))
	}
}

func cmdVersion() {
	fmt.Printf("pp-citation-audit v%s\n", version)
	fmt.Printf("Server: %s\n", serverURL)
}

func doQuickCheck(company, city, state, industry, owner, email string) {
	payload := map[string]interface{}{
		"company_name": company,
		"city":         city,
		"state":        state,
		"industry":     industry,
	}
	if owner != "" {
		payload["owner_name"] = owner
	}
	if email != "" {
		payload["email"] = email
	}

	bodyBytes, _ := json.Marshal(payload)
	url := serverURL + "/api/citation-audit/quick"

	client := &http.Client{Timeout: 120 * time.Second}
	req, _ := http.NewRequest("POST", url, bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("❌ Request failed: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		fmt.Printf("❌ Server error %d: %s\n", resp.StatusCode, string(respBody))
		os.Exit(1)
	}

	var data map[string]interface{}
	if err := json.Unmarshal(respBody, &data); err != nil {
		fmt.Printf("❌ Bad JSON from server: %v\n", err)
		fmt.Println(string(respBody))
		os.Exit(1)
	}

	if useJSON {
		pretty, _ := json.MarshalIndent(data, "", "  ")
		fmt.Println(string(pretty))
		return
	}

	// Pretty output matching SKILL + client
	grade := "F"
	if g, ok := data["grade"].(string); ok {
		grade = g
	}
	color := gradeColor(grade)
	appeared := 0
	if a, ok := data["appeared_in"].(float64); ok {
		appeared = int(a)
	}
	checked := 4
	if c, ok := data["models_checked"].(float64); ok {
		checked = int(c)
	}
	score := 0
	if s, ok := data["visibility_score"].(float64); ok {
		score = int(s)
	}

	printHeader(
		getString(data, "company", company),
		getString(data, "city", city),
		getString(data, "state", state),
	)

	fmt.Printf("  %sAI Visibility Score:%s %s%s%s  (%d/%d models cited you)\n", bold, reset, color, grade, reset, appeared, checked)
	fmt.Printf("  %sScore:%s %d/100\n\n", bold, reset, score)

	if oneLine, ok := data["one_line"].(string); ok && oneLine != "" {
		fmt.Printf("  %sOne-line verdict:%s\n", bold, reset)
		fmt.Printf("  %s\n\n", oneLine)
	}

	if topGap, ok := data["top_gap"].(string); ok && topGap != "" {
		fmt.Printf("  %sTop gap:%s %s\n", bold, reset, topGap)
	}
	if comp, ok := data["competitor_cited"].(string); ok && comp != "" {
		fmt.Printf("  %s🔴 Competitor:%s %s\n", bold, reset, comp)
	}

	fmt.Println()
	cta := "https://cal.com/thekapowsincompany/discovery"
	if c, ok := data["cta_url"].(string); ok && c != "" {
		cta = c
	}
	fmt.Printf("  %s📅 Book Your Full Assessment →%s\n", bold, reset)
	fmt.Printf("  %s\n", cta)
	fmt.Printf("%s%s%s\n\n", bold, strings.Repeat("=", 58), reset)
}

func doFullAudit(company, city, state, industry, owners, aliases, website, email string) {
	payload := map[string]interface{}{
		"company_name": company,
		"city":         city,
		"state":        state,
		"industry":     industry,
	}
	if owners != "" {
		ownerList := []string{}
		for _, o := range strings.Split(owners, ",") {
			if t := strings.TrimSpace(o); t != "" {
				ownerList = append(ownerList, t)
			}
		}
		payload["owner_names"] = ownerList
	}
	if aliases != "" {
		aliasList := []string{}
		for _, a := range strings.Split(aliases, ",") {
			if t := strings.TrimSpace(a); t != "" {
				aliasList = append(aliasList, t)
			}
		}
		payload["aliases"] = aliasList
	}
	if website != "" {
		payload["website"] = website
	}
	if email != "" {
		payload["email"] = email
	}

	bodyBytes, _ := json.Marshal(payload)
	url := serverURL + "/api/citation-audit/full"

	client := &http.Client{Timeout: 180 * time.Second}
	req, _ := http.NewRequest("POST", url, bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Audit-Token", token)

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("❌ Request failed: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		fmt.Printf("❌ Server error %d: %s\n", resp.StatusCode, string(respBody))
		os.Exit(1)
	}

	var data map[string]interface{}
	if err := json.Unmarshal(respBody, &data); err != nil {
		fmt.Printf("❌ Bad JSON from server: %v\n", err)
		os.Exit(1)
	}

	if useJSON {
		pretty, _ := json.MarshalIndent(data, "", "  ")
		fmt.Println(string(pretty))
		return
	}

	// Formatted summary (full matrix is verbose — user can --json for raw)
	grade := "F"
	if g, ok := data["grade"].(string); ok {
		grade = g
	}
	color := gradeColor(grade)
	score := 0
	if s, ok := data["ai_visibility_score"].(float64); ok {
		score = int(s)
	}

	printHeader(
		getString(data, "company", company),
		getString(data, "city", city),
		getString(data, "state", state),
	)

	fmt.Printf("  %sAI Visibility Score:%s %s%s%s  (%d/100)\n\n", bold, reset, color, grade, reset, score)

	// Quick wins if present
	if qw, ok := data["quick_wins"].([]interface{}); ok && len(qw) > 0 {
		fmt.Printf("  %sQuick wins:%s\n", bold, reset)
		for i, w := range qw {
			fmt.Printf("  %d. %v\n", i+1, w)
		}
		fmt.Println()
	}

	// Name consistency
	if nc, ok := data["name_consistency"].(map[string]interface{}); ok {
		ncGrade := "?"
		if g, ok := nc["grade"].(string); ok {
			ncGrade = g
		}
		fmt.Printf("  %sName Consistency:%s Grade %s%s%s\n", bold, reset, gradeColor(ncGrade), ncGrade, reset)
		if note, ok := nc["note"].(string); ok && note != "" {
			fmt.Printf("  %s\n", note)
		}
		fmt.Println()
	}

	// Competitors
	if comps, ok := data["competitor_citations"].([]interface{}); ok && len(comps) > 0 {
		fmt.Printf("  %s⚠️  Competitors appearing instead of you:%s\n", bold, reset)
		for _, c := range comps {
			if m, ok := c.(map[string]interface{}); ok {
				compName := getString(m, "competitor", "?")
				apps := 0
				if a, ok := m["appeared_in"].(float64); ok {
					apps = int(a)
				}
				fmt.Printf("    • %s — cited in %d models\n", compName, apps)
			}
		}
		fmt.Println()
	}

	fmt.Printf("  %sFull matrix available with --json%s\n", gray, reset)
	fmt.Printf("  %s📅 Book full review to get the complete 13-model breakdown + action plan%s\n", bold, reset)
	fmt.Printf("  https://cal.com/thekapowsincompany/ai-assessment-report-call\n")
	fmt.Printf("%s%s%s\n\n", bold, strings.Repeat("=", 58), reset)
}

func getString(m map[string]interface{}, key, fallback string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return fallback
}

// extractPositionalAndFlags pulls first non-flag arg as company name (supports company-first style)
// and returns the remaining args for flag parsing.
func extractPositionalAndFlags(args []string) (string, []string) {
	if len(args) == 0 {
		return "", args
	}
	// find first arg that does not start with -
	for i, a := range args {
		if !strings.HasPrefix(a, "-") {
			company := a
			// return args without the company (flags before + after)
			flagArgs := append([]string{}, args[:i]...)
			flagArgs = append(flagArgs, args[i+1:]...)
			return company, flagArgs
		}
	}
	return "", args // all flags, no company yet
}

func usage() {
	fmt.Printf(`pp-citation-audit — Multi-model AI citation audit (Kapowsin)

Usage:
  pp-citation-audit health
  pp-citation-audit check "Company Name" --city <city> [--state WA] --industry <ind>
  pp-citation-audit audit "Company Name" --city <city> --industry <ind> [flags]
  pp-citation-audit version

Global flags:
  --server URL     Override server (env: CITATION_AUDIT_URL)
  --json           Raw JSON output

check flags:
  --owner string   Owner/agent name
  --email string   Email for logging/leads

audit flags:
  --owners "A,B"   Comma-separated owner names
  --aliases "X,Y"  Comma-separated known name variants
  --website domain Website (e.g. theoryre.com)
  --email string

Server must be running: uvicorn scripts.citation_audit_server:app --port 8421
`)
}

func main() {
	// Env first
	serverURL = os.Getenv("CITATION_AUDIT_URL")
	if serverURL == "" {
		serverURL = defaultServerURL
	}
	token = os.Getenv("CITATION_AUDIT_TOKEN")
	if token == "" {
		token = defaultToken
	}

	// Global flags (parsed before subcommand for simplicity)
	flag.StringVar(&serverURL, "server", serverURL, "Server base URL")
	flag.BoolVar(&useJSON, "json", false, "Output raw JSON")
	flag.Parse()

	args := flag.Args()
	if len(args) == 0 {
		usage()
		os.Exit(1)
	}

	cmd := args[0]
	subArgs := args[1:]

	switch cmd {
	case "health":
		cmdHealth()
	case "version":
		cmdVersion()
	case "check":
		// Support "check Company --city X" (company first) or flags first
		checkFlags := flag.NewFlagSet("check", flag.ExitOnError)
		city := checkFlags.String("city", "", "City (required)")
		state := checkFlags.String("state", "WA", "State")
		industry := checkFlags.String("industry", "real estate", "Industry")
		owner := checkFlags.String("owner", "", "Owner name")
		email := checkFlags.String("email", "", "Email")
		checkFlags.BoolVar(&useJSON, "json", useJSON, "JSON output")
		checkFlags.StringVar(&serverURL, "server", serverURL, "Server")

		company, flagArgs := extractPositionalAndFlags(subArgs)
		checkFlags.Parse(flagArgs)
		if company == "" {
			// fallback if company passed after flags
			remaining := checkFlags.Args()
			if len(remaining) > 0 {
				company = remaining[0]
			}
		}
		if company == "" {
			fmt.Println("check requires company name (positional)")
			os.Exit(1)
		}
		if *city == "" {
			fmt.Println("--city is required")
			os.Exit(1)
		}
		doQuickCheck(company, *city, *state, *industry, *owner, *email)

	case "audit":
		auditFlags := flag.NewFlagSet("audit", flag.ExitOnError)
		city := auditFlags.String("city", "", "City (required)")
		state := auditFlags.String("state", "WA", "State")
		industry := auditFlags.String("industry", "real estate", "Industry")
		owners := auditFlags.String("owners", "", "Owner names, comma sep")
		aliases := auditFlags.String("aliases", "", "Aliases, comma sep")
		website := auditFlags.String("website", "", "Website domain")
		email := auditFlags.String("email", "", "Email")
		auditFlags.BoolVar(&useJSON, "json", useJSON, "JSON output")
		auditFlags.StringVar(&serverURL, "server", serverURL, "Server")

		company, flagArgs := extractPositionalAndFlags(subArgs)
		auditFlags.Parse(flagArgs)
		if company == "" {
			remaining := auditFlags.Args()
			if len(remaining) > 0 {
				company = remaining[0]
			}
		}
		if company == "" {
			fmt.Println("audit requires company name (positional)")
			os.Exit(1)
		}
		if *city == "" {
			fmt.Println("--city is required for audit")
			os.Exit(1)
		}
		doFullAudit(company, *city, *state, *industry, *owners, *aliases, *website, *email)

	default:
		fmt.Printf("Unknown command: %s\n\n", cmd)
		usage()
		os.Exit(1)
	}
}
