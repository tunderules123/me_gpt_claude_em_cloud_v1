from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel
from typing import List, Literal, Optional, Dict, Any
import uuid
import time
from openai import OpenAI
from anthropic import Anthropic

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize API clients
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
anthropic_client = Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

# Create the main app
app = FastAPI()

# Message types
Author = Literal["user", "gpt", "claude"]
Role = Literal["user", "assistant"]

class Msg(BaseModel):
    id: str
    author: Author
    role: Role
    content: str
    ts: int

class SendRequest(BaseModel):
    content: str
    tags: List[Literal["@gpt", "@claude"]]

class Reply(BaseModel):
    id: str
    author: Author
    content: str
    ts: int

class SendResponse(BaseModel):
    ok: bool
    userMessageId: str
    replies: List[Reply]

class HistoryResponse(BaseModel):
    history: List[Msg]

class ResetResponse(BaseModel):
    ok: bool

# In-memory message history
message_history: List[Msg] = []

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_speaker_labeled_content(history: List[Msg]) -> List[Dict[str, str]]:
    """Convert message history to provider format with speaker labels"""
    messages = []
    for msg in history:
        if msg.role == "user":
            content = f"[SPEAKER: USER] {msg.content}"
        else:
            speaker = msg.author.upper()
            content = f"[SPEAKER: {speaker}] {msg.content}"
        
        messages.append({
            "role": msg.role,
            "content": content
        })
    
    return messages

async def call_openai(messages: List[Dict[str, str]], timeout: int = 20) -> str:
    """Call OpenAI API with timeout and retries"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            timeout=timeout
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise

async def call_anthropic_faithful(messages: List[Dict[str, str]], timeout: int = 20) -> str:
    """Call Anthropic API with faithful role mapping"""
    try:
        # Convert to Anthropic format
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        kwargs = {
            "model": "claude-3-sonnet-20240229",
            "messages": anthropic_messages,
            "max_tokens": 1000,
            "timeout": timeout
        }
        
        if system_message:
            kwargs["system"] = system_message
            
        response = anthropic_client.messages.create(**kwargs)
        return response.content[0].text
    except Exception as e:
        logger.error(f"Anthropic faithful API error: {e}")
        raise

async def call_anthropic_compat(messages: List[Dict[str, str]], timeout: int = 20) -> str:
    """Call Anthropic API with compatibility mapping for role alternation"""
    try:
        # Compatibility mapping: rewrite only GPT's prior assistant messages to user
        # while preserving Claude's own assistant messages
        compat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                continue  # Handle separately
                
            content = msg["content"]
            role = msg["role"]
            
            # If this is an assistant message from GPT, convert to user for compatibility
            if role == "assistant" and "[SPEAKER: GPT]" in content:
                role = "user"
            
            compat_messages.append({
                "role": role,
                "content": content
            })
        
        response = anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            messages=compat_messages,
            max_tokens=1000,
            timeout=timeout
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Anthropic compat API error: {e}")
        raise

async def call_anthropic(messages: List[Dict[str, str]], timeout: int = 20) -> str:
    """Call Anthropic with faithful -> compat retry pattern"""
    try:
        return await call_anthropic_faithful(messages, timeout)
    except Exception as e:
        # Check if it's a role alternation error
        error_str = str(e).lower()
        if "alternate" in error_str or "role" in error_str:
            logger.info("Anthropic faithful failed with alternation error, retrying with compat mapping")
            try:
                return await call_anthropic_compat(messages, timeout)
            except Exception as compat_e:
                logger.error(f"Anthropic compat also failed: {compat_e}")
                raise compat_e
        else:
            raise e

async def call_provider(provider: str, messages: List[Dict[str, str]]) -> str:
    """Call the specified provider with retries and backoff"""
    max_retries = 2
    base_timeout = 20
    
    for attempt in range(max_retries + 1):
        try:
            timeout = base_timeout + (attempt * 10)  # Increase timeout on retries
            
            if provider == "gpt":
                return await call_openai(messages, timeout)
            elif provider == "claude":
                return await call_anthropic(messages, timeout)
            else:
                raise ValueError(f"Unknown provider: {provider}")
                
        except Exception as e:
            if attempt == max_retries:
                # Final attempt failed
                error_msg = f"timeout after {timeout * 1000}ms" if "timeout" in str(e).lower() else str(e)
                raise Exception(f"(error from {provider.title()}: {error_msg})")
            
            # Wait before retry with exponential backoff
            wait_time = 2 ** attempt
            logger.info(f"Provider {provider} attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
            await asyncio.sleep(wait_time)

@app.get("/history", response_model=HistoryResponse)
async def get_history():
    """Get chat history"""
    return HistoryResponse(history=message_history)

@app.post("/send", response_model=SendResponse)
async def send_message(request: SendRequest):
    """Send message and get replies from selected providers"""
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    
    if not request.tags:
        raise HTTPException(status_code=400, detail="At least one tag must be selected")
    
    # Create user message
    user_message_id = str(uuid.uuid4())
    user_message = Msg(
        id=user_message_id,
        author="user",
        role="user",
        content=request.content.strip(),
        ts=int(time.time() * 1000)
    )
    
    # Add user message to history
    message_history.append(user_message)
    
    # Prepare messages for providers (with speaker labels)
    provider_messages = create_speaker_labeled_content(message_history)
    
    # Add the new user message with speaker label
    provider_messages.append({
        "role": "user",
        "content": f"[SPEAKER: USER] {request.content.strip()}"
    })
    
    # Process providers in the exact order of tags
    replies = []
    for tag in request.tags:
        provider = tag[1:]  # Remove @ prefix
        
        try:
            # Call provider
            response_content = await call_provider(provider, provider_messages)
            
            # Create reply message
            reply = Reply(
                id=str(uuid.uuid4()),
                author=provider,  # type: ignore
                content=response_content,
                ts=int(time.time() * 1000)
            )
            replies.append(reply)
            
            # Add to history for subsequent providers
            history_msg = Msg(
                id=reply.id,
                author=reply.author,
                role="assistant",
                content=reply.content,
                ts=reply.ts
            )
            message_history.append(history_msg)
            
            # Update provider messages for next provider
            provider_messages.append({
                "role": "assistant",
                "content": f"[SPEAKER: {provider.upper()}] {response_content}"
            })
            
        except Exception as e:
            # Provider failed - create error reply but continue with other providers
            error_content = str(e)
            if not error_content.startswith("(error from"):
                error_content = f"(error from {provider.title()}: {error_content})"
            
            error_reply = Reply(
                id=str(uuid.uuid4()),
                author=provider,  # type: ignore
                content=error_content,
                ts=int(time.time() * 1000)
            )
            replies.append(error_reply)
            
            # Add error to history
            error_msg = Msg(
                id=error_reply.id,
                author=error_reply.author,
                role="assistant",
                content=error_reply.content,
                ts=error_reply.ts
            )
            message_history.append(error_msg)
            
            logger.error(f"Provider {provider} failed: {e}")
    
    return SendResponse(
        ok=True,
        userMessageId=user_message_id,
        replies=replies
    )

@app.post("/reset", response_model=ResetResponse)
async def reset_chat():
    """Reset chat history"""
    global message_history
    message_history = []
    return ResetResponse(ok=True)

# Health check endpoint
@app.get("/")
async def root():
    return {"message": "Chat API is running", "endpoints": ["/history", "/send", "/reset"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)