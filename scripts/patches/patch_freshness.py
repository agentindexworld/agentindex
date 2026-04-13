"""Patch main.py — Add freshness tier to check response"""

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

# Add freshness calculation before the check return statement
OLD = '''    # Incident test record
    try:
        from incident_tests import get_incident_summary
        from database import async_session as inc_db3
        inc_info = await get_incident_summary(inc_db3, row[0])
        inc_passed = inc_info.get("tests_passed", 0)
        inc_rate = inc_info.get("pass_rate")
    except Exception:
        inc_passed = 0
        inc_rate = None
    return {
        "found": True, "name": row[1],'''

NEW = '''    # Incident test record
    try:
        from incident_tests import get_incident_summary
        from database import async_session as inc_db3
        inc_info = await get_incident_summary(inc_db3, row[0])
        inc_passed = inc_info.get("tests_passed", 0)
        inc_rate = inc_info.get("pass_rate")
    except Exception:
        inc_passed = 0
        inc_rate = None
    # Freshness tier (credit: sonofsyts)
    from datetime import datetime, timedelta
    _now = datetime.utcnow()
    _created = row[7] if row[7] else _now
    _last_hb = None
    try:
        async with db_session_factory() as _fs:
            _last_hb = (await _fs.execute(text("SELECT last_heartbeat FROM agents WHERE uuid=:u"), {"u": row[0]})).scalar()
    except Exception:
        pass
    if _last_hb and (_now - _last_hb).days <= 7:
        freshness = "active"
    elif _last_hb and (_now - _last_hb).days <= 90:
        freshness = "dormant"
    elif _last_hb:
        freshness = "lapsed"
    elif isinstance(_created, datetime) and (_now - _created).days < 7:
        freshness = "new"
    else:
        freshness = "lapsed"
    return {
        "found": True, "name": row[1],'''

# Add freshness field to the return dict
OLD_RET = '''"incident_tests_passed": inc_passed,
        "incident_pass_rate": inc_rate,
        "trust_context": trust_context,'''

NEW_RET = '''"incident_tests_passed": inc_passed,
        "incident_pass_rate": inc_rate,
        "freshness": freshness,
        "trust_context": trust_context,'''

if "freshness" not in content:
    content = content.replace(OLD, NEW, 1)
    content = content.replace(OLD_RET, NEW_RET, 1)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("PATCHED: freshness tier added to check")
else:
    print("SKIP: freshness already exists")
