# -*- coding: utf-8 -*-
"""
Retrieval-Augmented Generation (RAG) with Ollama and LangChain,
and an extensible skill system, built with LCEL.
"""
import os
import json
import argparse
import subprocess
from langchain_community.document_loaders import DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama.llms import OllamaLLM
from langchain_community.embeddings import OllamaEmbeddings


# --- Configuration ---
def load_config():
    """Loads configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        print("config.json not found. Using default settings.")
        return {
            "model": "gemma2:9b",
            "rag_settings": {"docs_path": "../archive"}
        }
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
DEFAULT_MODEL = config.get("model", "gemma2:9b")
DEFAULT_DOCS_PATH = config.get("rag_settings", {}).get("docs_path", "../RAG")

# --- Skills ---

def git_commit_skill(llm):
    """
    Skill to automatically generate a commit message from staged changes
    and perform the commit.
    """
    print("--- Running Git Commit Skill ---")
    try:
        # Get staged changes
        diff_process = subprocess.run(
            ["git", "diff", "--staged"],
            capture_output=True, text=True, check=True
        )
        staged_diff = diff_process.stdout
        if not staged_diff:
            return "No staged changes to commit."

        # Create a prompt for the LLM to generate a commit message
        prompt = f"""
        Based on the following git diff, please generate a concise and descriptive
        commit message. The message should follow conventional commit standards.
        Format the output as a single line for the commit message.

        --- Git Diff ---
        {staged_diff}
        --- End of Diff ---

        Commit Message:
        """

        print("Generating commit message...")
        commit_message = llm.invoke(prompt).strip()

        # Show the generated message and ask for confirmation
        print(f"\nGenerated Commit Message:\n---\n{commit_message}\n---")
        confirm = input("Do you want to commit with this message? (y/n): ").lower()

        if confirm == 'y':
            # Perform the commit
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True
            )
            return "Commit successful."
        else:
            return "Commit cancelled."

    except FileNotFoundError:
        return "Error: 'git' command not found. Is Git installed and in your PATH?"
    except subprocess.CalledProcessError as e:
        return f"An error occurred with a git command: {e.stderr}"


# A dictionary to map keywords to skills
skills = {
    "git commit": git_commit_skill,
}

def skill_dispatcher(user_input, llm):
    """
    Checks for keywords in the user input and triggers the corresponding skill.
    """
    for keyword, skill_function in skills.items():
        if keyword in user_input.lower():
            return skill_function(llm)
    return None

# --- RAG ---

def get_rag_chain(model, docs_path):
    """
    Initializes and returns a RAG chain using LCEL.
    """
    print(f"--- Initializing RAG with model: {model} ---")
    print(f"--- Loading documents from: {docs_path} ---")

    llm = OllamaLLM(model=model)

    if not os.path.isdir(docs_path):
        print(f"Error: Document directory not found at '{docs_path}'")
        return llm, None

    loader = DirectoryLoader(docs_path, glob="**/*.md")
    documents = loader.load()
    if not documents:
        print("No markdown documents found in the specified directory.")
        return llm, None

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    embeddings = OllamaEmbeddings(model=model)
    db = FAISS.from_documents(texts, embeddings)
    retriever = db.as_retriever()

    template = """Answer the question based only on the following context:
    {context}

    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)

    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return llm, rag_chain


def main(model, docs_path):
    """
    Main function to run the interactive chat.
    """
    llm, rag_chain = get_rag_chain(model, docs_path)

    if rag_chain:
        print("\n--- RAG is enabled. Ready to answer questions about your documents ---")
    else:
        print("\n--- RAG is disabled. Running in standard chat mode ---")
    
    print("--- Type 'exit' or 'quit' to end the session ---")
    print("--- To use a skill, type its keyword (e.g., 'git commit') ---")

    while True:
        try:
            query = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if query.strip().lower() in ("exit", "quit"):
            print("Session ended.")
            break
        if not query.strip():
            continue

        # Check for skills
        skill_response = skill_dispatcher(query, llm)
        if skill_response:
            print(skill_response)
            continue

        # If no skill was triggered, use RAG (if available) or standard chat
        if rag_chain:
            answer = rag_chain.invoke(query)
            print("\n", answer, "\n")
        else:
            answer = llm.invoke(query)
            print("\n", answer, "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG-based QA with Ollama and skills.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"Ollama model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--docs_path", type=str, default=DEFAULT_DOCS_PATH,
                        help=f"Path to your documents (default: {DEFAULT_DOCS_PATH})")
    args = parser.parse_args()
    main(args.model, args.docs_path)
