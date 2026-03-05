# task.py 
import time

while True:
  user_input = input("Enter your command: ")
  if user_input == "exit":
    break
  else:
    print(f"You entered: {user_input}")
    time.sleep(1)