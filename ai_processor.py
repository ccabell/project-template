import os
from typing import Optional
import openai
from openai import OpenAI

# Initialize OpenAI client
client = None

def init_openai(api_key: str) -> bool:
    """Initialize OpenAI client with API key"""
    global client
    try:
        client = OpenAI(api_key=api_key)
        # Test the API key with a simple call
        client.models.list()
        return True
    except Exception as e:
        print(f"Error initializing OpenAI: {e}")
        return False

def process_prompt_with_openai(transcript: str, prompt: str, model: str = "gpt-3.5-turbo") -> tuple[str, str]:
    """
    Process a prompt against a transcript using OpenAI API
    Returns: (result, error_message)
    """
    global client
    
    if client is None:
        return "", "OpenAI client not initialized. Please provide a valid API key."
    
    try:
        # Create the full prompt with context
        full_prompt = f"""Here is a transcript to analyze:

TRANSCRIPT:
{transcript}

INSTRUCTION:
{prompt}

Please provide your analysis based on the transcript above."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant that analyzes transcripts and provides detailed, accurate responses based on the content provided."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        result = response.choices[0].message.content
        return result, ""
        
    except Exception as e:
        error_message = f"Error processing prompt: {str(e)}"
        return "", error_message

def process_prompt_mock(transcript: str, prompt: str) -> tuple[str, str]:
    """
    Mock function for processing prompts when OpenAI is not available
    Returns: (result, error_message)
    """
    # Simple mock response for testing
    word_count = len(transcript.split())
    char_count = len(transcript)
    
    mock_result = f"""MOCK AI RESPONSE:

Transcript Analysis:
- Word count: {word_count}
- Character count: {char_count}
- Your prompt was: "{prompt}"

This is a mock response. To get actual AI analysis, please:
1. Set up your OpenAI API key in the settings
2. The system will then use GPT to analyze your transcripts

Mock insights based on your prompt:
- The transcript contains {word_count} words
- Average words per sentence: ~{word_count // max(transcript.count('.'), 1)}
- This appears to be a {"long" if word_count > 500 else "short"} transcript
"""
    
    return mock_result, ""

def get_available_models() -> list:
    """Get list of available OpenAI models"""
    global client
    
    if client is None:
        return ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
    
    try:
        models = client.models.list()
        # Filter for chat models
        chat_models = [model.id for model in models.data if 'gpt' in model.id.lower()]
        return sorted(chat_models)
    except:
        return ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]

def is_openai_configured() -> bool:
    """Check if OpenAI is properly configured"""
    global client
    return client is not None