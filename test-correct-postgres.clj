(import [java.sql DriverManager])

(try
  (println "Testing connection to trust-server-postgres-local:5432...")
  (let [url "jdbc:postgresql://trust-server-postgres-local:5432/alfresco"
        conn (DriverManager/getConnection url "alfresco" "alfresco")]
    (println "SUCCESS: Connected to PostgreSQL")
    (with-open [stmt (.createStatement conn)]
      (let [rs (.executeQuery stmt "SELECT version(), current_database(), current_user")]
        (when (.next rs)
          (println "Version:" (.getString rs 1))
          (println "Database:" (.getString rs 2))
          (println "User:" (.getString rs 3)))))
    (.close conn))
  (catch Exception e
    (println "CONNECTION FAILED:" (.getMessage e))))
