import json, os
from setup_logger import setup_logger
from crm.AmoCRM import AmoCRM
from UserBot import UserBot
from ai.DeepSeek import DeepSeek

def main():
    # запуск логов
    logger = setup_logger("log")

    logger.info("[main] Initialization started...")
    
    # загруска настроек
    if not os.path.isfile("config1.json"): 
        raise FileNotFoundError("File config.json not found")

    try:
        with open("config.json", "r", encoding="utf-8") as file:
            config = json.load(file)    
        
        # amocrm
        CLIENT_ID = config["amocrm"]["client_id"]
        CLIENT_SECRET = config["amocrm"]["client_secret"]
        SUBDOMAIN = config["amocrm"]["subdomain"]
        REDIRECT_URL = config["amocrm"]["redirect_url"]
        PIPLINE_ID = config["amocrm"]["pipline_id"]

        # deepseek
        DEEPSEEK_KEY       = config['deepseek_token']
        SYSTEM_PROMPT      = config['system_promt']
        
        # telegram
        API_ID             = config['api_id']
        API_HASH           = config['api_hash']
        SESSION            = config['session_name']
        DEBOUNCE_SECONDS   = config['debounce_seconds']
        INACTIVITY_SECONDS = config['inactivity_seconds']
        
    except Exception as e:
        raise ValueError(f"Invalid config.json file format: {str(e)}") from e
    finally:
        logger.info("[main] Reading settings completed")

    # amocrm start
    try:
        logger.info("[main] Connection to AmoCRM...")
        crm = AmoCRM(CLIENT_ID, CLIENT_SECRET, SUBDOMAIN, REDIRECT_URL, PIPLINE_ID)
        
        while not os.path.isfile("refresh_token.txt") or not os.path.isfile("access_token.txt"):
            logger.info("[main] Tokens not found, starting authorization")
            auth_code = input("Enter 20-minute authorization code: ")
            logger.info(f"[main] User input: {auth_code}")
            AmoCRM.authorization(auth_code, True)

    except Exception as e:
        raise Exception(f"Error connecting to AmoCRM: {str(e)}") from e
    finally:
        logger.info("[main] Connection to AmoCRM completed")

    # deepseek start
    try:
        logger.info("[main] Connection to DeepSeek...")
        deepseek_api = DeepSeek(DEEPSEEK_KEY, SYSTEM_PROMPT)
    except Exception as e:
        raise Exception(f"Error connecting to DeepSeek: {str(e)}") from e
    finally:
        logger.info("[main] Connection to DeepSeek completed")
    
    logger.info("[main] Initialization completed")
    
    # user bot start
    try:
        logger.info("[main] Connection to Telegram...")
        UserBot(
            logger=logger,
            api_id=API_ID,
            api_hash=API_HASH,
            session=SESSION,
            debounce_seconds=DEBOUNCE_SECONDS,
            inactivity_seconds=INACTIVITY_SECONDS,
            ai=deepseek_api,
            crm=crm
        ).start()
    except Exception as e:
        raise Exception(f"Error connecting to Telegram: {str(e)}") from e
    finally:
        logger.info("[main] Connection to Telegram completed")
        
    logger.info("[main] END")