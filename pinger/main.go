package main

import (
	"bufio"
	"database/sql"
	"fmt"
	"io"
	"log"
	"math/rand"
	"os"
	"strings"
	"time"
)

// WorkerState stores information about running service workers.
type WorkerState struct {
	cancelChan chan struct{}
	url        string
	verifyKw   string
	excludeKw  string
	skipTls    bool
}

func main() {
	// Initialize random seed
	rand.Seed(time.Now().UnixNano())

	log.Println("Starting GSIS Monitor Pinger Daemon...")

	// Load environment variables from .env
	err := loadEnv(".env")
	if err != nil {
		// Try parent directory fallback
		err = loadEnv("../.env")
		if err != nil {
			log.Println("Warning: .env file not found, relying on system environment variables")
		}
	}

	dbHost := getEnv("DB_HOST", "localhost")
	dbPortStr := getEnv("DB_PORT", "5435")
	dbPort := 5435
	fmt.Sscanf(dbPortStr, "%d", &dbPort)
	dbName := getEnv("DB_NAME", "gsis_monitor")
	dbUser := getEnv("DB_USER", "gsis_user")
	dbPass := getEnv("DB_PASSWORD", "")

	log.Printf("Connecting to database at %s:%d/%s...", dbHost, dbPort, dbName)
	db, err := ConnectDB(dbHost, dbPort, dbUser, dbPass, dbName)
	if err != nil {
		log.Fatalf("Database connection failed: %s", err.Error())
	}
	defer db.Close()
	log.Println("Database connection successful.")

	workers := make(map[int]*WorkerState)

	// Main dynamic scheduler loop
	for {
		services, err := FetchActiveServices(db)
		if err != nil {
			log.Printf("Error fetching active services from database: %s", err.Error())
			time.Sleep(30 * time.Second)
			continue
		}

		activeServiceIDs := make(map[int]bool)

		for _, s := range services {
			activeServiceIDs[s.ID] = true

			state, exists := workers[s.ID]
			needStart := !exists

			if exists {
				// Check if service configuration has changed
				changed := state.url != s.URL ||
					state.skipTls != s.SkipTLSVerify ||
					getStrVal(s.VerificationKeyword) != state.verifyKw ||
					getStrVal(s.ExclusionKeyword) != state.excludeKw

				if changed {
					log.Printf("[%s] Configuration changed. Restarting worker...", s.Name)
					close(state.cancelChan)
					delete(workers, s.ID)
					needStart = true
				}
			}

			if needStart {
				cancelChan := make(chan struct{})
				workers[s.ID] = &WorkerState{
					cancelChan: cancelChan,
					url:        s.URL,
					verifyKw:   getStrVal(s.VerificationKeyword),
					excludeKw:  getStrVal(s.ExclusionKeyword),
					skipTls:    s.SkipTLSVerify,
				}
				go serviceWorker(s, db, cancelChan)
			}
		}

		// Clean up workers for services that are deactivated or deleted
		for id, state := range workers {
			if !activeServiceIDs[id] {
				log.Printf("Service ID %d is no longer active. Stopping worker...", id)
				close(state.cancelChan)
				delete(workers, id)
			}
		}

		// Check database for configuration updates every 30 seconds
		time.Sleep(30 * time.Second)
	}
}

// serviceWorker handles periodic pinging and alerting for a single service.
func serviceWorker(s Service, db *sql.DB, cancelChan chan struct{}) {
	// 1. WAF Bypass Staggered start: Sleep 1 to 15 seconds to prevent simultaneous starts
	startupDelay := rand.Intn(15) + 1
	log.Printf("[%s] Staggered start: sleeping for %d seconds before initial check", s.Name, startupDelay)
	
	select {
	case <-cancelChan:
		log.Printf("[%s] Worker stopped during staggered startup", s.Name)
		return
	case <-time.After(time.Duration(startupDelay) * time.Second):
	}

	for {
		log.Printf("[%s] Executing tracer HTTP request to %s", s.Name, s.URL)
		pingLog := PingService(s)

		// Insert telemetry log
		err := InsertPingLog(db, pingLog)
		if err != nil {
			log.Printf("[%s] Error inserting ping log: %s", s.Name, err.Error())
		} else {
			log.Printf("[%s] Telemetry logged successfully. Healthy: %t, Status: %s, Latency: %s ms, SSL Expiry: %s days",
				s.Name,
				pingLog.IsHealthy,
				getValOrNilStr(pingLog.StatusCode),
				getValOrNilStr(pingLog.TotalResponseMs),
				getValOrNilStr(pingLog.SSLExpiryDays),
			)
		}

		// Retrieve and evaluate alert rules
		rules, err := FetchAlertRules(db, s.ID)
		if err != nil {
			log.Printf("[%s] Error retrieving alert rules: %s", s.Name, err.Error())
		} else {
			err = ProcessAlerts(db, s.ID, pingLog, rules)
			if err != nil {
				log.Printf("[%s] Error processing alerts: %s", s.Name, err.Error())
			}
		}

		// 2. WAF Bypass Jitter: Random interval between 2 and 5 minutes (120 to 300 seconds)
		jitter := rand.Intn(181) + 120
		log.Printf("[%s] Worker sleeping for %d seconds before next check", s.Name, jitter)

		select {
		case <-cancelChan:
			log.Printf("[%s] Worker stopped", s.Name)
			return
		case <-time.After(time.Duration(jitter) * time.Second):
		}
	}
}

// loadEnv parses env variables from a file and sets them in system environment.
func loadEnv(filename string) error {
	file, err := os.Open(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	reader := bufio.NewReader(file)
	for {
		line, err := reader.ReadString('\n')
		if err != nil && err != io.EOF {
			return err
		}

		line = strings.TrimSpace(line)
		if line != "" && !strings.HasPrefix(line, "#") {
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				val := strings.TrimSpace(parts[1])
				val = strings.Trim(val, `"'`)
				os.Setenv(key, val)
			}
		}

		if err == io.EOF {
			break
		}
	}
	return nil
}

// getEnv returns env variable value or fallback.
func getEnv(key, fallback string) string {
	if val, ok := os.LookupEnv(key); ok {
		return val
	}
	return fallback
}

// getStrVal extracts string content from pointer, returning empty if nil.
func getStrVal(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// getValOrNilStr returns formatted string representing the pointer value or "nil".
func getValOrNilStr(v interface{}) string {
	if v == nil {
		return "nil"
	}
	switch p := v.(type) {
	case *int:
		if p == nil {
			return "nil"
		}
		return fmt.Sprintf("%d", *p)
	case *float64:
		if p == nil {
			return "nil"
		}
		return fmt.Sprintf("%.2f", *p)
	case *string:
		if p == nil {
			return "nil"
		}
		return *p
	}
	return fmt.Sprintf("%v", v)
}
