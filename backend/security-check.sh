#!/bin/bash
# AgentIndex Local Security Scanner
# Runs LOCALLY on YOUR machine. Nothing sent anywhere.
# https://agentindex.world/security-check.sh

echo ""
echo "========================================"
echo "  AgentIndex Local Security Scanner"
echo "  Everything runs on YOUR machine."
echo "========================================"
echo ""

ISSUES=0
CRITICAL=0

check_port() {
    local port=$1
    local service=$2
    local risk=$3
    local msg=$4
    (echo >/dev/tcp/127.0.0.1/$port) 2>/dev/null
    if [ $? -eq 0 ]; then
        if [ "$risk" = "CRITICAL" ]; then
            echo "  [X] Port $port ($service) - OPEN - $risk"
            echo "      $msg"
            CRITICAL=$((CRITICAL+1))
        elif [ "$risk" = "HIGH" ]; then
            echo "  [!] Port $port ($service) - OPEN - $risk"
            echo "      $msg"
        else
            echo "  [i] Port $port ($service) - OPEN - $risk"
        fi
        ISSUES=$((ISSUES+1))
    else
        echo "  [OK] Port $port ($service) - CLOSED"
    fi
}

echo "-- OpenClaw Ports --"
check_port 18789 "OpenClaw Gateway" "CRITICAL" "Run: openclaw config set gateway.bind localhost"
check_port 18791 "OpenClaw Control" "HIGH" "Control service exposed"
check_port 18792 "OpenClaw CDP" "HIGH" "Browser automation exposed"
check_port 18793 "OpenClaw Canvas" "MEDIUM" "Canvas host exposed"

echo ""
echo "-- Database Ports --"
check_port 3306 "MySQL" "CRITICAL" "Bind to 127.0.0.1"
check_port 5432 "PostgreSQL" "CRITICAL" "Bind to 127.0.0.1"
check_port 27017 "MongoDB" "CRITICAL" "Bind to 127.0.0.1"
check_port 6379 "Redis" "CRITICAL" "Set requirepass"

echo ""
echo "-- Web and SSH --"
check_port 22 "SSH" "INFO" "Ensure key-based auth"
check_port 80 "HTTP" "INFO" "Web server"
check_port 443 "HTTPS" "INFO" "HTTPS server"
check_port 8080 "HTTP-Alt" "MEDIUM" "Alt HTTP port"
check_port 3000 "Dev Server" "MEDIUM" "Dev server port"

echo ""

# Check OpenClaw binding
if command -v ss &> /dev/null; then
    BIND=$(ss -tlnp 2>/dev/null | grep 18789 | head -1)
    if echo "$BIND" | grep -q "0.0.0.0"; then
        echo "  [!!] OpenClaw Gateway bound to 0.0.0.0 - EXPOSED"
        echo "       Fix: openclaw config set gateway.bind localhost"
        CRITICAL=$((CRITICAL+1))
    elif echo "$BIND" | grep -q "127.0.0.1"; then
        echo "  [OK] OpenClaw Gateway bound to localhost - SAFE"
    fi
fi

echo ""
echo "========================================"
if [ $CRITICAL -gt 0 ]; then
    echo "  GRADE: F - $CRITICAL CRITICAL issues"
elif [ $ISSUES -gt 5 ]; then
    echo "  GRADE: C - $ISSUES ports open"
elif [ $ISSUES -gt 2 ]; then
    echo "  GRADE: B - $ISSUES ports open"
else
    echo "  GRADE: A - Secure"
fi
echo ""
echo "  Ran entirely on your machine."
echo "  Nothing sent externally."
echo "  Passport: agentindex.world/for-agents"
echo "========================================"
