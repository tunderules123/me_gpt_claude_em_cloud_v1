#!/usr/bin/env python3
"""
Specific tests for the two main issues that were fixed:
1. Speaker labels appearing in output
2. Claude giving generic responses
"""

import requests
import sys
import json
import re
import time

class SpecificIssuesTester:
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

    def has_speaker_labels(self, content):
        """Check if content contains speaker labels"""
        # Look for patterns like [SPEAKER: CLAUDE], [SPEAKER: GPT], [SPEAKER: USER]
        speaker_patterns = [
            r'\[SPEAKER:\s*[^\]]+\]',
            r'\[speaker:\s*[^\]]+\]',
            r'\[SPEAKER\s*[^\]]+\]',
            r'\[speaker\s*[^\]]+\]'
        ]
        
        for pattern in speaker_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def is_generic_ai_response(self, content):
        """Check if Claude is giving generic AI assistant responses"""
        generic_phrases = [
            "as an ai assistant",
            "i'm not able to give personalized advice",
            "i cannot provide personalized",
            "as an artificial intelligence",
            "i'm an ai and cannot",
            "i don't have the ability to provide personalized"
        ]
        
        content_lower = content.lower()
        for phrase in generic_phrases:
            if phrase in content_lower:
                return True
        return False

    def test_speaker_labels_claude_only(self):
        """Test that Claude responses don't contain speaker labels"""
        try:
            # Reset chat first
            self.session.post(f"{self.base_url}/api/reset")
            
            payload = {"content": "What is 2+2?", "tags": ["@claude"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=30)
            
            if response.status_code != 200:
                return self.log_test("Speaker Labels - Claude Only", False, f"API call failed: {response.status_code}")
            
            data = response.json()
            replies = data.get('replies', [])
            
            if not replies:
                return self.log_test("Speaker Labels - Claude Only", False, "No replies received")
            
            claude_reply = replies[0]
            content = claude_reply.get('content', '')
            
            has_labels = self.has_speaker_labels(content)
            success = not has_labels
            
            details = f"Content preview: '{content[:100]}...', Has speaker labels: {has_labels}"
            return self.log_test("Speaker Labels - Claude Only", success, details)
            
        except Exception as e:
            return self.log_test("Speaker Labels - Claude Only", False, f"Error: {str(e)}")

    def test_speaker_labels_gpt_only(self):
        """Test that GPT responses don't contain speaker labels"""
        try:
            payload = {"content": "What is 3+3?", "tags": ["@gpt"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=30)
            
            if response.status_code != 200:
                return self.log_test("Speaker Labels - GPT Only", False, f"API call failed: {response.status_code}")
            
            data = response.json()
            replies = data.get('replies', [])
            
            if not replies:
                return self.log_test("Speaker Labels - GPT Only", False, "No replies received")
            
            gpt_reply = replies[0]
            content = gpt_reply.get('content', '')
            
            has_labels = self.has_speaker_labels(content)
            success = not has_labels
            
            details = f"Content preview: '{content[:100]}...', Has speaker labels: {has_labels}"
            return self.log_test("Speaker Labels - GPT Only", success, details)
            
        except Exception as e:
            return self.log_test("Speaker Labels - GPT Only", False, f"Error: {str(e)}")

    def test_speaker_labels_both_providers(self):
        """Test that both provider responses don't contain speaker labels"""
        try:
            payload = {"content": "What is 4+4? Please both answer.", "tags": ["@gpt", "@claude"]}
            response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=45)
            
            if response.status_code != 200:
                return self.log_test("Speaker Labels - Both Providers", False, f"API call failed: {response.status_code}")
            
            data = response.json()
            replies = data.get('replies', [])
            
            if len(replies) != 2:
                return self.log_test("Speaker Labels - Both Providers", False, f"Expected 2 replies, got {len(replies)}")
            
            all_clean = True
            details_parts = []
            
            for i, reply in enumerate(replies):
                content = reply.get('content', '')
                author = reply.get('author', 'unknown')
                has_labels = self.has_speaker_labels(content)
                
                if has_labels:
                    all_clean = False
                
                details_parts.append(f"{author}: has_labels={has_labels}")
            
            details = ", ".join(details_parts)
            return self.log_test("Speaker Labels - Both Providers", all_clean, details)
            
        except Exception as e:
            return self.log_test("Speaker Labels - Both Providers", False, f"Error: {str(e)}")

    def test_claude_direct_questions(self):
        """Test that Claude gives direct answers to simple questions"""
        try:
            # Reset chat first
            self.session.post(f"{self.base_url}/api/reset")
            
            questions = [
                "What is the capital of France?",
                "How do you calculate the area of a circle?",
                "What is 15 * 7?"
            ]
            
            all_direct = True
            details_parts = []
            
            for question in questions:
                payload = {"content": question, "tags": ["@claude"]}
                response = self.session.post(f"{self.base_url}/api/send", json=payload, timeout=30)
                
                if response.status_code != 200:
                    all_direct = False
                    details_parts.append(f"'{question}': API failed")
                    continue
                
                data = response.json()
                replies = data.get('replies', [])
                
                if not replies:
                    all_direct = False
                    details_parts.append(f"'{question}': No reply")
                    continue
                
                content = replies[0].get('content', '')
                is_generic = self.is_generic_ai_response(content)
                
                if is_generic:
                    all_direct = False
                
                details_parts.append(f"'{question}': generic={is_generic}")
                
                # Small delay between requests
                time.sleep(1)
            
            details = "; ".join(details_parts)
            return self.log_test("Claude Direct Questions", all_direct, details)
            
        except Exception as e:
            return self.log_test("Claude Direct Questions", False, f"Error: {str(e)}")

    def test_claude_conversation_context(self):
        """Test that Claude can respond to conversation context properly"""
        try:
            # Reset chat first
            self.session.post(f"{self.base_url}/api/reset")
            
            # First, send a message to GPT
            payload1 = {"content": "GPT, please say 'The weather is sunny today'", "tags": ["@gpt"]}
            response1 = self.session.post(f"{self.base_url}/api/send", json=payload1, timeout=30)
            
            if response1.status_code != 200:
                return self.log_test("Claude Conversation Context", False, "GPT message failed")
            
            # Then ask Claude to comment on GPT's response
            payload2 = {"content": "Claude, what did GPT just say about the weather?", "tags": ["@claude"]}
            response2 = self.session.post(f"{self.base_url}/api/send", json=payload2, timeout=30)
            
            if response2.status_code != 200:
                return self.log_test("Claude Conversation Context", False, f"Claude response failed: {response2.status_code}")
            
            data = response2.json()
            replies = data.get('replies', [])
            
            if not replies:
                return self.log_test("Claude Conversation Context", False, "No Claude reply")
            
            claude_content = replies[0].get('content', '').lower()
            
            # Check if Claude references the weather or GPT's message
            has_context = any(word in claude_content for word in ['weather', 'sunny', 'gpt', 'said'])
            is_generic = self.is_generic_ai_response(claude_content)
            
            success = has_context and not is_generic
            details = f"Has context: {has_context}, Is generic: {is_generic}, Content preview: '{claude_content[:100]}...'"
            
            return self.log_test("Claude Conversation Context", success, details)
            
        except Exception as e:
            return self.log_test("Claude Conversation Context", False, f"Error: {str(e)}")

    def test_history_no_speaker_labels(self):
        """Test that conversation history doesn't show speaker labels"""
        try:
            # Get current history
            response = self.session.get(f"{self.base_url}/api/history")
            
            if response.status_code != 200:
                return self.log_test("History No Speaker Labels", False, f"History API failed: {response.status_code}")
            
            data = response.json()
            history = data.get('history', [])
            
            if not history:
                return self.log_test("History No Speaker Labels", True, "No history to check")
            
            all_clean = True
            label_count = 0
            
            for msg in history:
                content = msg.get('content', '')
                if self.has_speaker_labels(content):
                    all_clean = False
                    label_count += 1
            
            details = f"Total messages: {len(history)}, Messages with labels: {label_count}"
            return self.log_test("History No Speaker Labels", all_clean, details)
            
        except Exception as e:
            return self.log_test("History No Speaker Labels", False, f"Error: {str(e)}")

    def run_all_tests(self):
        """Run all specific issue tests"""
        print("🔍 Testing Specific Fixed Issues")
        print("=" * 60)
        print("Issue 1: Speaker labels appearing in output")
        print("Issue 2: Claude giving generic responses")
        print("=" * 60)
        
        # Speaker label tests
        self.test_speaker_labels_claude_only()
        self.test_speaker_labels_gpt_only()
        self.test_speaker_labels_both_providers()
        self.test_history_no_speaker_labels()
        
        # Claude response quality tests
        self.test_claude_direct_questions()
        self.test_claude_conversation_context()
        
        # Final results
        print("=" * 60)
        print(f"📊 Specific Issues Test Summary:")
        print(f"   Tests Run: {self.tests_run}")
        print(f"   Tests Passed: {self.tests_passed}")
        print(f"   Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All specific issues appear to be FIXED!")
        else:
            print("⚠️  Some issues may still exist.")
        
        return self.tests_passed == self.tests_run

def main():
    tester = SpecificIssuesTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())