(ns disk-monitor
  "Disk usage monitoring for Riemann"
  (:require [clojure.java.shell :as shell]
            [clojure.string :as str])
  (:import [java.io File]))

;; Configuration
(def disk-config
  {:warning-threshold 0.80   ; 80% usage warning
   :critical-threshold 0.90  ; 90% usage critical
   :monitored-paths ["/" "/home" "/var" "/tmp"]})

;; Utility functions
(defn bytes-to-gb [bytes]
  "Convert bytes to gigabytes"
  (/ bytes 1024 1024 1024))

(defn get-disk-usage [path]
  "Get disk usage for a given path"
  (try
    (let [file (File. path)
          total-space (.getTotalSpace file)
          free-space (.getFreeSpace file)
          usable-space (.getUsableSpace file)
          used-space (- total-space free-space)
          usage-percent (if (> total-space 0)
                         (/ used-space total-space)
                         0)]
      {:path path
       :total-gb (bytes-to-gb total-space)
       :free-gb (bytes-to-gb free-space)
       :used-gb (bytes-to-gb used-space)
       :usable-gb (bytes-to-gb usable-space)
       :usage-percent usage-percent
       :available-percent (- 1.0 usage-percent)})
    (catch Exception e
      (println "Error getting disk usage for" path ":" (.getMessage e))
      nil)))

(defn get-disk-usage-df []
  "Get disk usage using df command"
  (try
    (let [result (shell/sh "df" "-h")
          lines (str/split (:out result) #"\n")
          data-lines (drop 1 lines)]
      (for [line data-lines
            :when (not (str/blank? line))
            :let [parts (str/split line #"\s+")
                  filesystem (first parts)
                  size (nth parts 1 "")
                  used (nth parts 2 "")  
                  avail (nth parts 3 "")
                  use-percent (nth parts 4 "")
                  mount-point (nth parts 5 "")]
            :when (and mount-point
                      (not (str/starts-with? mount-point "/dev"))
                      (not (str/starts-with? mount-point "/sys"))
                      (not (str/starts-with? mount-point "/proc"))
                      (not (str/starts-with? mount-point "/run")))]
        {:filesystem filesystem
         :size size
         :used used
         :available avail
         :use-percent (if (str/ends-with? use-percent "%")
                       (/ (Integer/parseInt (str/replace use-percent "%" "")) 100.0)
                       0.0)
         :mount-point mount-point}))
    (catch Exception e
      (println "Error running df command:" (.getMessage e))
      [])))

(defn create-disk-event [disk-info service-prefix]
  "Create Riemann event for disk usage"
  {:service (str service-prefix ".usage.percent")
   :metric (:usage-percent disk-info)
   :state (cond
            (>= (:usage-percent disk-info) (:critical-threshold disk-config)) "critical"
            (>= (:usage-percent disk-info) (:warning-threshold disk-config)) "warning"
            :else "ok")
   :description (format "Disk %s: %.1f%% used (%.1fGB/%.1fGB)"
                       (:path disk-info)
                       (* (:usage-percent disk-info) 100)
                       (:used-gb disk-info)
                       (:total-gb disk-info))
   :tags ["disk" "usage" "monitoring"]
   :host "trust-server"
   :time (/ (System/currentTimeMillis) 1000)})

(defn create-disk-events []
  "Create disk monitoring events"
  (let [disk-data (map get-disk-usage (:monitored-paths disk-config))
        valid-data (filter identity disk-data)]
    (for [disk valid-data
          :let [mount-name (if (= (:path disk) "/")
                            "root"
                            (str/replace (:path disk) "/" "_"))]]
      [(create-disk-event disk (str "disk." mount-name))
       {:service (str "disk." mount-name ".free.gb")
        :metric (:free-gb disk)
        :state "ok"
        :host "trust-server"
        :time (/ (System/currentTimeMillis) 1000)}
       {:service (str "disk." mount-name ".used.gb")
        :metric (:used-gb disk)
        :state "ok"
        :host "trust-server"
        :time (/ (System/currentTimeMillis) 1000)}
       {:service (str "disk." mount-name ".total.gb")
        :metric (:total-gb disk)
        :state "ok"
        :host "trust-server"
        :time (/ (System/currentTimeMillis) 1000)}])))

(defn collect-disk-metrics []
  "Collect all disk metrics and return events"
  (flatten (create-disk-events)))
