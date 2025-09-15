from amocrm.v2 import tokens, Lead as _Lead, custom_field, Pipeline

STATUS_LIST = {
    "error" : "нужен человек",
    "start" : "Первичный контакт",
    "midle" : "Переговоры",
    "end" : "Принимаю решение",
}

class Lead(_Lead):
    scope = custom_field.NumericCustomField('Оценка')
    phone_number = custom_field.TextCustomField('Номер телефона')
    user_tag = custom_field.TextCustomField('Тег')
    company_direction = custom_field.TextCustomField('Направление компании')
    budget = custom_field.NumericCustomField('Бюджет')
    user_name = custom_field.TextCustomField('ФИО')
 
class AmoCRM():
    def __init__(self, client_id: str, client_secret: str, subdomain: str, redirect_url: str, pipeline_id: int):
        self.create_token(client_id, client_secret, subdomain, redirect_url)
        self.pipeline_id = pipeline_id
    
    def create_token(
        self,
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
        self,
        auth_code: str,
        skip_error: bool = True,
    ):
        tokens.default_token_manager.init(code=auth_code, skip_error=skip_error)

    def create_task(
        self,
        name: str = "",
        user_name: str = "",
        scope: int = 0,
        phone_number: str = "",
        user_tag: str = "",
        company_direction: str = "",
        budget: int = 0,
    ):  
        pipeline = Pipeline.objects.get(object_id=self.pipeline_id)
        lead = Lead(
            name=name,
            user_name=user_name,
            scope=scope,
            phone_number=phone_number,
            user_tag=user_tag,
            company_direction=company_direction,
            budget=budget,
            pipeline=pipeline
        )
        lead.create()
        
    def update_task(
        self,
        name: str,
        user_name: str = "",
        scope: str = None,
        phone_number: str = None,
        user_tag: str = None,
        company_direction: str = None,
        budget: int = None,
        status_name: str = None
    ):      
        pipeline: Pipeline = Pipeline.objects.get(object_id=self.pipeline_id)
        lead: Lead = Lead.objects.get(query=name)
        if user_name:
            lead.user_name = user_name
        if scope:
            lead.scope = scope
        if phone_number:
            lead.phone_number = phone_number
        if user_tag:
            lead.user_tag = user_tag
        if company_direction:
            lead.company_direction = company_direction
        if budget:
            lead.budget = budget
        if status_name:
            for status in pipeline.statuses:
                if status.name == STATUS_LIST[status_name]:
                    lead.status = status
                    break
            
        lead.update()
    

if __name__ == "__main__":
    import json
    
    with open("config.json", "r", encoding="utf-8") as file:
            config = json.load(file)    
        
    CLIENT_ID = config["amocrm"]["client_id"]
    CLIENT_SECRET = config["amocrm"]["client_secret"]
    SUBDOMAIN = config["amocrm"]["subdomain"]
    REDIRECT_URL = config["amocrm"]["redirect_url"]
    
    CRM = AmoCRM(CLIENT_ID, CLIENT_SECRET, SUBDOMAIN, REDIRECT_URL, 10091846)
    
    # CRM.create_task("name2", 0, "phone_number", "user_tag", "company_direction", 1)
    CRM.update_task("qweqwe", scope="100", status_name="midle")
    
