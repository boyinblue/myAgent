# question_answerer.py
import openai

openai.api_key = "YOUR_API_KEY"

def generate_response(question):
  response = openai.Completion.create(
    engine="text-davinci-003",
    prompt=f"Q: {question}\nA:",
    max_tokens=150,
    temperature=0.7
  )
  return response.choices[0].text.strip() 

# Get user input
question = input("Ask me anything: ")

# Generate and print the response
print(generate_response(question))