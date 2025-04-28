from dsk.api import DeepSeekAPI, AuthenticationError, RateLimitError, NetworkError, APIError
import sys, os
from typing import Generator, Dict, Any
from dotenv import load_dotenv

load_dotenv()

def print_response(chunks: Generator[Dict[str, Any], None, None]) -> str:
    """Helper function to print response chunks in a clean format"""
    thinking_lines = []
    text_content = []

    try:
        for chunk in chunks:
            if chunk['type'] == 'thinking':
                if chunk['content'] and chunk['content'] not in thinking_lines:
                    thinking_lines.append(chunk['content'])
            elif chunk['type'] == 'text':
                text_content.append(chunk['content'])
    except KeyError as e:
        return (f"❌ Error: Malformed response chunk - missing key {str(e)}")


    if thinking_lines:
        print("\n🤔 Thinking:")
        for line in thinking_lines:
            print(f"  • {line}")
        print()

    return (''.join(text_content))

def run_chat_example(api: DeepSeekAPI, title: str, prompt: str, thinking_enabled: bool = True, search_enabled: bool = False) -> str:
    """Run a chat example with error handling"""

    try:
        chunks = api.chat_completion(
            api.create_chat_session(),
            prompt,
            thinking_enabled=thinking_enabled,
            search_enabled=search_enabled
        )
        return print_response(chunks)

    except AuthenticationError as e:
        return(f"❌ Authentication Error: {str(e)}")
    except RateLimitError as e:
        return(f"❌ Rate Limit Error: {str(e)}")
    except NetworkError as e:
        return(f"❌ Network Error: {str(e)}")
    except APIError as e:
        return(f"❌ API Error: {str(e)}")
    except Exception as e:
        return(f"❌ Unexpected Error: {str(e)}")

def main(prompt: str) -> str:
    try:
        # Initialize the API with your auth token
        api = DeepSeekAPI("DEEPSEEK_AUTH_TOKEN")

        # Example 3: Without thinking
        run_chat_example(
            api,
            "Books recomendation",
            prompt,
            thinking_enabled=False
        )

    except KeyboardInterrupt:
        return ("\n\n⚠️ Operation cancelled by user")
    except Exception as e:
        return (f"\n❌ Fatal Error: {str(e)}")

if __name__ == "__main__":
    main()
