"""Patch check endpoint to include incident fields"""
with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

OLD = '''        peer_total = 0
        peer_avg = 0
    return {
        "found": True, "name": row[1],'''

NEW = '''        peer_total = 0
        peer_avg = 0
    # Incident test record
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

OLD_RET = '''"peer_verified": peer_total >= 3,
        "trust_context": trust_context,'''

NEW_RET = '''"peer_verified": peer_total >= 3,
        "incident_tests_passed": inc_passed,
        "incident_pass_rate": inc_rate,
        "trust_context": trust_context,'''

if OLD in content and "inc_passed" not in content.split("check_agent")[1].split("badge_svg")[0]:
    content = content.replace(OLD, NEW, 1)
    content = content.replace(OLD_RET, NEW_RET, 1)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("PATCHED: check with incident fields")
else:
    print("SKIP or already done")
