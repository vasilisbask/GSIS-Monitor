package main

import (
	"database/sql"
	"fmt"

	_ "github.com/lib/pq"
)

// ConnectDB establishes a connection to PostgreSQL/TimescaleDB.
func ConnectDB(host string, port int, user, password, dbname string) (*sql.DB, error) {
	connStr := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname)
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, err
	}
	// Verify connection
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return db, nil
}

// FetchActiveServices retrieves all active services from the database.
func FetchActiveServices(db *sql.DB) ([]Service, error) {
	rows, err := db.Query("SELECT id, name, url, verification_keyword, exclusion_keyword, skip_tls_verify, is_active, created_at, updated_at FROM service WHERE is_active = true")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var services []Service
	for rows.Next() {
		var s Service
		err := rows.Scan(&s.ID, &s.Name, &s.URL, &s.VerificationKeyword, &s.ExclusionKeyword, &s.SkipTLSVerify, &s.IsActive, &s.CreatedAt, &s.UpdatedAt)
		if err != nil {
			return nil, err
		}
		services = append(services, s)
	}
	return services, rows.Err()
}

// InsertPingLog writes a ping telemetry log entry to the database.
func InsertPingLog(db *sql.DB, log *PingLog) error {
	query := `
		INSERT INTO ping_log (
			time, service_id, is_healthy, status_code, error_message,
			dns_lookup_ms, tcp_connect_ms, tls_handshake_ms, ttfb_ms,
			total_response_ms, ssl_expiry_days, content_verified
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`
	_, err := db.Exec(query,
		log.Time, log.ServiceID, log.IsHealthy, log.StatusCode, log.ErrorMessage,
		log.DNSLookupMs, log.TCPConnectMs, log.TLSHandshakeMs, log.TTFBMs,
		log.TotalResponseMs, log.SSLExpiryDays, log.ContentVerified,
	)
	return err
}

// FetchAlertRules retrieves all active alert rules for a specific service.
func FetchAlertRules(db *sql.DB, serviceID int) ([]AlertRule, error) {
	rows, err := db.Query("SELECT id, service_id, metric, operator, value, is_active, created_at FROM alert_rule WHERE service_id = $1 AND is_active = true", serviceID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var rules []AlertRule
	for rows.Next() {
		var r AlertRule
		err := rows.Scan(&r.ID, &r.ServiceID, &r.Metric, &r.Operator, &r.Value, &r.IsActive, &r.CreatedAt)
		if err != nil {
			return nil, err
		}
		rules = append(rules, r)
	}
	return rules, rows.Err()
}

// EvaluateOperator performs the mathematical/string comparison for alert rules.
func EvaluateOperator(val float64, op string, limit float64) bool {
	switch op {
	case ">":
		return val > limit
	case "<":
		return val < limit
	case "=":
		return val == limit
	case "!=":
		return val != limit
	default:
		return false
	}
}

// ProcessAlerts evaluates rules and updates the alert_log table.
func ProcessAlerts(db *sql.DB, serviceID int, pingLog *PingLog, rules []AlertRule) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// 1. Handle general connection health alert (rule_id is NULL)
	var activeGenAlertID int
	err = tx.QueryRow("SELECT id FROM alert_log WHERE service_id = $1 AND alert_rule_id IS NULL AND status = 'active'", serviceID).Scan(&activeGenAlertID)
	if err != nil && err != sql.ErrNoRows {
		return err
	}

	if !pingLog.IsHealthy {
		// Service is unhealthy, check if we need to trigger an alert
		if err == sql.ErrNoRows {
			errMsg := "Service is unreachable"
			if pingLog.ErrorMessage != nil {
				errMsg = fmt.Sprintf("Service is unreachable: %s", *pingLog.ErrorMessage)
			}
			_, err = tx.Exec(
				"INSERT INTO alert_log (service_id, alert_rule_id, status, message, triggered_at) VALUES ($1, NULL, 'active', $2, $3)",
				serviceID, errMsg, pingLog.Time,
			)
			if err != nil {
				return err
			}
		}
	} else {
		// Service is healthy, resolve general health alert if active
		if err == nil {
			_, err = tx.Exec(
				"UPDATE alert_log SET status = 'resolved', resolved_at = $1, message = message || ' (Auto-resolved)' WHERE id = $2",
				pingLog.Time, activeGenAlertID,
			)
			if err != nil {
				return err
			}
		}
	}

	// 2. Handle specific rules
	for _, rule := range rules {
		violated := false
		var reason string

		switch rule.Metric {
		case "latency":
			if pingLog.TotalResponseMs == nil {
				violated = true
				reason = "Service latency is unavailable (unreachable/timeout)"
			} else {
				violated = EvaluateOperator(*pingLog.TotalResponseMs, rule.Operator, rule.Value)
				if violated {
					reason = fmt.Sprintf("Latency %.2f ms violated threshold %s %.2f ms", *pingLog.TotalResponseMs, rule.Operator, rule.Value)
				}
			}

		case "status_code":
			if pingLog.StatusCode == nil {
				violated = true
				reason = "Status code is unavailable (connection error)"
			} else {
				violated = EvaluateOperator(float64(*pingLog.StatusCode), rule.Operator, rule.Value)
				if violated {
					reason = fmt.Sprintf("Status code %d violated threshold %s %.0f", *pingLog.StatusCode, rule.Operator, rule.Value)
				}
			}

		case "ssl_expiry":
			if pingLog.SSLExpiryDays == nil {
				// Only violate if HTTPS, ignore for HTTP
				violated = true
				reason = "SSL certificate details are unavailable"
			} else {
				violated = EvaluateOperator(float64(*pingLog.SSLExpiryDays), rule.Operator, rule.Value)
				if violated {
					if *pingLog.SSLExpiryDays < 0 {
						absDays := -(*pingLog.SSLExpiryDays)
						reason = fmt.Sprintf("SSL certificate expired %d days ago, violating threshold %s %.0f days", absDays, rule.Operator, rule.Value)
					} else {
						reason = fmt.Sprintf("SSL certificate expires in %d days, violating threshold %s %.0f days", *pingLog.SSLExpiryDays, rule.Operator, rule.Value)
					}
				}
			}

		case "content_verified":
			// rule.Value = 1 means content must be verified (ContentVerified must be true). If false, it's violated.
			// rule.Value = 0 means content must NOT be verified.
			val := 0.0
			if pingLog.ContentVerified {
				val = 1.0
			}
			violated = EvaluateOperator(val, rule.Operator, rule.Value)
			if violated {
				reason = "Content keyword verification failed"
			}
		}

		// Check if there is already an active alert for this rule
		var activeAlertID int
		errRuleAlert := tx.QueryRow("SELECT id FROM alert_log WHERE service_id = $1 AND alert_rule_id = $2 AND status = 'active'", serviceID, rule.ID).Scan(&activeAlertID)
		if errRuleAlert != nil && errRuleAlert != sql.ErrNoRows {
			return errRuleAlert
		}

		if violated {
			// Rule violated, insert alert if not already active
			if errRuleAlert == sql.ErrNoRows {
				_, err = tx.Exec(
					"INSERT INTO alert_log (service_id, alert_rule_id, status, message, triggered_at) VALUES ($1, $2, 'active', $3, $4)",
					serviceID, rule.ID, reason, pingLog.Time,
				)
				if err != nil {
					return err
				}
			}
		} else {
			// Rule is NOT violated, resolve existing alert if active
			if errRuleAlert == nil {
				_, err = tx.Exec(
					"UPDATE alert_log SET status = 'resolved', resolved_at = $1, message = message || ' (Auto-resolved)' WHERE id = $2",
					pingLog.Time, activeAlertID,
				)
				if err != nil {
					return err
				}
			}
		}
	}

	return tx.Commit()
}
