#!/usr/bin/env python3
"""
Backend API Testing for 3-Person Chat Application
Tests all endpoints: /api/history, /api/send, /api/reset
"""

import requests
import sys
import json
import time
from datetime import datetime

class ChatAPITester:
    def __init__(self, base_url="https://trio-messenger.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED {details}")
        else:
            print(f"❌ {name} - FAILED {details}")
        return success

    def test_health_check(self):
        """Test basic API health"""
        try:
            response = self.session.get(f"{self.base_url}/api/")
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Message: {data.get('message', 'N/A')}"
            return self.log_test("Health Check", success, details)
        except Exception as e:
            return self.log_test("Health Check", False, f"Error: {str(e)}")

    def test_get_history_empty(self):
        """Test getting empty history initially"""
        try:
            response = self.session.get(f"{self.base_url}/api/history")
            success = response.status_code == 200
            if success:
                data = response.json()
                history_empty = len(data.get('history', [])) == 0
                success = history_empty
                details = f"Status: {response.status_code}, History length: {len(data.get('history', []))}"
            else:
                details = f"Status: {response.status_code}"
            return self.log_test("Get Empty History", success, details)
        except Exception as e:
            return self.log_test("Get Empty History", False, f"Error: {str(e)}")

    def test_reset_chat(self):
        """Test reset functionality"""
        try:
            response = self.session.post(f"{self.base_url}/api/reset")
            success = response.status_code == 200
            if success:
                data = response.json()
                success = data.get('ok', False)
                details = f"Status: {response.status_code}, OK: {data.get('ok')}"
            else:
                details = f"Status: {response.status_code}"
            return self.log_test("Reset Chat", success, details)
        except Exception as e:
            return self.log_test("Reset Chat", False, f"Error: {str(e)}")

    def test_send_message_validation(self):
        """Test message validation (empty content, no tags)"""
        # Test empty content
        try:
            payload = {"content": "", "tags": ["@gpt"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload)
            success = response.status_code == 400
            details = f"Empty content - Status: {response.status_code}"
            self.log_test("Send Message Validation (Empty Content)", success, details)
        except Exception as e:
            self.log_test("Send Message Validation (Empty Content)", False, f"Error: {str(e)}")

        # Test no tags
        try:
            payload = {"content": "Hello", "tags": []}
            response = self.session.post(f"{self.base_url}/api/send", json=payload)
            success = response.status_code == 400
            details = f"No tags - Status: {response.status_code}"
            return self.log_test("Send Message Validation (No Tags)", success, details)
        except Exception as e:
            return self.log_test("Send Message Validation (No Tags)", False, f"Error: {str(e)}")

    def test_send_message_gpt_only(self):
        """Test sending message to GPT only"""
        try:
            payload = {"content": "Hello GPT, please respond with 'GPT received your message'", "tags": ["@gpt"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=30)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                replies = data.get('replies', [])
                success = (
                    data.get('ok', False) and 
                    len(replies) == 1 and 
                    replies[0].get('author') == 'gpt'
                )
                details = f"Status: {response.status_code}, Replies: {len(replies)}, Author: {replies[0].get('author') if replies else 'None'}"
                if replies:
                    details += f", Content preview: {replies[0].get('content', '')[:50]}..."
            else:
                details = f"Status: {response.status_code}"
                
            return self.log_test("Send Message to GPT Only", success, details)
        except Exception as e:
            return self.log_test("Send Message to GPT Only", False, f"Error: {str(e)}")

    def test_send_message_claude_only(self):
        """Test sending message to Claude only"""
        try:
            payload = {"content": "Hello Claude, please respond with 'Claude received your message'", "tags": ["@claude"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=30)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                replies = data.get('replies', [])
                success = (
                    data.get('ok', False) and 
                    len(replies) == 1 and 
                    replies[0].get('author') == 'claude'
                )
                details = f"Status: {response.status_code}, Replies: {len(replies)}, Author: {replies[0].get('author') if replies else 'None'}"
                if replies:
                    details += f", Content preview: {replies[0].get('content', '')[:50]}..."
            else:
                details = f"Status: {response.status_code}"
                
            return self.log_test("Send Message to Claude Only", success, details)
        except Exception as e:
            return self.log_test("Send Message to Claude Only", False, f"Error: {str(e)}")

    def test_send_message_both_gpt_first(self):
        """Test sending message to both GPT then Claude"""
        try:
            payload = {"content": "Hello both! Please each respond with your name.", "tags": ["@gpt", "@claude"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=45)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                replies = data.get('replies', [])
                success = (
                    data.get('ok', False) and 
                    len(replies) == 2 and 
                    replies[0].get('author') == 'gpt' and
                    replies[1].get('author') == 'claude'
                )
                details = f"Status: {response.status_code}, Replies: {len(replies)}"
                if len(replies) >= 2:
                    details += f", Order: {replies[0].get('author')} → {replies[1].get('author')}"
            else:
                details = f"Status: {response.status_code}"
                
            return self.log_test("Send Message to Both (GPT→Claude)", success, details)
        except Exception as e:
            return self.log_test("Send Message to Both (GPT→Claude)", False, f"Error: {str(e)}")

    def test_send_message_both_claude_first(self):
        """Test sending message to both Claude then GPT"""
        try:
            payload = {"content": "Hello again! Please each respond with your name.", "tags": ["@claude", "@gpt"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=45)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                replies = data.get('replies', [])
                success = (
                    data.get('ok', False) and 
                    len(replies) == 2 and 
                    replies[0].get('author') == 'claude' and
                    replies[1].get('author') == 'gpt'
                )
                details = f"Status: {response.status_code}, Replies: {len(replies)}"
                if len(replies) >= 2:
                    details += f", Order: {replies[0].get('author')} → {replies[1].get('author')}"
            else:
                details = f"Status: {response.status_code}"
                
            return self.log_test("Send Message to Both (Claude→GPT)", success, details)
        except Exception as e:
            return self.log_test("Send Message to Both (Claude→GPT)", False, f"Error: {str(e)}")

    def test_get_history_with_messages(self):
        """Test getting history after sending messages"""
        try:
            response = self.session.get(f"{self.base_url}/api/history")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                history = data.get('history', [])
                # Should have messages from previous tests
                success = len(history) > 0
                details = f"Status: {response.status_code}, History length: {len(history)}"
                
                # Check message structure
                if history:
                    msg = history[0]
                    has_required_fields = all(field in msg for field in ['id', 'author', 'role', 'content', 'ts'])
                    details += f", Has required fields: {has_required_fields}"
                    success = success and has_required_fields
            else:
                details = f"Status: {response.status_code}"
                
            return self.log_test("Get History with Messages", success, details)
        except Exception as e:
            return self.log_test("Get History with Messages", False, f"Error: {str(e)}")

    def test_conversation_context(self):
        """Test that conversation context is maintained"""
        try:
            # Reset first
            self.session.post(f"{self.base_url}/api/reset")
            
            # Send first message
            payload1 = {"content": "My name is TestUser. Remember this.", "tags": ["@gpt"]}
            response1 = self.session.post(f"{self.base_url}/api/send", json=payload1, timeout=30)
            
            if response1.status_code != 200:
                return self.log_test("Conversation Context", False, "First message failed")
            
            # Send second message asking about the name
            payload2 = {"content": "What name did I tell you?", "tags": ["@gpt"]}
            response2 = self.session.post(f"{self.base_url}/api/send", json=payload2, timeout=30)
            
            success = response2.status_code == 200
            if success:
                data = response2.json()
                replies = data.get('replies', [])
                if replies:
                    content = replies[0].get('content', '').lower()
                    # Check if GPT remembers the name
                    remembers_name = 'testuser' in content
                    details = f"Status: {response2.status_code}, Remembers name: {remembers_name}"
                    success = remembers_name
                else:
                    details = f"Status: {response2.status_code}, No replies"
                    success = False
            else:
                details = f"Status: {response2.status_code}"
                
            return self.log_test("Conversation Context", success, details)
        except Exception as e:
            return self.log_test("Conversation Context", False, f"Error: {str(e)}")

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Backend API Tests")
        print(f"Testing endpoint: {self.base_url}")
        print("=" * 60)
        
        # Basic functionality tests
        self.test_health_check()
        self.test_reset_chat()
        self.test_get_history_empty()
        
        # Validation tests
        self.test_send_message_validation()
        
        # Core functionality tests
        self.test_send_message_gpt_only()
        self.test_send_message_claude_only()
        self.test_send_message_both_gpt_first()
        self.test_send_message_both_claude_first()
        
        # History and context tests
        self.test_get_history_with_messages()
        self.test_conversation_context()
        
        # Final results
        print("=" * 60)
        print(f"📊 Backend Tests Summary:")
        print(f"   Tests Run: {self.tests_run}")
        print(f"   Tests Passed: {self.tests_passed}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    tester = ChatAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())