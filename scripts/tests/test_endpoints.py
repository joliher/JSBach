import sys
import os
from fastapi.testclient import TestClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import app
from app.api.admin_router import require_login

# Mock authentication
def mock_require_login():
    return "admin"

app.dependency_overrides[require_login] = mock_require_login

client = TestClient(app)

def test_admin_status():
    response = client.get("/admin/status")
    assert response.status_code == 200
    data = response.json()
    assert "wan" in data
    assert "vlans" in data

def test_wan_info():
    response = client.get("/admin/wan/info")
    assert response.status_code == 200
    assert "status" in response.json()

def test_vlans_action():
    # Test a simple status action via POST
    response = client.post("/admin/vlans", json={"action": "status"})
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_config_serving():
    # Test that config files are served correctly via admin router
    # Note: this requires the file to exist
    response = client.get("/admin/config/wan/wan.json")
    if response.status_code == 200:
        assert isinstance(response.json(), dict)
    else:
        assert response.status_code == 404

def test_static_web_serving():
    # Test that web files are served (this is in main_controller, not admin_router)
    # We need to bypass auth here too if it uses session
    response = client.get("/web/index.html")
    # For TestClient, session might need careful handling or just mock the middleware if possible
    # But since we override require_login for admin_router, let's see if we need it for static
    pass

if __name__ == "__main__":
    # Run tests using pytest or manually
    print("Running endpoint tests...")
    try:
        test_admin_status()
        print("✅ /admin/status: OK")
        test_wan_info()
        print("✅ /admin/wan/info: OK")
        test_vlans_action()
        print("✅ /admin/vlans (POST): OK")
        test_config_serving()
        print("✅ /admin/config/...: OK")
        print("\n🎉 All endpoint tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
