(ns postgres-monitor
  (:require [clojure.tools.logging :as log])
  (:import [java.sql DriverManager Connection PreparedStatement ResultSet]))

(def ^:dynamic *db-config*
  {:host "postgres"
   :port 5432
   :dbname "alfresco"
   :user "alfresco"
   :password "alfresco"})

(defn make-connection-url
  "Create JDBC connection URL from config"
  [config]
  (str "jdbc:postgresql://" (:host config) ":" (:port config) "/" (:dbname config)))


(defn get-connection
  "Get a database connection using pure Java interop"
  []
  (try
    ; Explicitly load the PostgreSQL driver
    (Class/forName "org.postgresql.Driver")
    (let [url (make-connection-url *db-config*)
          user (:user *db-config*)
          password (:password *db-config*)]
      (DriverManager/getConnection url user password))
    (catch Exception e
      (log/error e "Failed to create database connection")
      nil)))


(defn execute-query
  "Execute a SQL query and return results as a vector of maps"
  [conn query & params]
  (try
    (with-open [stmt (if params
                       (let [ps (.prepareStatement conn query)]
                         (doseq [[i param] (map-indexed vector params)]
                           (.setObject ps (inc i) param))
                         ps)
                       (.createStatement conn))]
      (with-open [rs (if params
                       (.executeQuery stmt)
                       (.executeQuery stmt query))]
        (let [meta (.getMetaData rs)
              cols (doall (for [i (range 1 (inc (.getColumnCount meta)))]
                           (keyword (clojure.string/lower-case (.getColumnName meta i)))))]
          (loop [results []]
            (if (.next rs)
              (recur (conj results 
                          (zipmap cols
                                 (for [col cols]
                                   (.getObject rs (name col))))))
              results)))))
    (catch Exception e
      (log/error e "Failed to execute query:" query)
      [])))

(defn test-connection
  "Test if we can connect to PostgreSQL"
  []
  (try
    (with-open [conn (get-connection)]
      (when conn
        (let [result (execute-query conn "SELECT version()")]
          (log/info "PostgreSQL connection successful:" (-> result first :version))
          true)))
    (catch Exception e
      (log/error e "Failed to connect to PostgreSQL")
      false)))

(defn collect-database-stats
  "Collect basic database statistics"
  []
  (try
    (with-open [conn (get-connection)]
      (when conn
        (execute-query conn 
          "SELECT datname, numbackends, xact_commit, xact_rollback, 
                  blks_read, blks_hit, deadlocks, temp_files, temp_bytes
           FROM pg_stat_database 
           WHERE datname NOT IN ('template0', 'template1', 'postgres')")))
    (catch Exception e
      (log/error e "Failed to collect database stats")
      [])))

(defn collect-connection-stats
  "Collect connection and activity statistics"
  []
  (try
    (with-open [conn (get-connection)]
      (when conn
        (first (execute-query conn
                 "SELECT 
                    count(*) as total_connections,
                    count(case when state = 'active' then 1 end) as active_connections,
                    count(case when state = 'idle' then 1 end) as idle_connections,
                    count(case when state = 'idle in transaction' then 1 end) as idle_in_transaction
                  FROM pg_stat_activity 
                  WHERE datname = ?" (:dbname *db-config*)))))
    (catch Exception e
      (log/error e "Failed to collect connection stats")
      {:total_connections 0 :active_connections 0 :idle_connections 0 :idle_in_transaction 0})))

(defn collect-table-stats
  "Collect table-level statistics for top tables"
  []
  (try
    (with-open [conn (get-connection)]
      (when conn
        (execute-query conn
          "SELECT schemaname, relname, seq_scan, seq_tup_read, 
                  idx_scan, idx_tup_fetch, n_tup_ins, n_tup_upd, n_tup_del
           FROM pg_stat_user_tables 
           ORDER BY (seq_tup_read + idx_tup_fetch) DESC 
           LIMIT 10")))
    (catch Exception e
      (log/error e "Failed to collect table stats")
      [])))

(defn safe-divide
  "Safe division that handles divide by zero"
  [numerator denominator]
  (if (and denominator (> denominator 0))
    (double (/ numerator denominator))
    0.0))

(defn format-database-events
  "Convert database stats to Riemann events"
  [stats timestamp]
  (mapcat 
    (fn [row]
      (let [db (:datname row)
            total-reads (+ (or (:blks_read row) 0) (or (:blks_hit row) 0))
            cache-hit-ratio (if (> total-reads 0)
                             (safe-divide (:blks_hit row) total-reads)
                             1.0)]
        [{:service (str "postgres." db ".connections")
          :metric (or (:numbackends row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "connections"]
          :description (str "Active connections to " db)}
         
         {:service (str "postgres." db ".transactions.commits") 
          :metric (or (:xact_commit row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "transactions"]
          :description "Total committed transactions"}
         
         {:service (str "postgres." db ".transactions.rollbacks")
          :metric (or (:xact_rollback row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "transactions"]
          :description "Total rolled back transactions"}
         
         {:service (str "postgres." db ".cache_hit_ratio")
          :metric cache-hit-ratio
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "performance"]
          :description "Buffer cache hit ratio"}
         
         {:service (str "postgres." db ".deadlocks")
          :metric (or (:deadlocks row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "locks"]
          :description "Number of deadlocks detected"}
         
         {:service (str "postgres." db ".temp_files")
          :metric (or (:temp_files row) 0)
          :time timestamp  
          :host "riemann-server"
          :tags ["postgresql" "performance"]
          :description "Number of temporary files created"}
         
         {:service (str "postgres." db ".temp_bytes")
          :metric (or (:temp_bytes row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "performance"] 
          :description "Total bytes in temporary files"}]))
    stats))

(defn format-connection-events
  "Convert connection stats to Riemann events"
  [stats timestamp]
  (let [db (:dbname *db-config*)]
    [{:service (str "postgres." db ".connections.total")
      :metric (or (:total_connections stats) 0)
      :time timestamp
      :host "riemann-server"
      :tags ["postgresql" "connections"]
      :description "Total database connections"}
     
     {:service (str "postgres." db ".connections.active")
      :metric (or (:active_connections stats) 0)
      :time timestamp
      :host "riemann-server"
      :tags ["postgresql" "connections"]
      :description "Currently active connections"}
     
     {:service (str "postgres." db ".connections.idle")
      :metric (or (:idle_connections stats) 0)
      :time timestamp
      :host "riemann-server"
      :tags ["postgresql" "connections"] 
      :description "Currently idle connections"}
     
     {:service (str "postgres." db ".connections.idle_in_transaction")
      :metric (or (:idle_in_transaction stats) 0)
      :time timestamp
      :host "riemann-server"
      :tags ["postgresql" "connections"]
      :description "Connections idle in transaction"}]))

(defn format-table-events
  "Convert table stats to Riemann events"
  [stats timestamp]
  (mapcat
    (fn [row]
      (let [table (str (:schemaname row) "." (:relname row))]
        [{:service (str "postgres.table." table ".sequential_scans")
          :metric (or (:seq_scan row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "tables"]
          :description (str "Sequential scans on " table)}
         
         {:service (str "postgres.table." table ".index_scans") 
          :metric (or (:idx_scan row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "tables"]
          :description (str "Index scans on " table)}
         
         {:service (str "postgres.table." table ".tuples_inserted")
          :metric (or (:n_tup_ins row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "tables"]
          :description (str "Tuples inserted into " table)}
         
         {:service (str "postgres.table." table ".tuples_updated")
          :metric (or (:n_tup_upd row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "tables"] 
          :description (str "Tuples updated in " table)}
         
         {:service (str "postgres.table." table ".tuples_deleted")
          :metric (or (:n_tup_del row) 0)
          :time timestamp
          :host "riemann-server"
          :tags ["postgresql" "tables"]
          :description (str "Tuples deleted from " table)}]))
    stats))

(defn collect-all-postgres-metrics
  "Collect all PostgreSQL metrics and return as Riemann events"
  []
  (let [timestamp (quot (System/currentTimeMillis) 1000)]
    (try
      (if (test-connection)
        (let [db-stats (collect-database-stats)
              conn-stats (collect-connection-stats) 
              table-stats (collect-table-stats)]
          (concat
            (format-database-events db-stats timestamp)
            (format-connection-events conn-stats timestamp)
            (format-table-events table-stats timestamp)
            [{:service "postgres.monitor.health"
              :state "ok"
              :metric 1
              :time timestamp
              :host "riemann-server"
              :description "PostgreSQL monitoring is healthy"}]))
        ;; Connection failed
        [{:service "postgres.monitor.health"
          :state "critical"
          :metric 0
          :time timestamp
          :host "riemann-server"
          :description "PostgreSQL connection failed"}])
      (catch Exception e
        (log/error e "Error collecting PostgreSQL metrics")
        [{:service "postgres.monitor.health"
          :state "critical" 
          :metric 0
          :time timestamp
          :host "riemann-server"
          :description (str "PostgreSQL monitoring error: " (.getMessage e))}]))))

;; Configuration function to update database connection details
(defn configure-db!
  "Update database configuration"
  [config]
  (alter-var-root #'*db-config* (constantly (merge *db-config* config)))
  (log/info "PostgreSQL configuration updated:" *db-config*))
