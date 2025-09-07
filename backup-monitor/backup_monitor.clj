(ns backup-monitor
  "Alfresco Backup Monitoring for Riemann"
  (:require [clojure.java.io :as io]
            [clojure.string :as str])
  (:import [java.io File]
           [java.time LocalDateTime ZoneId]
           [java.time.format DateTimeFormatter]
           [java.util.concurrent.atomic AtomicLong]))

;; Configuration
(def config
  {:backup-root "/home/tmb/alfresco-backups"
   :expected-backup-interval-hours 25  ; Allow 1 hour leeway for daily backups
   :backup-retention {:daily 7, :weekly 4, :monthly 6}
   :min-backup-size-mb 1              ; Minimum expected backup size
   :max-backup-age-hours 168          ; 7 days - alert if backup is older
   :log-retention-days 30})

;; State tracking
(def backup-state (atom {}))
(def last-check-time (AtomicLong. 0))

;; Utility functions
(defn log-info [& messages]
  "Log info message"
  (println (str "[" (java.time.LocalDateTime/now) "] INFO: " (str/join " " messages))))

(defn log-error [& messages]
  "Log error message"
  (println (str "[" (java.time.LocalDateTime/now) "] ERROR: " (str/join " " messages))))

(defn file-size-mb [^File file]
  "Get file size in megabytes"
  (/ (.length file) (* 1024 1024)))

(defn file-age-hours [^File file]
  "Get file age in hours"
  (/ (- (System/currentTimeMillis) (.lastModified file)) (* 1000 60 60)))

(defn parse-backup-timestamp [filename]
  "Parse timestamp from backup filename like alfresco_20250902_235538.tar.gz"
  (when-let [match (re-find #"(\d{8}_\d{6})" filename)]
    (try
      (let [timestamp-str (second match)
            formatter (DateTimeFormatter/ofPattern "yyyyMMdd_HHmmss")
            date-time (LocalDateTime/parse timestamp-str formatter)]
        (.toEpochSecond (.atZone date-time (ZoneId/systemDefault))))
      (catch Exception e
        (log-error "Failed to parse timestamp from" filename ":" (.getMessage e))
        nil))))

(defn analyze-backup-file [^File file backup-type]
  "Analyze a single backup file and return metrics"
  (let [filename (.getName file)
        size-mb (file-size-mb file)
        age-hours (file-age-hours file)
        timestamp (parse-backup-timestamp filename)
        is-healthy (and (> size-mb (:min-backup-size-mb config))
                       (< age-hours (:max-backup-age-hours config)))]
    {:filename filename
     :path (.getAbsolutePath file)
     :type backup-type
     :size-mb size-mb
     :age-hours age-hours
     :timestamp timestamp
     :last-modified (.lastModified file)
     :healthy is-healthy}))

(defn get-backup-files [backup-dir backup-type]
  "Get all backup files in a directory"
  (try
    (let [dir (io/file backup-dir)]
      (if (.exists dir)
        (->> (.listFiles dir)
             (filter #(.isFile %))
             (filter #(str/ends-with? (.getName %) ".tar.gz"))
             (map #(analyze-backup-file % backup-type))
             (sort-by :timestamp)
             (reverse)) ; Most recent first
        []))
    (catch Exception e
      (log-error "Failed to read backup directory" backup-dir ":" (.getMessage e))
      [])))

(defn check-backup-freshness [backups expected-interval-hours]
  "Check if we have recent backups"
  (if (empty? backups)
    {:status :missing :message "No backups found"}
    (let [latest-backup (first backups)
          age-hours (:age-hours latest-backup)]
      (if (< age-hours expected-interval-hours)
        {:status :healthy :message "Recent backup available" :age-hours age-hours}
        {:status :stale :message (str "Latest backup is " (int age-hours) " hours old") :age-hours age-hours}))))

(defn check-backup-retention [backups expected-count]
  "Check if we have the expected number of backups"
  (let [actual-count (count backups)
        healthy-count (count (filter :healthy backups))]
    {:actual-count actual-count
     :expected-count expected-count
     :healthy-count healthy-count
     :status (cond
               (< actual-count (/ expected-count 2)) :critical
               (< actual-count expected-count) :warning
               :else :healthy)}))

(defn analyze-backup-integrity []
  "Analyze backup integrity by checking the latest backup"
  (try
    (let [daily-backups (get-backup-files (str (:backup-root config) "/daily") :daily)
          latest-backup (first daily-backups)]
      (if latest-backup
        (let [size-mb (:size-mb latest-backup)
              integrity-score (cond
                               (< size-mb 0.1) 0.0  ; Suspiciously small
                               (< size-mb 1.0) 0.3  ; Probably missing components
                               (< size-mb 5.0) 0.7  ; Likely missing content
                               (< size-mb 50) 0.9   ; Reasonable size
                               :else 1.0)]           ; Good size
          {:status (if (> integrity-score 0.5) :healthy :degraded)
           :score integrity-score
           :size-mb size-mb
           :filename (:filename latest-backup)})
        {:status :missing :score 0.0 :message "No backup files found"}))
    (catch Exception e
      (log-error "Backup integrity check failed:" (.getMessage e))
      {:status :error :score 0.0 :error (.getMessage e)})))

(defn calculate-backup-metrics []
  "Calculate comprehensive backup metrics"
  (try
    (let [daily-backups (get-backup-files (str (:backup-root config) "/daily") :daily)
          weekly-backups (get-backup-files (str (:backup-root config) "/weekly") :weekly)
          monthly-backups (get-backup-files (str (:backup-root config) "/monthly") :monthly)
          
          ; Freshness check
          freshness (check-backup-freshness daily-backups (:expected-backup-interval-hours config))
          
          ; Retention checks
          daily-retention (check-backup-retention daily-backups (get-in config [:backup-retention :daily]))
          weekly-retention (check-backup-retention weekly-backups (get-in config [:backup-retention :weekly]))
          monthly-retention (check-backup-retention monthly-backups (get-in config [:backup-retention :monthly]))
          
          ; Integrity check
          integrity (analyze-backup-integrity)
          
          ; Storage usage
          total-size-mb (reduce + (map :size-mb (concat daily-backups weekly-backups monthly-backups)))
          
          ; Overall health score
          health-score (/ (+ (case (:status freshness) :healthy 3 :stale 1 :missing 0)
                            (case (:status daily-retention) :healthy 2 :warning 1 :critical 0)
                            (case (:status integrity) :healthy 3 :degraded 1 :missing 0 :error 0)) 8.0)]
      
      {:timestamp (System/currentTimeMillis)
       :freshness freshness
       :retention {:daily daily-retention
                  :weekly weekly-retention
                  :monthly monthly-retention}
       :integrity integrity
       :storage {:total-size-mb total-size-mb
                :daily-count (count daily-backups)
                :weekly-count (count weekly-backups)
                :monthly-count (count monthly-backups)}
       :health-score health-score
       :overall-status (cond
                        (> health-score 0.8) :healthy
                        (> health-score 0.5) :warning
                        :else :critical)})
    (catch Exception e
      (log-error "Failed to calculate backup metrics:" (.getMessage e))
      {:timestamp (System/currentTimeMillis)
       :error (.getMessage e)
       :health-score 0.0
       :overall-status :error})))

(defn backup-metrics-to-riemann-events [metrics]
  "Convert backup metrics to Riemann events"
  (let [base-event {:time (/ (:timestamp metrics) 1000)
                   :host "trust-server"
                   :ttl 300}] ; 5 minute TTL
    
    (remove nil?
      [(merge base-event
              {:service "backup.health.score"
               :metric (:health-score metrics)
               :state (name (:overall-status metrics))
               :description (str "Overall backup health score: " (format "%.2f" (:health-score metrics)))})
       
       ; Freshness metrics
       (when-let [freshness (:freshness metrics)]
         (merge base-event
                {:service "backup.freshness.age_hours"
                 :metric (:age-hours freshness 999)
                 :state (name (:status freshness))
                 :description (:message freshness)}))
       
       ; Retention metrics
       (merge base-event
              {:service "backup.retention.daily.count"
               :metric (get-in metrics [:retention :daily :actual-count] 0)
               :state (name (get-in metrics [:retention :daily :status] :unknown))
               :description (str "Daily backups: " (get-in metrics [:retention :daily :actual-count] 0))})
       
       (merge base-event
              {:service "backup.retention.daily.healthy"
               :metric (get-in metrics [:retention :daily :healthy-count] 0)
               :description (str "Healthy daily backups: " (get-in metrics [:retention :daily :healthy-count] 0))})
       
       ; Integrity metrics
       (when-let [integrity (:integrity metrics)]
         (merge base-event
                {:service "backup.integrity.score"
                 :metric (:score integrity)
                 :state (name (:status integrity))
                 :description (str "Backup integrity score: " (format "%.2f" (:score integrity)))}))
       
       ; Storage metrics
       (merge base-event
              {:service "backup.storage.total_size_mb"
               :metric (get-in metrics [:storage :total-size-mb] 0)
               :description (str "Total backup storage: " (format "%.1f MB" (get-in metrics [:storage :total-size-mb] 0)))})
       
       (merge base-event
              {:service "backup.storage.daily_count"
               :metric (get-in metrics [:storage :daily-count] 0)
               :description (str "Number of daily backups: " (get-in metrics [:storage :daily-count] 0))})
       
       ; Backup process health
       (merge base-event
              {:service "backup.process.last_success"
               :metric (if (= (:overall-status metrics) :healthy) 1 0)
               :state (if (= (:overall-status metrics) :healthy) "ok" "critical")
               :description (str "Last backup process status: " (name (:overall-status metrics)))})])))

;; Main monitoring functions
(defn collect-backup-metrics []
  "Collect all backup metrics and return Riemann events"
  (try
    (log-info "Starting backup metrics collection...")
    (let [metrics (calculate-backup-metrics)
          events (backup-metrics-to-riemann-events metrics)]
      
      ; Update state
      (swap! backup-state assoc :last-metrics metrics :last-collection-time (System/currentTimeMillis))
      (.set last-check-time (System/currentTimeMillis))
      
      (log-info "Collected" (count events) "backup events, health score:" (format "%.2f" (:health-score metrics)))
      events)
    (catch Exception e
      (log-error "Backup metrics collection failed:" (.getMessage e))
      [{:service "backup.monitor.error"
        :state "critical"
        :metric 0
        :description (str "Backup monitoring error: " (.getMessage e))
        :time (/ (System/currentTimeMillis) 1000)
        :host "trust-server"
        :ttl 300}])))

(defn backup-monitor-health []
  "Return health status of the backup monitor itself"
  (let [last-check (.get last-check-time)
        current-time (System/currentTimeMillis)
        minutes-since-check (/ (- current-time last-check) (* 1000 60))]
    
    {:service "backup.monitor.health"
     :metric (if (< minutes-since-check 10) 1 0) ; Healthy if checked within 10 minutes
     :state (if (< minutes-since-check 10) "ok" "critical")
     :description (str "Backup monitor last ran " (int minutes-since-check) " minutes ago")
     :time (/ current-time 1000)
     :host "trust-server"
     :ttl 300}))

;; Public API
(defn get-current-backup-status []
  "Get current backup status summary"
  (:last-metrics @backup-state))

(defn force-backup-check []
  "Force an immediate backup check"
  (collect-backup-metrics))

(log-info "Backup monitor initialized. Config:" config)
