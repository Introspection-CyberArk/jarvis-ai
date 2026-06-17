import json
import re
from datetime import datetime

class MemoryManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def extract_memory_from_text(self, text):
        memory = {}
        
        # Name extraction
        name_patterns = [
            r'(?:my name is|call me|i am|im)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'(?:name\'s|name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                memory['name'] = match.group(1)
                break
        
        # Age extraction
        age_match = re.search(r'(?:i am|im|age)\s+(\d+)\s*(?:years old|yo|yr)', text, re.IGNORECASE)
        if age_match:
            memory['age'] = int(age_match.group(1))
        
        # Location extraction
        location_match = re.search(r'(?:from|live in|located in|staying in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text, re.IGNORECASE)
        if location_match:
            memory['location'] = location_match.group(1)
        
        # Interests extraction
        interests_keywords = ['like', 'love', 'enjoy', 'interested in', 'hobby', 'passion']
        for keyword in interests_keywords:
            if keyword in text.lower():
                sentences = re.split(r'[.!?]', text)
                for sent in sentences:
                    if keyword in sent.lower():
                        interest = sent.strip()
                        if 'interests' not in memory:
                            memory['interests'] = []
                        memory['interests'].append(interest)
                        break
        
        # Occupation extraction
        job_match = re.search(r'(?:work as|job is|occupation|i am a|im a)\s+([a-z]+(?:\s+[a-z]+)?)', text, re.IGNORECASE)
        if job_match:
            memory['occupation'] = job_match.group(1)
        
        # Preferences extraction
        if any(word in text.lower() for word in ['like', 'love', 'enjoy', 'favorite']):
            topics = ['movies', 'music', 'books', 'games', 'food', 'sports', 'coding', 'tech']
            for topic in topics:
                if topic in text.lower():
                    if 'preferences' not in memory:
                        memory['preferences'] = {}
                    sentences = [s for s in re.split(r'[.!?]', text) if topic in s.lower()]
                    for sent in sentences:
                        if 'like' in sent or 'love' in sent or 'favorite' in sent:
                            memory['preferences'][topic] = sent.strip()
        
        return memory
    
    def extract_memory_from_conversation(self, user_id, messages):
        memory_updates = {}
        
        for msg in messages:
            if msg['role'] == 'user':
                extracted = self.extract_memory_from_text(msg['content'])
                memory_updates.update(extracted)
        
        if memory_updates:
            current_memory = self.db.get_user_memory(user_id)
            current_memory.update(memory_updates)
            self.db.update_user_memory(user_id, current_memory)
            
            for key, value in memory_updates.items():
                if isinstance(value, list):
                    for item in value:
                        self.db.add_memory(user_id, f"{key}: {item}")
                else:
                    self.db.add_memory(user_id, f"{key}: {value}")
        
        return memory_updates
