"""Security Scan - Port scanning for agent vulnerabilities."""
import socket
from datetime import datetime, timezone

COMMON_PORTS = {
    18789: {"service": "OpenClaw Gateway", "risk": "CRITICAL"},
    18791: {"service": "OpenClaw Control", "risk": "HIGH"},
    18792: {"service": "OpenClaw CDP", "risk": "HIGH"},
    3306: {"service": "MySQL", "risk": "CRITICAL"},
    5432: {"service": "PostgreSQL", "risk": "CRITICAL"},
    27017: {"service": "MongoDB", "risk": "CRITICAL"},
    6379: {"service": "Redis", "risk": "CRITICAL"},
    8080: {"service": "HTTP Alt", "risk": "MEDIUM"},
    3000: {"service": "Dev Server", "risk": "MEDIUM"},
    22: {"service": "SSH", "risk": "INFO"},
    80: {"service": "HTTP", "risk": "INFO"},
    443: {"service": "HTTPS", "risk": "INFO"},
}

def scan_port(ip, port, timeout=3):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def scan_agent(ip_address):
    if not ip_address or ip_address in ('127.0.0.1', 'localhost'):
        return {"scanned": False, "reason": "No public IP"}

    findings = []
    open_ports = []

    for port, info in COMMON_PORTS.items():
        if scan_port(ip_address, port):
            open_ports.append(port)
            findings.append({"port": port, "service": info["service"], "risk": info["risk"], "status": "OPEN"})

    critical = sum(1 for f in findings if f["risk"] == "CRITICAL")
    high = sum(1 for f in findings if f["risk"] == "HIGH")

    if critical > 0:
        grade = "F"
        risk = "CRITICAL"
    elif high > 0:
        grade = "D"
        risk = "HIGH"
    elif len(open_ports) > 5:
        grade = "C"
        risk = "MEDIUM"
    elif len(open_ports) > 2:
        grade = "B"
        risk = "LOW"
    else:
        grade = "A"
        risk = "LOW"

    recs = []
    if 18789 in open_ports:
        recs.append("URGENT: Close port 18789 or add authentication.")
    if any(p in open_ports for p in [3306, 5432, 27017]):
        recs.append("URGENT: Database exposed. Bind to 127.0.0.1.")
    if 6379 in open_ports:
        recs.append("URGENT: Redis exposed. Set requirepass.")
    if not recs:
        recs.append("No critical issues found.")

    return {
        "scanned": True, "ip": ip_address,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "open_ports": open_ports, "findings": findings,
        "risk_level": risk, "security_grade": grade,
        "recommendations": recs, "open_count": len(open_ports),
    }
