import os
import logging
from supabase import create_client, Client
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        try:
            self.supabase_url = os.getenv('SUPABASE_URL')
            self.supabase_key = os.getenv('SUPABASE_KEY')
            
            if not self.supabase_url:
                raise ValueError("SUPABASE_URL environment variable is not set")
            if not self.supabase_key:
                raise ValueError("SUPABASE_KEY environment variable is not set")
            
            logger.info(f"Connecting to Supabase: {self.supabase_url}")
            
            self.supabase: Client = create_client(
                self.supabase_url,
                self.supabase_key
            )
            
            # Test connection
            try:
                test = self.supabase.table('user_profiles').select('*').limit(1).execute()
                logger.info("✅ Tables already exist")
            except Exception as e:
                if "relation" in str(e) and "does not exist" in str(e):
                    logger.warning("⚠️ Tables don't exist. Please run SQL schema.")
                else:
                    raise e
                
            logger.info("✅ Supabase connected successfully!")
                
        except Exception as e:
            logger.error(f"❌ Supabase connection failed: {e}")
            raise
    
    def get_or_create_user(self, user_id, username=None, first_name=None):
        try:
            # Try to get existing user
            response = self.supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
            
            if response.data:
                return response.data[0]
            
            # Create new user with retry
            data = {
                'user_id': user_id,
                'username': username or '',
                'first_name': first_name or '',
                'memory': '{}',
                'updated_at': datetime.now().isoformat()
            }
            
            try:
                result = self.supabase.table('user_profiles').insert(data).execute()
                if result.data:
                    return result.data[0]
                return data
            except Exception as insert_error:
                # If RLS error, try one more time
                if "row-level security" in str(insert_error):
                    logger.warning("RLS policy error - trying to create user anyway")
                    # Return default data (bot will work with in-memory fallback)
                    return data
                raise
                
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {e}")
            # Return default data to keep bot running
            return {
                'user_id': user_id,
                'username': username or '',
                'first_name': first_name or '',
                'memory': '{}'
            }
    
    def update_user_memory(self, user_id, memory_data):
        try:
            current = self.get_user_memory(user_id)
            if current:
                current.update(memory_data)
            else:
                current = memory_data
            
            try:
                result = self.supabase.table('user_profiles').update({
                    'memory': json.dumps(current),
                    'updated_at': datetime.now().isoformat()
                }).eq('user_id', user_id).execute()
                return current
            except Exception as e:
                logger.error(f"Update failed: {e}")
                return current
                
        except Exception as e:
            logger.error(f"Error in update_user_memory: {e}")
            return memory_data
    
    def get_user_memory(self, user_id):
        try:
            response = self.supabase.table('user_profiles').select('memory').eq('user_id', user_id).execute()
            if response.data and response.data[0].get('memory'):
                try:
                    return json.loads(response.data[0]['memory'])
                except:
                    return {}
            return {}
        except Exception as e:
            logger.error(f"Error in get_user_memory: {e}")
            return {}
    
    def add_chat_history(self, user_id, role, content):
        try:
            data = {
                'user_id': user_id,
                'role': role,
                'content': content,
                'created_at': datetime.now().isoformat()
            }
            self.supabase.table('chat_history').insert(data).execute()
        except Exception as e:
            logger.error(f"Error in add_chat_history: {e}")
    
    def get_chat_history(self, user_id, limit=10):
        try:
            response = self.supabase.table('chat_history')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            return response.data[::-1] if response.data else []
        except Exception as e:
            logger.error(f"Error in get_chat_history: {e}")
            return []
    
    def add_memory(self, user_id, memory_text):
        try:
            data = {
                'user_id': user_id,
                'memory': memory_text,
                'created_at': datetime.now().isoformat()
            }
            self.supabase.table('memories').insert(data).execute()
        except Exception as e:
            logger.error(f"Error in add_memory: {e}")
    
    def get_memories(self, user_id, limit=20):
        try:
            response = self.supabase.table('memories')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error in get_memories: {e}")
            return []
