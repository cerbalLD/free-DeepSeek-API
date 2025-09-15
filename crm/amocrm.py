from amocrm.v2 import tokens, Lead
    
def create_token(
    client_id: str,
    client_secret: str,
    subdomain: str,
    redirect_url: str,
    storage: tokens.TokensStorage = tokens.FileTokensStorage(),
):
    tokens.default_token_manager(
        client_id=client_id,
        client_secret=client_secret,
        subdomain=subdomain,
        redirect_url=redirect_url,
        storage=storage,
    )
    
    
def authorization(
    auth_code: str,
    skip_error: bool = True,
):
    tokens.default_token_manager.init(code=auth_code, skip_error=skip_error)


def create_task():
    lead = Lead(
        name="Новая сделка 2",
        price=10000,
    )
    lead.create()

if __name__ == "__main__":
    import json
    
    with open("config.json", "r", encoding="utf-8") as file:
            config = json.load(file)    
        
    CLIENT_ID = config["amocrm"]["client_id"]
    CLIENT_SECRET = config["amocrm"]["client_secret"]
    SUBDOMAIN = config["amocrm"]["subdomain"]
    REDIRECT_URL = config["amocrm"]["redirect_url"]
    
    create_token(CLIENT_ID, CLIENT_SECRET, SUBDOMAIN, REDIRECT_URL)
    
    create_task()
    
