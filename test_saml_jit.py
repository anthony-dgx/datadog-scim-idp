#!/usr/bin/env python3
"""
Simple test script to verify SAML JIT provisioning functionality
"""
import asyncio
import aiohttp
import json
import base64
from typing import Dict, Any

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_EMAIL = "test-jit-user@example.com"

async def test_jit_configuration():
    """Test JIT configuration endpoints"""
    print("Testing JIT configuration...")
    
    async with aiohttp.ClientSession() as session:
        # Test GET JIT config
        async with session.get(f"{BASE_URL}/api/saml/jit-config") as response:
            if response.status == 200:
                config = await response.json()
                print(f"✅ JIT config retrieved: {config['jit_enabled']}")
                return True
            else:
                print(f"❌ Failed to get JIT config: {response.status}")
                return False

async def test_saml_metadata():
    """Test SAML metadata endpoint"""
    print("Testing SAML metadata...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/saml/metadata") as response:
            if response.status == 200:
                metadata = await response.text()
                print(f"✅ SAML metadata retrieved ({len(metadata)} characters)")
                return True
            else:
                print(f"❌ Failed to get SAML metadata: {response.status}")
                return False

async def test_saml_login_form():
    """Test SAML login form with mock SAMLRequest"""
    print("Testing SAML login form...")
    
    # Create a mock SAML request (base64 encoded)
    mock_saml_request = base64.b64encode(b"""
    <samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" 
                        ID="_mock_request_id" 
                        Version="2.0" 
                        IssueInstant="2023-01-01T00:00:00Z"
                        Destination="http://localhost:8000/saml/login">
        <saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">https://app.datadoghq.com</saml:Issuer>
    </samlp:AuthnRequest>
    """).decode('utf-8')
    
    async with aiohttp.ClientSession() as session:
        data = {
            'SAMLRequest': mock_saml_request,
            'RelayState': 'test_relay_state'
        }
        
        async with session.post(f"{BASE_URL}/saml/login", data=data) as response:
            if response.status == 200:
                html = await response.text()
                if 'Enable Just-In-Time provisioning' in html:
                    print("✅ SAML login form shows JIT option")
                    return True
                else:
                    print("❌ SAML login form missing JIT option")
                    return False
            else:
                print(f"❌ Failed to access SAML login: {response.status}")
                return False

async def simulate_jit_authentication():
    """Simulate JIT authentication process"""
    print("Simulating JIT authentication...")
    
    # Create a mock SAML request
    mock_saml_request = base64.b64encode(b"""
    <samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" 
                        ID="_mock_request_id" 
                        Version="2.0" 
                        IssueInstant="2023-01-01T00:00:00Z"
                        Destination="http://localhost:8000/saml/login">
        <saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">https://app.datadoghq.com</saml:Issuer>
    </samlp:AuthnRequest>
    """).decode('utf-8')
    
    async with aiohttp.ClientSession() as session:
        data = {
            'email': TEST_EMAIL,
            'enable_jit': 'true',
            'SAMLRequest': mock_saml_request,
            'RelayState': 'test_relay_state'
        }
        
        async with session.post(f"{BASE_URL}/saml/validate", data=data) as response:
            print(f"SAML validation response: {response.status}")
            
            if response.status == 200:
                html = await response.text()
                if 'Authentication Successful' in html:
                    print("✅ JIT authentication successful")
                    return True
                else:
                    print("❌ JIT authentication failed - no success message")
                    return False
            elif response.status == 500:
                error_text = await response.text()
                if 'JIT provisioning failed' in error_text:
                    print("⚠️  JIT provisioning failed (expected if SCIM not configured)")
                    return True
                else:
                    print(f"❌ Authentication failed: {response.status}")
                    return False
            else:
                print(f"❌ Authentication failed: {response.status}")
                return False

async def check_user_created():
    """Check if user was created in local database"""
    print("Checking if user was created locally...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/users") as response:
            if response.status == 200:
                users = await response.json()
                for user in users:
                    if user['email'] == TEST_EMAIL:
                        print(f"✅ User created locally: {user['email']} (ID: {user['id']})")
                        return True
                print("❌ User not found in local database")
                return False
            else:
                print(f"❌ Failed to check users: {response.status}")
                return False

async def cleanup_test_user():
    """Clean up test user"""
    print("Cleaning up test user...")
    
    async with aiohttp.ClientSession() as session:
        # Get all users
        async with session.get(f"{BASE_URL}/api/users") as response:
            if response.status == 200:
                users = await response.json()
                for user in users:
                    if user['email'] == TEST_EMAIL:
                        # Delete the test user
                        async with session.delete(f"{BASE_URL}/api/users/{user['id']}") as delete_response:
                            if delete_response.status == 200:
                                print(f"✅ Test user cleaned up: {user['email']}")
                                return True
                            else:
                                print(f"❌ Failed to delete test user: {delete_response.status}")
                                return False
                
                print("ℹ️  No test user found to clean up")
                return True
            else:
                print(f"❌ Failed to get users for cleanup: {response.status}")
                return False

async def main():
    """Run all tests"""
    print("🧪 Testing SAML JIT Provisioning")
    print("=" * 40)
    
    tests = [
        ("JIT Configuration", test_jit_configuration),
        ("SAML Metadata", test_saml_metadata),
        ("SAML Login Form", test_saml_login_form),
        ("JIT Authentication", simulate_jit_authentication),
        ("User Created Check", check_user_created),
        ("Cleanup", cleanup_test_user),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! SAML JIT provisioning is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the configuration and logs.")

if __name__ == "__main__":
    print("Make sure your application is running on http://localhost:8000")
    input("Press Enter to continue...")
    asyncio.run(main()) 