import os
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory
from mangum import Mangum
from pydantic import BaseModel;
from prompts import reconstruct_query_with_history_prompt, answer_prompt
from load_data import all_specs
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

app = FastAPI()

load_dotenv()
GEMINI_APIKEY = os.environ.get('GEMINI_APIKEY')

chatModel = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash",
    google_api_key=GEMINI_APIKEY,
    temperature=0.5
)
chat_history = ChatMessageHistory()

def generate_answer(query):
  
  chat_history.add_user_message(query);
  message = answer_prompt.invoke({
        "question": query,
        "context": all_specs,
        "chat_history": chat_history.messages 
    }).to_messages()
  result = StrOutputParser().invoke(chatModel.invoke(message))
  chat_history.add_ai_message(result);
  return result

@app.get("/")
def read_root():
    return {"Hello": f"World"}

@app.get("/data")
def read_root():
    return {"data": all_specs}

class Question(BaseModel):
   query: str

@app.post("/ask")
def ask_recommendation(query: Question):
  try:
    ans = generate_answer(query.query)
  except Exception as e:
    return {"Error": e}
  
  json_answer = jsonable_encoder(ans)
  return JSONResponse(content={"answer": json_answer})

handler = Mangum(app)