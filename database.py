import os
from supabase import create_client, Client
from datetime import datetime
import json

class DatabaseManager:
    def __init__(self):
        # Get from environment variables directly
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
    
    def get_or_create_user(self, user_id, username=None, first_name=None):
        response = self.supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if not response.data:
            data = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'memory': '{}',
                'updated_at': datetime.now().isoformat()
            }
            self.supabase.table('user_profiles').insert(data).execute()
            return data
        return response.data[0]
    
    def update_user_memory(self, user_id, memory_data):
        current = self.get_user_memory(user_id)
        if current:
            current.update(memory_data)
        else:
            current = memory_data
        
        self.supabase.table('user_profiles').update({
            'memory': json.dumps(current),
            'updated_at': datetime.now().isoformat()
        }).eq('user_id', user_id).execute()
        
        return current
    
    def get_user_memory(self, user_id):
        response = self.supabase.table('user_profiles').select('memory').eq('user_id', user_id).execute()
        if response.data and response.data[0].get('memory'):
            try:
                return json.loads(response.data[0]['memory'])
            except:
                return {}
        return {}
    
    def add_chat_history(self, user_id, role, content):
        data = {
            'user_id': user_id,
            'role': role,
            'content': content,
            'created_at': datetime.now().isoformat()
        }
        self.supabase.table('chat_history').insert(data).execute()
    
    def get_chat_history(self, user_id, limit=10):
        response = self.supabase.table('chat_history')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        return response.data[::-1]
    
    def add_memory(self, user_id, memory_text):
        data = {
            'user_id': user_id,
            'memory': memory_text,
            'created_at': datetime.now().isoformat()
        }
        self.supabase.table('memories').insert(data).execute()
    
    def get_memories(self, user_id, limit=20):
        response = self.supabase.table('memories')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        return response.data
