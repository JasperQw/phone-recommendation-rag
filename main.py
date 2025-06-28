import os
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ChatMessageHistory;
from prompts import reconstruct_query_with_history_prompt, answer_prompt
from load_data import all_specs

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
  if (len(chat_history.messages) != 0):
    reconstruct_query_with_history_message = reconstruct_query_with_history_prompt.invoke({"question": query, "chat_history": chat_history.messages}).to_messages()
    query = StrOutputParser().invoke(chatModel.invoke(reconstruct_query_with_history_message))
  
  chat_history.add_user_message(query);
  message = answer_prompt.invoke({
        "question": query,
        "context": all_specs
    }).to_messages()
  result = StrOutputParser().invoke(chatModel.invoke(message))
  chat_history.add_ai_message(result);
  return result

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/ask")
def ask_recommendation(query: str):
   ans = generate_answer(query)
   return ans