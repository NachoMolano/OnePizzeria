import asyncio
from app.orchestrator.agent import orchestrator_executor # Importar el executor del orquestador

async def main():
    """
    Main function to run the chat interface.
    """
    # You can change this user_id to test conversations with different users
    user_id = "local_test_user"
    channel = "console"
    chat_history = [] # Inicializar un historial de chat vacío

    print(f"Starting chat session for user: {user_id}")
    print('Type "exit" or "quit" to end the session.')

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Ending chat session.")
                break

            inputs = {
                "input": user_input,
                "user_id": user_id,
                "channel": channel,
                "chat_history": chat_history # Pasar el historial de chat
            }

            result = await orchestrator_executor.ainvoke(inputs)
            
            print(f"\nAgent: {result['output']}")

            # Actualizar el historial de chat (simplificado para esta prueba)
            chat_history.append(("user", user_input))
            chat_history.append(("ai", result['output']))

        except KeyboardInterrupt:
            print("\nEnding chat session.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")