"""OS Infrastructure domain knowledge — Prometheus node exporter metric classification.

Contains:
  OS_METRIC_RULES       : metric name → category / metric_type / meaning / filter_hints / thresholds / investigation_hints
  classify_os_metric()  : look up a metric by name_s

Each entry covers one metric family from Prometheus_OSExporter_CL.
value_d is the raw metric value.

Counter vs Gauge:
  Counters (_total suffix): monotonically increasing since boot.
    In KQL: compute delta as (max(value_d) - min(value_d)) over a time window or per bin.
    Do NOT use Prometheus rate() — Azure Log Analytics does not support it.
  Gauges (no _total suffix): current instantaneous value; read directly.
  Typical scrape interval: 60 seconds. Use wider time windows if scrape interval is large.
"""
from __future__ import annotations

# ── OS Metric Rules ───────────────────────────────────────────────────────────
# key   : exact name_s value from Prometheus_OSExporter_CL
# value : classification dict with category, metric_type, meaning, filter_hints,
#         thresholds, and investigation_hints.

OS_METRIC_RULES: dict[str, dict] = {

    # ── CPU ───────────────────────────────────────────────────────────────────

    "node_cpu_seconds_total": {
        "category": "CPU",
        "metric_type": "counter",
        "meaning": (
            "Cumulative CPU time in seconds per core per mode since boot. "
            "labels_s carries 'cpu' (e.g. '0', '1', '2', '3') and 'mode' "
            "(idle | user | system | iowait | steal | softirq | irq | nice). "
            "Each row is one (cpu, mode) combination. "
            "Correct KQL computation over a time window: "
            "  CPU Usage % = 100 * (1 - idle_delta / total_delta) "
            "  Mode %      = (mode_delta / total_delta) * 100 "
            "where _delta = max(value_d) - min(value_d) per (cpu, mode) bin."
        ),
        "filter_hints": [],
        "thresholds": {
            "cpu_usage_pct_warning":  70,
            "cpu_usage_pct_critical": 90,
            "iowait_pct_warning":     20,
            "iowait_pct_critical":    40,
        },
        "investigation_hints": [
            "Compute CPU usage %: 100 * (1 - idle_delta / total_delta) across all CPU cores and time window.",
            "High 'user' mode % indicates application-level CPU — identify which process is consuming it.",
            "High 'system' mode % indicates kernel activity — check for heavy I/O, syscall load, or network traffic.",
            "High 'iowait' mode % means CPUs are stalled waiting for disk — correlate with node_disk_io_now and node_disk_io_time_seconds_total.",
            "High 'steal' mode % in a VM means the hypervisor is not allocating CPU quota — a platform-level issue.",
            "For SAP systems, CPU spikes often correlate with batch jobs — check SapNetweaver_BatchJobs_CL for concurrent runs.",
            "KQL TROUBLESHOOTING PATTERN — the delta-per-bin method already captures peak within each bin correctly. "
            "Avoid single-scalar summaries over long windows (e.g. summarize over 15 min) for incident diagnosis: "
            "a 100% CPU burst for 30 seconds looks like ~3% in a 15-minute scalar average. "
            "Use make-series with small bins (1m-5m) to see the per-interval peak, not an averaged overview tile.",
        ],
    },

    # ── Memory ────────────────────────────────────────────────────────────────

    "node_memory_MemTotal_bytes": {
        "category": "Memory",
        "metric_type": "gauge",
        "meaning": "Total physical RAM installed on the host in bytes. Constant unless memory hotplug changes occur.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Use as denominator: memory_usage % = (1 - MemAvailable / MemTotal) * 100.",
        ],
    },

    "node_memory_MemAvailable_bytes": {
        "category": "Memory",
        "metric_type": "gauge",
        "meaning": (
            "Estimated RAM available for new allocations without swapping, in bytes. "
            "This is the PREFERRED memory pressure indicator — it accounts for reclaimable buffer/cache. "
            "When this approaches zero, the OS begins swapping."
        ),
        "filter_hints": [],
        "thresholds": {
            "usage_pct_warning":  80,
            "usage_pct_critical": 90,
        },
        "investigation_hints": [
            "Compute memory usage %: (1 - MemAvailable / MemTotal) * 100.",
            "Above 80% warrants investigation; above 90% is critical for SAP workloads.",
            "Low MemAvailable combined with an increasing pswpin/pswpout delta confirms active swapping — SAP performance degrades severely.",
            "For SAP systems, memory pressure causes ABAP short dumps (MEMORY_NO_MORE_PAGING, SYSTEM_NO_ROLL) — check SapNetweaver_ShortDumps_CL.",
            "KQL TROUBLESHOOTING PATTERN — use min() per time bin, NOT avg(): "
            "min(value_d) shows the lowest available RAM in each bin, revealing pressure spikes that avg() would mask. "
            "Example: | make-series min_avail=min(value_d) on TimeGenerated step 5m by instance_s",
            "COMMON QUERY MISTAKE: do not use node_memory_MemFree_bytes as a proxy for 'available'. "
            "MemFree excludes reclaimable page cache, so (Total - MemFree)/Total overestimates memory pressure. "
            "Always use MemAvailable_bytes as the pressure denominator.",
        ],
    },

    "node_memory_MemFree_bytes": {
        "category": "Memory",
        "metric_type": "gauge",
        "meaning": (
            "Completely unused RAM in bytes (not cached, not buffered). "
            "A low value does NOT indicate memory pressure — "
            "Linux aggressively uses spare RAM for page cache. "
            "Use node_memory_MemAvailable_bytes as the primary pressure indicator."
        ),
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Low MemFree alone is normal on Linux. Use MemAvailable as the real pressure indicator.",
            "COMMON QUERY MISTAKE: some workbook queries compute used_memory = MemTotal - MemFree. "
            "This counts page cache as 'used', inflating the usage % by 30-60% on typical SAP systems. "
            "Correct formula: used_pct = (1 - MemAvailable / MemTotal) * 100.",
        ],
    },

    "node_memory_Buffers_bytes": {
        "category": "Memory",
        "metric_type": "gauge",
        "meaning": "RAM used by the kernel for I/O buffer cache in bytes. Reclaimable under memory pressure.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Buffer memory is reclaimable — a high value indicates heavy filesystem I/O but is not itself a problem.",
        ],
    },

    "node_memory_Cached_bytes": {
        "category": "Memory",
        "metric_type": "gauge",
        "meaning": "RAM used for the page cache (file contents) in bytes. Reclaimable under memory pressure.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "A sudden drop in Cached_bytes means the OS is reclaiming page cache under pressure — check MemAvailable.",
        ],
    },

    "node_memory_SwapTotal_bytes": {
        "category": "Swap",
        "metric_type": "gauge",
        "meaning": "Total configured swap space in bytes.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Use as denominator: swap_usage % = (1 - SwapFree / SwapTotal) * 100.",
            "SAP recommends swap size >= physical RAM for ABAP systems. A very small swap indicates a configuration risk.",
        ],
    },

    "node_memory_SwapFree_bytes": {
        "category": "Swap",
        "metric_type": "gauge",
        "meaning": (
            "Free swap space in bytes. "
            "A declining trend indicates the OS is writing pages to swap. "
            "Context-check with node_vmstat_pswpin/pswpout deltas to confirm active swapping."
        ),
        "filter_hints": [],
        "thresholds": {
            "swap_usage_pct_warning":  50,
            "swap_usage_pct_critical": 80,
        },
        "investigation_hints": [
            "Compute swap usage %: (1 - SwapFree / SwapTotal) * 100.",
            "Alert when swap usage is high AND MemAvailable is also low — both conditions together indicate real memory pressure.",
            "Any sustained swap usage on an SAP system is a concern — SAP ABAP memory management is incompatible with heavy swapping.",
            "Correlate swap spikes with SAP dump spikes in SapNetweaver_ShortDumps_CL.",
            "KQL TROUBLESHOOTING PATTERN — use max(swap_used) per time bin, NOT avg(): "
            "a swap spike lasting 2-3 minutes is invisible in avg() across a 5-minute bin. "
            "Example: | make-series max_swap_used=max(total_swap-avail_swap) on TimeGenerated step 5m",
        ],
    },

    "node_memory_SwapCached_bytes": {
        "category": "Swap",
        "metric_type": "gauge",
        "meaning": "RAM used to cache swap pages that have been read back in. A growing value confirms active swap I/O cycling.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Growing SwapCached alongside declining SwapFree confirms the OS is actively cycling pages between RAM and swap.",
        ],
    },

    # ── Disk I/O ──────────────────────────────────────────────────────────────

    "node_disk_io_now": {
        "category": "Disk I/O",
        "metric_type": "gauge",
        "meaning": (
            "Number of I/O operations currently in flight on the device (instantaneous gauge). "
            "labels_s carries 'device' (e.g. 'sda', 'sdb', 'sdc', 'dm-0'). "
            "This reflects in-flight I/O count, NOT an exact queue length. "
            "A sustained non-zero value indicates the device is busy."
        ),
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr* (optical drives always show 0).",
            "dm-* (LVM logical volumes) may overlap with underlying physical device — be aware of double-counting.",
        ],
        "thresholds": {
            "io_inflight_warning":  4,
            "io_inflight_critical": 16,
        },
        "investigation_hints": [
            "A sustained high value means I/O is not completing promptly — the device may be saturated.",
            "Identify the specific device from parse_json(labels_s).device.",
            "Correlate with node_cpu_seconds_total iowait % — high iowait + high io_now confirms an I/O bottleneck.",
            "For SAP systems, check if the saturated device hosts data volumes, log volumes, or swap.",
            "Correlate with SapNetweaver_BatchJobs_CL — large batch jobs often cause disk saturation.",
        ],
    },

    "node_disk_io_time_seconds_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": (
            "Cumulative time the disk was busy (had I/O in progress) in seconds since boot. "
            "labels_s carries 'device'. "
            "Disk utilisation % = (delta / time_window_seconds) * 100. "
            "Note: this value CAN exceed 100% on devices with parallel I/O (e.g. NVMe, RAID) — "
            "values above 100% are valid and indicate parallel I/O saturation."
        ),
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {
            "utilisation_pct_warning":  70,
            "utilisation_pct_critical": 90,
        },
        "investigation_hints": [
            "Compute utilisation %: (max(value_d) - min(value_d)) / time_window_seconds * 100.",
            "Values > 100% are possible on parallel-capable devices and indicate heavy concurrent I/O.",
            "A device at > 70% utilisation is a potential bottleneck for SAP workloads.",
            "Identify the affected device from parse_json(labels_s).device.",
        ],
    },

    "node_disk_read_bytes_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": "Cumulative bytes read from the device since boot. labels_s carries 'device'. Compute delta to get throughput over a time window.",
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute read throughput: (max - min) / time_window_seconds = bytes/sec.",
            "A spike in read throughput indicates heavy sequential or random read activity — correlate with SAP batch jobs or HANA data scans.",
        ],
    },

    "node_disk_written_bytes_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": "Cumulative bytes written to the device since boot. labels_s carries 'device'. Compute delta to get throughput over a time window.",
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute write throughput: (max - min) / time_window_seconds = bytes/sec.",
            "A spike in write throughput indicates heavy write activity — HANA redo log writes, SAP update tasks, or spool output.",
            "Sustained high write on a log device may indicate HANA redo log pressure.",
        ],
    },

    "node_disk_reads_completed_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": "Cumulative read operations completed since boot. labels_s carries 'device'. Compute delta to get IOPS over a time window.",
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute read IOPS: (max - min) / time_window_seconds.",
            "High read IOPS with low throughput (small bytes/op from read_bytes/reads) indicates many small random reads — typical of OLTP.",
        ],
    },

    "node_disk_writes_completed_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": "Cumulative write operations completed since boot. labels_s carries 'device'. Compute delta to get IOPS over a time window.",
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute write IOPS: (max - min) / time_window_seconds.",
            "High write IOPS can saturate a device — correlate with node_disk_io_now and node_disk_io_time_seconds_total.",
        ],
    },

    "node_disk_read_time_seconds_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": (
            "Cumulative time spent on read I/O requests in seconds since boot. labels_s carries 'device'. "
            "Average read latency = read_time_delta / reads_completed_delta (in same time window)."
        ),
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {
            "avg_read_latency_ms_warning":  10,
            "avg_read_latency_ms_critical": 50,
        },
        "investigation_hints": [
            "Compute avg read latency (ms): (read_time_delta / reads_completed_delta) * 1000.",
            "Both read_time and reads_completed must be delta-computed over the same time window.",
            "SAP recommends < 1ms for HANA data volumes. > 10ms is a significant performance concern.",
        ],
    },

    "node_disk_write_time_seconds_total": {
        "category": "Disk I/O",
        "metric_type": "counter",
        "meaning": (
            "Cumulative time spent on write I/O requests in seconds since boot. labels_s carries 'device'. "
            "Average write latency = write_time_delta / writes_completed_delta (in same time window)."
        ),
        "filter_hints": [
            "Exclude devices: loop*, ram*, sr*.",
        ],
        "thresholds": {
            "avg_write_latency_ms_warning":  10,
            "avg_write_latency_ms_critical": 50,
        },
        "investigation_hints": [
            "Compute avg write latency (ms): (write_time_delta / writes_completed_delta) * 1000.",
            "Both write_time and writes_completed must be delta-computed over the same time window.",
            "High write latency on the HANA log volume directly increases HANA commit times — causes cascading application slowness.",
        ],
    },

    # ── Filesystem ────────────────────────────────────────────────────────────

    "node_filesystem_size_bytes": {
        "category": "Filesystem",
        "metric_type": "gauge",
        "meaning": "Total size of the filesystem in bytes. labels_s carries 'device', 'mountpoint', and 'fstype'.",
        "filter_hints": [
            "Filter fstype to: xfs, ext4, nfs4 — exclude tmpfs, devtmpfs, fuse.*, squashfs.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Use as denominator: usage % = (1 - avail_bytes / size_bytes) * 100.",
        ],
    },

    "node_filesystem_avail_bytes": {
        "category": "Filesystem",
        "metric_type": "gauge",
        "meaning": (
            "Bytes available to unprivileged users on the filesystem. labels_s carries 'device', 'mountpoint', 'fstype'. "
            "This is the correct value for disk-full alerts — not free_bytes, which includes root-reserved space."
        ),
        "filter_hints": [
            "Filter fstype to: xfs, ext4, nfs4 — exclude tmpfs, devtmpfs, fuse.*, squashfs.",
            "Also exclude fuse.azsec-bpftrace and similar Azure agent mounts which always show 0.",
        ],
        "thresholds": {
            "usage_pct_warning":  80,
            "usage_pct_critical": 90,
        },
        "investigation_hints": [
            "Compute usage %: (1 - avail_bytes / size_bytes) * 100.",
            "Identify the affected mountpoint from parse_json(labels_s).mountpoint.",
            "Key SAP mountpoints: /usr/sap, /sapmnt/<SID>, /usr/sap/trans, /usr/sap/install, /, /boot.",
            "NFS4 mounts (e.g. /sapmnt/CHA, /usr/sap/trans) are shared — a full NFS share affects all nodes.",
            "A full /hana/log volume causes HANA to stop all write operations immediately — critical.",
            "A full /usr/sap or /sapmnt can prevent SAP instance startup.",
            "Check for large trace files, spool output, or core dumps: /usr/sap/<SID>/<instance>/work.",
        ],
    },

    "node_filesystem_free_bytes": {
        "category": "Filesystem",
        "metric_type": "gauge",
        "meaning": (
            "Total free bytes on the filesystem including root-reserved space. labels_s carries 'device', 'mountpoint', 'fstype'. "
            "Use node_filesystem_avail_bytes for alert thresholds — free_bytes includes space apps cannot use."
        ),
        "filter_hints": [
            "Filter fstype to: xfs, ext4, nfs4 — exclude tmpfs, devtmpfs, fuse.*, squashfs.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Prefer node_filesystem_avail_bytes for disk-full alerts, not this metric.",
        ],
    },

    # ── Network ───────────────────────────────────────────────────────────────

    "node_network_receive_bytes_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative bytes received on a network interface since boot. labels_s carries 'device' (e.g. 'eth0', 'eth1').",
        "filter_hints": [
            "Exclude 'lo' (loopback — only reflects local inter-process traffic).",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute throughput: (max - min) / time_window_seconds = bytes/sec.",
            "High receive throughput on NFS-mounted SAP shares (e.g. sapmnt, trans) indicates heavy remote filesystem reads.",
            "Correlate with corosync ring interfaces — high traffic on cluster interfaces may affect cluster stability.",
        ],
    },

    "node_network_transmit_bytes_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative bytes transmitted on a network interface since boot. labels_s carries 'device'.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute throughput: (max - min) / time_window_seconds = bytes/sec.",
            "High transmit rate to the DB host combined with high disk writes on the DB host may indicate heavy data replication or large batch inserts.",
        ],
    },

    "node_network_receive_packets_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative packets received on a network interface since boot. labels_s carries 'device'.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compute PPS: (max - min) / time_window_seconds.",
            "High PPS with low bytes/packet indicates many small messages — typical of RFC/TCP or corosync heartbeat traffic.",
        ],
    },

    "node_network_transmit_packets_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative packets transmitted on a network interface since boot. labels_s carries 'device'.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Compare receive vs transmit PPS to understand traffic asymmetry.",
        ],
    },

    "node_network_receive_errs_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative receive errors on a network interface since boot. labels_s carries 'device'. Any non-zero rate indicates NIC or cabling issues.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {
            "error_rate_warning": 1,
        },
        "investigation_hints": [
            "Any sustained receive error rate is abnormal — check NIC health, cable quality, and switch port configuration.",
            "Receive errors on a corosync ring interface can trigger corosync ring fault events — correlate with ha_cluster_corosync_ring_errors in Prometheus_HaClusterExporter_CL.",
        ],
    },

    "node_network_transmit_errs_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative transmit errors on a network interface since boot. labels_s carries 'device'. Any non-zero rate indicates NIC or network issues.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {
            "error_rate_warning": 1,
        },
        "investigation_hints": [
            "Any sustained transmit error rate warrants investigation — check NIC, cable, and switch port.",
            "Transmit errors on a corosync ring interface can cause ring faults and eventual cluster split-brain.",
        ],
    },

    "node_network_receive_drop_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative receive packets dropped on a network interface since boot. labels_s carries 'device'. Drops indicate buffer overflow or resource exhaustion.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {
            "drop_rate_warning": 1,
        },
        "investigation_hints": [
            "Receive drops indicate the kernel receive buffer overflowed — system is under high network or CPU load.",
            "Drops on corosync ring interfaces can cause missed heartbeats and cluster node expulsion.",
        ],
    },

    "node_network_transmit_drop_total": {
        "category": "Network",
        "metric_type": "counter",
        "meaning": "Cumulative transmit packets dropped on a network interface since boot. labels_s carries 'device'. Drops indicate transmit buffer exhaustion.",
        "filter_hints": [
            "Exclude 'lo' (loopback).",
        ],
        "thresholds": {
            "drop_rate_warning": 1,
        },
        "investigation_hints": [
            "Transmit drops indicate the kernel transmit buffer overflowed — check for network saturation or NIC queue depth.",
        ],
    },

    # ── Processes ─────────────────────────────────────────────────────────────

    "node_procs_running": {
        "category": "Processes",
        "metric_type": "gauge",
        "meaning": (
            "Number of processes in a runnable state (R state) at the moment of scrape. "
            "Indicates CPU pressure but is NOT equivalent to load average — "
            "load average also counts D-state (I/O-blocked) processes and is time-averaged."
        ),
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "A consistently high value relative to CPU core count suggests CPU saturation.",
            "Cross-reference with node_cpu_seconds_total user/system delta — high procs_running + high CPU confirms saturation.",
            "This is NOT load average. If load average metrics are available (node_load1/5/15), prefer those for trend analysis.",
        ],
    },

    "node_procs_blocked": {
        "category": "Processes",
        "metric_type": "gauge",
        "meaning": (
            "Number of processes currently blocked waiting for I/O (D state) at the moment of scrape. "
            "A sustained non-zero value is a strong indicator of I/O contention."
        ),
        "filter_hints": [],
        "thresholds": {
            "warning":  1,
            "critical": 5,
        },
        "investigation_hints": [
            "Any sustained procs_blocked > 0 means processes are stuck waiting for disk — identify the saturated device using node_disk_io_now.",
            "D-state blocked processes cannot be killed — the underlying I/O blockage must be resolved.",
            "For SAP: blocked processes in the work process pool cause subsequent user requests to queue — check SapNetweaver_ABAPGetWPTable_CL.",
        ],
    },

    "node_forks_total": {
        "category": "Processes",
        "metric_type": "counter",
        "meaning": "Cumulative number of process forks since boot. Compute delta to get fork rate over a time window.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "An abnormally high fork rate delta may indicate a runaway process spawning children.",
        ],
    },

    # ── Virtual Memory / Swap I/O ─────────────────────────────────────────────

    "node_vmstat_pgpgin": {
        "category": "Virtual Memory",
        "metric_type": "counter",
        "meaning": "Cumulative pages paged in from disk since boot. Compute delta to get paging rate. Includes both page cache fills and swap-in activity.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "A high paging-in delta alongside declining MemAvailable may indicate memory pressure.",
            "Distinguish from swap: if pswpin delta is also high, pages are being read back from swap (not just page cache).",
        ],
    },

    "node_vmstat_pgpgout": {
        "category": "Virtual Memory",
        "metric_type": "counter",
        "meaning": "Cumulative pages paged out to disk since boot. Compute delta to get paging rate. Includes both dirty page writeback and swap-out activity.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "A high paging-out delta alongside declining MemAvailable confirms the OS is evicting pages under pressure.",
            "Distinguish dirty page writeback (normal filesystem activity) from swap-out (pswpout delta also high).",
        ],
    },

    "node_vmstat_pswpin": {
        "category": "Swap",
        "metric_type": "counter",
        "meaning": "Cumulative swap pages swapped IN (read from swap device into RAM) since boot. Compute delta to get swap-in rate.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Some cumulative swap activity is normal at low levels and does not require action.",
            "ALERT only when: sustained pswpin delta is growing AND node_memory_MemAvailable_bytes is simultaneously low.",
            "Significant sustained swap-in combined with low MemAvailable confirms active memory pressure — SAP performance will degrade.",
            "Correlate with SapNetweaver_ShortDumps_CL for MEMORY_NO_MORE_PAGING or SYSTEM_NO_ROLL errors.",
        ],
    },

    "node_vmstat_pswpout": {
        "category": "Swap",
        "metric_type": "counter",
        "meaning": "Cumulative swap pages swapped OUT (written from RAM to swap device) since boot. Compute delta to get swap-out rate.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Some cumulative swap activity is normal at low levels and does not require action.",
            "ALERT only when: sustained pswpout delta is growing AND node_memory_MemAvailable_bytes is simultaneously low.",
            "Sustained swap-out alongside low MemAvailable confirms the OS is under real memory pressure — investigate memory consumers.",
            "Correlate with SapNetweaver_ShortDumps_CL for memory-related ABAP short dumps.",
        ],
    },

    # ── System Info ───────────────────────────────────────────────────────────

    "node_boot_time_seconds": {
        "category": "System",
        "metric_type": "gauge",
        "meaning": "Unix epoch timestamp of the last system boot. Use to detect unexpected reboots.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "An unexpectedly recent boot time indicates the host rebooted — correlate with HA cluster failover events in Prometheus_HaClusterExporter_CL.",
            "KQL conversion: datetime(1970-01-01) + totimespan(value_d * 1s) = human-readable boot time.",
        ],
    },

    "node_time_seconds": {
        "category": "System",
        "metric_type": "gauge",
        "meaning": "Current system clock time as Unix epoch. Useful for detecting NTP drift between cluster nodes.",
        "filter_hints": [],
        "thresholds": {
            "ntp_drift_seconds_warning":  2,
            "ntp_drift_seconds_critical": 10,
        },
        "investigation_hints": [
            "Compare node_time_seconds across cluster nodes at the same TimeGeneratedPrometheus_t — drift > 2s can destabilize Pacemaker/corosync.",
            "SAP HANA replication requires tight time synchronization between primary and secondary nodes.",
        ],
    },

    "node_uname_info": {
        "category": "System",
        "metric_type": "gauge",
        "meaning": (
            "OS and kernel version info. value_d is always 1. "
            "labels_s carries: 'sysname' (e.g. 'Linux'), 'release' (kernel version, e.g. '5.14.21-150500.55.141-default'), "
            "'version' (build string), 'machine' (architecture, e.g. 'x86_64'), "
            "'nodename' (hostname, e.g. 'chaapp01l0c2'), 'domainname'."
        ),
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            "Check parse_json(labels_s).release to identify the kernel version — some SAP issues are kernel-version specific.",
            "Compare kernel versions across cluster nodes — mismatched kernels can cause unexpected behaviour.",
            "parse_json(labels_s).nodename provides the actual hostname, useful when sid_s alone does not identify the host.",
        ],
    },

    # ── Load Average (may not be available in all environments) ─────────────────

    "node_load1": {
        "category": "Load",
        "metric_type": "gauge",
        "meaning": (
            "1-minute CPU load average. Reflects the average number of runnable + D-state processes "
            "over the last 1 minute. More responsive than node_load5/15 but noisier."
        ),
        "filter_hints": [],
        "thresholds": {
            "note": "Alert when load > number of CPU cores (saturation).",
        },
        "investigation_hints": [
            "Load average > CPU core count indicates system saturation (processes queuing for CPU or I/O).",
            "If unavailable, use node_procs_running (CPU pressure proxy) and node_procs_blocked (I/O pressure proxy) instead.",
            "node_load1 includes both CPU-bound (R state) and I/O-blocked (D state) processes — use iowait % to distinguish.",
        ],
    },

    "node_load5": {
        "category": "Load",
        "metric_type": "gauge",
        "meaning": (
            "5-minute CPU load average. Smoothed view of system load. "
            "More reliable than node_load1 for alerting — less susceptible to transient spikes."
        ),
        "filter_hints": [],
        "thresholds": {
            "note": "Alert when load > number of CPU cores.",
        },
        "investigation_hints": [
            "node_load5 > CPU count sustained confirms the system is overloaded.",
            "Compare node_load1 vs node_load5 vs node_load15 to understand whether load is rising, stable, or falling.",
        ],
    },

    "node_load15": {
        "category": "Load",
        "metric_type": "gauge",
        "meaning": (
            "15-minute CPU load average. Long-term trend indicator. "
            "Useful for identifying sustained overload vs transient spikes."
        ),
        "filter_hints": [],
        "thresholds": {
            "note": "Alert when load > number of CPU cores.",
        },
        "investigation_hints": [
            "High node_load15 with low node_load1 means load was recently high but is now recovering.",
            "High node_load1 with low node_load15 means load just spiked recently.",
            "Sustained node_load15 > CPU count indicates a chronic capacity problem.",
        ],
    },

    # ── SAP Monitor Heartbeat (metadata row — not an OS metric) ───────────────

    "sapmon": {
        "category": "Metadata",
        "metric_type": "gauge",
        "meaning": (
            "SAP Monitor (AMS) heartbeat/metadata row. value_d is always 1. "
            "labels_s carries PROVIDER_INSTANCE, SAPMON_VERSION, sapsid, Time_Generated, and METADATA. "
            "Confirms the AMS collector is active and submitting data."
        ),
        "filter_hints": [
            "Exclude this row when querying OS metrics — filter name_s != 'sapmon' in most KQL queries.",
        ],
        "thresholds": {},
        "investigation_hints": [
            "Absence of recent 'sapmon' rows for an instance_s indicates the AMS collector may be offline.",
            "parse_json(labels_s).SAPMON_VERSION identifies the collector version.",
        ],
    },
}


# ── Convenience function ────────────────────────────────────────────────────

def classify_os_metric(metric_name: str) -> dict:
    """Return category, metric_type, meaning, filter_hints, thresholds, and investigation_hints for an OS metric name."""
    entry = OS_METRIC_RULES.get(metric_name)
    if entry:
        return entry
    return {
        "category": "Unknown",
        "metric_type": "unknown",
        "meaning": f"OS metric '{metric_name}' is not in the local knowledge base.",
        "filter_hints": [],
        "thresholds": {},
        "investigation_hints": [
            f"Check Prometheus node exporter documentation for metric '{metric_name}'.",
            "Inspect labels_s with parse_json(labels_s) to understand the context of this metric.",
        ],
    }
